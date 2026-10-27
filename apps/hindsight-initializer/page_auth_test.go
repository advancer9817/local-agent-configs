package main

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestOpenPageRemainsAuthorizedAfterRestart(t *testing.T) {
	root := t.TempDir()
	first, err := newApp(root)
	if err != nil {
		t.Fatal(err)
	}
	restarted, err := newApp(root)
	if err != nil {
		t.Fatal(err)
	}
	restarted.host = "127.0.0.1:19081"
	for _, test := range []struct {
		token string
		code  int
	}{{first.token, 200}, {"", 403}, {randomToken(), 403}} {
		r := httptest.NewRequest("GET", "http://"+restarted.host+"/api/state", nil)
		r.Header.Set("X-Setup-Token", test.token)
		w := httptest.NewRecorder()
		restarted.handler().ServeHTTP(w, r)
		if w.Code != test.code {
			t.Fatalf("HTTP %d, want %d", w.Code, test.code)
		}
	}
	info, err := os.Stat(filepath.Join(root, "page-token"))
	if err != nil {
		t.Fatal(err)
	}
	if runtime.GOOS != "windows" && info.Mode().Perm() != 0600 {
		t.Fatal("page credential must remain private", err)
	}
	other, err := newApp(t.TempDir())
	if err != nil || other.token == first.token {
		t.Fatal("different installations must have different credentials", err)
	}
}

func TestInvalidPageCredentialFailsClosed(t *testing.T) {
	root := t.TempDir()
	for _, value := range []string{"", "not-a-token", string(make([]byte, 64))} {
		mustFile(t, filepath.Join(root, "page-token"), value)
		if _, err := newApp(root); err == nil {
			t.Fatal("invalid saved credential was accepted")
		}
	}
}
