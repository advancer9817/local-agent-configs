package main

import (
	"archive/zip"
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func mustFile(t *testing.T, path, body string) {
	t.Helper()
	if err := atomicWrite(path, []byte(body), 0600); err != nil {
		t.Fatal(err)
	}
}
func oldFile(t *testing.T, path, body string) {
	mustFile(t, path, body)
	old := time.Now().Add(-48 * time.Hour)
	if err := os.Chtimes(path, old, old); err != nil {
		t.Fatal(err)
	}
}

func TestCanonicalTranscriptNoDoubleEvents(t *testing.T) {
	raw := `{"type":"session_meta","payload":{"id":"s1","cwd":"/project"}}
{"type":"event_msg","payload":{"role":"assistant","content":"duplicated"}}
{"type":"response_item","payload":{"role":"user","content":[{"type":"input_text","text":"hello"}]}}
{"type":"response_item","payload":{"role":"assistant","content":[{"type":"output_text","text":"answer"},{"type":"reasoning","text":"private chain"}]}}
`
	text, sid, project, _, err := parseTranscript([]byte(raw), "codex")
	if err != nil || sid != "s1" || project != "/project" || text != "user: hello\n\nassistant: answer" {
		t.Fatalf("%q %q %q %v", text, sid, project, err)
	}
	if strings.Contains(text, "private") || strings.Contains(text, "duplicated") {
		t.Fatal("unexpected internal or duplicate text")
	}
}

func TestScanSafetyAndExactDedup(t *testing.T) {
	dir := t.TempDir()
	docs := filepath.Join(dir, "docs")
	body := "Decision: preserve project boundaries.\napi_key = sk-" + strings.Repeat("x", 24) + "\nBearer xyz-secret-value\n"
	oldFile(t, filepath.Join(docs, "decision.md"), body)
	oldFile(t, filepath.Join(docs, "duplicate.md"), body)
	oldFile(t, filepath.Join(docs, ".ssh", "notes.md"), "SECRET")
	oldFile(t, filepath.Join(docs, "config.md"), "SECRET")
	oldFile(t, filepath.Join(docs, "node_modules", "notes.md"), "SECRET")
	mustFile(t, filepath.Join(docs, "active.md"), "recent document")
	outside := filepath.Join(dir, "outside.md")
	oldFile(t, outside, "SYMLINK SECRET")
	_ = os.Symlink(outside, filepath.Join(docs, "linked.md"))
	cfg := defaultConfig()
	cfg.Agents = map[string]AgentConfig{}
	cfg.Roots = []string{docs}
	inv, err := scanLocal(context.Background(), cfg, filepath.Join(dir, "stage"), func(string) {})
	if err != nil {
		t.Fatal(err)
	}
	if inv.Ready != 1 || len(inv.Sources) != 3 {
		t.Fatalf("%+v", inv)
	}
	var dup, active int
	for _, s := range inv.Sources {
		if s.Status == "duplicate" {
			dup++
		}
		if s.Status == "active" {
			active++
		}
		if strings.Contains(s.Text, "sk-") || strings.Contains(s.Text, "xyz-secret") {
			t.Fatal("unredacted credential")
		}
	}
	if dup != 1 || active != 1 {
		t.Fatalf("dup=%d active=%d", dup, active)
	}
}

func TestHermesReadOnlyWAL(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "state.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	for _, q := range []string{
		"PRAGMA journal_mode=WAL",
		"CREATE TABLE sessions(id TEXT,title TEXT,cwd TEXT,started_at REAL,ended_at REAL)",
		"CREATE TABLE messages(id INTEGER,session_id TEXT,role TEXT,content TEXT,timestamp REAL,active INTEGER)",
		"INSERT INTO sessions VALUES('ended','历史会话','/p',1,2),('live','活跃','/p',1,NULL)",
		"INSERT INTO messages VALUES(1,'ended','user','hello',1,1),(2,'ended','assistant','world',2,1),(3,'ended','assistant','rewound',3,0)",
	} {
		if _, err = db.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	var sources []Source
	err = scanHermesDB(context.Background(), path, 24*time.Hour, 1024*1024, func(s Source) error { sources = append(sources, s); return nil })
	if err != nil {
		t.Fatal(err)
	}
	if len(sources) != 2 || sources[0].Text != "user: hello\n\nassistant: world" || sources[1].Status != "active" {
		t.Fatalf("%+v", sources)
	}
}

func TestCompactionUsesServerJobsAndReusesReceipts(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/archives") {
			calls.Add(1)
			respond(w, 200, map[string]string{"job_id": "remote-one", "status": "pending"})
		} else if strings.HasSuffix(r.URL.Path, "/jobs/remote-one") {
			respond(w, 200, map[string]string{"job_id": "remote-one", "status": "prepared", "refined_text": "# 历史迁移要求\n历史迁移未完成。"})
		} else {
			t.Errorf("client contacted unexpected endpoint: %s", r.URL.Path)
			w.WriteHeader(500)
		}
	}))
	defer server.Close()
	c := defaultConfig()
	c.API, c.Token = server.URL, "token"
	dir := t.TempDir()
	shared := t.TempDir()
	inv := Inventory{}
	for i := range 2 {
		body := strings.Repeat("重要的历史迁移需求。", 1000) + fmt.Sprint(i)
		s := Source{ID: fmt.Sprintf("source%d", i), Agent: "codex", Project: "/same-project", Title: "历史会话", SHA: hashText(body), Chars: len([]rune(body)), Status: "ready"}
		inv.Sources = append(inv.Sources, s)
		mustFile(t, filepath.Join(dir, "raw", s.ID+".md"), body)
	}
	products, err := compactInventory(context.Background(), c, inv, dir, shared, func(string) {})
	if err != nil {
		t.Fatal(err)
	}
	if len(products) != 1 || products[0].Status != "approved" || len(products[0].References) != 2 {
		t.Fatalf("%+v", products)
	}
	// A new local scan resumes the same durable server task.
	_, err = compactInventory(context.Background(), c, inv, dir, shared, func(string) {})
	if err != nil || calls.Load() != 1 {
		t.Fatalf("server receipt not reused %v", err)
	}
}

