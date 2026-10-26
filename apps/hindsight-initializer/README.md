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

1. 配置 Hindsight 服务根地址和 Bank ID，测试 API 与 MCP 连接。客户端不配置或发送 Hindsight 认证令牌，服务端 MCP 须允许无令牌连接。公网仅支持 HTTPS；SSH 隧道可使用本机 HTTP。
2. 配置兼容 Chat Completions 的压缩模型 API 根地址（通常以 `/v1` 结尾）、模型名及模型密钥，测试连接。仅填写域名时自动补齐 `/v1`，显式填写的自定义路径保持不变。模型密钥仍由模型服务要求。未配置模型仍可扫描、查看来源、配置 MCP，但不能执行语义压缩。
3. 勾选 Codex、Claude Code、Hermes，修改数据目录，选择文档目录及闲置时长。保存范围只更新文件清单；点击“提取本地正文”后才读取、脱敏并预览正文。
4. 勾选来源并执行本地压缩，在结果列表查看完整提炼正文、来源明细和核验状态，再逐篇选择是否上传。结果默认不选中；勾选上传确认并点击“上传所选结果”后才提交远端。
5. 在“智能体接入”配置所选智能体的 MCP，重启对应智能体。原有实时钩子不做修改，不代表本工具已安装 Hermes 的实时会话钩子。

“扫描”不访问模型或 Hindsight。“压缩”会把脱敏后的所选正文发送到用户配置的模型服务；它不意味着模型在本机运行。可以将模型地址指向本机兼容服务。

### 智能扫描文档

- 在“提取范围”点击“智能扫描”，选择“全电脑”或“指定目录”，再点击“扫描并加入”。
- 全电脑模式遍历本机可见的磁盘；Windows 使用本地固定盘、可移动盘和 RAM 盘，Linux/WSL 包括本地文件系统及 `/mnt`、`/media` 下的可见挂载目录。指定目录模式递归遍历该目录，不局限于常用文件夹。
- 只发现受支持格式的文件并记录标题、路径、大小和修改时间，显示到“本地归档”，状态为“待提取”。不解析正文，不调用模型，也不上传远端。
- 只展示当前解析器支持的格式：MD、TXT、RST、CSV、HTML、DOCX、XLSX、PPTX；PDF 仅在本机 `pdftotext` 可用时列入。DOC、XLS、PPT、带宏 Office、RTF、OpenDocument、EPUB、TeX 和 WPS 等未支持格式直接忽略。清单按解析能力筛选，不代表每个文件已经通过正文解析；手动提取中已确认解析失败、无正文或超过限制的条目不再显示，诊断记录仍保存在本地清单。
- 跳过系统、凭据、缓存、依赖目录、临时 Office 文件和符号链接；不可访问的路径会跳过并记录。智能扫描的标题过滤额外排除明显的账号、密码、密钥、手机号和身份证文件，不保证识别所有业务机密。
- 显示发现数量和当前位置，支持取消并保存已发现清单。单次最多发现 20,000 个文件，达到上限会明确报错并保留清单，不冒充已扫完整机；可改用指定目录分批处理。
- 来源列表分页显示并支持标题或路径筛选，不再只显示前 1,000 条。保存范围和已有清单可在重新打开应用后恢复；提取正文、提炼和上传仍需分别手动触发。

## 扫描支持

- Codex：数据目录下 `sessions/**/*.jsonl`、`archived_sessions/**/*.jsonl`，只解析 canonical `response_item`，不重复读取 `event_msg`，不导入内部 reasoning。
- Claude Code：`projects/**/*.jsonl` 中的 user/assistant 文本。
- Hermes：只读 `state.db`（包含 WAL 一致性读取、已结束会话、排除 active=0 的回退消息），同时支持 `sessions/` 中 JSON/JSONL 导出与 `memories/` 中 Markdown。未知数据库结构显式列为错误，不静默当作扫描完成。
- 文档：MD、TXT、RST、CSV、HTML、DOCX、PPTX、XLSX。PDF 需要用户安装 `pdftotext`，缺失时列为跳过/错误。文本编码须为 UTF-8。
- Windows 程序扫描 Windows 文件系统。WSL 文件不会自动混入；需要显式选择可访问的 WSL 目录，或在 WSL 内运行 Linux 版。WSL 智能体应使用 WSL 中的 Linux 可执行文件及配置，不能将 Windows 路径直接写入 WSL MCP。

默认排除最近 24 小时修改的文件与未结束的 Hermes 会话。闲置只是保守启发式，长期打开但暂时无更新的 Codex/Claude 会话仍可能进入候选，请在预览中取消选择。原始文件不会被修改或删除。

默认排除凭据、配置、备份、依赖目录、符号链接。脱敏规则无法保证识别所有业务机密，上传前仍应检查来源范围。相同项目内按脱敏正文 SHA-256 精确去重，不跨项目丢弃归属。扫描上限为 20,000 个来源、256 MB 累计正文，单文件大小可选 1–100 MB；超过上限不会以截断内容冒充完整来源。

