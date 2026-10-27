package main

import (
	"encoding/hex"
	"errors"
	"os"
	"path/filepath"
)

// Keep an open browser's authorization valid when this installation restarts.
// The credential stays in the private state directory, outside public config.
func loadPageToken(root string) (string, error) {
	path := filepath.Join(root, "page-token")
	b, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		token := randomToken()
		if err := atomicWrite(path, []byte(token), 0600); err != nil {
			return "", err
		}
		return token, nil
	}
	if err != nil {
		return "", err
	}
	if _, err := hex.DecodeString(string(b)); err != nil || len(b) != 64 {
		return "", errors.New("invalid local page credential")
	}
	if err := os.Chmod(path, 0600); err != nil {
		return "", err
	}
	return string(b), nil
}
