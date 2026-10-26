package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestDocumentCatalogDoesNotExtractContents(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	documents := t.TempDir()
	a.cfg.Roots = []string{documents}
	for _, name := range []string{"笔记.md", "报告.pdf", "资料.docx", "表格.xlsx"} {
		oldFile(t, filepath.Join(documents, name), "invalid-format-and-private-content")
	}
	if err := saveConfig(a.root, a.cfg); err != nil {
		t.Fatal(err)
	}
	mustFile(t, filepath.Join(documents, "credentials.txt"), "must-not-be-listed")
	w := workflowRequest(t, a, "POST", "/api/catalog", map[string]any{})
	job := waitWorkflowJob(t, a)
	if w.Code != http.StatusAccepted || job.Status != "completed" {
		t.Fatal("metadata catalog failed", w.Code, job)
	}
	a.mu.Lock()
	inventory, dir := a.inventory, a.scanDir
	a.mu.Unlock()
	count := 3
	if supportedDocument("报告.pdf") {
		count++
	}
	if len(inventory.Sources) != count || inventory.Ready != 0 || inventory.Chars != 0 {
		t.Fatal("metadata was treated as extracted content", inventory)
	}
	for _, source := range inventory.Sources {
		if source.Status != "pending" || source.SHA != "" || source.Chars != 0 {
			t.Fatal("catalog tried to extract document content", source)
		}
	}
	if _, err := os.Stat(filepath.Join(dir, "raw")); !os.IsNotExist(err) {
		t.Fatal("metadata catalog wrote document bodies")
	}
	reloaded, err := newApp(a.root)
	if err != nil || len(reloaded.inventory.Sources) != count {
		t.Fatal("catalog did not survive reopening", err)
	}
}

func TestSmartDirectoryScanAddsNestedDocumentMetadata(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	root := t.TempDir()
	a.cfg.Roots = []string{filepath.Join(root, "nested")}
	oldFile(t, filepath.Join(root, "nested", "报告.docx"), "not-a-docx")
	oldFile(t, filepath.Join(root, "笔记.md"), "must-not-be-read")
	oldFile(t, filepath.Join(root, "node_modules", "dependency.md"), "excluded")
	oldFile(t, filepath.Join(root, "AppData", "cached.md"), "excluded")
	oldFile(t, filepath.Join(root, "credentials.txt"), "excluded")
	w := workflowRequest(t, a, "POST", "/api/discover", map[string]any{"mode": "directory", "path": root})
	job := waitWorkflowJob(t, a)
	if w.Code != http.StatusAccepted || job.Status != "completed" {
		t.Fatal("smart directory scan failed", w.Code, job)
	}
	a.mu.Lock()
	inventory := a.inventory
	roots := append([]string{}, a.cfg.Roots...)
	a.mu.Unlock()
	if len(inventory.Sources) != 2 || inventory.Pending != 2 || inventory.Ready != 0 || inventory.Chars != 0 {
		t.Fatal("discovery did not stay metadata-only", inventory)
	}
	if len(roots) != 1 || roots[0] != root {
		t.Fatal("selected directory not registered or overlaps not removed", roots)
	}
	for _, source := range inventory.Sources {
		if source.SHA != "" || source.Text != "" || source.Chars != 0 {
			t.Fatal("discovery extracted document contents")
		}
	}
	reloaded, err := newApp(a.root)
	if err != nil || len(reloaded.inventory.Sources) != 2 {
		t.Fatal("smart scan results were not persisted", err)
	}
}

func TestSmartScanRejectsInvalidScope(t *testing.T) {
	for _, body := range []map[string]any{
		{"mode": "invalid"},
		{"mode": "directory", "path": "relative/path"},
		{"mode": "directory", "path": ""},
	} {
		a, err := newApp(t.TempDir())
		if err != nil {
			t.Fatal(err)
		}
		a.host = "127.0.0.1:45123"
		if w := workflowRequest(t, a, "POST", "/api/discover", body); w.Code != http.StatusBadRequest {
			t.Fatal("invalid scan scope accepted", w.Code)
		}
	}
}

