package main

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"
)

// Extract an existing document catalog without walking the disks again. Each
// finished file is checkpointed before starting the next one.
func extractCatalog(ctx context.Context, cfg Config, inv Inventory, ids []string, root string, publish func(Inventory)) (result Inventory, err error) {
	result = cloneInventory(inv)
	selected := map[string]bool{}
	for _, id := range ids {
		selected[id] = true
	}
	var targets []int
	for i, source := range result.Sources {
		if len(ids) > 0 && !selected[source.ID] {
			continue
		}
		if source.Status == "ready" {
			delete(selected, source.ID)
			continue
		}
		if source.Agent == "document" && source.Status == "pending" {
			targets = append(targets, i)
			delete(selected, source.ID)
		}
	}
	if len(selected) > 0 {
		return result, errors.New("选择包含不可提取的来源，请刷新清单")
	}
	seen := map[string]int{}
	totalBytes := int64(0)
	for i, source := range result.Sources {
		if source.Status == "ready" && source.SHA != "" {
			seen[source.Project+"\x00"+source.SHA] = i
			if info, e := os.Stat(filepath.Join(root, "raw", source.ID+".md")); e == nil {
				totalBytes += info.Size()
			}
		}
	}
	lastSaved := time.Time{}
	checkpoint := func(force bool) error {
		if !force && time.Since(lastSaved) < 500*time.Millisecond {
			return nil
		}
		result.Ready, result.Pending, result.Chars, result.Skipped = 0, 0, 0, 0
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
		if e := atomicJSON(filepath.Join(root, "inventory.json"), result); e != nil {
			return e
		}
		if publish != nil {
			publish(cloneInventory(result))
		}
		lastSaved = time.Now()
		return nil
	}
	defer func() {
		if e := checkpoint(true); e != nil && err == nil {
			err = e
		}
	}()
	reportProgress(ctx, "提取正文", 0, len(targets), "", "篇")
	for done, index := range targets {
		if err = ctx.Err(); err != nil {
			return result, err
		}
		source := result.Sources[index]
		reportProgress(ctx, "提取正文", done, len(targets), source.Path, "篇")
		reportDetail(ctx, "读取、脱敏与去重", source.Path)
		info, readErr := os.Lstat(source.Path)
		if readErr == nil && (!info.Mode().IsRegular() || !supportedDocument(source.Path)) {
			readErr = errors.New("文件类型不支持或文件已变为符号链接")
		}
		if readErr == nil {
			var resolved string
			resolved, readErr = documentRoot(filepath.Dir(source.Path))
			if readErr == nil && filepath.Clean(resolved) != filepath.Clean(filepath.Dir(source.Path)) {
				readErr = errors.New("文件目录已变为符号链接，请重新扫描")
			}
		}
		if readErr == nil && time.Since(info.ModTime()) < time.Duration(cfg.IdleHours)*time.Hour {
			source.Status, source.Reason = "active", "文档仍在近期修改"
		} else if readErr == nil && info.Size() > int64(cfg.MaxFileMB)*1024*1024 {
			source.Status, source.Reason = "skipped", "超过单文件限制"
		} else if readErr == nil {
			var text string
			text, readErr = readDocument(ctx, source.Path, int64(cfg.MaxFileMB)*1024*1024)
			if ctx.Err() != nil {
				return result, ctx.Err()
			}
			if readErr == nil {
				text = strings.TrimSpace(redact(text))
				if text == "" {
					source.Status, source.Reason = "skipped", "无正文"
				} else {
					source.SHA, source.Chars = hashText(text), utf8.RuneCountInString(text)
					key := source.Project + "\x00" + source.SHA
					if first, ok := seen[key]; ok {
						source.Status, source.Reason = "duplicate", result.Sources[first].ID
						result.Sources[first].Aliases = append(result.Sources[first].Aliases, source.ID)
					} else {
						if totalBytes+int64(len(text)) > 256*1024*1024 {
							return result, errors.New("正文总量超过 256 MB，请分批提取")
						}
						totalBytes += int64(len(text))
						source.Status, source.Reason = "ready", ""
						seen[key] = index
					}
					if readErr = atomicWrite(filepath.Join(root, "raw", source.ID+".md"), []byte(text), 0600); readErr != nil {
						return result, readErr
					}
				}
			}
		}
		if readErr != nil {
			source.Status, source.Reason = "error", readErr.Error()
		}
		result.Sources[index] = source
		if err = checkpoint(false); err != nil {
			return result, err
		}
		reportProgress(ctx, "提取正文", done+1, len(targets), source.Path, "篇")
	}
	return result, nil
}

func cloneInventory(inv Inventory) Inventory {
	inv.Sources = append([]Source(nil), inv.Sources...)
	for i := range inv.Sources {
		inv.Sources[i].Aliases = append([]string(nil), inv.Sources[i].Aliases...)
	}
	return inv
}
