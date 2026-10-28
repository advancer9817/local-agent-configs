package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

func newHTTPClient(timeout time.Duration) *http.Client {
	return &http.Client{
		Timeout: timeout,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return errors.New("拒绝自动重定向，请使用服务的最终 HTTPS 地址")
		},
	}
}

func requestJSON(ctx context.Context, method, address, token string, payload, result any) error {
	var body io.Reader
	if payload != nil {
		b, err := json.Marshal(payload)
		if err != nil {
			return err
		}
		body = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, address, body)
	if err != nil {
		return errors.New("无效请求地址")
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	resp, err := newHTTPClient(180 * time.Second).Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		return errors.New("请求未完成（网络、证书或超时），请检查连接；未记录响应正文")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("服务返回 HTTP %d", resp.StatusCode)
	}
	b, err := io.ReadAll(io.LimitReader(resp.Body, 8*1024*1024+1))
	if err != nil {
		return err
	}
	if len(b) > 8*1024*1024 {
		return errors.New("响应超过 8 MB")
	}
	if result == nil {
		return nil
	}
	if err = json.Unmarshal(b, result); err != nil {
		return errors.New("服务返回的不是有效 JSON")
	}
	return nil
}

func bankURL(c Config, path string) string {
	return strings.TrimRight(c.API, "/") + "/v1/default/banks/" + url.PathEscape(c.Bank) + path
}

func ingestURL(c Config, path string) string {
	return strings.TrimRight(c.API, "/") + "/ext/ingest/banks/" + url.PathEscape(c.Bank) + path
}

func checkRemote(ctx context.Context, c Config) (map[string]any, error) {
	if err := c.validate(true, false); err != nil {
		return nil, err
	}
	var result map[string]any
	if err := requestJSON(ctx, "GET", bankURL(c, "/stats"), c.Token, nil, &result); err != nil {
		return nil, err
	}
	// The API's stats endpoint can be public; verify the token against MCP too.
	reqBody := `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"hindsight-initializer","version":"1.0.0"}}}`
	req, err := http.NewRequestWithContext(ctx, "POST", strings.TrimRight(c.API, "/")+"/mcp/"+url.PathEscape(c.Bank)+"/", strings.NewReader(reqBody))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+c.Token)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json, text/event-stream")
	resp, err := newHTTPClient(20 * time.Second).Do(req)
	if err != nil {
		return nil, errors.New("MCP 连接未完成，请检查地址与证书")
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("MCP 认证测试返回 HTTP %d", resp.StatusCode)
	}
	var envelope map[string]json.RawMessage
	if strings.Contains(resp.Header.Get("Content-Type"), "text/event-stream") {
		scanner := bufio.NewScanner(io.LimitReader(resp.Body, 1024*1024))
		scanner.Buffer(make([]byte, 65536), 1024*1024)
		for scanner.Scan() {
			line := scanner.Text()
			if strings.HasPrefix(line, "data:") && json.Unmarshal([]byte(strings.TrimSpace(strings.TrimPrefix(line, "data:"))), &envelope) == nil && envelope["id"] != nil {
				break
			}
		}
	} else {
		_ = json.NewDecoder(io.LimitReader(resp.Body, 1024*1024)).Decode(&envelope)
	}
	if envelope["result"] == nil || envelope["error"] != nil {
		return nil, errors.New("MCP 握手未确认成功，认证未通过")
	}
	return result, nil
}
