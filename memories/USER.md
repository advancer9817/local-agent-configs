Hermes as general router not SDLC-only. Preserve local UI customizations in mcore/CPA frontend work.
§
User prefers durable learning in lmmcp/MCP plus class-level skill updates. Local Hermes config should be versioned in /home/advancer/project/hermes-local-agent-configs as a sanitized repo excluding secrets/runtime state, with ITERATION.md current.
§
User prefers deliverables in C:\Users\e-pengyang.DU\Desktop\output (WSL /mnt/c/Users/e-pengyang.DU/Desktop/output), EXCEPT 工作周报 xlsx → C:\Users\e-pengyang.DU\Documents\工作周报 (WSL /mnt/c/Users/e-pengyang.DU/Documents/工作周报).
§
项目可移植: 严禁硬编码路径/IP/用户名，优先支持参数化或环境变量。仓库默认在/home/advancer/project/。
§
直接给原始数据/凭据不追问；连接故障全自动修复；不喜繁琐确认；激进清理无用数据。
§
交互沟通: 默认全中文；交代动作去主语、严禁'正在/我正在'前缀，直述要做什么；重大决策/排障核心/方案取舍输出详实长文本深入剖析；命令单步原子化严禁&&或分号。程序层聚合计算，禁SQL堆复杂函数。
§
千帆报表: 禁非标bi_*表; 部门对齐sys_dept规整至二级中心; 全量统计(含自测); 支持已发布/全量双视角; 筛选单行; 未发布不等于0。
§
Hermes与CPA联动必须由cc-switch统一管理激活，不得绕过cc-switch直接硬编码改动配置。
§
命令与安全偏好: 排障或操作命令必须单步原子给出，严禁 && 或分号组合; 严禁使用第三方不可信免费穿透传输含Key/敏感数据的明文业务(防抓包泄露); 敏感服务必走自建SSH加密隧道或本地回环; 公网严禁暴露无认证Shell终端; 凭据文件收紧权限(600/700); 偏好大厂纯用户态免tun方案。
§
受控电脑规范: 禁装后台服务/虚拟网卡(TUN/TAP); 桌面禁建快捷方式图标; 仅原生工具(mstsc/ssh); 反向隧道禁流传大文件(防8MB断流)。
§
UI/桌面偏好：偏好macOS Light浅白风格(#f5f5f7底色、白底黑字终端、彩色交通灯按钮左置)。严禁浏览器原生alert/confirm，交互提示与诊断必须用全局模态弹窗或Toast。远程桌面用纯色背景防重绘卡顿。