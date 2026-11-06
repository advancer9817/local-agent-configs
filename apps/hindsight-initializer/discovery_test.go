package main

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDiscoveryReadsMetadataNotDocumentOrSessionBodies(t *testing.T) {
	root := t.TempDir()
	paths := []string{
		filepath.Join(root, "work", "notes.md"),
		filepath.Join(root, ".codex", "sessions", "invalid.jsonl"),
		filepath.Join(root, "another-user", ".claude", "projects", "p", "invalid.jsonl"),
		filepath.Join(root, ".hermes", "profiles", "work", "state.db"),
	}
	for _, path := range paths {
		oldFile(t, path, "NOT VALID JSON OR DATABASE OR OFFICE")
	}
	oldFile(t, filepath.Join(root, "work", "page.docx"), "NOT AN OFFICE ZIP")
	oldFile(t, filepath.Join(root, ".codex", "AGENTS.md"), "private system instructions")
	oldFile(t, filepath.Join(root, ".ssh", "notes.md"), "secret")
	oldFile(t, filepath.Join(root, "node_modules", "notes.md"), "dependency")
	oldFile(t, filepath.Join(root, "cache", "notes.md"), "cached")
	oldFile(t, filepath.Join(root, "auth.txt"), "secret")
	oldFile(t, filepath.Join(root, "custom-agent", "sessions", "more.jsonl"), "invalid")
	cfg := defaultConfig()
	cfg.Agents["codex"] = AgentConfig{Enabled: true, Path: filepath.Join(root, "custom-agent")}
	inv, err := discoverSources(context.Background(), cfg, []string{root}, nil, func(string) {}, nil)
	if err != nil || len(inv.Sources) != 6 || inv.Ready != 0 {
		t.Fatalf("unexpected metadata catalog: %+v %v", inv, err)
	}
	counts := map[string]int{}
	for _, s := range inv.Sources {
		counts[s.Agent]++
		if s.Status != "discovered" || s.SHA != "" || s.Chars != 0 || s.Text != "" {
			t.Fatalf("discovery parsed source contents: %+v", s)
		}
	}
	if counts["codex"] != 2 || counts["claude"] != 1 || counts["hermes"] != 1 || counts["document"] != 2 {
		t.Fatalf("agent identity was lost: %v", counts)
	}
}

func TestDiscoveryHonorsDisabledAgentsAndExcludesOwnState(t *testing.T) {
	root := t.TempDir()
	oldFile(t, filepath.Join(root, ".codex", "sessions", "one.jsonl"), "data")
	oldFile(t, filepath.Join(root, "own-state", "raw", "source.md"), "must not find itself")
	oldFile(t, filepath.Join(root, "docs", "keep.md"), "keep")
	cfg := defaultConfig()
	cfg.Agents["codex"] = AgentConfig{}
	inv, err := discoverSources(context.Background(), cfg, []string{root, filepath.Join(root, "docs")},
		[]string{filepath.Join(root, "own-state")}, func(string) {}, nil)
	if err != nil || len(inv.Sources) != 1 || inv.Sources[0].Agent != "document" {
		t.Fatalf("scope or path deduplication failed: %+v %v", inv, err)
	}
}

