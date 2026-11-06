package main

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
	"unicode/utf8"
)

type Product struct {
	ID         string            `json:"id"`
	Title      string            `json:"title"`
	Chars      int               `json:"chars"`
	Input      int               `json:"input_chars"`
	SourceIDs  []string          `json:"source_ids"`
	SHA        string            `json:"sha256"`
	Status     string            `json:"status"`
	Reason     string            `json:"reason,omitempty"`
	Content    string            `json:"-"`
	References map[string]Source `json:"source_map"`
	JobID      string            `json:"job_id"`
	Target     string            `json:"target"`
}

type RemoteJob struct {
	ID       string `json:"job_id"`
	Status   string `json:"status"`
	Stage    string `json:"stage"`
	Text     string `json:"refined_text"`
	Parsed   string `json:"parsed_text"`
	Document string `json:"document_id"`
	Error    string `json:"error"`
}

type SessionUpload struct {
	Accepted []RemoteJob `json:"accepted"`
	Failed   []RemoteJob `json:"failed"`
}

func jsonText(v any) string { b, _ := json.Marshal(v); return string(b) }

func waitIngest(ctx context.Context, c Config, id string, prepared bool) (RemoteJob, error) {
	timer := time.NewTimer(20 * time.Minute)
	defer timer.Stop()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		var job RemoteJob
		if err := requestJSON(ctx, "GET", ingestURL(c, "/jobs/"+id+"?preview=true"), c.Token, nil, &job); err != nil {
			return job, err
		}
		if job.ID != id {
			return job, errors.New("远端任务身份不匹配")
		}
		if job.Status == "failed" || job.Status == "degraded" || job.Status == "cancelled" || job.Status == "skipped" {
			return job, errors.New("服务端处理未完成：" + job.Stage + " " + job.Error)
		}
		if job.Status == "completed" || (prepared && job.Status == "prepared") {
			return job, nil
		}
		select {
		case <-ctx.Done():
			return job, ctx.Err()
		case <-timer.C:
			return job, errors.New("服务端仍在处理，任务编号已保留，可稍后继续")
		case <-ticker.C:
		}
	}
}

func clientSourceID(sharedRoot string) (string, error) {
	path := filepath.Join(sharedRoot, "source-id.json")
	var saved struct {
		ID string `json:"source_id"`
	}
	if readJSON(path, &saved) != nil || saved.ID == "" {
		saved.ID = randomToken()
		if err := atomicJSON(path, saved); err != nil {
			return "", err
		}
	}
	return saved.ID, nil
}

func sessionProduct(ctx context.Context, c Config, sourceID string, s Source, root, sharedRoot string,
	log func(string)) (Product, error) {
	body, err := os.ReadFile(filepath.Join(root, "raw", s.ID+".md"))
	if err != nil || hashText(string(body)) != s.SHA {
		return Product{}, errors.New("本地暂存来源指纹不匹配，请重新扫描")
	}
	p := Product{
		ID: hashText(s.ID + ":" + s.SHA), Status: "review_required", Target: strings.TrimRight(c.API, "/") + "/" + c.Bank,
		References: map[string]Source{"S1": s}, SourceIDs: append([]string{s.ID}, s.Aliases...), Input: s.Chars,
	}
	receipt := filepath.Join(sharedRoot, "remote-jobs", hashText(p.Target+"\x00"+p.ID)+".json")
	var job RemoteJob
	_ = readJSON(receipt, &job)
	if job.ID == "" {
		sessionID := s.SessionID
		if sessionID == "" {
			sessionID = s.ID
		}
		manifest, _ := json.Marshal(map[string]any{
			"source_id": sourceID, "session_id": sessionID, "agent": s.Agent, "title": s.Title,
			"project": s.Project, "modified": s.Modified, "auto_commit": false,
		})
		var uploaded SessionUpload
		log("上传历史会话至服务端准备区：" + s.Title)
		err = requestMultipart(ctx, ingestURL(c, "/sessions"), c.Token,
			map[string]string{"manifest": string(manifest)}, "session", s.ID+".txt", body, &uploaded)
		if err != nil {
			return p, err
		}
		if len(uploaded.Accepted) != 1 || uploaded.Accepted[0].ID == "" {
			return p, errors.New("服务端未确认历史会话任务")
		}
		job = uploaded.Accepted[0]
		if err = atomicJSON(receipt, job); err != nil {
			return p, err
		}
	}
	p.JobID = job.ID
	job, err = waitIngest(ctx, c, job.ID, true)
	if err != nil {
		p.Reason = err.Error()
		return p, nil
	}
	p.Content = job.Text
	p.Title = s.Title
	p.SHA, p.Chars, p.Status = hashText(job.Text), utf8.RuneCountInString(job.Text), "approved"
	if err = atomicWrite(filepath.Join(root, "products", p.ID+".md"), []byte(job.Text), 0600); err != nil {
		return p, err
	}
	return p, nil
}

