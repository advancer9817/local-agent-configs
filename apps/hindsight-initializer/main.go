package main

import (
	"context"
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
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
	Kind   string   `json:"kind"`
	Status string   `json:"status"`
	Error  string   `json:"error,omitempty"`
	Log    []string `json:"log"`
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
}

func newApp(root string) (*App, error) {
	c, err := loadConfig(root)
	if err != nil {
		return nil, errors.New("无法读取本地初始化配置")
	}
	a := &App{root: root, cfg: c, token: randomToken(), job: Job{Status: "idle", Log: []string{}}, inventory: Inventory{Sources: []Source{}}, products: []Product{}}
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
	a.cancel = cancel
	a.job = Job{Kind: kind, Status: "running", Log: []string{}}
	cfg := a.cfg
	go func() {
		err := fn(ctx, cfg)
		a.mu.Lock()
		defer a.mu.Unlock()
		a.job.Status = "completed"
		if err != nil {
			a.job.Status = "failed"
			a.job.Error = redact(err.Error())
			if errors.Is(err, context.Canceled) {
				a.job.Status = "cancelled"
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
	mux.HandleFunc("GET /api/state", func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		defer a.mu.Unlock()
		respond(w, 200, map[string]any{"config": publicConfig(a.cfg), "job": a.job, "inventory": a.inventory, "products": a.products, "home": homePath(), "data_dir": a.root, "os": runtime.GOOS})
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
		if cfg.Token == "" && cfg.API == a.cfg.API {
			cfg.Token = a.cfg.Token
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
				child, cancel := context.WithTimeout(ctx, 20*time.Second)
				defer cancel()
				res, err := checkRemote(child, c)
				if err != nil {
					return err
				}
				a.log("Hindsight 连接与认证通过，文档数：" + fmt.Sprint(res["total_documents"]))
			} else {
				var out struct {
					Ready bool `json:"model_configured"`
				}
				if err := requestJSON(ctx, "GET", ingestURL(c, "/capabilities"), c.Token, nil, &out); err != nil {
					return err
				}
				if !out.Ready {
					return errors.New("服务端未配置文档处理模型")
				}
				a.log("服务端文档处理能力已启用，模型已配置（未执行推理测试）")
			}
			return nil
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/scan", func(w http.ResponseWriter, r *http.Request) {
		err := a.start("scan", func(ctx context.Context, c Config) error {
			if err := c.validate(false, false); err != nil {
				return err
			}
			dir := filepath.Join(a.root, "scans", time.Now().UTC().Format("20060102T150405")+"-"+randomToken()[:8])
			inv, err := scanLocal(ctx, c, dir, a.log)
			if err != nil {
				return err
			}
			if err = atomicJSON(filepath.Join(a.root, "current-scan.json"), map[string]string{"directory": dir, "scope_key": c.scopeKey()}); err != nil {
				return err
			}
			a.mu.Lock()
			a.scanDir = dir
			a.inventory = inv
			a.products = []Product{}
			a.mu.Unlock()
			a.log(fmt.Sprintf("扫描完成：%d 篇待处理，%d 篇跳过/重复/活跃，%d 字", inv.Ready, inv.Skipped, inv.Chars))
			return nil
		})
		if err != nil {
			fail(w, err)
			return
		}
		respond(w, 202, map[string]bool{"started": true})
	})
	mux.HandleFunc("POST /api/compact", func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			IDs     []string `json:"ids"`
			Confirm bool     `json:"confirm_source_upload"`
		}
		if err := decode(w, r, &req); err != nil {
			fail(w, err)
			return
		}
		if len(req.IDs) == 0 || !req.Confirm {
			fail(w, errors.New("请选择来源并确认上传原件至服务端准备区"))
			return
		}
		err := a.start("compact", func(ctx context.Context, c Config) error {
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
			a.log(fmt.Sprintf("服务端处理完成：%d 份成品，%d 份待复核", len(ps)-review, review))
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
			Confirm bool `json:"confirm"`
		}
		if err := decode(w, r, &req); err != nil || !req.Confirm {
			fail(w, errors.New("必须明确确认上传已核验成品"))
			return
		}
		err := a.start("upload", func(ctx context.Context, c Config) error {
			a.mu.Lock()
			ps, dir := append([]Product(nil), a.products...), a.scanDir
			a.mu.Unlock()
			return uploadProducts(ctx, c, ps, dir, a.root, a.log)
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
					return restoreAgents(a.root, a.log)
				}
				return configureAgents(c, a.root, a.log)
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
		if r.URL.Query().Get("kind") == "product" {
			folder = "products"
			for _, p := range a.products {
				if p.ID == id {
					valid = true
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
		b, err := readBounded(filepath.Join(dir, folder, id+".md"), 100*1024*1024)
		if err != nil {
			fail(w, err)
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
