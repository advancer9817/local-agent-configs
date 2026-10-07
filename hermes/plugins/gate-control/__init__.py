"""gate-control Hermes plugin: registers /gate slash command natively."""
import os
from pathlib import Path
from typing import Any

FLAGS_DIR = Path.home() / ".hermes" / "flags"
MODE_FILE = FLAGS_DIR / "gate_mode"
DISABLED_FILE = FLAGS_DIR / "superpowers_gate.disabled"

def get_current_mode() -> str:
    if DISABLED_FILE.exists():
        return "off"
    if MODE_FILE.exists():
        try:
            val = MODE_FILE.read_text(encoding="utf-8").strip().lower()
            if val in ("off", "on", "auto"):
                return val
        except Exception:
            pass
    return "auto"

def handle_gate_slash(raw_args: str = "") -> str:
    FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    arg = str(raw_args).strip().lower() if raw_args else ""

    if not arg or arg == "toggle":
        curr = get_current_mode()
        if curr == "off":
            DISABLED_FILE.unlink(missing_ok=True)
            MODE_FILE.write_text("auto", encoding="utf-8")
            return (
                "🤖 门禁已一键切换为: 【AUTO 智能自适应模式】\n"
                "   • Gemini Flash 全系列等基础模型: ✅ 自动全量注入排版规范 (专为 Flash 防黑盒)\n"
                "   • 高等模型 (Opus / Sonnet / GPT-4o 等): 仅保留硬门禁，自动静默排版废话"
            )
        else:
            DISABLED_FILE.unlink(missing_ok=True)
            MODE_FILE.write_text("off", encoding="utf-8")
            return (
                "⚡ 门禁已一键切换为: 【OFF 强制全关闭】\n"
                "   • 每轮注入 0 字符，解除前置刹车与排版约束，自由直接交付"
            )

    if arg == "off":
        DISABLED_FILE.unlink(missing_ok=True)
        MODE_FILE.write_text("off", encoding="utf-8")
        return (
            "⚡ 门禁与排版规则已【强制全关闭】(FORCE DISABLED)\n"
            "   • 每轮注入 0 字符，彻底解除前置刹车与排版格式约束，自主直接交付"
        )
    elif arg == "on":
        DISABLED_FILE.unlink(missing_ok=True)
        MODE_FILE.write_text("on", encoding="utf-8")
        return (
            "🛡️ 门禁与排版规则已【强制全开启】(FORCE ENABLED)\n"
            "   • 无论任何模型，每轮强制注入硬门禁 + 工具空行自然分段透明规范"
        )
    elif arg == "auto":
        DISABLED_FILE.unlink(missing_ok=True)
        MODE_FILE.write_text("auto", encoding="utf-8")
        return (
            "🤖 门禁与排版规则已切换为【AUTO 智能自适应模式】(默认推荐)\n"
            "   • Gemini Flash 全系列等基础模型: ✅ 自动全量注入排版规范 (专为 Flash 防黑盒)\n"
            "   • 高等模型 (Opus / Sonnet / GPT-4o 等): 仅保留硬门禁，自动静默排版废话"
        )
    elif arg == "status":
        curr = get_current_mode()
        output = [
            "==================================================",
            "  Hermes 门禁与工具排版智能中枢状态汇报",
            "==================================================",
        ]
        if curr == "auto":
            output.extend([
                "📊 当前运行模式: 【AUTO 智能自适应模式】(推荐)",
                "   • Gemini Flash 系列 (gemini-3.8-flash 等低级模型):",
                "     - Superpowers 开工硬门禁: ✅ 生效",
                "     - 工具调用排版约束:       ✅ 自动注入 (空行分段，专为 Flash 防黑盒)",
                "   • 高等模型 (Opus / Sonnet / GPT-4o / Pro 等):",
                "     - Superpowers 开工硬门禁: ✅ 生效",
                "     - 工具调用排版约束:       ❌ 自动静默 (无多余废话)",
            ])
        elif curr == "off":
            output.append("⚡ 当前运行模式: 【OFF 强制全关闭】 (0 字符注入，自由直接交付)")
        elif curr == "on":
            output.append("🛡️ 当前运行模式: 【ON 强制全开启】 (所有模型强制注入硬门禁 + 工具排版规范)")
        output.append("==================================================")
        return "\n".join(output)
    else:
        return "用法: /gate [auto|off|on|status] (直接输入 /gate 可在 OFF 与 AUTO 间一键切换)"

def register(ctx: Any) -> None:
    """Register /gate command into Hermes."""
    ctx.register_command(
        name="gate",
        handler=handle_gate_slash,
        description="Superpowers 门禁与工具排版智能开关 (auto/off/on/status)",
        argument_mode="options",
    )
