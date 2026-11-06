package main

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

const discoveryLimit = 20000

type DocumentVolume struct {
	Path string `json:"path"`
	Name string `json:"name"`
}

type DiscoveryProgress struct {
	Roots   []string `json:"roots"`
	Visited int      `json:"visited"`
	Files   int      `json:"files"`
	Current string   `json:"current"`
}

var discoverySystemDirs = map[string]bool{
	"windows": true, "program files": true, "program files (x86)": true,
	"$recycle.bin": true, "system volume information": true, "recovery": true,
	"proc": true, "sys": true, "dev": true, "run": true, "boot": true,
	"usr": true, "bin": true, "sbin": true, "lib": true, "lib64": true,
	"etc": true, "snap": true, "lost+found": true,
	".next": true, "target": true, "bower_components": true, "backups": true,
	"cache": true, "caches": true, ".cache": true, "temp": true,
}

func supportedDocument(path string) bool {
	switch strings.ToLower(filepath.Ext(path)) {
	case ".md", ".txt", ".rst", ".csv", ".html", ".htm", ".docx", ".xlsx", ".pptx", ".pdf":
		return true
	}
	return false
}

func pathWithin(parent, child string) bool {
	rel, err := filepath.Rel(parent, child)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator))
}

func discoveryRoot(raw string) (string, error) {
	root := filepath.Clean(expandPath(strings.TrimSpace(raw)))
	if !filepath.IsAbs(root) || strings.HasPrefix(root, `\\`) || strings.HasPrefix(root, "//") {
		return "", errors.New("请选择本机目录的绝对路径")
	}
	resolved, err := filepath.EvalSymlinks(root)
	if err != nil || !sameLocalPath(root, resolved) {
		return "", errors.New("所选目录不可访问或经过符号链接")
	}
	for _, part := range strings.Split(filepath.ToSlash(root), "/") {
		if excludedPart(part) {
			return "", errors.New("所选目录属于敏感或排除范围")
		}
	}
	info, err := os.Stat(root)
	if err != nil || !info.IsDir() || discoverySystemDirs[strings.ToLower(filepath.Base(root))] {
		return "", errors.New("请选择可访问的非系统目录")
	}
	return root, nil
}

func sameLocalPath(left, right string) bool {
	if runtime.GOOS == "windows" {
		return strings.EqualFold(left, right)
	}
	return left == right
}

func agentFile(agent, base, path string) bool {
	rel, err := filepath.Rel(base, path)
	if err != nil || !pathWithin(base, path) {
		return false
	}
	parts := strings.Split(filepath.ToSlash(rel), "/")
	if agent == "hermes" && len(parts) > 2 && parts[0] == "profiles" {
		parts = parts[2:]
	}
	if agent == "hermes" && len(parts) == 1 && parts[0] == "state.db" {
		return true
	}
	ext := strings.ToLower(filepath.Ext(path))
	if len(parts) < 2 {
		return false
	}
	if agent == "hermes" && parts[0] == "memories" && ext == ".md" {
		return true
	}
	if ext != ".json" && ext != ".jsonl" {
		return false
	}
	return (agent == "claude" && parts[0] == "projects") ||
		(agent != "claude" && parts[0] == "sessions") ||
		(agent == "codex" && parts[0] == "archived_sessions")
}

