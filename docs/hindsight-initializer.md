# Hindsight 接入与处理边界

源码：[初始化应用](../apps/hindsight-initializer/README.md)、
[会话与服务端处理](../apps/hindsight-session-ingest/README.md)。

## 两种入口

| 入口 | 用途 | 本机职责 |
| --- | --- | --- |
| 初始化应用 | 新电脑接入、历史会话与文档整理、MCP 注册 | 扫描、预检、传输、展示远端预览及确认 |
| 日常钩子 | Codex/Claude 提示前召回、回合结束上传 | 收集会话与变化产物、凭据预检、一次提交 |

初始化应用不安装实时钩子；恢复配置脚本和 `apps/hindsight-session-ingest/install.py` 为独立入口。
Hermes 双机加密交接不受影响，恢复脱敏模板不等于完成真实客户端连接配置。

## 服务端流程

```text
客户端原件 -> 访问网关鉴权与数据仓授权 -> 入库扩展与任务库
  会话：清洗 -> 原生 retain -> completed
  产物：解析去噪 -> LLM 压缩 -> 原生 retain -> completed
  初始化归档：解析与提炼 -> 预览 -> 用户确认 -> 原生 retain
```

客户端不保存模型密钥，不解析 Office，不调用模型。原件被安全检查拒绝时需提供安全副本，不绕过预检上传。
客户端配置的访问令牌只用于 Hindsight，模型连接和密钥由服务端管理。

## 构建与验证

```bash
bash apps/hindsight-initializer/build.sh
cd apps/hindsight-initializer
go test -race ./...
go vet ./...
go build -o /tmp/hindsight-setup-test .
SETUP_BINARY=/tmp/hindsight-setup-test node ui_test.cjs
```

源码可交叉构建 Windows/Linux，Windows WebView2、DPAPI 和各外部客户端仍需在目标电脑验收。
构建产物、运行状态、页面授权和连接凭据不纳入 Git。
