package main

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

type AgentConfig struct {
	Enabled bool   `json:"enabled"`
	Path    string `json:"path"`
}

type Config struct {
	API       string                 `json:"api_url"`
	Bank      string                 `json:"bank_id"`
	ModelURL  string                 `json:"model_url"`
	Model     string                 `json:"model"`
	ModelKey  string                 `json:"model_key"`
	Agents    map[string]AgentConfig `json:"agents"`
	Roots     []string               `json:"document_roots"`
	IdleHours int                    `json:"idle_hours"`
	MaxFileMB int                    `json:"max_file_mb"`
	HasKey    bool                   `json:"has_model_key,omitempty"`
}

func hashText(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}

func randomToken() string {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}

func homePath(parts ...string) string {
	home, _ := os.UserHomeDir()
	return filepath.Join(append([]string{home}, parts...)...)
}

func defaultConfig() Config {
	return Config{
		Bank: "mcore-active-snapshot", IdleHours: 24, MaxFileMB: 10,
		Agents: map[string]AgentConfig{
			"codex":  {true, homePath(".codex")},
			"claude": {true, homePath(".claude")},
			"hermes": {true, homePath(".hermes")},
		},
		Roots: []string{},
	}
}

func readJSON(path string, target any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, target)
}

func atomicJSON(path string, value any) error {
	b, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return atomicWrite(path, b, 0600)
}

func atomicWrite(path string, b []byte, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".hindsight-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(mode); err == nil {
		_, err = f.Write(b)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(f.Name(), path)
}

func loadConfig(root string) (Config, error) {
	c := defaultConfig()
	err := readJSON(filepath.Join(root, "settings.json"), &c)
	if errors.Is(err, os.ErrNotExist) {
		// Import only connection settings. Never modify the existing hook config.
		var old struct {
			API  string `json:"api_url"`
			Bank string `json:"bank_id"`
		}
		if readJSON(homePath(".config", "hindsight", "connection.json"), &old) == nil {
			c.API = old.API
			if old.Bank != "" {
				c.Bank = old.Bank
			}
		}
		return c, nil
	}
	if err != nil {
		return c, err
	}
	c.ModelURL = normalizeModelURL(c.ModelURL)
	c.ModelKey, err = unprotect(c.ModelKey)
	if err != nil {
		return c, err
	}
	var stored map[string]json.RawMessage
	if err = readJSON(filepath.Join(root, "settings.json"), &stored); err != nil {
		return c, err
	}
	if stored["mcp_token"] != nil || stored["has_token"] != nil {
		err = saveConfig(root, c)
	}
	return c, err
}

func saveConfig(root string, c Config) error {
	var err error
	c.ModelURL = normalizeModelURL(c.ModelURL)
	c.ModelKey, err = protect(c.ModelKey)
	if err != nil {
		return err
	}
	c.HasKey = false
	return atomicJSON(filepath.Join(root, "settings.json"), c)
}

func publicConfig(c Config) Config {
	c.HasKey = c.ModelKey != ""
	c.ModelKey = ""
	return c
}

func normalizeModelURL(raw string) string {
	raw = strings.TrimRight(strings.TrimSpace(raw), "/")
	u, err := url.Parse(raw)
	if err == nil && u.Host != "" && u.Path == "" {
		u.Path = "/v1"
		return u.String()
	}
	return raw
}

func (c Config) scopeKey() string {
	b, _ := json.Marshal(struct {
		Agents               map[string]AgentConfig
		Roots                []string
		IdleHours, MaxFileMB int
	}{c.Agents, c.Roots, c.IdleHours, c.MaxFileMB})
	return hashText(string(b))
}

func validateEndpoint(raw string) error {
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return errors.New("地址必须是无用户名、参数和片段的完整 HTTP(S) URL")
	}
	ip := net.ParseIP(u.Hostname())
	local := u.Hostname() == "localhost" || (ip != nil && ip.IsLoopback())
	if u.Scheme != "https" && !(u.Scheme == "http" && local) {
		return errors.New("远程地址必须使用 HTTPS；仅本机回环地址允许 HTTP")
	}
	return nil
}

func (c Config) validate(requireRemote, requireModel bool) error {
	if c.IdleHours < 1 || c.IdleHours > 8760 || c.MaxFileMB < 1 || c.MaxFileMB > 100 {
		return errors.New("闲置时长需为 1–8760 小时，单文件限制需为 1–100 MB")
	}
	if strings.TrimSpace(c.Bank) == "" || strings.ContainsAny(c.Bank, "/\\?#\r\n") {
		return errors.New("Bank ID 无效")
	}
	if requireRemote {
		if err := validateEndpoint(c.API); err != nil {
			return fmt.Errorf("Hindsight：%w", err)
		}
	}
	if requireModel {
		if strings.TrimSpace(c.ModelURL) == "" {
			return errors.New("尚未配置压缩模型接口地址，请在「连接设置」中配置压缩模型")
		}
		if strings.TrimSpace(c.Model) == "" {
			return errors.New("尚未配置压缩模型名称，请在「连接设置」中填写模型 ID")
		}
		if err := validateEndpoint(c.ModelURL); err != nil {
			return fmt.Errorf("压缩模型：%w", err)
		}
	}
	for name := range c.Agents {
		if name != "codex" && name != "claude" && name != "hermes" {
			return errors.New("未知智能体")
		}
	}
	return nil
}
