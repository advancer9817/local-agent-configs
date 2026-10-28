# Hindsight 会话与产物入库

## 可视化初始化工具

独立的 [Hindsight 初始化工具](../hindsight-initializer/README.md)：Windows EXE / Linux 本机界面仅管理连接、选择来源、传输和显示远端预览，不持有模型密钥，也不执行文档转换、总结或模型核验。服务端生成预览，用户再次确认后才进入 Hindsight 检索库。

## 职责划分

| 位置 | 做什么 | 不做什么 |
| --- | --- | --- |
| 客户端钩子 `hindsight-hook.py` | 会话前召回；每轮结束把整篇会话和有变化的产物（最多 3 份）一次 POST 上去 | 不解析、不调用模型、不轮询任务、不保存游标 |
| `ingest_safety.py` / `session_documents.py` | 产物范围、大小、凭据预检；会话文本与产物收集 | 不转换文档 |
| 访问网关 `server/access_gateway.py` | 令牌鉴权、数据仓授权、控制台登录、账号与令牌管理 | 不碰文档内容 |
| 入库扩展 `server/ingest_extension.py` | 接收上传、生成文档 ID、任务查询/重试/确认 | 不做账号授权（由网关负责） |
| 任务队列 `server/ingest_jobs.py` | 每个文档只保留最新版本；清洗、解析、LLM、原生 retain、重试 | |
| `artifact_digest.py` / `server/artifact_refine.py` | 格式解析去噪；LLM 压缩提炼 | |

## 入库流程

```text
一轮结束 → 钩子 POST /ext/ingest/banks/{bank}/sessions（manifest + session + file0..2）
        → 网关校验令牌和读写权限 → 扩展写入任务表，立即返回 {accepted, failed}
        → 后台：会话  清洗（去掉注入的召回背景、环境块、凭据）→ 原生 retain
                产物  解析去噪 → LLM 压缩 → 原生 retain
```

- 同一会话始终是同一份文档；每轮上传整篇，Hindsight 的 replace 按分块哈希只处理变化的分块。会话不经过 LLM。
- 产物和初始化归档必须经过 LLM；模型不可用、超限或输出不合格时不降级入库。
- 任务表以 (bank, document) 为主键：新版本覆盖未处理的旧版本，相同内容版本不重复处理，前一次 retain 未结束时新版本等待它结束。
- 状态：pending → processing → submitting → retaining → completed；异常进入 retrying，3 次后 failed；无有效正文为 skipped。failed 的文档再次上传或调用 retry 会重新排队。
- 客户端只记录已成功提交的内容哈希；上传失败下一轮自动重传，不需要查询任务。
- 任务库为单机 SQLite，默认 `/opt/hindsight-research/session-ingest/jobs.sqlite`（0600）。

产物格式处理（服务端）：HTML 去掉脚本、导航、按钮和重复文字，SVG 图表还原为组件与关系；PPTX 按页输出标题、要点、表格和备注，跳过隐藏页；DOCX 保留标题层级、列表和表格；XLSX 按可见工作表输出；PDF 去掉页码和重复页眉页脚；超过 30 行的表格只保留前 30 行并附统计。客户端只做范围和凭据预检，含凭据、宏或嵌入二进制的文件会被拒绝并给出原因。

归档正文只作为历史数据，其中出现的命令和提示不是当前指令。

## 访问控制

网关一个进程监听两个端口，Hindsight API 和原版控制台都改为只监听本机：

| 对外端口 | 转发到 | 规则 |
| --- | --- | --- |
| 18888 API / MCP / 入库 | 127.0.0.1:18887 | `Authorization: Bearer hs_...`，按数据仓授权；开关关闭时直接透传 |
| 19999 控制台 | 127.0.0.1:19998 | 必须登录（不受开关影响）；`/access/` 为账号与令牌管理 |

