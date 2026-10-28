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
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/pelletier/go-toml/v2"
	"gopkg.in/yaml.v3"
)

type Backup struct {
	Path     string `json:"path"`
	Before   string `json:"before"`
	AfterSHA string `json:"after_sha256"`
	Existed  bool   `json:"existed"`
}

func childMap(m map[string]any, key string) map[string]any {
	x, ok := m[key].(map[string]any)
	if !ok {
		x = map[string]any{}
		m[key] = x
	}
	return x
}

func configureAgents(c Config, root string, log func(string)) error {
	if err := c.validate(true, false); err != nil {
		return err
	}
	for _, name := range []string{"codex", "claude", "hermes"} {
		a := c.Agents[name]
		if a.Enabled && strings.TrimSpace(a.Path) == "" {
			return errors.New("智能体目录不能为空")
		}
	}
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	stable := filepath.Join(root, "bin", "hindsight-client")
	if runtime.GOOS == "windows" {
		stable += ".exe"
	}
	if exe != stable {
		b, err := os.ReadFile(exe)
		if err != nil {
			return err
		}
		old, _ := os.ReadFile(stable)
		if !bytes.Equal(old, b) {
			if err = atomicWrite(stable, b, 0700); err != nil {
				return errors.New("无法安装接入程序，请先关闭正在运行的 MCP 会话")
			}
		}
	}
	dir := filepath.Join(root, "backups", time.Now().UTC().Format("20060102T150405.000000000"))
	backups := []Backup{}
	write := func(path string, b []byte) error {
		old, err := os.ReadFile(path)
		existed := err == nil
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		if bytes.Equal(old, b) {
			return nil
		}
		bak := filepath.Join(dir, fmt.Sprintf("%02d.backup", len(backups)))
		if existed {
			if err = atomicWrite(bak, old, 0600); err != nil {
				return err
			}
		}
		entry := Backup{Path: path, Before: bak, Existed: existed, AfterSHA: hashText(string(b))}
		backups = append(backups, entry)
		// Journal before mutation, so interruption is recoverable.
		if err = atomicJSON(filepath.Join(root, "last-install.json"), backups); err != nil {
			return err
		}
		return atomicWrite(path, b, 0600)
	}
	args := []string{"--data-dir", root, "--mcp"}
	for _, name := range []string{"codex", "claude", "hermes"} {
		a := c.Agents[name]
		if !a.Enabled {
			continue
		}
		base := expandPath(a.Path)
		if !filepath.IsAbs(base) {
			return errors.New("智能体配置目录必须为绝对路径")
		}
		m := map[string]any{}
		var path string
		var b []byte
		server := map[string]any{"command": stable, "args": args}
		switch name {
		case "codex":
			path = filepath.Join(base, "config.toml")
			b, err = os.ReadFile(path)
			if err != nil && !os.IsNotExist(err) {
				return err
			}
			if len(b) > 0 {
				if err = toml.Unmarshal(b, &m); err != nil {
					return errors.New("Codex TOML 无法解析；未覆盖")
				}
			}
			childMap(m, "mcp_servers")["hindsight"] = server
			b, err = toml.Marshal(m)
		case "claude":
			path = filepath.Join(base, ".claude.json")
			if filepath.Base(base) == ".claude" {
				path = filepath.Join(filepath.Dir(base), ".claude.json")
			}
			b, err = os.ReadFile(path)
			if err != nil && !os.IsNotExist(err) {
				return err
			}
			if len(b) > 0 {
				if err = json.Unmarshal(b, &m); err != nil {
					return errors.New("Claude JSON 无法解析；未覆盖")
				}
			}
			server["type"] = "stdio"
			childMap(m, "mcpServers")["hindsight"] = server
			b, err = json.MarshalIndent(m, "", "  ")
		case "hermes":
			path = filepath.Join(base, "config.yaml")
			b, err = os.ReadFile(path)
			if err != nil && !os.IsNotExist(err) {
				return err
			}
			if len(b) > 0 {
				if err = yaml.Unmarshal(b, &m); err != nil {
					return errors.New("Hermes YAML 无法解析；未覆盖")
				}
			}
			server["enabled"] = true
			childMap(m, "mcp_servers")["hindsight"] = server
			b, err = yaml.Marshal(m)
		}
		if err != nil {
			return err
		}
		if err = write(path, b); err != nil {
			return err
		}
		log("已配置 " + name + " MCP（原文件已备份，现有钩子未修改）")
	}
	log("接入配置完成；请重启所选智能体。历史归档与实时会话钩子相互独立。")
	return nil
}

