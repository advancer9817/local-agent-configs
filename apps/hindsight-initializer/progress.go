package main

import (
	"context"
	"time"
)

type TaskProgress struct {
	Stage      string    `json:"stage"`
	Detail     string    `json:"detail,omitempty"`
	Waiting    string    `json:"waiting,omitempty"`
	Current    string    `json:"current,omitempty"`
	Completed  int       `json:"completed"`
	Total      int       `json:"total"`
	Unit       string    `json:"unit"`
	PhaseStart time.Time `json:"phase_started_at"`
	UpdatedAt  time.Time `json:"updated_at"`
}

type progressEvent struct {
	TaskProgress
	detailOnly bool
	waitOnly   bool
}
type progressContextKey struct{}
type inventoryContextKey struct{}

func reportInventory(ctx context.Context, inv Inventory) error {
	if fn, ok := ctx.Value(inventoryContextKey{}).(func(Inventory) error); ok {
		return fn(inv)
	}
	return nil
}

func withProgress(ctx context.Context, fn func(progressEvent)) context.Context {
	return context.WithValue(ctx, progressContextKey{}, fn)
}

func reportProgress(ctx context.Context, stage string, done, total int, current, unit string) {
	if fn, ok := ctx.Value(progressContextKey{}).(func(progressEvent)); ok {
		fn(progressEvent{TaskProgress: TaskProgress{Stage: stage, Completed: done, Total: total, Current: current, Unit: unit}})
	}
}

func reportDetail(ctx context.Context, detail, current string) {
	if fn, ok := ctx.Value(progressContextKey{}).(func(progressEvent)); ok {
		fn(progressEvent{TaskProgress: TaskProgress{Detail: detail, Current: current}, detailOnly: true})
	}
}

func reportWaiting(ctx context.Context, message string) {
	if fn, ok := ctx.Value(progressContextKey{}).(func(progressEvent)); ok {
		fn(progressEvent{TaskProgress: TaskProgress{Waiting: message}, waitOnly: true})
	}
}

func (a *App) updateProgress(event progressEvent) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.job.Status != "running" {
		return
	}
	p := &a.job.Progress
	if event.waitOnly {
		p.Waiting = event.Waiting
	} else if event.detailOnly {
		p.Detail = redact(event.Detail)
		if event.Current != "" {
			p.Current = redact(event.Current)
		}
	} else {
		if event.Stage != p.Stage || event.Total != p.Total {
			p.PhaseStart = time.Now().UTC()
		}
		p.Stage, p.Completed, p.Total = event.Stage, event.Completed, event.Total
		p.Current, p.Unit, p.Detail = redact(event.Current), event.Unit, ""
	}
	p.UpdatedAt = time.Now().UTC()
}

func taskLabel(kind string) string {
	if label := map[string]string{"scan": "提取本地正文", "discover": "智能扫描", "catalog": "刷新文档清单", "compact": "压缩与独立核验", "upload": "上传与回读验证", "test": "连接测试", "install": "配置智能体接入", "restore": "恢复接入配置"}[kind]; label != "" {
		return label
	}
	return "处理任务"
}

func optionalContext(contexts []context.Context) context.Context {
	if len(contexts) > 0 {
		return contexts[0]
	}
	return context.Background()
}
