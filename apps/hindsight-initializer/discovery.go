package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"path/filepath"
	"time"
)

type DiscoveryProgress struct {
	Mode    string   `json:"mode"`
	Roots   []string `json:"roots"`
	Files   int      `json:"files"`
	Current string   `json:"current"`
}

func (a *App) saveCatalog(c Config, inventory Inventory, dir string) error {
	if dir == "" {
		dir = filepath.Join(a.root, "scans", time.Now().UTC().Format("20060102T150405")+"-catalog-"+randomToken()[:8])
	}
	if err := atomicJSON(filepath.Join(dir, "inventory.json"), inventory); err != nil {
		return err
	}
	if err := atomicJSON(filepath.Join(a.root, "current-scan.json"), map[string]string{"directory": dir, "scope_key": c.scopeKey()}); err != nil {
		return err
	}
	a.mu.Lock()
	a.inventory, a.scanDir = inventory, dir
	a.mu.Unlock()
	return nil
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
			fail(w, errors.New("智能扫描参数无效"))
			return
		}
		roots := []string{}
		switch req.Mode {
		case "all":
			for _, volume := range documentVolumes() {
				roots = append(roots, volume.Path)
			}
			if len(roots) == 0 {
				fail(w, errors.New("未发现可访问的本地磁盘，请指定目录"))
				return
			}
		case "directory":
			root, err := documentRoot(req.Path)
			if err != nil {
				fail(w, err)
				return
			}
			roots = append(roots, root)
		default:
			fail(w, errors.New("请选择全电脑或指定目录模式"))
			return
		}
		err := a.start("discover", func(ctx context.Context, c Config) error {
			a.mu.Lock()
			previous, dir := a.inventory, a.scanDir
			a.discovery = DiscoveryProgress{Mode: req.Mode, Roots: roots}
			a.mu.Unlock()
			search := c
			search.Roots = roots
			lastPublished := time.Time{}
			listed, scanErr := catalogDocuments(ctx, search, a.log, func(partial Inventory, current string) {
				reportProgress(ctx, "查找文档", len(partial.Sources), 0, current, "个文件")
				if !lastPublished.IsZero() && time.Since(lastPublished) < 300*time.Millisecond {
					return
				}
				inventory := mergeCatalog(previous, partial)
				a.mu.Lock()
				a.inventory = inventory
				a.discovery.Files, a.discovery.Current = len(partial.Sources), current
				a.mu.Unlock()
				lastPublished = time.Now()
			})
			updated := c
			updated.Roots = combineDocumentRoots(c.Roots, roots)
			if err := saveConfig(a.root, updated); err != nil {
				return err
			}
			inventory := mergeCatalog(previous, listed)
			if err := a.saveCatalog(updated, inventory, dir); err != nil {
				_ = saveConfig(a.root, c)
				return err
			}
			a.mu.Lock()
			a.cfg = updated
			a.discovery.Files = len(listed.Sources)
			a.mu.Unlock()
			a.log(fmt.Sprintf("智能扫描已加入 %d 个文件；仅保存本地清单，未提取正文", len(listed.Sources)))
			return scanErr
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
}
