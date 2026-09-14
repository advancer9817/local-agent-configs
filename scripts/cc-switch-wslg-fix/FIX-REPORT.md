# cc-switch (WSLg) 输入框卡死 / 点击失效 — 修复报告

生成时间：2026-09-14 09:24:08
报告环境：WSL2 + WSLg(RDP RAIL) / Ubuntu 24.04.4 LTS / cc-switch 3.20.2 (Tauri + WebKitGTK)
结论状态：**根因已定位，修复已由用户实测确认生效**

---

## 1. 一句话结论

cc-switch「输入框选不了、字打不进去、点返回按钮却弹出官网」**不是 cc-switch 的缺陷**，
而是 **WebKitGTK 2.40+ 在 Linux 下与输入法框架交互的已知上游缺陷**：

> GTK 探测到系统已安装 `fcitx5` / `ibus` 的 IM 模块，但对应的输入法守护进程**并没有运行**。
> 当 WebView 中的输入框获得焦点并进入 IME 组合态时，`WebKitWebProcess` 被挂死，
> 导致整个 WebView 之后**所有交互（包括按钮点击）全部失效**。

强制回退到 GTK 内置的简单输入上下文（3 个环境变量）即修复。

---

## 2. 症状

| 现象 | 说明 |
|---|---|
| 输入框无法聚焦、无法输入 | 点击任何输入框均无光标、无字符 |
| 随后所有按钮失效 | 一旦点过输入框，连「保存 / 返回」等按钮也点不动 |
| 点返回按钮弹出浏览器 | 表现为误触发界面上的链接元素，拉起外部浏览器 |
| 重启应用后短暂可用 | 再次碰到输入框即复发 |

**关键判据**：故障由「点过输入框」这一动作**触发**，触发后整页交互死锁。这是 IME 组合态挂死的典型特征。

---

## 3. 环境基线（实测）

| 项 | 值 | 取证命令 |
|---|---|---|
| 发行版 | Ubuntu 24.04.4 LTS (Noble Numbat) | `grep VERSION= /etc/os-release` |
| 内核 | 6.18.33.2-microsoft-standard-WSL2 | `uname -r` |
| cc-switch | **3.20.2**（deb 安装） | `dpkg-query -W cc-switch` |
| WebKitGTK | **libwebkit2gtk-4.1-0 = 2.52.6-0ubuntu0.24.04.1** | `dpkg-query -W libwebkit2gtk-4.1-0` |
| GTK3 | libgtk-3-0t64 = 3.24.41-4ubuntu1.3 | `dpkg-query -W libgtk-3-0t64` |
| WSLg 合成器 | `--backend=rdp-backend` + `--shell=rdprail-shell` | `ps -eo cmd \| grep weston` |
| 显示缩放 | DPI = 96（**100%**） | Windows `GetDeviceCaps(...,88)` |
| 已装 IM 模块 | `im-fcitx5.so`、`im-ibus.so` | 检查 `/usr/lib/x86_64-linux-gnu/gtk-3.0/3.0.0/immodules/` |
| 运行中的 IM 守护进程 | **无**（fcitx / ibus 均未运行） | `ps -eo cmd \| grep -E "fcitx\|ibus-daemon"` |

> ⚠ **`libwebkit2gtk-4.1-0` 版本 2.52.6 与上游 issue #7059 报告的环境完全一致** —— 同一缺陷。

---

## 4. 根因

### 4.1 上游证据

| 来源 | 内容 |
|---|---|
| farion1231/cc-switch **#7059** | `Linux + fcitx5 + WebKitGTK 2.52：点击"添加 → 自定义"时 WebKitWebProcess 卡死` |
| farion1231/cc-switch **#349** | `点击任意输入框后界面卡死`（Open） |
| farion1231/cc-switch **#3897** | `ubuntu 和 kali 用 ccswitch 在编辑时会卡死`（Open） |

**#7059 的受控实验结论**：

| 启动方式 | 结果 |
|---|---|
| 默认（不设 IM 变量） | 点输入框 → **卡死** |
| 设置 3 个 IM 环境变量 | **不再卡死，恢复正常** |

### 4.2 本机为何命中

cc-switch 是 Tauri 应用，UI 跑在 WebKitGTK 里。本机同时满足触发条件：

