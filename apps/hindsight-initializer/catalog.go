package main

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

func privateDocumentName(path string) bool {
	name := filepath.Base(path)
	if strings.HasPrefix(name, "~$") || excludedPart(name) {
		return true
	}
	for _, private := range []string{"账号", "密码", "密钥", "口令", "手机号", "身份证"} {
		if strings.Contains(name, private) {
			return true
		}
	}
	return false
}

func supportedDocument(path string) bool {
	if privateDocumentName(path) {
		return false
	}
	switch strings.ToLower(filepath.Ext(path)) {
	case ".md", ".txt", ".rst", ".csv", ".html", ".htm", ".docx", ".xlsx", ".pptx":
		return true
	case ".pdf":
		_, err := exec.LookPath("pdftotext")
		return err == nil
	default:
		return false
	}
}

func catalogDocuments(ctx context.Context, cfg Config, log func(string), progress func(Inventory, string)) (Inventory, error) {
	inventory := Inventory{Sources: []Source{}}
	seen := map[string]bool{}
	for _, root := range cfg.Roots {
		log("列出文档 " + root)
		err := walkDocuments(ctx, root, func(path string, info os.FileInfo) error {
			if info.IsDir() {
				if progress != nil {
					progress(inventory, path)
				}
				return nil
			}
			if seen[path] || !supportedDocument(path) {
				return nil
			}
			if len(inventory.Sources) >= 20000 {
				return errors.New("超过 20,000 篇清单上限，请缩小范围")
			}
			seen[path] = true
			source := Source{
				ID: hashText("document\x00" + path + "\x00"), Agent: "document", Path: path,
				Title:   redact(strings.TrimSuffix(filepath.Base(path), filepath.Ext(path))),
				Project: filepath.Dir(path), Modified: info.ModTime().UTC().Format(time.RFC3339),
				Size: info.Size(), Status: "pending",
			}
			if time.Since(info.ModTime()) < time.Duration(cfg.IdleHours)*time.Hour {
				source.Status, source.Reason = "active", "文档仍在近期修改"
			} else if info.Size() > int64(cfg.MaxFileMB)*1024*1024 {
				source.Status, source.Reason = "skipped", "超过单文件限制"
			}
			inventory.Sources = append(inventory.Sources, source)
			if progress != nil {
				progress(inventory, filepath.Dir(path))
			}
			return nil
		}, func(path string, err error) { log("跳过不可访问路径：" + path) })
		if err != nil {
			if ctx.Err() != nil {
				return mergeCatalog(Inventory{}, inventory), ctx.Err()
			}
			if len(inventory.Sources) >= 20000 {
				return mergeCatalog(Inventory{}, inventory), err
			}
			inventory.Sources = append(inventory.Sources, Source{
				ID: hashText("document\x00" + root + "\x00"), Agent: "document", Path: root,
				Title: redact(filepath.Base(root)), Project: root, Status: "error", Reason: err.Error(),
			})
		}
	}
	return mergeCatalog(Inventory{}, inventory), nil
}

func mergeCatalog(existing, listed Inventory) Inventory {
	result := Inventory{Sources: []Source{}}
	for _, source := range existing.Sources {
		if source.Status != "unsupported" {
			result.Sources = append(result.Sources, source)
		}
	}
	positions := map[string]int{}
	for i, source := range result.Sources {
		positions[source.ID] = i
	}
	for _, source := range listed.Sources {
		if i, ok := positions[source.ID]; ok {
			if result.Sources[i].SHA == "" {
				result.Sources[i] = source
			}
		} else {
			positions[source.ID] = len(result.Sources)
			result.Sources = append(result.Sources, source)
		}
	}
	for _, source := range result.Sources {
		switch source.Status {
		case "ready":
			result.Ready++
			result.Chars += source.Chars
		case "pending":
			result.Pending++
		default:
			result.Skipped++
		}
	}
	return result
}
