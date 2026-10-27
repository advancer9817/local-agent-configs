package main

import (
	"context"
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

//go:embed web/*
var assets embed.FS

type Job struct {
	Kind       string       `json:"kind"`
	Status     string       `json:"status"`
	Error      string       `json:"error,omitempty"`
	Log        []string     `json:"log"`
	StartedAt  time.Time    `json:"started_at"`
	FinishedAt *time.Time   `json:"finished_at,omitempty"`
	Progress   TaskProgress `json:"progress"`
}

type App struct {
	mu        sync.Mutex
	root      string
	cfg       Config
	token     string
	host      string
	scanDir   string
	inventory Inventory
	products  []Product
	job       Job
	cancel    context.CancelFunc
	shutdown  func()
	discovery DiscoveryProgress
}

func newApp(root string) (*App, error) {
	c, err := loadConfig(root)
	if err != nil {
		return nil, errors.New("无法读取本地初始化配置")
	}
	token, err := loadPageToken(root)
	if err != nil {
		return nil, errors.New("无法读取本地页面授权")
	}
	a := &App{root: root, cfg: c, token: token, job: Job{Status: "idle", Log: []string{}}, inventory: Inventory{Sources: []Source{}}, products: []Product{}}
	var current struct {
		Dir   string `json:"directory"`
		Scope string `json:"scope_key"`
	}
	if readJSON(filepath.Join(root, "current-scan.json"), &current) == nil && current.Scope == c.scopeKey() {
		// Only paths owned by this installation can become a staging directory.
		rel, e := filepath.Rel(filepath.Join(root, "scans"), current.Dir)
		if e == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(os.PathSeparator)) {
			a.scanDir = current.Dir
			_ = readJSON(filepath.Join(current.Dir, "inventory.json"), &a.inventory)
			a.inventory = mergeCatalog(a.inventory, Inventory{})
			_ = readJSON(filepath.Join(current.Dir, "products.json"), &a.products)
		}
	}
	return a, nil
}

func respond(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func fail(w http.ResponseWriter, err error) {
	respond(w, 400, map[string]any{"error": redact(err.Error())})
}

func decode(w http.ResponseWriter, r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(w, r.Body, 2*1024*1024)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	return d.Decode(v)
}

func (a *App) log(s string) {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.job.Log = append(a.job.Log, time.Now().Format("15:04:05")+"  "+redact(s))
	if len(a.job.Log) > 400 {
		a.job.Log = a.job.Log[len(a.job.Log)-400:]
	}
}

func (a *App) start(kind string, fn func(context.Context, Config) error) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.job.Status == "running" {
		return errors.New("已有任务执行中，请等待或取消")
	}
	ctx, cancel := context.WithCancel(context.Background())
	ctx = withProgress(ctx, a.updateProgress)
	a.cancel = cancel
	now := time.Now().UTC()
	a.job = Job{Kind: kind, Status: "running", Log: []string{}, StartedAt: now, Progress: TaskProgress{Stage: taskLabel(kind), PhaseStart: now, UpdatedAt: now}}
	cfg := a.cfg
	go func() {
		err := fn(ctx, cfg)
		a.mu.Lock()
		defer a.mu.Unlock()
		a.job.Status = "completed"
		finished := time.Now().UTC()
		a.job.FinishedAt = &finished
		if err != nil {
			a.job.Status = "failed"
			a.job.Error = redact(err.Error())
			if errors.Is(err, context.Canceled) {
				a.job.Status = "cancelled"
				a.job.Error = ""
			}
		}
		a.cancel = nil
		_ = atomicJSON(filepath.Join(a.root, "last-job.json"), a.job)
		cancel()
	}()
	return nil
}

