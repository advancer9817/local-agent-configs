package main

import (
	"archive/zip"
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"encoding/xml"
	"errors"
	"fmt"
	"html"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	_ "modernc.org/sqlite"
)

type Source struct {
	ID        string   `json:"id"`
	Agent     string   `json:"agent"`
	SessionID string   `json:"session_id,omitempty"`
	Title     string   `json:"title"`
	Project   string   `json:"project"`
	Path      string   `json:"path"`
	SHA       string   `json:"sha256"`
	Chars     int      `json:"chars"`
	Modified  string   `json:"modified"`
	Status    string   `json:"status"`
	Reason    string   `json:"reason,omitempty"`
	Text      string   `json:"-"`
	Aliases   []string `json:"aliases,omitempty"`
}

type Inventory struct {
	Sources []Source `json:"sources"`
	Ready   int      `json:"ready"`
	Chars   int      `json:"chars"`
	Skipped int      `json:"skipped"`
}

var privateName = regexp.MustCompile(`(?i)(^|[-_.])(auth|credentials?|secrets?|tokens?|passwords?|connection|runtime|config|settings|private|backup|before)([-_.]|$)`)
var bearerRE = regexp.MustCompile(`(?i)Bearer\s+[A-Za-z0-9_./+=-]+`)
var keyRE = regexp.MustCompile(`\b(sk-|ghp_|github_pat_|gsk_)[A-Za-z0-9_-]{12,}`)
var assignmentRE = regexp.MustCompile(`(?im)((?:api[_-]?key|(?:auth|access|refresh|mcp)[_-]?token|password|secret)["']?\s*[=:]\s*)("[^"\r\n]*"|'[^'\r\n]*'|[^\s,;}]+)`)
var pemRE = regexp.MustCompile(`(?s)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----`)
var htmlRE = regexp.MustCompile(`(?s)<[^>]*>`)

func redact(s string) string {
	s = pemRE.ReplaceAllString(s, "[REDACTED PRIVATE KEY]")
	s = bearerRE.ReplaceAllString(s, "Bearer [REDACTED]")
	s = keyRE.ReplaceAllString(s, "[REDACTED]")
	return assignmentRE.ReplaceAllString(s, "${1}[REDACTED]")
}

func excludedPart(name string) bool {
	name = strings.ToLower(name)
	switch name {
	case ".git", ".ssh", ".aws", ".azure", ".gnupg", "node_modules", ".venv",
		"venv", "vendor", "dist", "build", "cache", "__pycache__", "bootstrap-staging":
		return true
	}
	return strings.HasPrefix(name, ".env") || privateName.MatchString(name)
}