- 角色：管理员看到并管理全部数据仓；普通账号只看到被授权的数据仓，列表接口会被过滤，访问其他数据仓返回 403。
- 权限分三级：只读（召回、浏览）、读写（上传、retain、删除文档）、管理（数据仓配置、清空、迁移）。令牌可以设置更低的权限上限和有效期，可随时吊销。
- MCP 按工具名判断级别；无法识别的工具按读写处理，跨数据仓接口和未知路径只允许管理员访问。
- 密码使用 scrypt，令牌和会话只存哈希；控制台写操作需要 CSRF 令牌；同一地址 10 分钟内登录失败 8 次即锁定。

首次启动会创建管理员 `admin`，随机密码写入 `$HS_GATEWAY_HOME/admin-initial-password.txt`（0600），登录后请修改密码并删除该文件。

```bash
cd /root/.local/lib/hindsight
export HS_GATEWAY_HOME=/opt/hindsight-research/access
/opt/hindsight-research/venv/bin/python access_gateway.py auth off          # 一键关闭 API 鉴权，2 秒内生效
/opt/hindsight-research/venv/bin/python access_gateway.py auth on
/opt/hindsight-research/venv/bin/python access_gateway.py reset-admin admin # 忘记管理员密码
```

控制台“设置与审计”页也有同一个开关。网关环境变量：`HS_GATEWAY_HOME`、`HS_GATEWAY_API_LISTEN`、`HS_GATEWAY_API_UPSTREAM`、`HS_GATEWAY_CONSOLE_LISTEN`、`HS_GATEWAY_CONSOLE_UPSTREAM`、`HS_GATEWAY_SECURE_COOKIE=1`（启用 HTTPS 后设置）。

## 部署与测试

源代码改动不代表运行环境已经升级。顺序：备份 → 部署服务端 → 切换端口 → 发令牌 → 升级客户端。

1. 把 `server/*.py`、`server/access_console/`、`artifact_digest.py`、`ingest_safety.py`、`session_documents.py` 复制到服务端 PYTHONPATH。
2. API 改为 `hindsight-api --host 127.0.0.1 --port 18887`；API 与全部 worker 设置：

```text
HINDSIGHT_API_HTTP_EXTENSION=ingest_extension:SessionIngestExtension
HINDSIGHT_API_OPERATION_VALIDATOR_EXTENSION=hindsight_session_metadata:SessionDocumentMetadata
HINDSIGHT_API_HTTP_SPOOL_DIR=/opt/hindsight-research/session-ingest
HINDSIGHT_API_EMBEDDINGS_OPENAI_BATCH_SIZE=20   # 阿里百炼 embedding 每批最多 20 条
```

3. 控制台设置 `HOSTNAME=127.0.0.1 PORT=19998 HINDSIGHT_CP_DATAPLANE_API_URL=http://127.0.0.1:18887`；启动网关接管 18888 和 19999。
4. 在控制台为每台客户端发令牌，写入客户端 `connection.json` 的 `mcp_token`（URL 不变）。

模型默认复用 `HINDSIGHT_API_LLM_*`，可用 `HINDSIGHT_API_HTTP_REFINE_*` 覆盖。新客户端发现服务端接口未启用时显式失败，不回退到旧接口。

```bash
python3 -m unittest discover -p 'test_*.py'
/opt/hindsight-research/venv/bin/python -m unittest discover -s server -p 'test_*.py'
cd ../hindsight-initializer && go test ./...
```

## Windows / WSL / Linux 客户端更新

将 install.py、hindsight-hook.py、session_documents.py 和 ingest_safety.py 放到客户端，用 Python 3 执行 install.py。安装器保留连接配置和其他钩子，并备份旧文件。云端无法读取 Windows/WSL 的本地文件，必须在对应机器安装新版上传脚本。

## 成本

内容不变时不重复上传；会话按分块增量处理，只有变化的分块会重新提取和生成向量。产物每个新版本调用一次 LLM 压缩。