1. GTK3 的 IM 模块目录里**存在** `im-fcitx5.so` / `im-ibus.so` → GTK 会自动探测并尝试加载；
2. 但 `fcitx5` / `ibus-daemon` **并未运行** → IM 上下文无法建立；
3. 输入框获得焦点时，WebKit 进入 IME 组合态并阻塞等待 IM 后端 → `WebKitWebProcess` 挂死。

GTK 对 `GTK_IM_MODULE` 未显式设置时的**自动探测行为**，是本缺陷的开关。

### 4.3 完整因果链

```
点击输入框
   └─> WebKit 请求 IC（输入上下文）
        └─> GTK 自动探测到 fcitx5/ibus IM 模块
             └─> 尝试连接对应守护进程 —— 不存在
                  └─> IME 组合态阻塞，WebKitWebProcess 挂死
                       └─> WebView 停止响应一切事件
                            └─> 症状：按钮全失效 / 点击被误判落到链接上 → 拉起浏览器
```

---

## 5. 排查中被证伪的假设（诚实记录）

本次排查走了两条弯路，结论均被**实测推翻**，记录在此以免后人重走：

| 假设 | 曾据以立论 | 证伪方式 |
|---|---|---|
| **125% 分数缩放导致输入坐标错位** | Windows DPI=120，WSLg 日志 `clientScale:1.00`（把 125% 取整丢弃）；上游 microsoft/wslg#23 称 WSLg 只支持 100%/200% | 用户实测把缩放改成 **100%（DPI=96）并重启 WSL 后，故障依旧** → 缩放非根因 |
| **点击落点存在系统性坐标偏移** | weston 日志恒定 `view = XWM - (32,32)`；早期误读的 (568,-541) 偏移 | X 指针强移 4 点后 Windows 光标纹丝不动（**X→Windows 无指针回传**），该读数系 X 指针陈旧冻结造成的假象，已撤回 |
| **cc-switch 3.20.1 版本缺陷** | 重装后问题仍在 | 升级/覆盖安装（3.20.1 → 3.20.2）**未改变症状**；上游 3.20.3 的发布说明亦无任何 Linux 输入相关改动 |

> 教训：**症状"点击无效"不等于"点击落点错误"**。
> 本次真正的判别性事实是——故障**由点过输入框触发**，且触发后**整页死锁**（而非个别按钮落空）。
> 前者指向 WebProcess 挂死，后者才指向坐标变换。

---

## 6. 修复方案

### 6.1 核心修复：3 个环境变量

```bash
export GTK_IM_MODULE=gtk-im-context-simple   # 强制 GTK 内置简单输入上下文
export QT_IM_MODULE=simple                   # 同上（Qt 侧）
export XMODIFIERS=@im=none                   # 禁用 XIM
```

作用：**绕开 IME 组合态路径**，让输入框不再等待输入法后端，WebProcess 不再挂死。

### 6.2 ⚠ 关键坑：两条启动路径必须同时覆盖

本机 `/etc/environment` 的 PATH 为：

```
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin
```

**不包含 `~/.local/bin`**。后果：

| 启动方式 | 实际落地 | 是否经过包装脚本 |
|---|---|---|
| 终端 `cc-switch start` | `~/.local/bin/cc-switch`（包装脚本） | ✅ 是 |
| Windows 开始菜单 / 桌面项 | `/usr/bin/cc-switch`（真实二进制） | ❌ **否，绕过** |
| 深链接 `ccswitch://` | `/usr/bin/cc-switch %u` | ❌ **否，绕过** |

**只改包装脚本不够** —— 从开始菜单启动仍然命中未修复的二进制。必须同时覆盖桌面项。

### 6.3 落地清单

**① 包装脚本** `~/.local/bin/cc-switch`（所有 CLI 调用路径的公共入口）

在 `WEBKIT_DISABLE_*` 之后插入：

```bash
# 输入法兼容 (上游 issue #7059 / #349): WebKitGTK 2.40+ 在 Linux 下挂载输入框时,
# 若 GTK 探测到 fcitx5/ibus 的 IM 模块而对应守护进程并未运行, WebKitWebProcess 会挂死
# ——现象即"点击任意输入框后界面卡死/无法输入, 随后所有按钮失效"。
# 强制退回 GTK 内置的简单输入上下文, 绕开 IME 组合态路径。
export GTK_IM_MODULE="${GTK_IM_MODULE:-gtk-im-context-simple}"
export QT_IM_MODULE="${QT_IM_MODULE:-simple}"
export XMODIFIERS="${XMODIFIERS:-@im=none}"
```