func expandPath(path string) string {
	if path == "~" {
		return homePath()
	}
	if strings.HasPrefix(path, "~/") || strings.HasPrefix(path, `~\`) {
		return homePath(path[2:])
	}
	return os.ExpandEnv(path)
}

func textContent(value any) string {
	if s, ok := value.(string); ok {
		return s
	}
	var parts []string
	if blocks, ok := value.([]any); ok {
		for _, b := range blocks {
			if m, ok := b.(map[string]any); ok {
				t, _ := m["type"].(string)
				if t == "text" || t == "input_text" || t == "output_text" {
					if text, ok := m["text"].(string); ok {
						parts = append(parts, text)
					}
				}
			}
		}
	}
	return strings.Join(parts, "\n")
}

func stringAt(m map[string]any, keys ...string) string {
	for _, k := range keys {
		if s, ok := m[k].(string); ok && s != "" {
			return s
		}
	}
	return ""
}

func parseTranscript(raw []byte, agent string) (text, sid, project, title string, err error) {
	var rows []string
	appendMessage := func(m map[string]any) {
		role := stringAt(m, "role")
		if role != "user" && role != "assistant" {
			return
		}
		body := textContent(m["content"])
		if strings.TrimSpace(body) != "" {
			rows = append(rows, role+": "+strings.TrimSpace(body))
		}
	}
	var whole map[string]any
	if json.Unmarshal(raw, &whole) == nil && whole["messages"] != nil {
		sid, project, title = stringAt(whole, "session_id", "id"), stringAt(whole, "cwd", "project"), stringAt(whole, "title", "name")
		if msgs, ok := whole["messages"].([]any); ok {
			for _, value := range msgs {
				if m, ok := value.(map[string]any); ok {
					appendMessage(m)
				}
			}
		}
	} else {
		scanner := bufio.NewScanner(strings.NewReader(string(raw)))
		scanner.Buffer(make([]byte, 65536), 16*1024*1024)
		for scanner.Scan() {
			var r map[string]any
			if json.Unmarshal(scanner.Bytes(), &r) != nil {
				return "", "", "", "", errors.New("会话包含无效 JSON 行；未截断入库")
			}
			if sid == "" {
				sid = stringAt(r, "sessionId", "session_id")
			}
			if project == "" {
				project = stringAt(r, "cwd")
			}
			typ := stringAt(r, "type")
			if typ == "session_meta" {
				if meta, ok := r["payload"].(map[string]any); ok {
					sid, project = stringAt(meta, "id"), stringAt(meta, "cwd")
				}
				continue
			}
			if typ == "custom-title" {
				title = stringAt(r, "customTitle", "title")
				continue
			}
			// Codex repeats messages as event_msg; only canonical response_item is used.
			if typ == "event_msg" {
				continue
			}
			if m, ok := r["message"].(map[string]any); ok {
				appendMessage(m)
			} else if m, ok := r["payload"].(map[string]any); ok {
				appendMessage(m)
			} else {
				appendMessage(r)
			}
		}
		if err = scanner.Err(); err != nil {
			return "", "", "", "", errors.New("会话行超出解析上限；未截断入库")
		}
	}
	text = strings.Join(rows, "\n\n")
	if text == "" {
		err = errors.New("无可归档的用户或助手正文")
	}
	return
}

func readBounded(path string, max int64) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, max+1))
	if int64(len(b)) > max {
		return nil, errors.New("文件超过大小限制")
	}
	return b, err
}

func readDocument(ctx context.Context, path string, max int64) (string, error) {
	ext := strings.ToLower(filepath.Ext(path))
	switch ext {
	case ".pdf":
		child, cancel := context.WithTimeout(ctx, 30*time.Second)
		defer cancel()
		b, err := exec.CommandContext(child, "pdftotext", "-enc", "UTF-8", path, "-").Output()
		if err != nil {
			return "", errors.New("PDF 需安装 pdftotext；本篇未提取")
		}
		if int64(len(b)) > max*4 {
			return "", errors.New("PDF 提取正文过大")
		}
		return string(b), nil
	case ".docx", ".xlsx", ".pptx":
		z, err := zip.OpenReader(path)
		if err != nil {
			return "", err
		}
		defer z.Close()
		var out strings.Builder
		var shared []string
		if ext == ".xlsx" {
			for _, f := range z.File {
				if f.Name == "xl/sharedStrings.xml" {
					b, e := zipBytes(f, max*4)
					if e != nil {
						return "", e
					}
					var s struct {
						Items []struct {
							Text string `xml:"t"`
							Runs []struct {
								Text string `xml:"t"`
							} `xml:"r"`
						} `xml:"si"`
					}
					if e = xml.Unmarshal(b, &s); e != nil {
						return "", e
					}
					for _, item := range s.Items {
						v := item.Text
						for _, r := range item.Runs {
							v += r.Text
						}
						shared = append(shared, v)
					}
				}
			}
		}
		sort.Slice(z.File, func(i, j int) bool { return z.File[i].Name < z.File[j].Name })
		for _, f := range z.File {
			keep := f.Name == "word/document.xml" || (strings.HasPrefix(f.Name, "ppt/slides/slide") && strings.HasSuffix(f.Name, ".xml")) ||
				(strings.HasPrefix(f.Name, "xl/worksheets/sheet") && strings.HasSuffix(f.Name, ".xml"))
			if !keep {
				continue
			}
			b, e := zipBytes(f, max*4)
			if e != nil {
				return "", e
			}
			if ext == ".xlsx" {
				var sheet struct {
					Rows []struct {
						Cells []struct {
							Type   string `xml:"t,attr"`
							Value  string `xml:"v"`
							Inline struct {
								Text string `xml:"t"`
							} `xml:"is"`
						} `xml:"c"`
					} `xml:"sheetData>row"`
				}
				if e := xml.Unmarshal(b, &sheet); e != nil {
					return "", e
				}
				out.WriteString("\n" + f.Name + "\n")
				for _, row := range sheet.Rows {
					var values []string
					for _, c := range row.Cells {
						v := c.Value
						if c.Type == "s" {
							n, e := strconv.Atoi(v)
							if e != nil || n < 0 || n >= len(shared) {
								return "", errors.New("无效 Excel 字符串索引")
							}
							v = shared[n]
						} else if c.Type == "inlineStr" {
							v = c.Inline.Text
						}
						values = append(values, v)
					}
					out.WriteString(strings.Join(values, "\t") + "\n")
				}
			} else {
				decoder := xml.NewDecoder(strings.NewReader(string(b)))
				inside := false
				for {
					tok, e := decoder.Token()
					if e == io.EOF {
						break
					}
					if e != nil {
						return "", e
					}
					switch t := tok.(type) {
					case xml.StartElement:
						if t.Name.Local == "t" {
							inside = true
						}
					case xml.EndElement:
						if t.Name.Local == "t" {
							inside = false
						}
						if t.Name.Local == "p" {
							out.WriteString("\n")
						}
					case xml.CharData:
						if inside {
							out.Write(t)
						}
					}
				}
			}
			if int64(out.Len()) > max*4 {
				return "", errors.New("Office 解压正文超过上限")
			}
		}
		return out.String(), nil
	case ".md", ".txt", ".rst", ".csv", ".html", ".htm":
		b, err := readBounded(path, max)
		if err != nil {
			return "", err
		}
		if !utf8.Valid(b) {
			return "", errors.New("文本不是 UTF-8；请转换编码后重试")
		}
		s := string(b)
		if ext == ".html" || ext == ".htm" {
			s = html.UnescapeString(htmlRE.ReplaceAllString(s, " "))
		}
		return s, nil
	}
	return "", errors.New("格式不支持")
}

func zipBytes(f *zip.File, max int64) ([]byte, error) {
	if f.UncompressedSize64 > uint64(max) {
		return nil, errors.New("Office 解压体积超过上限")
	}
	r, err := f.Open()
	if err != nil {
		return nil, err
	}
	defer r.Close()
	b, err := io.ReadAll(io.LimitReader(r, max+1))
	if int64(len(b)) > max {
		return nil, errors.New("Office 解压体积超过上限")
	}
	return b, err
}

func walkSafe(ctx context.Context, root string, visit func(string, os.FileInfo) error) error {
	root = expandPath(root)
	resolved, err := filepath.EvalSymlinks(root)
	if err != nil {
		return err
	}
	for _, part := range strings.Split(filepath.ToSlash(resolved), "/") {
		if excludedPart(part) {
			return errors.New("所选目录属于敏感或排除范围")
		}
	}
	return filepath.WalkDir(resolved, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if err := ctx.Err(); err != nil {
			return err
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return nil
		}
		if entry.IsDir() {
			if path != resolved && excludedPart(entry.Name()) {
				return filepath.SkipDir
			}
			return nil
		}
		if excludedPart(entry.Name()) {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return nil
		}
		return visit(path, info)
	})
}

func scanLocal(ctx context.Context, cfg Config, root string, log func(string)) (Inventory, error) {
	inv := Inventory{Sources: []Source{}}
	seenPath, seenHash := map[string]bool{}, map[string]int{}
	totalBytes := 0
	add := func(s Source) error {
		if len(inv.Sources) >= 20000 {
			return errors.New("超过 20,000 篇扫描上限，请缩小范围")
		}
		if s.Status == "" {
			s.Text = strings.TrimSpace(redact(s.Text))
			if s.Text == "" {
				s.Status, s.Reason = "skipped", "无正文"
			}
		}
		s.Chars = utf8.RuneCountInString(s.Text)
		s.ID = hashText(s.Agent + "\x00" + s.Path + "\x00" + s.SessionID)
		if s.Title == "" {
			s.Title = strings.TrimSuffix(filepath.Base(s.Path), filepath.Ext(s.Path))
		}
		s.Title = redact(s.Title)
		if s.Project == "" {
			s.Project = filepath.Dir(s.Path)
		}
		if s.Status == "" {
			s.SHA = hashText(s.Text)
			hashKey := s.Project + "\x00" + s.SHA
			if idx, ok := seenHash[hashKey]; ok {
				s.Status, s.Reason = "duplicate", inv.Sources[idx].ID
				inv.Sources[idx].Aliases = append(inv.Sources[idx].Aliases, s.ID)
			} else {
				s.Status = "ready"
				seenHash[hashKey] = len(inv.Sources)
				totalBytes += len(s.Text)
				if totalBytes > 256*1024*1024 {
					return errors.New("正文总量超过 256 MB，请分批扫描")
				}
				inv.Ready++
				inv.Chars += s.Chars
			}
			if err := atomicWrite(filepath.Join(root, "raw", s.ID+".md"), []byte(s.Text), 0600); err != nil {
				return err
			}
		}
		if s.Status != "ready" {
			inv.Skipped++
		}
		inv.Sources = append(inv.Sources, s)
		return nil
	}
	age := time.Duration(cfg.IdleHours) * time.Hour
	max := int64(cfg.MaxFileMB) * 1024 * 1024
	for _, agent := range []string{"codex", "claude", "hermes"} {
		a := cfg.Agents[agent]
		if !a.Enabled {
			continue
		}
		base := expandPath(a.Path)
		log("扫描 " + agent)
		if agent == "hermes" {
			db := filepath.Join(base, "state.db")
			if _, err := os.Stat(db); err == nil {
				if err = scanHermesDB(ctx, db, age, max, add); err != nil {
					if e := add(Source{Agent: agent, Path: db, Status: "error", Reason: err.Error()}); e != nil {
						return inv, e
					}
				}
			}
		}
		subdirs := []string{"sessions"}
		if agent == "codex" {
			subdirs = append(subdirs, "archived_sessions")
		}
		if agent == "claude" {
			subdirs = []string{"projects"}
		}
		if agent == "hermes" {
			subdirs = append(subdirs, "memories")
		}
		for _, dir := range subdirs {
			path := filepath.Join(base, dir)
			if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
				continue
			}
			err := walkSafe(ctx, path, func(path string, info os.FileInfo) error {
				if seenPath[path] {
					return nil
				}
				seenPath[path] = true
				ext := strings.ToLower(filepath.Ext(path))
				if ext != ".jsonl" && ext != ".json" && !(agent == "hermes" && dir == "memories" && ext == ".md") {
					return nil
				}
				s := Source{Agent: agent, Path: path, Modified: info.ModTime().UTC().Format(time.RFC3339)}
				if time.Since(info.ModTime()) < age {
					s.Status, s.Reason = "active", "尚未达到闲置时长"
					return add(s)
				}
				if info.Size() > max {
					s.Status, s.Reason = "skipped", "超过单文件限制"
					return add(s)
				}
				var err error
				if ext == ".md" {
					s.Text, err = readDocument(ctx, path, max)
				} else {
					var b []byte
					b, err = readBounded(path, max)
					if err == nil {
						s.Text, s.SessionID, s.Project, s.Title, err = parseTranscript(b, agent)
					}
				}
				if err != nil {
					s.Status, s.Reason = "error", err.Error()
				}
				return add(s)
			})
			if err != nil {
				if e := add(Source{Agent: agent, Path: path, Status: "error", Reason: err.Error()}); e != nil {
					return inv, e
				}
			}
		}
	}
	for _, path := range cfg.Roots {
		log("扫描文档 " + path)
		err := walkSafe(ctx, path, func(path string, info os.FileInfo) error {
			if seenPath[path] {
				return nil
			}
			seenPath[path] = true
			ext := strings.ToLower(filepath.Ext(path))
			switch ext {
			case ".md", ".txt", ".rst", ".csv", ".html", ".htm", ".docx", ".xlsx", ".pptx", ".pdf":
			default:
				return nil
			}
			s := Source{Agent: "document", Path: path, Project: filepath.Dir(path), Modified: info.ModTime().UTC().Format(time.RFC3339)}
			if time.Since(info.ModTime()) < age {
				s.Status, s.Reason = "active", "文档仍在近期修改"
				return add(s)
			}
			if info.Size() > max {
				s.Status, s.Reason = "skipped", "超过单文件限制"
				return add(s)
			}
			var err error
			s.Text, err = readDocument(ctx, path, max)
			if err != nil {
				s.Status, s.Reason = "error", err.Error()
			}
			return add(s)
		})
		if err != nil {
			if e := add(Source{Agent: "document", Path: path, Status: "error", Reason: err.Error()}); e != nil {
				return inv, e
			}
		}
	}
	if err := ctx.Err(); err != nil {
		return inv, err
	}
	return inv, atomicJSON(filepath.Join(root, "inventory.json"), inv)
}

func scanHermesDB(ctx context.Context, path string, age time.Duration, max int64, add func(Source) error) error {
	u := &url.URL{Scheme: "file", Path: filepath.ToSlash(path)}
	db, err := sql.Open("sqlite", u.String()+"?mode=ro")
	if err != nil {
		return err
	}
	defer db.Close()
	db.SetMaxOpenConns(2)
	// Read in a transaction to get a consistent snapshot, including the WAL.
	tx, err := db.BeginTx(ctx, &sql.TxOptions{ReadOnly: true})
	if err != nil {
		return err
	}
	defer tx.Rollback()
	rows, err := tx.QueryContext(ctx, "SELECT id,COALESCE(title,''),COALESCE(cwd,''),ended_at FROM sessions ORDER BY started_at")
	if err != nil {
		return fmt.Errorf("Hermes 数据库结构不兼容：%w", err)
	}
	type session struct {
		id, title, cwd string
		end            sql.NullFloat64
	}
	var sessions []session
	for rows.Next() {
		var s session
		if err = rows.Scan(&s.id, &s.title, &s.cwd, &s.end); err != nil {
			rows.Close()
			return err
		}
		sessions = append(sessions, s)
	}
	err = rows.Err()
	rows.Close()
	if err != nil {
		return err
	}
	for _, entry := range sessions {
		s := Source{Agent: "hermes", Path: path, SessionID: entry.id, Title: entry.title, Project: entry.cwd}
		if !entry.end.Valid || time.Since(time.Unix(int64(entry.end.Float64), 0)) < age {
			s.Status, s.Reason = "active", "会话未结束或尚未达到闲置时长"
			if err := add(s); err != nil {
				return err
			}
			continue
		}
		s.Modified = time.Unix(int64(entry.end.Float64), 0).UTC().Format(time.RFC3339)
		// Active flag excludes rewound messages on Hermes versions that support it.
		query := "SELECT role,content FROM messages WHERE session_id=? AND role IN ('user','assistant') AND COALESCE(active,1)=1 ORDER BY timestamp,id"
		msgs, err := tx.QueryContext(ctx, query, entry.id)
		if err != nil {
			msgs, err = tx.QueryContext(ctx, "SELECT role,content FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY timestamp,id", entry.id)
		}
		if err != nil {
			return err
		}
		var parts []string
		size := 0
		for msgs.Next() {
			var role string
			var body sql.NullString
			if err = msgs.Scan(&role, &body); err != nil {
				msgs.Close()
				return err
			}
			content := body.String
			var blocks []any
			if json.Unmarshal([]byte(content), &blocks) == nil {
				content = textContent(blocks)
			}
			size += len(content)
			if int64(size) > max {
				s.Status, s.Reason = "skipped", "会话正文超过大小限制"
				break
			}
			if strings.TrimSpace(content) != "" {
				parts = append(parts, role+": "+content)
			}
		}
		err = msgs.Err()
		msgs.Close()
		if err != nil {
			return err
		}
		s.Text = strings.Join(parts, "\n\n")
		if err := add(s); err != nil {
			return err
		}
	}
	return nil
}
