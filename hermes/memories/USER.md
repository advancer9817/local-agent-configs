Hermes as general router not SDLC-only. Preserve local UI customizations in mcore/CPA frontend work.
§
User prefers durable learning in lmmcp/MCP plus class-level skill updates. Local Hermes config should be versioned in /home/advancer/project/hermes-local-agent-configs as a sanitized repo excluding secrets/runtime state, with ITERATION.md current.
§
用户希望项目可被他人复用；实现时要优先考虑兼容性、通用性、可移植部署脚本，以及运行命令的执行目录。路径、IP、用户名、项目根目录等不应硬编码，应支持参数、环境变量或自动发现。
§
直接给原始数据/凭据不追问；环境故障全自动后台修复；不喜繁琐确认；中文回复；激进清理无用数据(保护高重要度与已用数据)。
§
交互沟通铁律: 默认全中文，自然说人话; 严禁'正在'/'上步已'等死板标签; 严禁tool_calls时content留空(严禁将推导藏入reasoning当哑巴调用); 调工具时content按序自然输出: ①上步核心结果 ②思考因果中文提炼 ③本步动词动作，随后发起调用; 拿到分水岭事实先判断再转向; 命令单步严禁&&或分号; 严禁可爱风。架构偏好: 业务聚合在程序层，严禁SQL堆复杂函数。
§
千帆报表偏好: 严禁非标bi_*表; 部门对齐sp_cloud.sys_dept规整至第二级中心(禁主观改动原始数据); 全局大盘全量统计(含admin/自测); 部门/人员支持已发布与全量双视角切换; 筛选栏严格单一行水平排列; 未发布不等于0调用(Prometheus与obs双源兜底)。
§
Hermes与CPA联动必须由cc-switch统一管理激活，不得绕过cc-switch直接硬编码改动配置。
§
命令与安全偏好: 排障或操作命令必须单步原子给出，严禁 && 或分号组合; 严禁使用第三方不可信免费穿透传输含Key/敏感数据的明文业务(防抓包泄露); 敏感服务必走自建SSH加密隧道或本地回环; 公网严禁暴露无认证Shell终端; 凭据文件收紧权限(600/700); 偏好大厂纯用户态免tun方案。
§
受控公司电脑约束与桌面规范：用户使用受控公司电脑，严禁安装本地后台服务、第三方虚拟网卡驱动（如 TUN/TAP），严禁在 Windows 桌面上生成未明确要求的快捷方式（.rdp 等桌面图标，用户不喜欢桌面杂乱），必须仅使用系统原生工具（mstsc、原生终端 ssh）。排障或调试时严禁直接通过反向隧道流式传输大文件（易触发 8MB 断流与守护误杀）。
§
UI/桌面偏好：偏好macOS Light浅白风格(#f5f5f7底色、白底黑字终端、彩色交通灯按钮左置)。严禁浏览器原生alert/confirm，交互提示与诊断必须用全局模态弹窗或Toast。远程桌面用纯色背景防重绘卡顿。