func TestSingleWriterLock(t *testing.T) {
	path := filepath.Join(t.TempDir(), "initializer.lock")
	a, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := os.OpenFile(path, os.O_RDWR, 0600)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	if err = lockState(a); err != nil {
		t.Fatal(err)
	}
	if err = lockState(b); err == nil {
		t.Fatal("multiple writers acquired same data directory")
	}
}

func TestUploadReadbackAndIdempotency(t *testing.T) {
	var submissions atomic.Int32
	committed := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/commit"):
			submissions.Add(1)
			committed = true
			respond(w, 200, map[string]string{"job_id": "remote-one", "status": "retaining"})
		case strings.Contains(r.URL.Path, "/jobs/remote-one"):
			status := "prepared"
			if committed {
				status = "completed"
			}
			respond(w, 200, map[string]string{"job_id": "remote-one", "status": status, "refined_text": "验证后的历史记录\n"})
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL.Path)
			w.WriteHeader(500)
		}
	}))
	defer server.Close()
	c := defaultConfig()
	c.API = server.URL
	c.Token = "secret"
	dir := t.TempDir()
	p := Product{ID: hashText("group"), Title: "测试归档", Content: "验证后的历史记录\n", Status: "approved",
		JobID: "remote-one", Target: server.URL + "/" + c.Bank}
	p.SHA = hashText(p.Content)
	mustFile(t, filepath.Join(dir, "products", p.ID+".md"), p.Content)
	for range 2 {
		if err := uploadProducts(context.Background(), c, []Product{p}, dir, dir, func(string) {}); err != nil {
			t.Fatal(err)
		}
	}
	if submissions.Load() != 1 {
		t.Fatal("duplicate retain", submissions.Load())
	}
	// A second initialization scan shares the durable upload ledger.
	another := t.TempDir()
	mustFile(t, filepath.Join(another, "products", p.ID+".md"), p.Content)
	if err := uploadProducts(context.Background(), c, []Product{p}, another, dir, func(string) {}); err != nil {
		t.Fatal(err)
	}
	if submissions.Load() != 1 {
		t.Fatal("re-uploaded across scan batches")
	}
	mustFile(t, filepath.Join(dir, "products", p.ID+".md"), "tampered")
	if err := uploadProducts(context.Background(), c, []Product{p}, dir, dir, func(string) {}); err == nil {
		t.Fatal("tampered product accepted")
	}
}

