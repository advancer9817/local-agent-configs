package main

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestProgressVisibleBeforeTaskFinishes(t *testing.T) {
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	ready, release := make(chan struct{}), make(chan struct{})
	if err := a.start("compact", func(ctx context.Context, c Config) error {
		reportProgress(ctx, "压缩与核验", 2, 5, "/docs/report.md", "篇来源")
		reportDetail(ctx, "等待模型响应", "")
		close(ready)
		<-release
		return errors.New("fixture failure")
	}); err != nil {
		t.Fatal(err)
	}
	<-ready
	w := workflowRequest(t, a, "GET", "/api/state", nil)
	var state struct {
		Job Job `json:"job"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &state); err != nil {
		t.Fatal(err)
	}
	close(release)
	job := waitWorkflowJob(t, a)
	if w.Code != 200 || state.Job.Status != "running" || state.Job.Progress.Completed != 2 || state.Job.Progress.Total != 5 || state.Job.Progress.Detail != "等待模型响应" || state.Job.StartedAt.IsZero() {
		t.Fatal("running progress was missing", w.Code, state.Job)
	}
	if job.Status != "failed" || job.Progress.Completed != 2 || job.FinishedAt == nil {
		t.Fatal("failure falsely completed progress or lost timing", job)
	}
}

func catalogFixture(t *testing.T) (*App, string) {
	t.Helper()
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	root := t.TempDir()
	for _, name := range []string{"first.md", "second.md", "third.md"} {
		oldFile(t, filepath.Join(root, name), "unique historical decision "+name+"\napi_key = sk-abcdefghijklmnopqrstuvwx")
	}
	for name, cfg := range a.cfg.Agents {
		cfg.Enabled = false
		a.cfg.Agents[name] = cfg
	}
	a.cfg.Roots = []string{root}
	if err := saveConfig(a.root, a.cfg); err != nil {
		t.Fatal(err)
	}
	inv, err := catalogDocuments(context.Background(), a.cfg, func(string) {}, nil)
	if err != nil {
		t.Fatal(err)
	}
	dir := filepath.Join(a.root, "scans", "fixture")
	if err := a.saveCatalog(a.cfg, inv, dir); err != nil {
		t.Fatal(err)
	}
	return a, dir
}

func TestSelectedExtractionStaysLocalAndUpdatesCatalog(t *testing.T) {
	a, dir := catalogFixture(t)
	id := a.inventory.Sources[1].ID
	a.products = []Product{{ID: "existing-product", Status: "approved"}}
	w := workflowRequest(t, a, "POST", "/api/scan", map[string]any{"ids": []string{id}})
	job := waitWorkflowJob(t, a)
	if w.Code != http.StatusAccepted || job.Status != "completed" {
		t.Fatal(w.Code, job)
	}
	if a.inventory.Ready != 1 || a.inventory.Pending != 2 || a.scanDir != dir || len(a.products) != 1 {
		t.Fatal("selected extraction altered unrelated data", a.inventory, a.products)
	}
	files, _ := filepath.Glob(filepath.Join(dir, "raw", "*.md"))
	if len(files) != 1 || filepath.Base(files[0]) != id+".md" {
		t.Fatal("extracted unselected files", files)
	}
	body, _ := os.ReadFile(files[0])
	if strings.Contains(string(body), "sk-abcdefghijklmnopqrstuvwx") {
		t.Fatal("unredacted credential")
	}
	if job.Progress.Total != 1 || job.Progress.Completed != 1 {
		t.Fatal("missing extraction progress", job)
	}
	reloaded, err := newApp(a.root)
	if err != nil || reloaded.inventory.Ready != 1 || reloaded.inventory.Pending != 2 {
		t.Fatal("checkpoint lost", err)
	}
}

func TestCancelledExtractionKeepsCheckpointAndContinues(t *testing.T) {
	a, dir := catalogFixture(t)
	ctx, cancel := context.WithCancel(context.Background())
	ctx = withProgress(ctx, func(e progressEvent) {
		if !e.detailOnly && e.Completed == 1 {
			cancel()
		}
	})
	inv, err := extractCatalog(ctx, a.cfg, a.inventory, nil, dir, nil)
	if !errors.Is(err, context.Canceled) || inv.Ready != 1 || inv.Pending != 2 {
		t.Fatal("cancel lost partial work", inv, err)
	}
	var saved Inventory
	if err := readJSON(filepath.Join(dir, "inventory.json"), &saved); err != nil || saved.Ready != 1 {
		t.Fatal("no partial checkpoint", saved, err)
	}
	id := ""
	for _, source := range saved.Sources {
		if source.Status == "ready" {
			id = source.ID
		}
	}
	first := filepath.Join(dir, "raw", id+".md")
	before, _ := os.Stat(first)
	time.Sleep(5 * time.Millisecond)
	inv, err = extractCatalog(context.Background(), a.cfg, saved, nil, dir, nil)
	after, _ := os.Stat(first)
	if err != nil || inv.Ready != 3 || inv.Pending != 0 || !before.ModTime().Equal(after.ModTime()) {
		t.Fatal("resume re-extracted completed file", inv, err)
	}
}

func TestInvalidExtractionSelectionDoesNotReadFiles(t *testing.T) {
	a, dir := catalogFixture(t)
	_, err := extractCatalog(context.Background(), a.cfg, a.inventory, []string{"unknown"}, dir, nil)
	files, _ := filepath.Glob(filepath.Join(dir, "raw", "*.md"))
	if err == nil || len(files) > 0 {
		t.Fatal("invalid selection extracted files", err)
	}
}
