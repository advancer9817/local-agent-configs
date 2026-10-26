package main

import (
	"strings"
	"testing"
)

func TestWindowsCredentialRoundTrip(t *testing.T) {
	const value = "fixture-only-token-not-a-real-credential"
	encrypted, err := protect(value)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(encrypted, "dpapi:") || strings.Contains(encrypted, value) {
		t.Fatal("credential was not protected")
	}
	plain, err := unprotect(encrypted)
	if err != nil || plain != value {
		t.Fatalf("DPAPI round trip failed: %v", err)
	}
}