func TestMCPBridgeSessionAndProtocol(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := requests.Add(1)
		if r.Header.Get("Authorization") != "Bearer test-token" {
			t.Error("missing auth")
		}
		var in map[string]any
		_ = json.NewDecoder(r.Body).Decode(&in)
		if n == 1 {
			w.Header().Set("Content-Type", "text/event-stream")
			w.Header().Set("Mcp-Session-Id", "session-test")
			fmt.Fprint(w, "event: message\ndata: {\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"protocolVersion\":\"2025-03-26\"}}\n\n")
		} else {
			if r.Header.Get("Mcp-Session-Id") != "session-test" || r.Header.Get("MCP-Protocol-Version") != "2025-03-26" {
				t.Error("session or negotiated protocol missing")
			}
			if _, ok := in["id"]; !ok {
				w.WriteHeader(202)
				return
			}
			respond(w, 200, map[string]any{"jsonrpc": "2.0", "id": 2, "result": map[string]any{"tools": []any{}}})
		}
	}))
	defer server.Close()
	input := `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
`
	c := defaultConfig()
	c.API = server.URL
	c.Token = "test-token"
	var out bytes.Buffer
	if err := stdioBridge(context.Background(), c, strings.NewReader(input), &out); err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(out.String()), "\n")
	if requests.Load() != 3 || len(lines) != 2 {
		t.Fatalf("requests=%d output=%s", requests.Load(), out.String())
	}
	for _, line := range lines {
		if !json.Valid([]byte(line)) {
			t.Fatal("stdout is not newline-delimited JSON")
		}
	}
}

func TestRemoteTestRequiresMCPAuthentication(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.Contains(r.URL.Path, "/mcp/") {
			w.WriteHeader(401)
			return
		}
		respond(w, 200, map[string]any{"total_documents": 1})
	}))
	defer server.Close()
	c := defaultConfig()
	c.API = server.URL
	c.Token = "wrong"
	if _, err := checkRemote(context.Background(), c); err == nil {
		t.Fatal("public stats counted as successful authentication")
	}
}

func TestScopeChangeInvalidatesStagedProducts(t *testing.T) {
	dir := t.TempDir()
	a, err := newApp(dir)
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	a.scanDir = filepath.Join(dir, "old")
	a.inventory = Inventory{Sources: []Source{{ID: "old-source", Status: "ready"}}}
	a.products = []Product{{ID: "old-product", Status: "approved"}}
	c := a.cfg
	c.Roots = []string{"/a/different/project"}
	raw, _ := json.Marshal(publicConfig(c))
	r := httptest.NewRequest("POST", "http://"+a.host+"/api/config", bytes.NewReader(raw))
	r.Host = a.host
	r.Header.Set("X-Setup-Token", a.token)
	w := httptest.NewRecorder()
	a.handler().ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatal(w.Body.String())
	}
	if a.scanDir != "" || len(a.products) > 0 || len(a.inventory.Sources) > 0 {
		t.Fatal("stale scope remained uploadable")
	}
}