// Discovery reads directory entries and metadata only, never source contents.
func discoverSources(ctx context.Context, c Config, roots, excluded []string,
	log func(string), progress func(Inventory, DiscoveryProgress)) (Inventory, error) {
	inv := Inventory{Sources: []Source{}}
	seen, agentRoots := map[string]bool{}, map[string]string{}
	for _, name := range []string{"codex", "claude", "hermes"} {
		a := c.Agents[name]
		if a.Enabled && a.Path != "" {
			base, err := filepath.Abs(expandPath(a.Path))
			if err == nil {
				agentRoots[base] = name
			}
		}
	}
	for name, variable := range map[string]string{"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR", "hermes": "HERMES_HOME"} {
		if path := os.Getenv(variable); c.Agents[name].Enabled && filepath.IsAbs(path) {
			agentRoots[filepath.Clean(path)] = name
		}
	}
	p := DiscoveryProgress{Roots: roots}
	last := time.Time{}
	publish := func(force bool) {
		if progress != nil && (force || time.Since(last) >= 250*time.Millisecond) {
			p.Files = len(inv.Sources)
			progress(inv, p)
			last = time.Now()
		}
	}
	var firstErr error
	warnings := 0
	for _, raw := range roots {
		if err := ctx.Err(); err != nil {
			publish(true)
			return inv, err
		}
		root, err := discoveryRoot(raw)
		if err != nil {
			log("跳过不可访问的扫描范围：" + raw)
			if firstErr == nil {
				firstErr = err
			}
			continue
		}
		log("发现本地来源：" + root)
		err = filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
			if err := ctx.Err(); err != nil {
				return err
			}
			p.Visited++
			p.Current = path
			if walkErr != nil {
				warnings++
				if warnings <= 10 {
					log("跳过不可访问的文件或目录：" + path)
				}
				return nil
			}
			if entry.Type()&os.ModeSymlink != 0 {
				return nil
			}
			for _, skip := range excluded {
				if pathWithin(skip, path) {
					if entry.IsDir() {
						return filepath.SkipDir
					}
					return nil
				}
			}
			if entry.IsDir() {
				name := strings.ToLower(entry.Name())
				agent := strings.TrimPrefix(name, ".")
				if agent == "codex" || agent == "claude" || agent == "hermes" {
					if !c.Agents[agent].Enabled {
						return filepath.SkipDir
					}
					agentRoots[path] = agent
				}
				if path != root {
					_, isAgent := agentRoots[path]
					if excludedPart(name) || discoverySystemDirs[name] ||
						(strings.HasPrefix(name, ".") && !isAgent) {
						return filepath.SkipDir
					}
					if root == string(filepath.Separator) && (path == "/mnt" || path == "/media" || path == "/Volumes") {
						return filepath.SkipDir
					}
				}
				publish(false)
				return nil
			}
			if seen[path] || excludedPart(entry.Name()) {
				return nil
			}
			seen[path] = true
			agent, base := "document", ""
			for candidate, name := range agentRoots {
				if pathWithin(candidate, path) && len(candidate) > len(base) {
					agent, base = name, candidate
				}
			}
			if base != "" {
				if !agentFile(agent, base, path) {
					return nil
				}
			} else if !supportedDocument(path) {
				return nil
			}
			info, err := entry.Info()
			if err != nil || !info.Mode().IsRegular() {
				return nil
			}
			if len(inv.Sources) >= discoveryLimit {
				return errors.New("超过 20,000 个来源上限；已保存部分清单，请缩小范围继续")
			}
			s := Source{Agent: agent, Path: path, Project: filepath.Dir(path), Status: "discovered",
				Title: redact(strings.TrimSuffix(entry.Name(), filepath.Ext(path))), Modified: info.ModTime().UTC().Format(time.RFC3339),
				Bytes: info.Size()}
			s.ID = hashText(agent + "\x00" + path + "\x00")
			if !(agent == "hermes" && entry.Name() == "state.db") {
				if time.Since(info.ModTime()) < time.Duration(c.IdleHours)*time.Hour {
					s.Status, s.Reason = "active", "尚未达到闲置时长"
				} else if info.Size() > int64(c.MaxFileMB)*1024*1024 {
					s.Status, s.Reason = "skipped", "超过单文件限制"
				}
			}
			inv.Sources = append(inv.Sources, s)
			if s.Status != "discovered" {
				inv.Skipped++
			}
			publish(len(inv.Sources) == 1)
			return nil
		})
		if err != nil {
			publish(true)
			return inv, err
		}
	}
	publish(true)
	if err := ctx.Err(); err != nil {
		return inv, err
	}
	if len(inv.Sources) == 0 && firstErr != nil {
		return inv, firstErr
	}
	if warnings > 0 {
		log(fmt.Sprintf("发现完成，跳过 %d 个不可访问位置", warnings))
	}
	return inv, nil
}

