nvm v24;CLIs:codex/claude/opencode/gemini-cli;npm12 allow-scripts~/.npmrc
§
跳板机与远程环境(0909):GCP 34.81.84.197(Debian13,2核8G);Windows别名:ssh google=宿主机:22,ssh google-hermes=沙箱:2222;沙箱RDP走OpenFrp宁德59.60.79.74:57863(0丢包);安全铁律:严禁OpenFrp穿透mcore/HTTP/API(第三方节点无SLA会抓包泄露key),敏感业务/MCP/Hook一律走127.0.0.1或SSH加密映射;ttyd已退役,3000由ws_tunnel独占;cc-switch.db与settings权限600/700
§
mcore推送=git syncpush(pitfall19);remote=github.com/advancer9817/memorycore
§
CPA Kiro fix见local-ai-proxy-gateway-ops skill;BrightData brd.superproxy.io:33335;meiguodizhi.com信用卡MM/YY
§
Windows node≥26;npm allow-scripts白名单含claude-code(被拦=占位符);ELECTRON_SKIP_BINARY_DOWNLOAD;winget需--proxy 7890
§
WSL: xrdp 0.10.6.1源码版(3389纯TLS无NLA)+xfce4;ubuntu-desktop已卸,xorg栈hold
§
Desktop=Windows Electron,HERMES_HOME=C:\...\Local\hermes\(desktop-plugins放这);localStorage在Roaming;DSH在WSL:3080;运行中写LevelDB会损坏
§
§Desktop闪烁闭案(0901)已修复,ws-cycle-watch.sh监控
§
千帆培训资产在Desktop/output/千帆培训-流程图/;课件HORSE-AI模板(绿#A0B649/蓝#1795BA);教案:文档处理大师→周报助手→完整版;PPT配图横向
§
模型接入(0903):chat主用bigmodel glm-5.3-flash(/api/coding/paas/v4,无/api/v1);编码百炼;Hermes custom_providers=cpa(key_env引.env真key),jizhi/bailian/APIKEY.FUN已剔。cc-switch给Hermes配provider两坑:①base_url须带/v1(缺→404)②占位sk→401,修复后须回写cc-switch.db的settings_config否则切换provider时复写坏值;真key从CPA服务端config的api-keys块找回
§
tpms=F:\Code\tpms(无git);mvn -o -llr;syncUser终版0901=非流式+批量落库+岗位缓存+dept修复;库=rm-bp188835co8lm1400/sp_cloud;CDP:9222保留版;WSL无DISPLAY
§
千帆调试偏好:排错只给单节点修复源码供手动复制(禁反复打包zip);代码解释器直接给明文Python禁base64打包;最小改动原则
§
qai-report项目在F:\Code\qai-report(Dockerfile-NF+deploy-ali.yml→阿里云K8s, 入口uvicorn main:app); 表全qai_前缀(RDS rm-bp188835co8lm1400/tpms); 用户组织链路=teamList(u-xxx→域账号)+tpms.bi_user_ac_info(域账号→ORG/PATH), sp_cloud.sys_user.dept_id horse域全NULL勿用; qai域名→10.244.58.17绕Clash
§
0902:Clash代理一律127.0.0.1:7890;8MB以上大文件必断;git无代理GitHub直连
§
§mcore UI偏好:维护预览要全量候选列表(纯抽样被打回);按钮文案区分选项tab与执行按钮;指标值必须与标签语义一致(误标被打回,迭代41)
§
周报/小结写作偏好：未完成工作必须如实标'推进中/尚未完成'，不得写成已完成（0901用户纠正'都没有完成'）；周期小结要自然段小作文形式——无标题无bullet、简单一点，直接聊天输出，不必生成文档
§
mcore ITERATION编号0902冻结[1~208]禁重排;新条目=最大+1;映射docs/iteration-number-map-2026-09-02.md
§
体检批量(0902)在project/qianfan/health-check-analysis:文档解析(text=JSON信封,cells+matrix,还原code实测PASS)+循环array task10 3路;最终=汇总回填原花名册xlsx;坑:①code输出声明string须json.dumps否则code_output:null;②agent返markdown表→包装双通道+clean_txt;③花名册URL只能从系统fileUrls拿;④导入失败=外部agent引用→LLM占位+config精简;⑤双def坑
§
CPA(0903):CLIProxyAPI v7.2.147+CPAM v1.12.8已reset对齐upstream;部署=.deploy二进制+user systemd cpa-proxy(8317)/cpa-manager-plus(18317),8317面板走CLIProxyAPI/static/management.html勿动;CPAM管理员凭据在data/usage.sqlite settings.admin_credential_v1(env key仅首次种子);go拉大模块zip必断流,curl -C -断点续传塞GOMODCACHE后go build补齐
§
CPA升级铁律(0903用户严令记住):重编二进制必须注入版本ldflags,否则面板内核版本=dev、构建时间=Invalid Date被打回。CLIProxyAPI官方release姿势(release.yaml): -ldflags "-s -w -X main.Version=${REL_VER} -X main.Commit=${COMMIT} -X main.BuildDate=${BUILD_DATE}" (REL_VER=git describe去v去后缀,COMMIT=short SHA,BUILD_DATE=date -u +%Y-%m-%dT%H:%M:%SZ,CGO_ENABLED=1);CPAM web端VERSION=npm run build env注入,manager-server照package-native.sh
§
claude WSL修复(0903):已装三层=wsl-interop-binfmt.service(开机补binfmt)+/usr/local/bin/claude守门wrapper(拒/mnt/c)+wsl.conf appendWindowsPath=false(待WSL重启生效);根因=WSL#8842 binfmt竞态+zsh hash缓存/mnt/c shim;nvm下claude.exe是真Linux ELF,本地2.1.222/Win2.1.258靠版本分辨
§
CPA antigravity思考可见性已闭环(0903):①Hermes oneshot.py漏传reasoning_config已修(备份hermes-cpa-gemini-reasoning-fix-20260903.patch);②CPA d4b97e55默认includeThoughts,已按铁律重编部署7.2.147,任何客户端默认可见思考(短思考<100tok固有省略);遗留:模型表13仅4真路由;抓包法=skill cpa-antigravity-reasoning-streaming.md(用完必关);档案=Desktop/output/cpa-gemini-thinking-handoff-prompt.md
§
CPA仓库状态(0907全量对齐上游): CPA=v7.2.152/c76dfd4e(放弃0904 EOF补丁,tag local/eof-fix-backup留底,升级后EOF=0无回归); CPAMP=v1.12.9/58256f62; 41 antigravity账号0错误加载; 升级后离线cleanup-derived清12索引+1任务; 回滚备份=.deploy/*.bak-20260907_*; 大版本升级后面板必现数据库维护横幅属正常
§
排障铁律(0903):用户实测观察>合成测试绿,取证用真实jsonl/CPA usage.sqlite;过程要快出中间结论,久静默必被催
§
mcore memory_context瘦身已闭环(0904迭代220): P0/P1/P2落地,默认slim(只context+warnings),信封体积降98.6%;verbose=True由UI及测试使用,合并trace/quality为telemetry并删used_ids/sections/budget_chars;ContextLab字段补齐防toFixed报错;全量单测613通过,tools.md同步刷新;已git syncpush remote main对齐
§
qai-report运维(0909):采集已优化(Keep-Alive池+4并发压缩至40-70s且个人空间零漏采);凭据只认idaas-sessionid;严禁非标bi_*表,纯正sys_user.dept_id外键+sys_dept祖先树规整至二级中心;跑creator_backfill;报表双口径秒切;调用量以request_quantity为准由程序层聚合;K8s定时0904停摆靠手动补