func restoreAgents(root string, log func(string)) error {
	var entries []Backup
	if err := readJSON(filepath.Join(root, "last-install.json"), &entries); err != nil {
		return errors.New("没有可恢复的接入备份")
	}
	// Verify every file before restoring any file.
	pending := []Backup{}
	for _, b := range entries {
		current, err := os.ReadFile(b.Path)
		if os.IsNotExist(err) && !b.Existed {
			continue
		}
		if err == nil && hashText(string(current)) == b.AfterSHA {
			pending = append(pending, b)
			continue
		}
		if b.Existed && err == nil {
			original, readErr := os.ReadFile(b.Before)
			if readErr == nil && bytes.Equal(original, current) {
				continue
			}
		}
		return errors.New("接入配置在安装后发生变化，未自动覆盖，请查看备份目录")
	}
	for _, b := range pending {
		if b.Existed {
			data, err := os.ReadFile(b.Before)
			if err != nil {
				return err
			}
			if err = atomicWrite(b.Path, data, 0600); err != nil {
				return err
			}
		} else if err := os.Remove(b.Path); err != nil {
			return err
		}
		log("已恢复：" + b.Path)
	}
	return os.Remove(filepath.Join(root, "last-install.json"))
}

// stdioBridge lets all three clients share one protected local credential store.
// No credentials appear in MCP config files, arguments or stdout logs.
func stdioBridge(ctx context.Context, c Config, in io.Reader, out io.Writer) error {
	if err := c.validate(true, false); err != nil {
		return err
	}
	endpoint := strings.TrimRight(c.API, "/") + "/mcp/" + url.PathEscape(c.Bank) + "/"
	scanner := bufio.NewScanner(in)
	scanner.Buffer(make([]byte, 65536), 8*1024*1024)
	headers := map[string]string{}
	client := newHTTPClient(120 * time.Second)
	emit := func(b []byte) error {
		var response struct {
			Result struct {
				Protocol string `json:"protocolVersion"`
			} `json:"result"`
		}
		if json.Unmarshal(b, &response) != nil {
			return errors.New("无效 MCP JSON 响应")
		}
		if response.Result.Protocol != "" {
			headers["MCP-Protocol-Version"] = response.Result.Protocol
		}
		var compact bytes.Buffer
		if err := json.Compact(&compact, b); err != nil {
			return err
		}
		_, err := fmt.Fprintln(out, compact.String())
		return err
	}
	for scanner.Scan() {
		if len(bytes.TrimSpace(scanner.Bytes())) == 0 {
			continue
		}
		var envelope map[string]json.RawMessage
		if json.Unmarshal(scanner.Bytes(), &envelope) != nil {
			return errors.New("无效 MCP 输入")
		}
		req, err := http.NewRequestWithContext(ctx, "POST", endpoint, bytes.NewReader(scanner.Bytes()))
		if err != nil {
			return err
		}
		req.Header.Set("Authorization", "Bearer "+c.Token)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json, text/event-stream")
		for k, v := range headers {
			req.Header.Set(k, v)
		}
		resp, err := client.Do(req)
		if err != nil {
			return errors.New("MCP 远端连接失败")
		}
		if id := resp.Header.Get("Mcp-Session-Id"); id != "" {
			headers["Mcp-Session-Id"] = id
		}
		if resp.StatusCode < 200 || resp.StatusCode >= 300 {
			resp.Body.Close()
			return fmt.Errorf("MCP HTTP %d", resp.StatusCode)
		}
		if _, hasID := envelope["id"]; !hasID {
			resp.Body.Close()
			continue
		}
		if strings.Contains(resp.Header.Get("Content-Type"), "text/event-stream") {
			lines := bufio.NewScanner(io.LimitReader(resp.Body, 8*1024*1024))
			lines.Buffer(make([]byte, 65536), 8*1024*1024)
			found := false
			for lines.Scan() {
				line := strings.TrimSpace(lines.Text())
				if !strings.HasPrefix(line, "data:") {
					continue
				}
				data := strings.TrimSpace(strings.TrimPrefix(line, "data:"))
				var msg map[string]json.RawMessage
				if json.Unmarshal([]byte(data), &msg) == nil && string(msg["id"]) == string(envelope["id"]) {
					if err = emit([]byte(data)); err != nil {
						resp.Body.Close()
						return err
					}
					found = true
					break
				}
			}
			resp.Body.Close()
			if !found {
				return errors.New("MCP 未返回匹配的响应")
			}
		} else {
			b, err := io.ReadAll(io.LimitReader(resp.Body, 8*1024*1024+1))
			resp.Body.Close()
			if err != nil || len(b) > 8*1024*1024 || !json.Valid(b) {
				return errors.New("无效 MCP 响应")
			}
			if err = emit(b); err != nil {
				return err
			}
		}
	}
	return scanner.Err()
}