## 压缩与恢复

单篇长文本先按 16,000 字提炼，再与同项目来源打包合并。每份提案均执行独立证据核验；只对重要遗漏允许一次补充与再次核验，未知来源、无依据断言、范围混淆或不完整 JSON 不通过。压缩倍数是目标，不是保证。无法继续压缩的来源保留为“无收益”，不上传。

本地目录默认是 `~/.local/state/hindsight-initializer/`：

- `settings.json`：地址、模型密钥和扫描范围。Windows 的模型密钥由当前用户 DPAPI 加密；Linux 使用权限 0600 的本地文件，不宣称硬件加密。升级时自动删除旧版 `mcp_token`、`has_token` 字段。
- `scans/<批次>/raw/`：每篇来源的脱敏 Markdown，与 `inventory.json` 中的会话 ID、路径、项目、指纹关联。
- `candidates/`：跨扫描批次复用的精确输入指纹缓存、模型提案、独立核验和批准记录。
- `scans/<批次>/products/`：审核成品；`products.json` 保留来源映射。
- `uploads/`：跨扫描批次复用，按服务地址、Bank 和成品身份记录 operation_id。网络中断后继续确认原任务，不以标题覆盖其他文档。
- `backups/`、`last-install.json`：接入配置原文件与恢复日志。若安装后文件被用户改动，自动恢复会拒绝覆盖。

只上传明确选择、独立核验通过且指纹匹配的成品；等待异步任务完成，并回读正文、文档身份及记忆条数才标记完成。程序不删除远端原文，不进行跨机器远端全库语义去重，也不自动改写已上传的历史会话游标。标题只作展示，稳定的批次/内容身份用于防止覆盖。远端已有未归档原文应另行执行可审计的服务端治理。

### 结果复核与手动上传

- 点击结果行的明细图标，查看完整提炼正文、来源标题、项目、路径、会话 ID、字数变化和核验状态；来源正文仍使用脱敏预览。
- 提炼完成只写本地结果，不触发 Hindsight 入库。刷新或生成新结果后，上传选择和确认默认清空。
- 只有已核验且正文指纹匹配的结果可以上传。选择或上传目标变化后需重新确认，上传操作后也会取消确认。
- 本机 `/api/upload` 必须同时接收 `confirm: true` 与明确的结果 `ids`；空选择、无效 ID 或未通过核验的结果不会触发远端请求。

## MCP 接入

所选智能体的 Hindsight MCP 使用内置 stdio-to-HTTP 桥接，不添加认证请求头。智能体配置里只有本地程序路径和参数。保留其他服务器与现有钩子；修改前保存完整备份。TOML/YAML 使用结构化解析器重写，语义保留，但注释与格式可能变化。

- Codex：所选目录的 `config.toml`。
- Claude Code：默认 `~/.claude.json`；自定义目录为该目录下 `.claude.json`。
- Hermes：所选目录的 `config.yaml`。

Hindsight API 与 MCP 访问不发送 `Authorization`；只有模型调用按配置发送 API Key。禁用自动重定向，避免将模型凭据带到其他主机。不内置任何真实远端地址或模型密钥。首次启动只尝试读取本机原有 `~/.config/hindsight/connection.json` 的服务地址和 Bank ID，不导入令牌，不会联网或修改该文件。

服务端关闭令牌校验后，任何能够访问其地址的客户端都可能读写记忆。应在部署层限制访问范围；本工具的回环监听和本地页面授权保持启用。

## 构建与验证

构建依赖 Go 1.26。源依赖版本与校验和固定在 `go.mod`、`go.sum`。

本应用位于 `local-agent-configs/apps/hindsight-initializer/`。从仓库根目录运行 `bash apps/hindsight-initializer/build.sh`，产物默认输出到仓库的 `output/hindsight-initializer/`（不提交 Git）。以下开发命令在应用目录执行：

```bash
go test -race ./...
go vet ./...
bash build.sh
```

Windows 独立窗口使用 go-webview2，SQLite 使用 modernc 的纯 Go 驱动，因此可在 Linux 上交叉编译，无需 MinGW。Windows 原生 WebView2/DPAPI 行为仍须在 Windows 真机验证；Linux 浏览器测试不能替代该验证。

`ui_test.cjs` 使用 Playwright、临时应用实例和模拟模型/Hindsight 服务，覆盖测试连接、扫描、去重、预览、压缩、成品回读、上传幂等和多个视口；不接触真实远端或用户智能体配置。使用开发环境的 Playwright 模块与浏览器，并通过 `SETUP_BINARY` 指定已构建的程序：

```bash
go build -o /tmp/hindsight-setup-test .
SETUP_BINARY=/tmp/hindsight-setup-test node ui_test.cjs
```

可通过 `PLAYWRIGHT_MODULE`、`CHROME_PATH`、`UI_SCREENSHOT_DIR` 指定测试依赖与截图目录。不设置 `SETUP_BINARY` 时使用仓库默认构建输出。
