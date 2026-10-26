# Hindsight 初始化应用

源码入口：[apps/hindsight-initializer](../apps/hindsight-initializer/README.md)。

## 定位与关系

本工具用于新客户端首次连接 Hindsight 时的存量归档和 MCP 注册，不是另一个记忆服务端。

| 入口 | 适用任务 | 是否覆盖既有实时钩子 |
| --- | --- | --- |
| Hindsight 初始化应用 | 连接认证、选择历史来源、本地压缩核验、成品上传、注册 MCP | 否 |
| `scripts/restore_to_<agent>.sh` | 在指定 HOME 恢复仓库中的脱敏配置模板 | 按原恢复脚本处理，不由本应用调用 |
| `scripts/hermes_handoff.py` | 公司/家里电脑轮流使用 Hermes 的加密交接 | 保留既有交接边界，不由本应用调用 |
| `scripts/hindsight-hook.py` | 已部署客户端的日常会话召回与留存 | 本次并入不替换其实现 |

这几个入口独立选择，不需要为了使用可视化初始化而先覆盖整套智能体配置。

## 架构

```text
Windows WebView2 窗口 / Windows、Linux 浏览器
                         |
                  本机 Go 可执行文件
                         |
       配置认证 -> 扫描解析 -> 脱敏与项目内精确去重
                         |
             分段提炼 -> 同项目归并 -> 独立核验
                         |
              人工预览确认 -> Hindsight API

智能体 -> 同一可执行文件 --mcp -> Hindsight MCP
```

网页资源嵌入程序；运行不需要 Python、Node.js 或 Go。Windows 窗口需要 WebView2 Runtime，未安装时回退到浏览器。

压缩工作流在客户端执行，但所选正文会发送给用户配置的模型服务；只有指向本机模型地址时才是本机推理。客户端压缩不调用向量和重排模型，上传后的服务端入库由 Hindsight 处理。

## 目录

- `apps/hindsight-initializer/web/`：共用页面、图标与内置字体。
- `main.go`、`desktop_*.go`：本机 HTTP 服务、任务控制与平台窗口。
- `config.go`、`secrets_*.go`、`lock_*.go`：配置、凭据保护与单写者锁。
- `scan.go`、`compact.go`、`upload.go`：扫描、核验压缩、上传与回读。
- `install.go`：MCP 注册、配置备份恢复及 stdio-to-HTTP 桥接。
- `initializer_test.go`、`ui_test.cjs`：离线单元测试、临时模拟服务下的浏览器流程测试。
- `output/hindsight-initializer/`：构建产物，已被 Git 忽略。

客户端运行数据默认在 `~/.local/state/hindsight-initializer/`，不放进此仓库。Windows 密钥使用当前用户 DPAPI，Linux 使用权限 0600 的本地文件。

## 构建、运行和验证

在仓库根目录执行：

```bash
bash apps/hindsight-initializer/build.sh
```

Windows 双击产物 `Hindsight-Setup-windows-x64.exe`。网页模式使用 `Hindsight-Setup-Web.cmd` 或 `--browser`。Linux 运行 `output/hindsight-initializer/hindsight-setup-linux-x64`。

开发验证在应用目录执行：

```bash
go test -race ./...
go vet ./...
go build -o /tmp/hindsight-setup-test .
SETUP_BINARY=/tmp/hindsight-setup-test node ui_test.cjs
```

浏览器测试需要开发环境已有 Playwright 和 Chromium；可用 `PLAYWRIGHT_MODULE`、`CHROME_PATH` 指定路径。测试自行创建临时配置和源文档，启动临时应用与模拟模型/Hindsight 服务，不需要打开真实预览服务，不读取真实客户端认证，不修改真实智能体配置。

原有配置项目的回归保持原入口：

```bash
python3 scripts/test_portable_configs.py
python3 -m unittest discover -s tests -p test_hermes_handoff.py -v
```

## 边界

只上传用户明确选择且独立核验通过的精简成品，不删除远端原文、不跨机器改写历史会话游标、不自动安装新的实时留存钩子。跨机器远端全库去重仍需单独治理。

Windows 与 WSL 是不同运行环境。配置 WSL 智能体时应在 WSL 使用 Linux 版，不能将 Windows 可执行文件路径直接写入 WSL 配置。

Windows EXE 的交叉编译和浏览器测试不能代替 Windows 真机上的 WebView2/DPAPI 验收。