func TestCancelledCatalogKeepsDiscoveredMetadata(t *testing.T) {
	root := t.TempDir()
	for _, name := range []string{"a.md", "b.md", "c.md"} {
		oldFile(t, filepath.Join(root, name), "not extracted")
	}
	cfg := defaultConfig()
	cfg.Roots = []string{root}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	inventory, err := catalogDocuments(ctx, cfg, func(string) {}, func(partial Inventory, _ string) {
		if len(partial.Sources) > 0 {
			cancel()
		}
	})
	if err != context.Canceled || len(inventory.Sources) != 1 || inventory.Pending != 1 {
		t.Fatal("cancelled scan discarded partial metadata", inventory, err)
	}
}

func TestCatalogOmitsUnsupportedFormats(t *testing.T) {
	root := t.TempDir()
	for _, name := range []string{"历史.doc", "旧表.xls", "演示.ppt", "文档.odt", "电子书.epub", "密码.doc", "账号.xls", "~$打开.doc"} {
		oldFile(t, filepath.Join(root, name), "metadata only")
	}
	oldFile(t, filepath.Join(root, "可提取.md"), "metadata only")
	cfg := defaultConfig()
	cfg.Roots = []string{root}
	inventory, err := catalogDocuments(context.Background(), cfg, func(string) {}, nil)
	if err != nil || len(inventory.Sources) != 1 {
		t.Fatal("unsupported documents were not filtered", inventory, err)
	}
	for _, source := range inventory.Sources {
		if source.Status != "pending" || source.SHA != "" {
			t.Fatal("catalog extracted content unexpectedly", source)
		}
	}
}

func TestCatalogOmitsPDFWithoutParser(t *testing.T) {
	t.Setenv("PATH", "")
	root := t.TempDir()
	oldFile(t, filepath.Join(root, "报告.pdf"), "not read")
	oldFile(t, filepath.Join(root, "笔记.md"), "not read")
	cfg := defaultConfig()
	cfg.Roots = []string{root}
	inventory, err := catalogDocuments(context.Background(), cfg, func(string) {}, nil)
	if err != nil || len(inventory.Sources) != 1 || filepath.Ext(inventory.Sources[0].Path) != ".md" {
		t.Fatal("PDF shown without its parsing dependency", inventory, err)
	}
}

func TestCatalogPreservesExtractedSourcesAndProducts(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	root := t.TempDir()
	path := filepath.Join(root, "existing.md")
	oldFile(t, path, "already extracted")
	oldFile(t, filepath.Join(root, "new.md"), "not extracted")
	a.cfg.Roots = []string{root}
	source := Source{ID: hashText("document\x00" + path + "\x00"), Agent: "document", Path: path, SHA: hashText("already extracted"), Chars: 17, Status: "ready"}
	a.inventory = Inventory{Sources: []Source{source}, Ready: 1, Chars: 17}
	a.products = []Product{{ID: "existing-product", Status: "approved", SHA: "fixture"}}
	if w := workflowRequest(t, a, "POST", "/api/catalog", map[string]any{}); w.Code != http.StatusAccepted {
		t.Fatal(w.Code, w.Body.String())
	}
	if job := waitWorkflowJob(t, a); job.Status != "completed" {
		t.Fatal(job)
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	if len(a.inventory.Sources) != 2 || a.inventory.Ready != 1 || a.inventory.Pending != 1 || len(a.products) != 1 {
		t.Fatal("metadata refresh altered extracted results")
	}
}

func workflowRequest(t *testing.T, a *App, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	data, err := json.Marshal(body)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(method, "http://"+a.host+path, bytes.NewReader(data))
	req.Header.Set("X-Setup-Token", a.token)
	w := httptest.NewRecorder()
	a.handler().ServeHTTP(w, req)
	return w
}

func waitWorkflowJob(t *testing.T, a *App) Job {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		a.mu.Lock()
		job := a.job
		a.mu.Unlock()
		if job.Status != "running" {
			return job
		}
		time.Sleep(time.Millisecond)
	}
	t.Fatal("workflow job did not finish")
	return Job{}
}

