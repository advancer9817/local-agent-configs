package main

import (
	"context"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
)

type DocumentVolume struct {
	Path string `json:"path"`
	Name string `json:"name"`
}

var documentSystemDirs = map[string]bool{
	"windows": true, "program files": true, "program files (x86)": true,
	"programdata": true, "appdata": true, "$recycle.bin": true,
	"system volume information": true, "recovery": true,
	"proc": true, "sys": true, "dev": true, "run": true, "boot": true,
	"usr": true, "bin": true, "sbin": true, "lib": true, "lib64": true,
	"etc": true, "snap": true, "lost+found": true,
	"opt": true, "var": true, "tmp": true,
	".next": true, "target": true, "packages": true, "bower_components": true,
	"backups": true,
}

func documentRoot(raw string) (string, error) {
	root := expandPath(strings.TrimSpace(raw))
	if !filepath.IsAbs(root) || strings.HasPrefix(root, `\\`) || strings.HasPrefix(root, "//") {
		return "", errors.New("请选择本机目录的绝对路径")
	}
	resolved, err := filepath.EvalSymlinks(root)
	if err != nil {
		return "", errors.New("所选文档目录不可访问")
	}
	for _, part := range strings.Split(filepath.ToSlash(resolved), "/") {
		if excludedPart(part) {
			return "", errors.New("所选目录属于系统、缓存或敏感范围")
		}
	}
	if documentSystemDirs[strings.ToLower(filepath.Base(resolved))] {
		return "", errors.New("所选目录属于系统或缓存范围")
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.IsDir() {
		return "", errors.New("请选择可访问的文档目录")
	}
	return resolved, nil
}

func combineDocumentRoots(existing, added []string) []string {
	result := []string{}
	for _, candidate := range append(append([]string{}, existing...), added...) {
		candidate = filepath.Clean(candidate)
		covered := false
		for _, root := range result {
			if sameDocumentRoot(root, candidate) {
				covered = true
				break
			}
		}
		if covered {
			continue
		}
		next := []string{}
		for _, root := range result {
			if !sameDocumentRoot(candidate, root) {
				next = append(next, root)
			}
		}
		result = append(next, candidate)
	}
	return result
}

func sameDocumentRoot(parent, child string) bool {
	if parent == child {
		return true
	}
	// The Unix root walker does not cross mounted volumes.
	if parent == string(filepath.Separator) {
		for _, mount := range []string{"/mnt", "/media", "/Volumes"} {
			if child == mount || strings.HasPrefix(child, mount+"/") {
				return false
			}
		}
	}
	relative, err := filepath.Rel(parent, child)
	return err == nil && relative != ".." && !strings.HasPrefix(relative, ".."+string(filepath.Separator))
}

func walkDocuments(ctx context.Context, raw string, visit func(string, os.FileInfo) error, warning func(string, error)) error {
	root, err := documentRoot(raw)
	if err != nil {
		return err
	}
	return filepath.WalkDir(root, func(path string, entry fs.DirEntry, entryErr error) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		if entryErr != nil {
			// One inaccessible or disappearing file must not abort a whole volume.
			if path == root {
				return entryErr
			}
			if warning != nil {
				warning(path, entryErr)
			}
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return nil
		}
		if entry.IsDir() {
			if path != root {
				name := strings.ToLower(entry.Name())
				if excludedPart(entry.Name()) || strings.HasPrefix(name, ".") || documentSystemDirs[name] {
					return filepath.SkipDir
				}
				if root == string(filepath.Separator) && (path == "/mnt" || path == "/media" || path == "/Volumes") {
					return filepath.SkipDir
				}
			}
			reportDetail(ctx, "遍历目录", path)
			info, err := entry.Info()
			if err != nil {
				if warning != nil {
					warning(path, err)
				}
				return nil
			}
			return visit(path, info)
		}
		if excludedPart(entry.Name()) || !supportedDocument(path) {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			if warning != nil {
				warning(path, err)
			}
			return nil
		}
		if !info.Mode().IsRegular() {
			return nil
		}
		return visit(path, info)
	})
}