func sortedDiscoveryRoots(c Config, volumes []DocumentVolume) []string {
	roots, seen := []string{}, map[string]bool{}
	add := func(path string) {
		path = expandPath(path)
		if path != "" && !seen[path] {
			seen[path] = true
			roots = append(roots, path)
		}
	}
	// Seed explicit agent homes even when they live beneath hidden directories.
	for _, name := range []string{"codex", "claude", "hermes"} {
		if c.Agents[name].Enabled {
			add(c.Agents[name].Path)
		}
	}
	for name, variable := range map[string]string{"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR", "hermes": "HERMES_HOME"} {
		if c.Agents[name].Enabled {
			add(os.Getenv(variable))
		}
	}
	for _, volume := range volumes {
		add(volume.Path)
	}
	for _, path := range c.Roots {
		add(path)
	}
	return roots
}

func extractDiscovered(ctx context.Context, c Config, inv Inventory, ids []string, root string,
	log func(string), progress func(Inventory, DiscoveryProgress)) (Inventory, error) {
	selected := map[string]Source{}
	for _, s := range inv.Sources {
		if s.Status == "discovered" {
			selected[s.ID] = s
		}
	}
	requested := map[string]bool{}
	for _, id := range ids {
		if _, ok := selected[id]; !ok {
			return inv, errors.New("所选来源无效或已处理，请刷新清单")
		}
		requested[id] = true
	}
	if len(requested) == 0 {
		return inv, errors.New("请选择待提取的来源")
	}
	remaining := map[string]bool{}
	base := Inventory{Sources: []Source{}}
	for _, s := range inv.Sources {
		if requested[s.ID] {
			remaining[s.ID] = true
		} else {
			base.Sources = append(base.Sources, s)
		}
	}
	builder := newInventoryBuilder(root, base)
	snapshot := func() Inventory {
		result := builder.inv
		result.Sources = append([]Source{}, result.Sources...)
		for _, s := range inv.Sources {
			if remaining[s.ID] {
				result.Sources = append(result.Sources, s)
			}
		}
		return result
	}
	ordered := make([]string, 0, len(requested))
	for id := range requested {
		ordered = append(ordered, id)
	}
	sort.Strings(ordered)
	var extractErr error
	for _, id := range ordered {
		if err := ctx.Err(); err != nil {
			extractErr = err
			break
		}
		s := selected[id]
		builder.reserved = len(remaining) - 1
		if s.Agent == "hermes" && filepath.Base(s.Path) == "state.db" {
			// A partially expanded database keeps its discovery entry for retry.
			builder.reserved++
		}
		log("提取本地来源：" + s.Path)
		resolved, pathErr := filepath.EvalSymlinks(s.Path)
		if pathErr != nil || !sameLocalPath(filepath.Clean(s.Path), resolved) {
			s.Status, s.Reason = "error", "来源不可访问或已被替换为符号链接"
			extractErr = builder.add(s)
		} else if s.Agent == "hermes" && filepath.Base(s.Path) == "state.db" {
			extractErr = scanHermesDB(ctx, s.Path, time.Duration(c.IdleHours)*time.Hour,
				int64(c.MaxFileMB)*1024*1024, builder.add)
		} else {
			s.Status, s.Reason = "", ""
			info, err := os.Lstat(s.Path)
			if err != nil || !info.Mode().IsRegular() {
				s.Status, s.Reason = "error", "来源已移除或不再是普通文件"
			} else if time.Since(info.ModTime()) < time.Duration(c.IdleHours)*time.Hour {
				s.Status, s.Reason = "active", "来源在发现后发生修改"
			} else if info.Size() > int64(c.MaxFileMB)*1024*1024 {
				s.Status, s.Reason = "skipped", "超过单文件限制"
			} else {
				s.Modified = info.ModTime().UTC().Format(time.RFC3339)
				s.Bytes = info.Size()
				max := int64(c.MaxFileMB) * 1024 * 1024
				if s.Agent == "document" || strings.EqualFold(filepath.Ext(s.Path), ".md") {
					s.Text, err = readDocument(ctx, s.Path, max)
				} else {
					var raw []byte
					raw, err = readBounded(s.Path, max)
					if err == nil {
						s.Text, s.SessionID, s.Project, s.Title, err = parseTranscript(raw, s.Agent)
					}
				}
				if err != nil {
					s.Status, s.Reason = "error", err.Error()
				}
			}
			extractErr = builder.add(s)
		}
		if extractErr != nil {
			break
		}
		delete(remaining, id)
		if progress != nil {
			progress(snapshot(), DiscoveryProgress{Files: len(ordered) - len(remaining), Visited: len(ordered), Current: s.Path})
		}
	}
	result := snapshot()
	if err := atomicJSON(filepath.Join(root, "inventory.json"), result); err != nil {
		return result, err
	}
	return result, extractErr
}

