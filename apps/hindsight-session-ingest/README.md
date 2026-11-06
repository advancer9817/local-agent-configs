# Hindsight 会话与产物入库

## 可视化初始化工具

独立的 [Hindsight 初始化工具](../hindsight-initializer/README.md)：Windows EXE / Linux 本机界面仅管理连接、选择来源、传输和显示远端预览，不持有模型密钥，也不执行文档转换、总结或模型核验。服务端生成预览，用户再次确认后才进入 Hindsight 检索库。

## 职责划分

| 位置 | 做什么 | 不做什么 |
| --- | --- | --- |
| 客户端钩子 `hindsight-hook.py` | 会话前召回；每轮结束把整篇会话和有变化的产物（最多 3 份）一次 POST 上去 | 不解析、不调用模型、不轮询任务、不保存游标 |
| Hermes 插件 `hermes-plugin/hindsight-memory` | `pre_llm_call` 调用钩子召回并注入上下文；`post_llm_call` 后台调用钩子上传该会话 | 不另写上传逻辑 |
| `ingest_safety.py` / `session_documents.py` | 产物范围、大小、凭据预检；会话文本与产物收集 | 不转换文档 |
| 访问网关 `server/access_gateway.py` | 令牌鉴权、数据仓授权、控制台登录、账号与令牌管理 | 不碰文档内容 |
| 入库扩展 `server/ingest_extension.py` | 接收上传、生成文档 ID、任务查询/重试/确认 | 不做账号授权（由网关负责） |
| 任务队列 `server/ingest_jobs.py` | 每个文档只保留最新版本；清洗、解析、LLM、原生 retain、重试 | |
| `artifact_digest.py` / `server/artifact_refine.py` | 格式解析去噪；LLM 压缩提炼 | |
| `server/session_refine.py` | 会话清洗、原文分段、段笔记缓存与主线概览 | 不做关系图、不改写已缓存段 |

## 入库流程

```text
一轮结束 → 钩子 POST /ext/ingest/banks/{bank}/sessions（manifest + session + file0..2）
        → 网关校验令牌和读写权限 → 扩展写入任务表，立即返回 {accepted, failed}
        → 后台：会话  清洗 → 分段整理与缓存 → 主线概览 → 校验 → 原生 retain
                产物  解析去噪 → LLM 压缩 → 原生 retain
```