func TestLocalServerCredentialIsolation(t *testing.T) {
	dir := t.TempDir()
	a, err := newApp(dir)
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	a.cfg.Token = "NEVER_RETURN"
	check := func(token, host, origin string) *httptest.ResponseRecorder {
		req := httptest.NewRequest("GET", "http://"+a.host+"/api/state", nil)
		req.Host = host
		req.Header.Set("X-Setup-Token", token)
		if origin != "" {
			req.Header.Set("Origin", origin)
		}
		w := httptest.NewRecorder()
		a.handler().ServeHTTP(w, req)
		return w
	}
	for _, test := range []struct{ token, host, origin string }{
		{"", a.host, ""}, {a.token, "evil.example", ""}, {a.token, a.host, "https://evil.example"},
	} {
		if w := check(test.token, test.host, test.origin); w.Code != 403 {
			t.Fatalf("unauthorized HTTP %d", w.Code)
		}
	}
	w := check(a.token, a.host, "")
	if w.Code != 200 || strings.Contains(w.Body.String(), "NEVER_RETURN") || strings.Contains(w.Body.String(), "OTHER_SECRET") {
		t.Fatal("secret leak", w.Code)
	}
}

func TestAgentInstallPreservesAndRestores(t *testing.T) {
	dir := t.TempDir()
	c := defaultConfig()
	c.API = "https://example.com"
	c.Token = "secret"
	c.Agents = map[string]AgentConfig{"codex": {true, filepath.Join(dir, "codex")}}
	path := filepath.Join(c.Agents["codex"].Path, "config.toml")
	original := `model = "existing"
[mcp_servers.other]
command = "unchanged"
`
	mustFile(t, path, original)
	if err := configureAgents(c, filepath.Join(dir, "state"), func(string) {}); err != nil {
		t.Fatal(err)
	}
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(b, []byte("existing")) || !bytes.Contains(b, []byte("unchanged")) || bytes.Contains(b, []byte("secret")) {
		t.Fatal("config altered or secret leaked")
	}
	if err = restoreAgents(filepath.Join(dir, "state"), func(string) {}); err != nil {
		t.Fatal(err)
	}
	b, _ = os.ReadFile(path)
	if string(b) != original {
		t.Fatal("restore not exact")
	}
}

func TestEndpointCredentialSafety(t *testing.T) {
	for _, s := range []string{"http://example.com", "https://user:pass@example.com", "file:///tmp/a", "https://example.com/?key=x"} {
		if validateEndpoint(s) == nil {
			t.Errorf("unsafe URL accepted: %s", s)
		}
	}
	for _, s := range []string{"https://example.com/v1", "http://127.0.0.1:4321", "http://[::1]:4321"} {
		if err := validateEndpoint(s); err != nil {
			t.Errorf("%s: %v", s, err)
		}
	}
	var code atomic.Int32
	second := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { code.Add(1); w.Write([]byte(`{}`)) }))
	defer second.Close()
	first := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, second.URL, 302) }))
	defer first.Close()
	err := requestJSON(context.Background(), "GET", first.URL, "private-key", nil, nil)
	if err == nil || code.Load() != 0 {
		t.Fatal("followed credential redirect")
	}
}

func TestOfficeUploadKeepsOriginalBytes(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "sample.xlsx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatal(err)
	}
	z := zip.NewWriter(f)
	for name, body := range map[string]string{
		"xl/sharedStrings.xml":     `<sst><si><t>指标名称</t></si><si><r><t>报表</t></r><r><t>规则</t></r></si></sst>`,
		"xl/worksheets/sheet1.xml": `<worksheet><sheetData><row><c t="s"><v>0</v></c><c t="s"><v>1</v></c><c><v>42</v></c></row></sheetData></worksheet>`,
	} {
		w, e := z.Create(name)
		if e != nil {
			t.Fatal(e)
		}
		fmt.Fprint(w, body)
	}
	if err = z.Close(); err != nil {
		t.Fatal(err)
	}
	f.Close()
	text, err := readDocument(context.Background(), path, 1024*1024)
	original, _ := os.ReadFile(path)
	if err != nil || text != string(original) {
		t.Fatalf("Office was parsed on the client: %v", err)
	}
}