func (a *App) handler() http.Handler {
	mux := http.NewServeMux()
	a.registerDiscovery(mux)
	mux.HandleFunc("GET /api/state", func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		defer a.mu.Unlock()
		respond(w, 200, map[string]any{"config": publicConfig(a.cfg), "job": a.job, "inventory": a.inventory, "products": a.products, "discovery": a.discovery, "home": homePath(), "data_dir": a.root, "os": runtime.GOOS})
	})
	mux.HandleFunc("POST /api/config", func(w http.ResponseWriter, r *http.Request) {
		var cfg Config
		if err := decode(w, r, &cfg); err != nil {
			fail(w, errors.New("配置格式无效"))
			return
		}
		a.mu.Lock()
		defer a.mu.Unlock()
		if a.job.Status == "running" {
			fail(w, errors.New("任务运行中，不能修改配置"))
			return
		}
		cfg.ModelURL = normalizeModelURL(cfg.ModelURL)
		if cfg.ModelKey == "" && cfg.ModelURL == normalizeModelURL(a.cfg.ModelURL) {
			cfg.ModelKey = a.cfg.ModelKey
		}
		if err := cfg.validate(false, false); err != nil {
			fail(w, err)
			return
		}
		if cfg.API != "" {
			if err := validateEndpoint(cfg.API); err != nil {
				fail(w, err)
				return
			}
		}
		if cfg.ModelURL != "" {
			if err := validateEndpoint(cfg.ModelURL); err != nil {
				fail(w, err)
				return
			}
		}
		if err := saveConfig(a.root, cfg); err != nil {
			fail(w, err)
			return
		}
		if cfg.scopeKey() != a.cfg.scopeKey() {
			a.scanDir = ""
			a.inventory = Inventory{Sources: []Source{}}
			a.products = []Product{}
		}
		a.cfg = cfg
		respond(w, 200, map[string]any{"config": publicConfig(cfg)})
	})
	mux.HandleFunc("POST /api/test", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Kind string `json:"kind"`
		}
		if err := decode(w, r, &req); err != nil {
			fail(w, err)
			return
		}
		if req.Kind != "remote" && req.Kind != "model" {
			fail(w, errors.New("未知测试类型"))
			return
		}
		err := a.start("test", func(ctx context.Context, c Config) error {
			if req.Kind == "remote" {
				reportDetail(ctx, "连接 Hindsight API 与 MCP", c.API)
				child, cancel := context.WithTimeout(ctx, 20*time.Second)
				defer cancel()
				res, err := checkRemote(child, c)
				if err != nil {
					return err
				}
				a.log("Hindsight API 与 MCP 连接通过，文档数：" + fmt.Sprint(res["total_documents"]))
			} else {
				reportDetail(ctx, "等待模型响应", c.Model)
				var out struct {
					OK bool `json:"ok"`
				}
				if err := modelJSON(ctx, c, `连接测试，不包含任何用户文件。返回{"ok":true}`, &out); err != nil {
					return err
				}
				if !out.OK {
					return errors.New("模型未返回预期测试结果")
				}
				a.log("压缩模型连接与 JSON 输出测试通过")
			}
			return nil
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/catalog", func(w http.ResponseWriter, r *http.Request) {
		err := a.start("catalog", func(ctx context.Context, c Config) error {
			if err := c.validate(false, false); err != nil {
				return err
			}
			listed, catalogErr := catalogDocuments(ctx, c, a.log, func(partial Inventory, current string) {
				reportProgress(ctx, "枚举文档清单", len(partial.Sources), 0, current, "个文件")
			})
			a.mu.Lock()
			existing := Inventory{Sources: []Source{}}
			for _, source := range a.inventory.Sources {
				if source.Agent != "document" || source.SHA != "" {
					existing.Sources = append(existing.Sources, source)
				}
			}
			inventory, dir := mergeCatalog(existing, listed), a.scanDir
			a.mu.Unlock()
			if err := a.saveCatalog(c, inventory, dir); err != nil {
				return err
			}
			a.log(fmt.Sprintf("文档清单已更新：%d 个文件，%d 篇待提取；未读取正文", len(listed.Sources), inventory.Pending))
			return catalogErr
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/scan", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			IDs   []string `json:"ids"`
			Scope bool     `json:"scope"`
		}
		if err := decode(w, r, &req); err != nil && !errors.Is(err, io.EOF) {
			fail(w, errors.New("提取参数无效"))
			return
		}
		err := a.start("scan", func(ctx context.Context, c Config) error {
			if err := c.validate(false, false); err != nil {
				return err
			}
			a.mu.Lock()
			existing, existingDir := cloneInventory(a.inventory), a.scanDir
			a.mu.Unlock()
			if existingDir != "" && !req.Scope && (len(req.IDs) > 0 || existing.Pending > 0) {
				inv, err := extractCatalog(ctx, c, existing, req.IDs, existingDir, func(partial Inventory) {
					a.mu.Lock()
					a.inventory = partial
					a.mu.Unlock()
				})
				a.mu.Lock()
				a.inventory = inv
				a.mu.Unlock()
				a.log(fmt.Sprintf("正文已保存：%d 篇可压缩，%d 篇待提取", inv.Ready, inv.Pending))
				return err
			}
			if len(req.IDs) > 0 {
				return errors.New("所选来源已失效，请刷新清单")
			}
			dir := filepath.Join(a.root, "scans", time.Now().UTC().Format("20060102T150405")+"-"+randomToken()[:8])
			lastCheckpoint := time.Time{}
			ctx = context.WithValue(ctx, inventoryContextKey{}, func(partial Inventory) error {
				if time.Since(lastCheckpoint) < time.Second {
					return nil
				}
				if err := a.saveCatalog(c, cloneInventory(partial), dir); err != nil {
					return err
				}
				lastCheckpoint = time.Now()
				return nil
			})
			inv, err := scanLocal(ctx, c, dir, a.log)
			if saveErr := atomicJSON(filepath.Join(dir, "inventory.json"), inv); saveErr != nil {
				return saveErr
			}
			if saveErr := atomicJSON(filepath.Join(a.root, "current-scan.json"), map[string]string{"directory": dir, "scope_key": c.scopeKey()}); saveErr != nil {
				return saveErr
			}
			a.mu.Lock()
			a.scanDir = dir
			a.inventory = inv
			a.products = []Product{}
			a.mu.Unlock()
			a.log(fmt.Sprintf("提取结果已保存：%d 篇待处理，%d 篇跳过/重复/活跃，%d 字", inv.Ready, inv.Skipped, inv.Chars))
			return err
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/compact", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			IDs []string `json:"ids"`
		}
		if err := decode(w, r, &req); err != nil {
			fail(w, err)
			return
		}
		if len(req.IDs) == 0 {
			fail(w, errors.New("请至少选择一个待处理来源"))
			return
		}
		err := a.start("compact", func(ctx context.Context, c Config) error {
			if err := c.validate(false, true); err != nil {
				return err
			}
			a.mu.Lock()
			inv, dir := a.inventory, a.scanDir
			a.mu.Unlock()
			if dir == "" {
				return errors.New("请先扫描")
			}
			selected := map[string]bool{}
			valid := map[string]bool{}
			for _, s := range inv.Sources {
				if s.Status == "ready" {
					valid[s.ID] = true
				}
			}
			for _, id := range req.IDs {
				if !valid[id] {
					return errors.New("选择包含无效来源，请重新扫描")
				}
				selected[id] = true
			}
			filtered := Inventory{Sources: []Source{}}
			for _, s := range inv.Sources {
				if selected[s.ID] {
					filtered.Sources = append(filtered.Sources, s)
				}
			}
			a.mu.Lock()
			a.products = []Product{}
			a.mu.Unlock()
			if err := atomicJSON(filepath.Join(dir, "products.json"), []Product{}); err != nil {
				return err
			}
			ps, err := compactInventory(ctx, c, filtered, dir, a.root, a.log)
			a.mu.Lock()
			a.products = ps
			a.mu.Unlock()
			if err != nil {
				return err
			}
			review := 0
			for _, p := range ps {
				if p.Status != "approved" {
					review++
				}
			}
			a.log(fmt.Sprintf("本地压缩完成：%d 份成品，%d 份未通过或无压缩收益", len(ps)-review, review))
			return nil
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/upload", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Confirm bool     `json:"confirm"`
			IDs     []string `json:"ids"`
		}
		if err := decode(w, r, &req); err != nil || !req.Confirm {
			fail(w, errors.New("必须明确确认上传已核验成品"))
			return
		}
		if len(req.IDs) == 0 {
			fail(w, errors.New("请先选择需要上传的提炼结果"))
			return
		}
		err := a.start("upload", func(ctx context.Context, c Config) error {
			a.mu.Lock()
			ps, dir := append([]Product(nil), a.products...), a.scanDir
			a.mu.Unlock()
			chosen, err := selectUploadProducts(ps, req.IDs)
			if err != nil {
				return err
			}
			return uploadProducts(ctx, c, chosen, dir, a.root, a.log)
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	for _, kind := range []string{"install", "restore"} {
		mux.HandleFunc("POST /api/"+kind, func(w http.ResponseWriter, r *http.Request) {
			err := a.start(kind, func(ctx context.Context, c Config) error {
				if kind == "restore" {
					return restoreAgents(a.root, a.log, ctx)
				}
				return configureAgents(c, a.root, a.log, ctx)
			})
			if err != nil {
				fail(w, err)
				return
			}
			respond(w, 202, map[string]bool{"started": true})
		})
	}
	mux.HandleFunc("POST /api/cancel", func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		if a.cancel != nil {
			a.job.Progress.Detail = "取消已请求，保存已完成结果"
			a.job.Progress.UpdatedAt = time.Now().UTC()
			a.cancel()
		}
		a.mu.Unlock()
		respond(w, 200, map[string]bool{"cancel_requested": true})
	})
	mux.HandleFunc("GET /api/browse", func(w http.ResponseWriter, r *http.Request) {
		path := expandPath(r.URL.Query().Get("path"))
		if path == "" {
			path = homePath()
		}
		path, err := filepath.Abs(path)
		if err != nil {
			fail(w, err)
			return
		}
		entries, err := os.ReadDir(path)
		if err != nil {
			fail(w, errors.New("无法读取所选目录"))
			return
		}
		dirs := []string{}
		for _, e := range entries {
			if e.IsDir() && e.Type()&os.ModeSymlink == 0 && !excludedPart(e.Name()) {
				dirs = append(dirs, filepath.Join(path, e.Name()))
			}
		}
		respond(w, 200, map[string]any{"path": path, "parent": filepath.Dir(path), "directories": dirs})
	})
	mux.HandleFunc("GET /api/preview", func(w http.ResponseWriter, r *http.Request) {
		id := r.URL.Query().Get("id")
		a.mu.Lock()
		dir := a.scanDir
		valid := false
		folder := "raw"
		var product *Product
		if r.URL.Query().Get("kind") == "product" {
			folder = "products"
			for _, p := range a.products {
				if p.ID == id {
					valid = true
					copy := p
					product = &copy
					break
				}
			}
		} else {
			for _, s := range a.inventory.Sources {
				if s.ID == id && s.SHA != "" {
					valid = true
				}
			}
		}
		a.mu.Unlock()
		if !valid {
			fail(w, errors.New("预览来源无效"))
			return
		}
		if product != nil && product.SHA == "" {
			respond(w, 200, map[string]any{"text": "", "truncated": false, "product": product})
			return
		}
		b, err := readBounded(filepath.Join(dir, folder, id+".md"), 100*1024*1024)
		if err != nil {
			fail(w, err)
			return
		}
		if product != nil {
			if hashText(string(b)) != product.SHA {
				fail(w, errors.New("提炼结果正文指纹不匹配，拒绝显示为已核验结果"))
				return
			}
			respond(w, 200, map[string]any{"text": string(b), "truncated": false, "product": product})
			return
		}
		text := []rune(string(b))
		truncated := len(text) > 12000
		if truncated {
			text = text[:12000]
		}
		respond(w, 200, map[string]any{"text": string(text), "truncated": truncated})
	})
	mux.HandleFunc("POST /api/shutdown", func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		busy := a.job.Status == "running"
		a.mu.Unlock()
		if busy {
			fail(w, errors.New("请先取消运行中的任务"))
			return
		}
		respond(w, 200, map[string]bool{"closed": true})
		if a.shutdown != nil {
			go a.shutdown()
		}
	})
	mux.HandleFunc("POST /api/open-browser", func(w http.ResponseWriter, r *http.Request) {
		openBrowser("http://" + a.host + "/#" + a.token)
		respond(w, 200, map[string]bool{"opened": true})
	})
	static, _ := fs.Sub(assets, "web")
	mux.Handle("GET /", http.FileServer(http.FS(static)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
		if r.Host != a.host {
			http.Error(w, "Invalid Host", 403)
			return
		}
		if strings.HasPrefix(r.URL.Path, "/api/") {
			if subtle.ConstantTimeCompare([]byte(r.Header.Get("X-Setup-Token")), []byte(a.token)) != 1 {
				respond(w, 403, map[string]string{"error": "本地页面授权失效，请使用程序新打开的页面"})
				return
			}
			if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+a.host {
				respond(w, 403, map[string]string{"error": "Origin rejected"})
				return
			}
		}
		mux.ServeHTTP(w, r)
	})
}

func openBrowser(address string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", address)
	case "darwin":
		cmd = exec.Command("open", address)
	default:
		cmd = exec.Command("xdg-open", address)
	}
	if cmd.Start() == nil {
		go cmd.Wait()
	}
}

func main() {
	rootDefault := homePath(".local", "state", "hindsight-initializer")
	if p := os.Getenv("HINDSIGHT_INITIALIZER_HOME"); p != "" {
		rootDefault = p
	}
	root := flag.String("data-dir", rootDefault, "private local state directory")
	listen := flag.String("listen", "127.0.0.1:0", "loopback bind address")
	noBrowser := flag.Bool("no-browser", false, "do not open a browser")
	browser := flag.Bool("browser", false, "use browser UI instead of the Windows desktop window")
	mcp := flag.Bool("mcp", false, "stdio MCP bridge")
	flag.Parse()
	absolute, err := filepath.Abs(*root)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Invalid data directory")
		return
	}
	if *mcp {
		c, err := loadConfig(absolute)
		if err == nil {
			err = stdioBridge(context.Background(), c, os.Stdin, os.Stdout)
		}
		if err != nil {
			fmt.Fprintln(os.Stderr, "Hindsight MCP bridge failed")
			os.Exit(1)
		}
		return
	}
	if err = os.MkdirAll(absolute, 0700); err != nil {
		fmt.Fprintln(os.Stderr, "Cannot create private data directory")
		return
	}
	lock, err := os.OpenFile(filepath.Join(absolute, "initializer.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Cannot open initializer lock")
		return
	}
	defer lock.Close()
	if err = lockState(lock); err != nil {
		var running struct {
			URL string `json:"url"`
		}
		if readJSON(filepath.Join(absolute, "launcher.json"), &running) == nil {
			if !*noBrowser {
				openBrowser(running.URL)
			}
			fmt.Println(running.URL)
		}
		return
	}
	a, err := newApp(absolute)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return
	}
	host, _, err := net.SplitHostPort(*listen)
	if err != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		fmt.Fprintln(os.Stderr, "Only numeric loopback addresses are allowed")
		return
	}
	listener, err := net.Listen("tcp", *listen)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Cannot start local configuration page")
		return
	}
	a.host = listener.Addr().String()
	server := &http.Server{Handler: a.handler(), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second}
	closing := make(chan struct{})
	shutdownDone := make(chan struct{})
	var closeOnce sync.Once
	a.shutdown = func() {
		closeOnce.Do(func() {
			close(closing)
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			defer cancel()
			server.Shutdown(ctx)
			close(shutdownDone)
		})
	}
	address := "http://" + a.host + "/#" + a.token
	fmt.Println(address)
	// Private launcher receipt supports headless preview without exposing credentials.
	_ = atomicJSON(filepath.Join(absolute, "launcher.json"), map[string]string{"url": address})
	served := make(chan error, 1)
	go func() { served <- server.Serve(listener) }()
	if !*noBrowser {
		desktop := false
		if !*browser {
			desktop = launchDesktop(address, absolute, closing)
		}
		if desktop {
			a.mu.Lock()
			if a.cancel != nil {
				a.cancel()
			}
			a.mu.Unlock()
			// Give cancellation a chance to flush checkpoints before closing.
			for i := 0; i < 50; i++ {
				a.mu.Lock()
				busy := a.job.Status == "running"
				a.mu.Unlock()
				if !busy {
					break
				}
				time.Sleep(100 * time.Millisecond)
			}
			a.shutdown()
		} else {
			openBrowser(address)
		}
	}
	if err = <-served; err != nil && !errors.Is(err, http.ErrServerClosed) {
		fmt.Fprintln(os.Stderr, "Local server stopped unexpectedly")
	} else {
		<-shutdownDone
	}
}
