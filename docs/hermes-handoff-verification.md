# Hermes 交接工具：集成与验证报告

## 项目集成

工具位于本配置项目的 `scripts/hermes_handoff.py`，从脚本位置发现仓库，不硬编码用户路径、IP 或 Git 地址。README 提供入口，完整安装与日常交接见 `docs/hermes-handoff.md`。

新增依赖：cryptography、PyYAML。Python 3.10+；Linux/WSL。使用独立 venv，不安装服务、驱动或桌面快捷方式。

## 真实执行结果

普通 WSL（非隔离 PID namespace）运行：

```bash
python3 -m unittest discover -s tests -p test_hermes_handoff.py -v
```

```text
Ran 45 tests in 31.122s
OK
```

真实 Hermes 目录的初始化前诊断：

```bash
python3 scripts/hermes_handoff.py doctor
```

```text
doctor: not initialized; dependencies, home and shared config OK. Run init --device ALIAS, then doctor again with Hermes stopped.
```

`git diff --check` 通过。诊断不创建密钥、receipt 或交接包。

集成收尾复跑：Hermes venv 的 Python 3.11.15，cryptography 50.0.0、PyYAML 6.0.3，45 tests / 22.751s / OK；真实目录 `doctor` 再次成功。当前默认 `python3` 切换至 Python 3.14 后缺少 cryptography，直接调用会导入失败；这属于解释器依赖差异。部署时使用指南要求的 `.venv-handoff/bin/python`，不要依赖默认 PATH 中的 Python。

## 验证覆盖

- 临时公司端 / 家里端 Hermes homes，真实 SQLite 数据与 FTS5 表。
- 两个 Git clones 与本地 bare remote：出发提交/推送、到达拉取、往返聊天一致、remote HEAD 读回一致。
- API Key 和 MCP 本机配置保留，`.env` 和 auth 不导出，模型字段不覆盖。
- skills 执行权限保留及恢复后直接运行脚本。
- 初次显式 bootstrap、同设备身份拒绝、重复到达 no-op、重复出发拒绝。
- 冻结后数据库漂移阻断，纯 Key 轮换不误报，WAL checkpoint 不误报。
- 错密钥、密文/元数据篡改、清单校验失败、路径穿越、重复 ZIP 路径、符号链接拒绝。
- 配置白名单、严格类型检查、旧字符串 true/false 兼容、包容量约束。
- 打开的数据库 FD 阻断、锁冲突阻断、未知不可读同用户进程阻断；已退出僵尸和明确 systemd 会话管理组件不误报。
- 恢复失败回滚原文件、原权限和 receipt，保留本地备份。
- 脏 Git / 暂存区 / 本地 ahead 阻断，限定提交文件，不带入其他提交。
- push 失败保留 departed/pending；显式重试只发布原交接提交并验证远端。

所有 fixture 数据都为假的聊天和凭据；网络副作用仅发生于临时本地 bare remote。

## 尚未执行，不应宣称完成

- 未在真实 Hermes home 初始化密钥或设备身份。
- 未导出/恢复真实全量会话；真实 state.db 仅检查了文件大小（252,448,768 字节），未读取聊天正文。
- 未在第二台实体电脑执行；需对齐 Hermes 版本与本机模型/MCP 配置。
- 未提交或推送本配置仓库；原有未提交 ITERATION 内容保留。
- 未同步项目代码、附件、绝对路径、其他 Profile 或 MemoryCore 库。
- 未实现自动关机触发、后台定时同步、自动停止 Hermes 服务；入口是使用者明确执行命令。
- `AGENTS.md` 写入审批未通过，未写入，不绕过保护；当前通过 README / docs 提供操作说明，不能承诺所有 Agent 自动加载规则。

## 容量与运行限制

展开内容上限 512 MiB，密文文件上限 700 MiB，文件数上限 5000。界限用于拒绝异常包，不表示所有 Git 服务都允许如此大的单文件。GitHub 等有自己的单文件限制；首次真实导出需检查最终 `latest.enc` 的大小，超限应改用获准的 LFS / 加密备份存储，不强推或绕过公司网络政策。打包在内存中进行，大库需足够空闲内存和磁盘备份空间。

恢复具备普通异常回滚，但不是整个 home 的文件系统级原子事务；电源故障/强制终止仍需从本地备份人工恢复。离线检测是保守进程检查，不是防止外部程序启动的系统沙箱。两个电脑必须遵循单写端交接纪律。