- 同一会话始终是同一份文档：客户端仍上传完整原文，服务端沿用文档 ID 和原生 replace，不增加专用 bank 或客户端 LLM。原生 retain 继续提取记忆。
- 会话整理保留背景目标、关键要求与约束、最终方案与修订、实现结果、排障经验、未完成事项和产物入口；助手报告保留内容及来源限定，不因缺少工具日志而整项丢弃。合并重复和删除噪声，不要求固定条数或压缩比例。
- 确定性清洗剥离 skill 指令正文（保留技能名）、AGENTS 注入、历史召回、环境/git 包装、旧上传器的 `tool:` 消息和附件固定说明；现行上传器本来就不收集工具消息。保留用户请求、文件入口、助手结果和源码/SQL 代码块。不把正文里提到的 AGENTS 或 skill 当成注入。交接摘要可能是其他客户端唯一幸存的早期记录，因此保留并标明历史转述，不盲目删除。
- 以用户轮次组织约 24,000 字符的段，超长单轮按固定字符位置拆开，不能截尾。缓存键包含段原文、前序缓存键、清洗/提示词版本、模型、endpoint 和标题；已封闭段在追加时复用，末段从原文重提炼，不读取旧段摘要来滚动改写。前文发生修改时，从该位置开始失效。段表保存成功结果（包括暂时开放的末段），没有固定最多 8 段的限制。
- 多段会话从全体段笔记生成“主线与当前状态”，并补充最近两条消息（最多 12,000 字符）清洗原文以校准最新修订，防止段笔记把历史方案误归并成现状；单段不额外调用模型。永远不读取旧概览，形成固定两层，而非无限递归压缩。段笔记输入超过 64,000 字符时显式降级，不静默截断；最近原文窗口只作校准，完整细节仍在原文及段笔记。稳定段笔记在前，变化概览在后；不重复插入固定免责声明，正文仍保留各项结论的来源与状态限定。这有利于稳定文本前缀，但不保证原生 chunk 边界或成本不变。
- 汇总不是等待固定轮数或会话结束才触发：每轮 Stop 上传有变化的原文后，服务端后台队列处理最新版本。分段结果超过一段时生成概览；段笔记及最近原文未变则复用概览缓存。段数取决于正文长度与用户轮次边界，不取决于聊天轮数。文档排版版本也计入任务指纹，但不使已校验的段笔记和概览模型缓存失效。
- 概览发布前增加一次小输入校对，仅比较候选概览和最近原文，纠正“历史方案冒充最新方案”等冲突；不是再次压缩，不用旧概览滚动生成。模型升级、细节遗漏和未明确的状态仍需真实样本评测，校对不是正确性证明。
- 每段校验数字/路径/URL、防凭据，并检查重要回复和用户请求中的路径、链接、commit、测试数字等锚点；最多修正一次。锚点覆盖不代表语义无遗漏，需要真实会话要点评测。不强求固定压缩比例，也不把所有操作流水账视为必留内容。
- 会话段笔记和主线概览没有“输出必须短于输入”的硬限制：增加标题、说明归属和整理结构可以使短原文变长。仍校验非空、模型完整结束、来源字面量、关键锚点和凭据，模型输出 token 上限仍有效。产物压缩的长度约束不受此调整影响。
- `original` 保留最新完整原始上传字节，`parsed_text` 保留清洗正文，`refined_text` 仅保存可发布候选；`session_segments` 保存段笔记/概览缓存，按 owner、bank、document 隔离。预览接口返回脱敏后的原文与候选稿，原文不因清洗被修改。
- 提炼失败不会提交原文，也不会覆盖已入库的合格版本。成功段缓存可供重试复用；自动重试 3 次后状态为 `degraded`，在失败列表中可见，支持手动 retry 或相同原文重新上传。首次整理失败时检索库暂时没有此文档；已有版本则保持旧稿，可通过 `has_published_version` 区分。`completed` 只在 retain 确认完成（或候选正文与已确认版本相同）时标记。
- 产物和初始化归档必须经过 LLM；模型不可用、超限或输出不合格时不降级入库。
- 初始化器导入历史会话时复用 `/sessions` 和同一套会话整理规则，传入 `auto_commit=false`，先停在 `prepared` 等待确认，再调用任务的 `commit` 入库；实时钩子不传此字段，仍默认自动入库。`capabilities.session_preview=true` 表示服务端支持此流程，旧服务端未声明能力时初始化器拒绝上传会话。普通文档仍通过 `/archives` 批量归档。
- 任务表以 (bank, document) 为主键：新版本覆盖未处理的旧版本，相同内容版本不重复处理，前一次 retain 未结束时新版本等待它结束。
- 协调器最多同时推进 `HINDSIGHT_API_HTTP_CONCURRENCY` 篇文档（默认 3），同一文档从不并发；超长会话整理时不再阻塞其他会话。
- 状态：pending → processing → submitting → retaining → completed；异常进入 retrying，3 次后 failed（会话提炼不合格为 degraded）；无有效正文为 skipped。failed/degraded 的文档再次上传或调用 retry 会重新排队。
- 客户端只记录已成功提交的内容哈希；上传失败下一轮自动重传，不需要查询任务。
- 任务库为单机 SQLite，默认 `/opt/hindsight-research/session-ingest/jobs.sqlite`（0600）。

产物格式处理（服务端）：HTML 去掉脚本、导航、按钮和重复文字，SVG 图表还原为组件与关系；PPTX 按页输出标题、要点、表格和备注，跳过隐藏页；DOCX 保留标题层级、列表和表格；XLSX 按可见工作表输出；PDF 去掉页码和重复页眉页脚；超过 30 行的表格只保留前 30 行并附统计。客户端保留范围、大小、格式与二进制限制；原件中的凭据正则检测默认关闭，避免将 HTML 的 JavaScript 变量误识别为令牌。可设置 `HINDSIGHT_UPLOAD_CREDENTIAL_CHECK=1` 重新开启。关闭时真实凭据也可能随原件上传，服务端正文脱敏不代表原件已被脱敏；宏、嵌入二进制及 PDF 的安全导出限制仍保留。

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
HINDSIGHT_API_HTTP_CONCURRENCY=3                # 可选：协调器并发文档数，默认 3
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