func TestDiscoveryCancelReturnsPartialCatalog(t *testing.T) {
	root := t.TempDir()
	for i := range 10 {
		oldFile(t, filepath.Join(root, fmt.Sprintf("note-%02d.md", i)), "body")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	inv, err := discoverSources(ctx, defaultConfig(), []string{root}, nil, func(string) {},
		func(inv Inventory, _ DiscoveryProgress) {
			if len(inv.Sources) > 0 {
				cancel()
			}
		})
	if !errors.Is(err, context.Canceled) || len(inv.Sources) == 0 || len(inv.Sources) >= 10 {
		t.Fatalf("cancel did not preserve a partial result: %d %v", len(inv.Sources), err)
	}
}

func TestSelectedExtractionKeepsUnselectedSourcesUnread(t *testing.T) {
	root, stage := t.TempDir(), t.TempDir()
	oldFile(t, filepath.Join(root, "one.md"), "first result")
	oldFile(t, filepath.Join(root, "two.md"), "second result")
	cfg := defaultConfig()
	inv, err := discoverSources(context.Background(), cfg, []string{root}, nil, func(string) {}, nil)
	if err != nil {
		t.Fatal(err)
	}
	chosen := inv.Sources[0].ID
	result, err := extractDiscovered(context.Background(), cfg, inv, []string{chosen}, stage, func(string) {}, nil)
	if err != nil || result.Ready != 1 || len(result.Sources) != 2 {
		t.Fatalf("selection was not respected: %+v %v", result, err)
	}
	for _, s := range result.Sources {
		_, fileErr := os.Stat(filepath.Join(stage, "raw", s.ID+".md"))
		if s.ID == chosen && (s.Status != "ready" || fileErr != nil) {
			t.Fatalf("selected file not extracted: %+v %v", s, fileErr)
		}
		if s.ID != chosen && (s.Status != "discovered" || !errors.Is(fileErr, os.ErrNotExist)) {
			t.Fatalf("unselected file was read: %+v %v", s, fileErr)
		}
	}
}

func TestExtractionCancelCanResumeWithoutDuplicatingReadySources(t *testing.T) {
	root, stage := t.TempDir(), t.TempDir()
	for i := range 4 {
		oldFile(t, filepath.Join(root, fmt.Sprintf("%d.md", i)), fmt.Sprintf("unique body %d", i))
	}
	cfg := defaultConfig()
	inv, err := discoverSources(context.Background(), cfg, []string{root}, nil, func(string) {}, nil)
	if err != nil {
		t.Fatal(err)
	}
	ids := []string{}
	for _, s := range inv.Sources {
		ids = append(ids, s.ID)
	}
	ctx, cancel := context.WithCancel(context.Background())
	result, err := extractDiscovered(ctx, cfg, inv, ids, stage, func(string) {}, func(Inventory, DiscoveryProgress) { cancel() })
	if !errors.Is(err, context.Canceled) || result.Ready != 1 || len(result.Sources) != 4 {
		t.Fatalf("cancelled extraction lost sources: %+v %v", result, err)
	}
	var saved Inventory
	if err := readJSON(filepath.Join(stage, "inventory.json"), &saved); err != nil || saved.Ready != 1 {
		t.Fatalf("partial inventory not persisted: %+v %v", saved, err)
	}
	pending := []string{}
	for _, s := range saved.Sources {
		if s.Status == "discovered" {
			pending = append(pending, s.ID)
		}
	}
	done, err := extractDiscovered(context.Background(), cfg, saved, pending, stage, func(string) {}, nil)
	if err != nil || done.Ready != 4 || len(done.Sources) != 4 {
		t.Fatalf("resume duplicated or lost sources: %+v %v", done, err)
	}
}

func TestDiscoveryAndExtractionRejectSymlinkSubstitution(t *testing.T) {
	root, outside, stage := t.TempDir(), t.TempDir(), t.TempDir()
	original := filepath.Join(root, "folder", "note.md")
	oldFile(t, original, "allowed")
	oldFile(t, filepath.Join(outside, "note.md"), "must not be read")
	if err := os.Symlink(outside, filepath.Join(root, "linked")); err != nil {
		t.Skip(err)
	}
	cfg := defaultConfig()
	inv, err := discoverSources(context.Background(), cfg, []string{root}, nil, func(string) {}, nil)
	if err != nil || len(inv.Sources) != 1 {
		t.Fatalf("symlink was traversed: %+v %v", inv, err)
	}
	if err := os.Rename(filepath.Dir(original), filepath.Join(root, "moved")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, filepath.Dir(original)); err != nil {
		t.Fatal(err)
	}
	result, err := extractDiscovered(context.Background(), cfg, inv, []string{inv.Sources[0].ID}, stage, func(string) {}, nil)
	if err != nil || result.Ready != 0 || result.Sources[0].Status != "error" {
		t.Fatalf("changed source path was followed: %+v %v", result, err)
	}
}

func TestDiscoveredSessionUsesCanonicalParser(t *testing.T) {
	root, stage := t.TempDir(), t.TempDir()
	oldFile(t, filepath.Join(root, ".codex", "sessions", "one.jsonl"),
		"{\"type\":\"session_meta\",\"payload\":{\"id\":\"sid\",\"cwd\":\"/project\"}}\n"+
			"{\"type\":\"response_item\",\"payload\":{\"role\":\"user\",\"content\":\"request\"}}\n"+
			"{\"type\":\"response_item\",\"payload\":{\"role\":\"assistant\",\"content\":\"result\"}}")
	cfg := defaultConfig()
	inv, err := discoverSources(context.Background(), cfg, []string{root}, nil, func(string) {}, nil)
	if err != nil {
		t.Fatal(err)
	}
	result, err := extractDiscovered(context.Background(), cfg, inv, []string{inv.Sources[0].ID}, stage, func(string) {}, nil)
	if err != nil || result.Ready != 1 || result.Sources[0].SessionID != "sid" || result.Sources[0].Project != "/project" {
		t.Fatalf("session was flattened into a document: %+v %v", result, err)
	}
}

func TestDiscoveryHTTPRejectsInvalidModesAndEmptySelection(t *testing.T) {
	t.Setenv("HOME", t.TempDir())
	a, err := newApp(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.host = "127.0.0.1:45123"
	for route, body := range map[string]string{
		"/api/discover": `{"mode":"network"}`, "/api/extract": `{"ids":[]}`,
	} {
		r := httptest.NewRequest(http.MethodPost, "http://"+a.host+route, strings.NewReader(body))
		r.Host = a.host
		r.Header.Set("X-Setup-Token", a.token)
		w := httptest.NewRecorder()
		a.handler().ServeHTTP(w, r)
		if w.Code != 400 {
			t.Fatalf("invalid discovery request accepted: %s %d", route, w.Code)
		}
	}
}
