# Hindsight 初始化工具

面向新客户端接入的一次性存量整理工具。Windows 默认使用独立 WebView2 应用窗口；Windows 和 Linux 均支持本机网页。程序不依赖 Python、Node.js 或单独安装 Go。

## 使用

Windows：

- 双击 `Hindsight-Setup-windows-x64.exe` 打开桌面窗口。
- 双击 `Hindsight-Setup-Web.cmd` 或执行 `Hindsight-Setup-windows-x64.exe --browser` 打开浏览器模式。
- 桌面窗口需要 Microsoft Edge WebView2 Runtime。检测不到时自动使用浏览器。
- 此构建未签名，Windows 可能显示未知发布者。发布分发前应由实际发布者签名。

Linux：

```bash
chmod +x hindsight-setup-linux-x64
./hindsight-setup-linux-x64
```

无桌面的 Linux/SSH：

```bash
./hindsight-setup-linux-x64 --no-browser --listen 127.0.0.1:19081
# 在访问电脑建立 SSH 转发，再打开终端输出的带片段授权码的 URL。
ssh -L 19081:127.0.0.1:19081 user@linux-host
```

网页服务始终只监听本机回环地址，不应将端口映射到公网。不要公开终端输出的授权 URL。

## 初始化顺序

1. 配置 Hindsight 服务根地址、Bank ID、认证令牌，测试 API 与 MCP 认证。公网仅支持 HTTPS；SSH 隧道可使用本机 HTTP。
2. 检查服务端处理能力。客户端没有模型配置，不保存模型密钥、不直接请求模型；解析、去噪、合并、提炼、独立核验都在服务端。
3. 勾选 Codex、Claude Code、Hermes，修改数据目录，选择文档目录及闲置时长，扫描后预览脱敏正文。
4. 勾选来源并明确确认上传原件至服务端准备区；服务端返回核验预览。检查后再确认入库，服务端才将最终正文交给 Hindsight。
5. 在“智能体接入”配置所选智能体的 MCP，重启对应智能体。原有实时钩子不做修改，不代表本工具已安装 Hermes 的实时会话钩子。

“扫描”不联网。上传准备会把选中的原件发送到 Hindsight 服务端，并授权该服务端使用其配置的模型处理。准备完成不等于已纳入检索；界面再次确认后才写入 Hindsight。

## 扫描支持

- Codex：数据目录下 `sessions/**/*.jsonl`、`archived_sessions/**/*.jsonl`，只解析 canonical `response_item`，不重复读取 `event_msg`，不导入内部 reasoning。
- Claude Code：`projects/**/*.jsonl` 中的 user/assistant 文本。
- Hermes：只读 `state.db`（包含 WAL 一致性读取、已结束会话、排除 active=0 的回退消息），同时支持 `sessions/` 中 JSON/JSONL 导出与 `memories/` 中 Markdown。未知数据库结构显式列为错误，不静默当作扫描完成。
- 文档：MD、TXT、RST、CSV、HTML、DOCX、PPTX、XLSX。Office 原始字节保留，不在客户端转换；仅检查 XML 凭据。含图片等嵌入二进制的 Office、PDF 默认要求先提供安全文本副本，避免未经检查的原件离开本机。文本编码须为 UTF-8。
- Windows 程序扫描 Windows 文件系统。WSL 文件不会自动混入；需要显式选择可访问的 WSL 目录，或在 WSL 内运行 Linux 版。WSL 智能体应使用 WSL 中的 Linux 可执行文件及配置，不能将 Windows 路径直接写入 WSL MCP。

默认排除最近 24 小时修改的文件与未结束的 Hermes 会话。闲置只是保守启发式，长期打开但暂时无更新的 Codex/Claude 会话仍可能进入候选，请在预览中取消选择。原始文件不会被修改或删除。

默认排除凭据、配置、备份、依赖目录、符号链接。脱敏规则无法保证识别所有业务机密，上传前仍应检查来源范围。相同项目内按脱敏正文 SHA-256 精确去重，不跨项目丢弃归属。扫描上限为 20,000 个来源、256 MB 累计正文，单文件大小可选 1–100 MB；超过上限不会以截断内容冒充完整来源。

## 压缩与恢复

同项目来源每批不超过 20 份，客户端按传输体积分批，不做内容总结。服务端解析并生成带来源引用的提案，再独立核验重要遗漏、无依据断言和范围混淆。未通过不产生可确认成品；服务端三次失败后停止。超过服务端处理上限也不会静默截断，需减小批次或显式拆分来源。

本地目录默认是 `~/.local/state/hindsight-initializer/`：

- `settings.json`：地址、认证和扫描范围。Windows 令牌由 DPAPI 加密；Linux 使用权限 0600 文件。保存配置时不再保留旧的模型配置字段。
- `scans/<批次>/raw/`：会话为脱敏文本，普通文档为预检后的上传内容，Office 为原始字节；`.md` 是历史暂存文件后缀，不代表都已转成 Markdown。
- `scans/<批次>/products/`：服务端返回的只读预览缓存；`products.json` 保留来源映射、job_id 和目标服务。
- `remote-jobs/`：跨扫描批次复用的远端任务编号；中断后继续查询，不在客户端重做处理。
- `backups/`、`last-install.json`：接入配置原文件与恢复日志。若安装后文件被用户改动，自动恢复会拒绝覆盖。

原件只有在明确选择并确认后上传。确认入库时再次比对本地预览指纹和服务端预览，客户端不允许上传任意改写的预览绕过处理。服务端跟踪准确的原生 retain 任务，回读正文并关联原件附件后才完成。客户端只查 job_id。不会删除已有文档或改写活跃会话游标。准备区原件在服务端受控保存，当前没有自动清理，须由运维配置保留策略。

## MCP 接入

所选智能体的 Hindsight MCP 使用内置 stdio-to-HTTP 桥接。智能体配置里只有本地程序路径和参数，不写令牌。保留其他服务器与现有钩子；修改前保存完整备份。TOML/YAML 使用结构化解析器重写，语义保留，但注释与格式可能变化。

- Codex：所选目录的 `config.toml`。
- Claude Code：默认 `~/.claude.json`；自定义目录为该目录下 `.claude.json`。
- Hermes：所选目录的 `config.yaml`。

API 访问使用 `Authorization: Bearer`，禁用自动重定向，避免将凭据带到其他主机。不内置任何真实远端地址、令牌或模型密钥。首次启动只尝试读取本机原有 `~/.config/hindsight/connection.json`，不会联网或修改它。

## 构建与验证

构建依赖 Go 1.26。源依赖版本与校验和固定在 `go.mod`、`go.sum`。

```bash
go test -race ./...
go vet ./...
bash build.sh
```

Windows 独立窗口使用 go-webview2，SQLite 使用 modernc 的纯 Go 驱动，因此可在 Linux 上交叉编译，无需 MinGW。Windows 原生 WebView2/DPAPI 行为仍须在 Windows 真机验证；Linux 浏览器测试不能替代该验证。

`ui_test.cjs` 使用 Playwright 和模拟服务端，覆盖连接、扫描、去重、来源上传确认、远端预览、入库确认、幂等及多个视口，并断言客户端不访问模型端点。不接触真实远端或用户配置。设置 `LAUNCHER` 指向临时 `--data-dir` 下的 `launcher.json`。