func (a *App) saveDiscovery(c Config, dir string, inv Inventory) error {
	if err := atomicJSON(filepath.Join(dir, "inventory.json"), inv); err != nil {
		return err
	}
	if err := atomicJSON(filepath.Join(a.root, "current-scan.json"),
		map[string]string{"directory": dir, "scope_key": c.scopeKey()}); err != nil {
		return err
	}
	return nil
}

func (a *App) publishDiscovery(inv Inventory, p DiscoveryProgress) {
	copy := inv
	copy.Sources = append([]Source{}, inv.Sources...)
	a.mu.Lock()
	a.inventory, a.discovery = copy, p
	a.mu.Unlock()
}

func (a *App) registerDiscovery(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/document-volumes", func(w http.ResponseWriter, r *http.Request) {
		respond(w, 200, map[string]any{"volumes": documentVolumes()})
	})
	mux.HandleFunc("POST /api/discover", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Mode string `json:"mode"`
			Path string `json:"path"`
		}
		if err := decode(w, r, &req); err != nil {
			fail(w, errors.New("扫描参数无效"))
			return
		}
		if req.Mode != "all" && req.Mode != "directory" {
			fail(w, errors.New("请选择全电脑或指定目录"))
			return
		}
		if req.Mode == "directory" {
			path, err := discoveryRoot(req.Path)
			if err != nil {
				fail(w, err)
				return
			}
			req.Path = path
		}
		err := a.start("discover", func(ctx context.Context, c Config) error {
			roots := []string{req.Path}
			if req.Mode == "all" {
				roots = sortedDiscoveryRoots(c, documentVolumes())
			}
			dir := filepath.Join(a.root, "scans", time.Now().UTC().Format("20060102T150405")+"-discover-"+randomToken()[:8])
			a.mu.Lock()
			a.scanDir, a.products = dir, []Product{}
			a.mu.Unlock()
			lastSaved := time.Time{}
			inv, scanErr := discoverSources(ctx, c, roots, []string{a.root}, a.log, func(inv Inventory, p DiscoveryProgress) {
				a.publishDiscovery(inv, p)
				if time.Since(lastSaved) >= time.Second {
					if err := a.saveDiscovery(c, dir, inv); err == nil {
						lastSaved = time.Now()
					}
				}
			})
			if err := a.saveDiscovery(c, dir, inv); err != nil {
				return err
			}
			a.mu.Lock()
			a.inventory = inv
			a.mu.Unlock()
			a.log(fmt.Sprintf("发现 %d 个本地来源；未读取正文、未联网，清单已保存", len(inv.Sources)))
			return scanErr
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/extract", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			IDs []string `json:"ids"`
		}
		if err := decode(w, r, &req); err != nil || len(req.IDs) == 0 {
			fail(w, errors.New("请选择待提取来源"))
			return
		}
		err := a.start("extract", func(ctx context.Context, c Config) error {
			a.mu.Lock()
			inv, dir := a.inventory, a.scanDir
			a.mu.Unlock()
			if dir == "" {
				return errors.New("请先发现本地来源")
			}
			lastSaved := time.Time{}
			result, extractErr := extractDiscovered(ctx, c, inv, req.IDs, dir, a.log,
				func(partial Inventory, p DiscoveryProgress) {
					a.publishDiscovery(partial, p)
					if time.Since(lastSaved) >= time.Second {
						if err := a.saveDiscovery(c, dir, partial); err == nil {
							lastSaved = time.Now()
						}
					}
				})
			if err := a.saveDiscovery(c, dir, result); err != nil {
				return err
			}
			a.mu.Lock()
			a.inventory = result
			a.mu.Unlock()
			a.log(fmt.Sprintf("提取完成：%d 篇待上传；未选择来源保持未提取", result.Ready))
			return extractErr
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
}
