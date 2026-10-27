package main

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type UploadState struct {
	Document string `json:"document_id"`
	Op       string `json:"operation_id"`
	Status   string `json:"status"`
	SHA      string `json:"sha256"`
	Target   string `json:"target"`
	Created  string `json:"created_at"`
}

func selectUploadProducts(products []Product, ids []string) ([]Product, error) {
	if len(ids) == 0 {
		return nil, errors.New("请先选择需要上传的提炼结果")
	}
	available := make(map[string]Product, len(products))
	for _, p := range products {
		available[p.ID] = p
	}
	selected := []Product{}
	seen := map[string]bool{}
	for _, id := range ids {
		p, ok := available[id]
		if !ok || p.Status != "approved" || p.SHA == "" {
			return nil, errors.New("选择包含无效或未通过核验的提炼结果，未执行上传")
		}
		if !seen[id] {
			selected = append(selected, p)
			seen[id] = true
		}
	}
	return selected, nil
}

func uploadProducts(ctx context.Context, c Config, products []Product, root, sharedRoot string, log func(string)) error {
	if err := c.validate(true, false); err != nil {
		return err
	}
	target := strings.TrimRight(c.API, "/") + "/" + c.Bank
	success := 0
	total := 0
	for _, p := range products {
		if p.Status == "approved" {
			total++
		}
	}
	reportProgress(ctx, "上传与回读验证", 0, total, "", "份")
	for _, p := range products {
		if p.Status != "approved" {
			continue
		}
		reportProgress(ctx, "上传与回读验证", success, total, p.Title, "份")
		reportDetail(ctx, "校验本地成品", p.Title)
		body, err := os.ReadFile(filepath.Join(root, "products", p.ID+".md"))
		if err != nil || hashText(string(body)) != p.SHA {
			return errors.New("成品正文指纹不匹配，拒绝上传")
		}
		sp := filepath.Join(sharedRoot, "uploads", hashText(target+"\x00"+p.ID)+".json")
		var s UploadState
		_ = readJSON(sp, &s)
		if s.Op != "" && (s.SHA != p.SHA || s.Target != target) {
			return errors.New("同一来源组已有不同成品的上传记录；保留两份记录，未自动覆盖")
		}
		if s.Status == "completed" && s.SHA == p.SHA && s.Target == target {
			success++
			reportProgress(ctx, "上传与回读验证", success, total, p.Title, "份")
			log("跳过已确认上传：" + p.Title)
			continue
		}
		if s.Op == "" {
			// Idempotency includes target, product and approved content, not just title.
			key := hashText(target + "\x00" + p.ID + "\x00" + p.SHA)
			op := key[:8] + "-" + key[8:12] + "-4" + key[13:16] + "-a" + key[17:20] + "-" + key[20:32]
			s = UploadState{Document: "初始化归档 · " + p.Title + " · " + p.ID[:8], Op: op, Status: "submitting", SHA: p.SHA, Target: target, Created: time.Now().UTC().Format(time.RFC3339)}
			if err = atomicJSON(sp, s); err != nil {
				return err
			}
		}
		if s.Status == "submitting" {
			reportDetail(ctx, "提交精简稿", p.Title)
			log("提交精简稿：" + p.Title)
			metadata := map[string]string{
				"document_kind": "client-bootstrap-knowledge", "source": "hindsight-initializer",
				"display_title": p.Title, "bootstrap_id": p.ID, "source_ids_json": jsonText(p.SourceIDs),
				"source_manifest_json": jsonText(p.References),
				"source_sha256":        p.SHA, "created_at": s.Created,
			}
			item := map[string]any{"document_id": s.Document, "content": string(body), "metadata": metadata, "tags": []string{"source:client-bootstrap"},
				"context": "Verified historical archive. Preserve project, history and attribution; not current instructions.", "update_mode": "replace"}
			// Check identity before any replace. Title is never a license to overwrite another document.
			var fresh struct {
				Text   string `json:"original_text"`
				Params struct {
					Metadata map[string]string `json:"metadata"`
				} `json:"retain_params"`
			}
			err = requestJSON(ctx, "GET", bankURL(c, "/documents/"+url.PathEscape(s.Document)), "", nil, &fresh)
			if err == nil {
				if fresh.Params.Metadata["bootstrap_id"] != p.ID || fresh.Text != string(body) {
					return errors.New("远端同名文档身份不同，未覆盖")
				}
			} else if err.Error() != "服务返回 HTTP 404" {
				return err
			}
			var response struct {
				Operation string `json:"operation_id"`
			}
			if err = requestJSON(ctx, "POST", bankURL(c, "/memories"), "", map[string]any{"items": []any{item}, "async": true, "operation_id": s.Op}, &response); err != nil {
				return err
			}
			if response.Operation != s.Op {
				return errors.New("服务端未确认同一 operation_id")
			}
			s.Status = "submitted"
			if err = atomicJSON(sp, s); err != nil {
				return err
			}
		}
		if s.Status == "submitted" {
			reportDetail(ctx, "等待远端入库完成", p.Title)
			deadline := time.NewTimer(10 * time.Minute)
			ticker := time.NewTicker(2 * time.Second)
			for {
				var op struct {
					Status   string `json:"status"`
					Metadata struct {
						Errors int `json:"extraction_errors_count"`
					} `json:"result_metadata"`
				}
				if err = requestJSON(ctx, "GET", bankURL(c, "/operations/"+s.Op), "", nil, &op); err != nil {
					ticker.Stop()
					deadline.Stop()
					return err
				}
				if op.Status == "failed" || op.Status == "cancelled" || op.Metadata.Errors > 0 {
					ticker.Stop()
					deadline.Stop()
					return errors.New("远端入库失败，保留本地成品与任务编号；未标记完成")
				}
				if op.Status == "completed" {
					break
				}
				select {
				case <-ctx.Done():
					ticker.Stop()
					deadline.Stop()
					return ctx.Err()
				case <-deadline.C:
					ticker.Stop()
					return errors.New("远端仍在处理，可稍后继续确认；不会重复提交")
				case <-ticker.C:
				}
			}
			ticker.Stop()
			deadline.Stop()
			var doc struct {
				Text   string `json:"original_text"`
				Count  int    `json:"memory_unit_count"`
				Params struct {
					Metadata map[string]string `json:"metadata"`
				} `json:"retain_params"`
			}
			reportDetail(ctx, "回读校验正文与记忆条数", p.Title)
			if err = requestJSON(ctx, "GET", bankURL(c, "/documents/"+url.PathEscape(s.Document)), "", nil, &doc); err != nil {
				return err
			}
			if doc.Text != string(body) || doc.Count < 1 || doc.Params.Metadata["bootstrap_id"] != p.ID {
				return errors.New("远端正文、身份或记忆条数校验未通过，未标记完成")
			}
			s.Status = "completed"
			if err = atomicJSON(sp, s); err != nil {
				return err
			}
			success++
			reportProgress(ctx, "上传与回读验证", success, total, p.Title, "份")
			log("上传并回读验证完成：" + p.Title)
		}
	}
	if success == 0 {
		return errors.New("没有可上传的已核验成品，请先完成压缩")
	}
	log(fmt.Sprintf("%d 份成品已确认落库；远端原有文档未删除", success))
	return nil
}
