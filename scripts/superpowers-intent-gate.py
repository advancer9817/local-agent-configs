#!/usr/bin/env python3
"""Hermes Agent Pre-LLM Hook: Superpowers Intent Gate & Tool Formatting Router
Injects high-priority intent clarification and hard-gate instructions before each LLM turn.
Supports:
  - Mode override via ~/.hermes/flags/gate_mode ('off', 'on', 'auto', default: 'auto')
  - In 'auto' mode:
      - Advanced models (opus, sonnet, gpt-4o, o1, o3, gpt-5, pro): inject only hard-gate (clean, no verbose tool formatting)
      - Basic/Flash models (Gemini Flash 全系列等小模型): 自动全量注入硬门禁 + 工具排版透明规范（专为 Flash 防黑盒设计）
"""
import sys
import json
from pathlib import Path

FLAGS_DIR = Path.home() / ".hermes" / "flags"
MODE_FILE = FLAGS_DIR / "gate_mode"
DISABLED_FILE = FLAGS_DIR / "superpowers_gate.disabled"

HARD_GATE_CONTEXT = (
    "【Superpowers 意图对齐与开工硬门禁 (Hard-Gate)】\n"
    "1. 严禁未经确认直接动手：面对新需求、功能实现、代码修复、重构或行为变更任务，在获得用户明确批准前，严禁调用 write_file、patch 或任何修改代码的 terminal 命令（只读探索除外）；\n"
    "2. 意图先行：必须遵循 superpowers-brainstorming 与 using-superpowers 规范，先探明真实目的、业务边界与验收标准；\n"
    "3. 方案陈述与刹车：小改动必须在对话中讲清思路（改动点、影响文件、测试方法）并彻底停住（STOP）等待确认；复杂需求提供方案对比；\n"
    "4. 未拿到用户明确的首肯（如“确认/同意/开工”）前，不得擅自跨入实现阶段。"
)

TOOL_FORMAT_CONTEXT = (
    "【工具调用伴随透明规范】\n"
    "1. 严禁空 content 黑盒响应：发起工具调用时文本严禁留空或为 0 字符，严禁仅在内部 thinking 推导而对外做哑巴调用；\n"
    "2. 换行空行自然分段：每次调用工具前面向用户的文本严格通过换行空行自然分成 2~3 段呈现（事实 -> 因果决策 -> 动作意图），严禁挤占在单一行内；\n"
    "3. 严禁死板八股：严禁 123 或 ①②③ 等任何数字符号序号，严禁“上步/上一步”、“思考推导：”等机械前缀。"
)

# 高等智能模型关键字（命中时自动静默排版约束）
# 铁律：严禁包含 flash！Gemini 全系列 flash 模型全部纳入低级模型，本输出约束专为他而生！
ADVANCED_MODEL_KEYWORDS = [
    "opus",
    "sonnet",
    "gpt-4o",
    "gpt-5",
    "o1",
    "o3",
    "pro",
]

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

def is_advanced_model(model_name: str) -> bool:
    if not model_name:
        return False
    lower_name = model_name.lower()
    # 铁律：所有包含 flash 的模型（包括 gemini-3.8-flash 等）全部一票否决，归入需要排版约束的基础模型！
    if "flash" in lower_name:
        return False
    return any(kw in lower_name for kw in ADVANCED_MODEL_KEYWORDS)

def main():
    model_name = ""
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
            if isinstance(payload, dict):
                model_name = payload.get("model", "") or ""
    except Exception:
        pass

    mode = get_current_mode()

    if mode == "off":
        # 彻底静默，注入 0 字符
        print(json.dumps({}, ensure_ascii=False))
        return

    if mode == "on":
        # 强制全开：同时注入硬门禁与工具排版规范
        combined = f"{HARD_GATE_CONTEXT}\n\n{TOOL_FORMAT_CONTEXT}"
        print(json.dumps({"context": combined}, ensure_ascii=False))
        return

    # auto 自适应模式：根据模型智商分流
    if is_advanced_model(model_name):
        # 高等模型 (Opus / Sonnet / GPT-4o 等): 仅保留硬门禁防擅改，自动静默排版格式
        print(json.dumps({"context": HARD_GATE_CONTEXT}, ensure_ascii=False))
    else:
        # Gemini Flash 全系列等基础模型: 自动全量注入排版规范，防黑盒哑巴调用！
        combined = f"{HARD_GATE_CONTEXT}\n\n{TOOL_FORMAT_CONTEXT}"
        print(json.dumps({"context": combined}, ensure_ascii=False))

if __name__ == "__main__":
    main()