**② 桌面项（用户级覆盖，无需 sudo）**

| 文件 | 作用 |
|---|---|
| `~/.local/share/applications/CC Switch.desktop` | 覆盖系统 `/usr/share/applications/CC Switch.desktop`，令 `Exec` 指向包装脚本 |
| `~/.local/share/applications/cc-switch-handler.desktop` | 深链接处理器，原 `Exec` 直呼 `/usr/bin/cc-switch`，需一并改指向包装脚本 |

`Exec` 改为：

```ini
Exec=<HOME>/.local/bin/cc-switch %u
```

**③ 重启应用**

```bash
cc-switch restart
```

---

## 7. 验证

### 7.1 进程级实证（决定性）

修复后**读取运行进程真实的继承环境**，而非只看脚本静态内容：

```bash
PID=$(pgrep -f "^/usr/bin/cc-switch" | head -1)
tr '\0' '\n' < "/proc/${PID}/environ" | grep -E "^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)="
```

实测输出（PID 5735）：

```
GTK_IM_MODULE=gtk-im-context-simple
QT_IM_MODULE=simple
XMODIFIERS=@im=none
```

**这三个变量真实进入了运行中的应用** —— 修复已生效于目标进程，不是"改了文件但没重启"。

### 7.2 用户实测确认

用户在修复后实际操作 cc-switch 输入框，确认恢复正常。

> 口径说明：本次修复的最终确认来自**用户真实鼠标键盘操作**。
> 助手侧的合成输入（Windows `SetCursorPos`/`SendInput`、XTest）**无法等价替代真实输入路径**，
> 故不单独作为结案依据。

---

## 8. 回滚

三处改动均可独立撤销，互不影响：

| 改动 | 回滚 |
|---|---|
| 包装脚本 | 删除 3 行 `export`，或 `git checkout` 仓库内版本 |
| `CC Switch.desktop` | `rm ~/.local/share/applications/"CC Switch.desktop"` → 回落系统项 |
| `cc-switch-handler.desktop` | 删除用户级文件，恢复系统默认 |

数据面无风险：本次修复**不触碰** `~/.cc-switch/`（provider 配置库）。

---

## 9. 复发规避

1. **不要删掉这 3 个变量**。若将来真的安装了 fcitx5/ibus 输入法并常驻运行，可改为只设 `XMODIFIERS`，
   或在包装脚本中做条件判断（检测到守护进程则不走 simple 路径）。
2. **安装 cc-switch 新版本后会覆盖 `/usr/share/applications/CC Switch.desktop`，但用户级覆盖文件仍在**，
   修复不会因升级丢失；`~/.local/bin/cc-switch` 亦不在 deb 文件清单内，升级同样保留。
3. 同类症状判别口诀：**故障由点输入框触发 + 触发后整页死锁 → 先怀疑 WebKitGTK/IME**，
   不要一上来怀疑坐标缩放。

---

## 附录 A — 证据清单

| 证据 | 位置 / 值 |
|---|---|
| 修复后进程真实环境 | `/proc/5735/environ` |
| 包装脚本（已修复） | `~/.local/bin/cc-switch` |
| 桌面项覆盖 | `~/.local/share/applications/CC Switch.desktop` |
| 深链接处理器 | `~/.local/share/applications/cc-switch-handler.desktop` |
| 应用日志 | `~/.cc-switch/logs/cc-switch-gui.log` |
| WSLg 日志 | `/mnt/wslg/weston.log` |
| 数据备份 | `~/.cc-switch.bak-reinstall-20260911/`（db 7.0M） |
| 界面截图 | 本目录 `after-im-fix.png`、`hov-300-219.png`、`cp-after-delay.png`、`verify-final.png` |
| 上游 issue | #7059、#349、#3897 |

## 附录 B — 命令速查

```bash
# 重启并应用修复
cc-switch restart

# 确认修复已进入运行进程
PID=$(pgrep -f "^/usr/bin/cc-switch" | head -1)
tr '\0' '\n' < "/proc/${PID}/environ" | grep -E "^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)="

# 若无输出 → 说明是从桌面项启动了未覆盖的路径, 检查 ~/.local/share/applications/
```