func TestProductDetailsShowFullTextAndSources(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	a.scanDir = t.TempDir()
	body := strings.Repeat("完整提炼正文。\n", 2000) + "最后的结论"
	source := Source{ID: "source-1", SessionID: "session-1", Title: "历史决策", Project: "/project", Path: "/project/session.jsonl"}
	product := Product{
		ID: hashText("product"), Title: "提炼结果", Status: "approved", SHA: hashText(body),
		SourceIDs: []string{source.ID}, References: map[string]Source{"S1": source},
	}
	a.products = []Product{product}
	mustFile(t, filepath.Join(a.scanDir, "products", product.ID+".md"), body)
	w := workflowRequest(t, a, "GET", "/api/preview?kind=product&id="+product.ID, nil)
	var result struct {
		Text      string  `json:"text"`
		Truncated bool    `json:"truncated"`
		Product   Product `json:"product"`
	}
	if w.Code != http.StatusOK || json.Unmarshal(w.Body.Bytes(), &result) != nil {
		t.Fatal(w.Code, w.Body.String())
	}
	if result.Text != body || result.Truncated || result.Product.References["S1"].SessionID != source.SessionID {
		t.Fatal("full text or provenance missing")
	}
	mustFile(t, filepath.Join(a.scanDir, "products", product.ID+".md"), "tampered")
	if w := workflowRequest(t, a, "GET", "/api/preview?kind=product&id="+product.ID, nil); w.Code != http.StatusBadRequest {
		t.Fatal("tampered product displayed as verified")
	}
}

func TestProductDetailsWithoutApprovedBody(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	a.products = []Product{{ID: "review", Status: "review_required", Reason: "独立核验未通过"}}
	w := workflowRequest(t, a, "GET", "/api/preview?kind=product&id=review", nil)
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), "独立核验未通过") {
		t.Fatal("review details unavailable", w.Code, w.Body.String())
	}
	if w := workflowRequest(t, a, "GET", "/api/preview?kind=product&id=unknown", nil); w.Code != http.StatusBadRequest {
		t.Fatal("unknown product accepted")
	}
}