func compactInventory(ctx context.Context, c Config, inv Inventory, root, sharedRoot string, log func(string)) ([]Product, error) {
	if err := c.validate(true, false); err != nil {
		return nil, err
	}
	sourceID, err := clientSourceID(sharedRoot)
	if err != nil {
		return nil, err
	}
	groups := map[string][]Source{}
	sessions := []Source{}
	for _, s := range inv.Sources {
		if s.Status == "ready" {
			if s.SessionID != "" || (s.Agent != "document" && strings.ToLower(filepath.Ext(s.Path)) != ".md") {
				sessions = append(sessions, s)
			} else {
				groups[s.Project] = append(groups[s.Project], s)
			}
		}
	}
	sort.Slice(sessions, func(i, j int) bool { return sessions[i].ID < sessions[j].ID })
	keys := make([]string, 0, len(groups))
	for key := range groups {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	products := []Product{}
	target := strings.TrimRight(c.API, "/") + "/" + c.Bank
	if len(sessions) > 0 {
		var capabilities struct {
			SessionPreview bool `json:"session_preview"`
		}
		if err = requestJSON(ctx, "GET", ingestURL(c, "/capabilities"), c.Token, nil, &capabilities); err != nil {
			return products, err
		}
		if !capabilities.SessionPreview {
			return products, errors.New("服务端不支持历史会话预览确认，请先升级服务端；未上传会话")
		}
	}
	for _, source := range sessions {
		p, err := sessionProduct(ctx, c, sourceID, source, root, sharedRoot, log)
		if err != nil {
			return products, err
		}
		products = append(products, p)
		if err = atomicJSON(filepath.Join(root, "products.json"), products); err != nil {
			return products, err
		}
		if ctx.Err() != nil {
			return products, ctx.Err()
		}
	}
	for _, key := range keys {
		entries := groups[key]
		sort.Slice(entries, func(i, j int) bool { return entries[i].ID < entries[j].ID })
		for start := 0; start < len(entries); {
			batch, inputs, size := []map[string]any{}, []Source{}, 0
			signature := ""
			for start < len(entries) && len(batch) < 20 {
				s := entries[start]
				body, err := os.ReadFile(filepath.Join(root, "raw", s.ID+".md"))
				if err != nil || hashText(string(body)) != s.SHA {
					return products, errors.New("本地暂存来源指纹不匹配，请重新扫描")
				}
				if len(batch) > 0 && size+len(body) > 120000 {
					break
				}
				filename := filepath.Base(s.Path)
				if s.Agent != "document" {
					filename = s.ID + ".md"
				}
				batch = append(batch, map[string]any{"id": s.ID, "filename": filename, "data": base64.StdEncoding.EncodeToString(body),
					"title": s.Title, "project": s.Project, "agent": s.Agent, "modified": s.Modified,
					"sha256": s.SHA, "session_id": s.SessionID, "aliases": s.Aliases})
				inputs = append(inputs, s)
				signature += s.ID + ":" + s.SHA + "\n"
				size += len(body)
				start++
			}
			p := Product{ID: hashText(signature), Status: "review_required", Target: target, References: map[string]Source{}}
			for i, source := range inputs {
				p.SourceIDs = append(p.SourceIDs, source.ID)
				p.SourceIDs = append(p.SourceIDs, source.Aliases...)
				p.Input += source.Chars
				p.References[fmt.Sprintf("S%d", i+1)] = source
			}
			receipt := filepath.Join(sharedRoot, "remote-jobs", hashText(target+"\x00"+p.ID)+".json")
			var job RemoteJob
			_ = readJSON(receipt, &job)
			if job.ID == "" {
				log(fmt.Sprintf("上传 %d 个来源至服务端准备区", len(batch)))
				err = requestJSON(ctx, "POST", ingestURL(c, "/archives"), c.Token,
					map[string]any{"source_id": sourceID, "batch_id": p.ID, "sources": batch}, &job)
				if err != nil {
					return products, err
				}
				if job.ID == "" {
					return products, errors.New("服务端未确认任务编号")
				}
				if err = atomicJSON(receipt, job); err != nil {
					return products, err
				}
			}
			p.JobID = job.ID
			job, err = waitIngest(ctx, c, job.ID, true)
			if err == nil {
				p.Content = job.Text
				p.Title = strings.TrimSpace(strings.TrimPrefix(strings.SplitN(job.Text, "\n", 2)[0], "#"))
				p.SHA, p.Chars, p.Status = hashText(job.Text), utf8.RuneCountInString(job.Text), "approved"
				if err = atomicWrite(filepath.Join(root, "products", p.ID+".md"), []byte(job.Text), 0600); err != nil {
					return products, err
				}
			} else {
				p.Reason = err.Error()
			}
			products = append(products, p)
			if err = atomicJSON(filepath.Join(root, "products.json"), products); err != nil {
				return products, err
			}
			if ctx.Err() != nil {
				return products, ctx.Err()
			}
		}
	}
	return products, nil
}
