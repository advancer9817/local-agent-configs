nvm v24;CLIs:codex/claude/opencode/gemini-cli;npm12 allow-scripts~/.npmrc
§
跳板机与远程环境(0909):GCP 34.81.84.197(Debian13,2核8G);Windows别名:ssh google=宿主机:22,ssh google-hermes=沙箱:2222;沙箱RDP走OpenFrp宁德59.60.79.74:57863(0丢包);安全铁律:严禁OpenFrp穿透mcore/HTTP/API(第三方节点无SLA会抓包泄露key),ttyd已退役,3000由ws_tunnel独占;cc-switch.db与settings权限600/700
§
Windows node≥26;npm allow-scripts白名单含claude-code(被拦=占位符);ELECTRON_SKIP_BINARY_DOWNLOAD;winget需--proxy 7890
§
WSL: xrdp 0.10.6.1源码版(3389纯TLS无NLA)+xfce4;ubuntu-desktop已卸,xorg栈hold
§
Desktop=Windows Electron,HERMES_HOME=C:\...\Local\hermes\(desktop-plugins放这);localStorage在Roaming;DSH在WSL:3080;运行中写LevelDB会损坏
§
模型接入(0903):chat主用bigmodel glm-5.3-flash(/api/coding/paas/v4,无/api/v1);编码百炼;Hermes custom_providers=cpa(key_env引.env真key),jizhi/bailian/APIKEY.FUN已剔。cc-switch给Hermes配provider两坑:①base_url须带/v1(缺→404)②占位sk→401,修复后须回写cc-switch.db的settings_config否则切换provider时复写坏值;真key从CPA服务端config的api-keys块找回
§
0902:Clash代理一律127.0.0.1:7890;8MB以上大文件必断;git无代理GitHub直连
§
周报/小结写作偏好：未完成工作必须如实标'推进中/尚未完成'，不得写成已完成（0901用户纠正'都没有完成'）；周期小结要自然段小作文形式——无标题无bullet、简单一点，直接聊天输出，不必生成文档
§
排障铁律(0903):用户实测观察>合成测试绿,取证用真实jsonl/CPA usage.sqlite;过程要快出中间结论,久静默必被催
§
记忆架构(1019):内置MEMORY/USER.md只放全局环境与偏好;外部provider=hindsight(Bank mcore-active-snapshot，传输按用户选择);项目/任务细节在对应skill与Hindsight,旧条目备份MEMORY.md.bak-20261019
§
TPMS测试入口(1021):tpms-test/tpms.aurobaytech.com仅内网split DNS→私网ALB alb-jx3512xpop66hz0k6p(10.244.47.168/38.116);qai.aurobaytech.com→另一私网ALB;公网NXDOMAIN,gpri-tpms.geely.com内外网均不解析;WSL查内网域名用/mnt/c/Windows/System32/curl.exe
§
宿主Win10(19045):WSL无mirrored网络,仅localhostForwarding(wslrelay在WSL监听时抢占Windows同端口,先占者胜,后释放不重试)。Claude Desktop 3P(1021):会话在WSL执行,网关=仅WSL cc-switch(127.0.0.1:15721),Windows cc-switch须托盘退出;~/.config/Claude-3p/configLibrary软链到Windows AppData\Local\Claude-3p\configLibrary
§
GCP核心枢纽地址已由35.236.134.50改为35.194.237.91（2026-10-22，以原可信SSH密钥核验同主机）；ESA相关DNS/回源及Windows/WSL现役客户端已对齐。google别名→新IP:22；sshc→新IP:2224，但沙箱C反向入口当时未恢复，不可把别名更新当链路已通。
§
WSL Google Drive已通过rclone授权，remote=gdrive:，配置~/.config/rclone/rclone.conf（600，含自动续期授权），无默认挂载/同步。访问时需进程级使用Windows代理，宿主地址由WSL默认路由动态获取、端口7890；不注入全局代理。OAuth令牌及回调授权码不输出、不存入记忆；流程详见wsl-environment-ops references/rclone-drive-oauth.md。
§
GCP现役主机35.194.237.91：100GiB外挂盘google-disk-20261021-141952已格式化ext4挂载/data，UUID=6f343e3b-4907-4874-883c-84f30034ffe2，fstab已配置；/data/archive保留原路径层级，存迁移包、旧Hermes备份、CPAMP历史库备份及CPA旧二进制；迁移记录/data/migration-records/，入口root:700，noexec。SSH google用root；远程桌面及实际cc-switch进程属advancer9817，DB=./.cc-switch/cc-switch.db，与/root/.cc-switch独立。用户尚未批准删除普通账号或最终统一方案，不可误当已迁移配置。