func TestUploadRequiresSelectionAndExplicitConsent(t *testing.T) {
	var requests atomic.Int32
	var uploaded []string
	documents := map[string]map[string]any{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		switch {
		case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/memories"):
			var in struct {
				Items []struct {
					Document string            `json:"document_id"`
					Content  string            `json:"content"`
					Metadata map[string]string `json:"metadata"`
				} `json:"items"`
				Operation string `json:"operation_id"`
			}
			_ = json.NewDecoder(r.Body).Decode(&in)
			item := in.Items[0]
			uploaded = append(uploaded, item.Metadata["bootstrap_id"])
			documents[item.Document] = map[string]any{
				"original_text": item.Content, "memory_unit_count": 1,
				"retain_params": map[string]any{"metadata": item.Metadata},
			}
			respond(w, 200, map[string]string{"operation_id": in.Operation})
		case strings.Contains(r.URL.Path, "/operations/"):
			respond(w, 200, map[string]any{"status": "completed"})
		case strings.Contains(r.URL.Path, "/documents/"):
			document := documents[strings.SplitN(r.URL.Path, "/documents/", 2)[1]]
			if document == nil {
				w.WriteHeader(404)
				return
			}
			respond(w, 200, document)
		default:
			t.Error("unexpected remote request", r.URL.Path)
			w.WriteHeader(500)
		}
	}))
	defer server.Close()
	for _, test := range []struct {
		name    string
		body    map[string]any
		allowed bool
	}{
		{"no-consent", map[string]any{"ids": []string{hashText("first")}}, false},
		{"false-consent", map[string]any{"confirm": false, "ids": []string{hashText("first")}}, false},
		{"no-selection", map[string]any{"confirm": true}, false},
		{"empty-selection", map[string]any{"confirm": true, "ids": []string{}}, false},
		{"unknown-selection", map[string]any{"confirm": true, "ids": []string{"unknown"}}, false},
		{"mixed-selection", map[string]any{"confirm": true, "ids": []string{hashText("first"), "unknown"}}, false},
		{"unapproved", map[string]any{"confirm": true, "ids": []string{"review"}}, false},
		{"one-product", map[string]any{"confirm": true, "ids": []string{hashText("first")}}, true},
	} {
		t.Run(test.name, func(t *testing.T) {
			a, err := newApp(t.TempDir())
			if err != nil {
				t.Fatal(err)
			}
			a.host, a.cfg.API, a.scanDir = "127.0.0.1:45123", server.URL, t.TempDir()
			for _, name := range []string{"first", "second"} {
				body := name + " verified result"
				p := Product{ID: hashText(name), Title: name, Status: "approved", SHA: hashText(body)}
				a.products = append(a.products, p)
				mustFile(t, filepath.Join(a.scanDir, "products", p.ID+".md"), body)
			}
			a.products = append(a.products, Product{ID: "review", Status: "review_required"})
			before := requests.Load()
			w := workflowRequest(t, a, "POST", "/api/upload", test.body)
			job := waitWorkflowJob(t, a)
			if test.allowed {
				if w.Code != http.StatusAccepted || job.Status != "completed" || len(uploaded) != 1 || uploaded[0] != hashText("first") {
					t.Fatal("selection not respected", w.Code, job)
				}
			} else {
				rejected := w.Code == http.StatusBadRequest || (w.Code == http.StatusAccepted && job.Status == "failed")
				if requests.Load() != before || !rejected {
					t.Fatal("invalid upload contacted remote or was not rejected", w.Code, job)
				}
			}
		})
	}
}

func TestUploadSelectionDeduplicatesIDs(t *testing.T) {
	product := Product{ID: "approved", Status: "approved", SHA: "fixture"}
	chosen, err := selectUploadProducts([]Product{product}, []string{product.ID, product.ID})
	if err != nil || len(chosen) != 1 {
		t.Fatal("duplicate IDs were not coalesced", chosen, err)
	}
	chosen, err = selectUploadProducts([]Product{product}, []string{product.ID, "unknown"})
	if err == nil || chosen != nil {
		t.Fatal("partially valid selection was accepted")
	}
}

func TestCompactionDoesNotContactHindsight(t *testing.T) {
	model, _ := mockModel(t, false)
	defer model.Close()
	var requests atomic.Int32
	remote := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		w.WriteHeader(500)
	}))
	defer remote.Close()
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host, a.scanDir = "127.0.0.1:45123", t.TempDir()
	a.cfg.API, a.cfg.ModelURL, a.cfg.Model = remote.URL, model.URL, "fixture"
	body := strings.Repeat("历史需求和过程描述。", 100)
	s := Source{ID: "source", Project: "/project", Status: "ready", SHA: hashText(body), Chars: len([]rune(body))}
	a.inventory = Inventory{Sources: []Source{s}}
	mustFile(t, filepath.Join(a.scanDir, "raw", s.ID+".md"), body)
	w := workflowRequest(t, a, "POST", "/api/compact", map[string]any{"ids": []string{s.ID}})
	job := waitWorkflowJob(t, a)
	if w.Code != http.StatusAccepted || job.Status != "completed" || requests.Load() != 0 {
		t.Fatal("compaction must stay separate from Hindsight", w.Code, job, requests.Load())
	}
}
