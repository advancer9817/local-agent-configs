//go:build !windows

package main

import (
	"os"
	"path/filepath"
	"strings"
)

func documentVolumes() []DocumentVolume {
	volumes := []DocumentVolume{{Path: "/", Name: "本机文件系统"}}
	for _, parent := range []string{"/mnt", "/media", "/Volumes"} {
		entries, _ := os.ReadDir(parent)
		for _, entry := range entries {
			if !entry.IsDir() || entry.Type()&os.ModeSymlink != 0 {
				continue
			}
			if parent == "/mnt" && (entry.Name() == "wsl" || entry.Name() == "wslg") {
				continue
			}
			name := entry.Name()
			if parent == "/mnt" && len(name) == 1 && name[0] >= 'a' && name[0] <= 'z' {
				name = strings.ToUpper(name) + ":"
			}
			volumes = append(volumes, DocumentVolume{Path: filepath.Join(parent, entry.Name()), Name: name})
		}
	}
	return volumes
}