把整个 `apps/hindsight-session-ingest` 目录（含 `hermes-plugin/`）放到客户端，用 Python 3 执行：

```bash
python3 install.py                        # 自动安装本机已有的 Codex / Claude Code / Hermes
python3 install.py --agents claude,hermes # 只装指定客户端
python3 install.py --api-url http://127.0.0.1:18888 --bank agent-memory --token-file TOKEN_FILE  # 新电脑
```

| 客户端 | 每轮召回 | 每轮上传 | 安装位置 |
| --- | --- | --- | --- |
| Codex | `UserPromptSubmit` | `Stop` 与 `Interrupt`（被中断的轮次），读 rollout JSONL；下一条提问时后台补传 Stop 未覆盖的轮次 | `~/.codex/hooks.json`；变更后在 Codex 中确认信任 |
| Claude Code | `UserPromptSubmit` | `Stop`，读 `transcript_path`；跳过 `isMeta`、子代理、斜杠命令回显和工具结果 | `~/.claude/settings.json`（`CLAUDE_CONFIG_DIR`） |
| Hermes | 插件 `pre_llm_call`（≤9,000 字符，低于 Hermes 1 万字符转存阈值） | 插件 `post_llm_call` 后台读 `state.db`；`on_session_end` 补中断轮 | `$HERMES_HOME/plugins/hindsight-memory`，并 `hermes plugins enable` |

- 三者共用 `~/.local/lib/hindsight/hindsight-hook.py` 与 `~/.config/hindsight/connection.json`；`connection.json` 不存在时可由参数创建（0600，令牌不回显，也可用 `HINDSIGHT_TOKEN`）。
- Hermes 原文：`active=1` 加上原地压缩归档的 `compacted=1` 原始轮次，去掉压缩摘要、回退轮次和系统提示（模型切换、自动续跑），保留插话（steer）。`hermes serve` 不注册 shell hooks，因此用插件。
- 标题：Codex 读线程库；Claude 用 `/rename` 标题或自动标题，Hermes 用会话标题，并随改名更新；都没有时取首个用户请求。
- 安装器只替换命令中含 `hindsight-hook.py` 的条目，保留 MCORE 等其他钩子；修改前备份（Hermes 插件备份在 `~/.local/lib/hindsight/backups/`，避免被当成插件加载）。新会话生效，正在运行的客户端建议重启。
- 云端无法读取 Windows/WSL 的本地文件，必须在对应机器分别安装。可视化初始化工具负责存量归档和 MCP，不安装实时钩子。

升级时也保留已有 Hindsight 钩子的完整定义（包括解释器路径和超时），避免改变 Codex 已批准的钩子哈希；新增事件（如 `Interrupt`）作为新条目追加，需在 Codex 中审核一次。
提问时的补传只上传转录中已有的内容：转录里还没有助手回复时不上传，避免把待回答的提问单独生成一篇文档。
若钩子显示 `modified`，应恢复先前已批准的定义，或由用户在 Codex 中审核新定义；安装器不自动修改信任记录。

## 成本

内容不变时不重复上传；封闭段无需再次调用模型，变化的末段重提炼。概览输入随段笔记总量增长，因此不能承诺每轮总成本恒定。段笔记和最近原文均相同时复用概览，最终正文与已确认入库版本一致时跳过 retain；原生抽取成本仍取决于 Hindsight 自身的 chunk 切分。产物每个新版本经过 LLM 压缩。

只读预览与评测（输出含真实会话，必须放在 Git 仓库外）：

```bash
python server/preview_sessions.py \
  --source-db /opt/hindsight-research/session-ingest/jobs.sqlite \
  --output /root/project/output/hindsight-preview \
  --session SESSION_ID --run-model
```

预览仅以只读模式查询来源 SQLite；模型调用和缓存写入输出目录中的独立 `preview.sqlite`，从不调用 retain。输出原文/清洗稿/旧稿/新稿、锚点覆盖、模型调用开销、缓存回放结果及 `index.html`。可用 `--rubric PRIVATE_JSON` 指定独立要点检查（仅为词项冒烟，不能证明语义完整），`--attempts 1..3` 控制重试；未生成合格稿或缺失已在原文出现的评测要点时返回非零退出码。重复运行复用已合格段；处理模型或提示词升级后，同一原文重新上传即按版本重建。
