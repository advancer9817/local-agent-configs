# cc-switch WSLg 输入法 (IME) 兼容修复

解决 cc-switch 在 WSLg 下「输入框选不了、字打不进去、随后任何按钮都无效、点返回按钮却弹出官网」的问题。

## 根因

**不是 cc-switch 的缺陷**，而是 WebKitGTK 2.40+ 在 Linux 下与输入法框架交互的上游缺陷：

> GTK 探测到系统已安装 `fcitx5` / `ibus` 的 IM 模块，但对应的输入法守护进程**并没有运行**。
> 输入框获得焦点进入 IME 组合态时，`WebKitWebProcess` 被挂死，
> 导致整个 WebView 之后**所有交互（包括按钮点击）全部失效**。

上游 issue：`farion1231/cc-switch` **#7059**、**#349**、**#3897**（均 Open）。

本机命中条件（三者同时成立）：

1. `libwebkit2gtk-4.1-0 >= 2.40`（Ubuntu 24.04 为 2.52.x）
2. GTK IM 模块目录存在 `im-fcitx5.so` / `im-ibus.so`
3. `fcitx5` / `ibus-daemon` 未运行

## 修复内容

强制 GTK 退回内置的简单输入上下文，绕开 IME 组合态路径：

```bash
export GTK_IM_MODULE="${GTK_IM_MODULE:-gtk-im-context-simple}"
export QT_IM_MODULE="${QT_IM_MODULE:-simple}"
export XMODIFIERS="${XMODIFIERS:-@im=none}"
```

## ⚠ 为什么必须同时改桌面项

`/etc/environment` 的 PATH 通常**不含** `~/.local/bin`。因此：

| 启动方式 | 实际落地 | 是否经过包装脚本 |
|---|---|---|
| 终端 `cc-switch start` | `~/.local/bin/cc-switch` | ✅ 是 |
| Windows 开始菜单 / 桌面图标 | `/usr/bin/cc-switch` | ❌ **绕过** |
| 深链接 `ccswitch://` | `/usr/bin/cc-switch %u` | ❌ **绕过** |

**只改包装脚本不够** —— 从开始菜单启动仍会命中未修复的二进制。
本修复因此同时写入**用户级桌面项覆盖**（与系统项同名，优先生效，无需 sudo）。

## 安装

```bash
./install.sh --check     # 先做环境自检，不改动任何文件
./install.sh             # 安装
```

自定义位置：

```bash
BIN_DIR=/somewhere/bin APP_DIR=/somewhere/applications ./install.sh
```

## 验证

安装后重启应用：

```bash
cc-switch restart
```

然后读**运行进程的真实环境**（不是脚本内容）：

```bash
PID=$(pgrep -f "^/usr/bin/cc-switch" | head -1)
tr '\0' '\n' < "/proc/${PID}/environ" | grep -E "^(GTK_IM_MODULE|QT_IM_MODULE|XMODIFIERS)="
```

期望输出：

```
GTK_IM_MODULE=gtk-im-context-simple
QT_IM_MODULE=simple
XMODIFIERS=@im=none
```

**无输出** ⇒ 应用从某个未覆盖的入口启动了，检查 `~/.local/share/applications/` 与
`/usr/share/applications/` 中是否有同名 `.desktop` 且 `Exec` 直呼二进制。

## 回滚

```bash
rm -f ~/.local/share/applications/"CC Switch.desktop"
rm -f ~/.local/share/applications/cc-switch-handler.desktop
rm -f ~/.local/bin/cc-switch
```

三处改动互相独立，可单独撤销。本修复**不触碰** `~/.cc-switch/`（provider 配置库），数据面无风险。

## 注意事项

- **不要删掉这 3 个变量。** 若将来真的安装了 fcitx5/ibus 并常驻运行，可改为只设 `XMODIFIERS`，
  或在包装脚本中做条件判断（检测到守护进程则不走 simple 路径）。
- 升级 cc-switch 会覆盖 `/usr/share/applications/CC Switch.desktop`，
  但**用户级覆盖文件仍在**，修复不会因升级丢失；`~/.local/bin/cc-switch` 亦不在 deb 文件清单内。

## 同类症状判别口诀

> **故障由点输入框触发 + 触发后整页死锁 → 先怀疑 WebKitGTK / IME。**
> 只有「个别控件落空、误差随离窗口原点距离增长」才指向坐标缩放。
