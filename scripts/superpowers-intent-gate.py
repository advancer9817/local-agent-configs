#!/usr/bin/env python3
"""Hermes Agent Pre-LLM Hook: Superpowers Intent Gate
Injects high-priority intent clarification and hard-gate instructions before each LLM turn.
"""
import sys
import json
from pathlib import Path

FLAG_FILE = Path.home() / ".hermes" / "flags" / "superpowers_gate.disabled"

def main():
    try:
        raw = sys.stdin.read()
        if raw.strip():
            _ = json.loads(raw)
    except Exception:
        pass

    # 若检测到禁用标志文件，则跳过注入，直接返回空 JSON
    if FLAG_FILE.exists():
        print(json.dumps({}, ensure_ascii=False))
        return

    gate_context = (
        "【Superpowers 意图对齐与开工硬门禁 (Hard-Gate)】\n"
        "1. 严禁未经确认直接动手：面对新需求、功能实现、代码修复、重构或行为变更任务，在获得用户明确批准前，严禁调用 write_file、patch 或任何修改代码的 terminal 命令（只读探索除外）；\n"
        "2. 意图先行：必须遵循 superpowers-brainstorming 与 using-superpowers 规范，先探明真实目的、业务边界与验收标准；\n"
        "3. 方案陈述与刹车：小改动必须在对话中讲清思路（改动点、影响文件、测试方法）并彻底停住（STOP）等待确认；复杂需求提供方案对比；\n"
        "4. 未拿到用户明确的首肯（如“确认/同意/开工”）前，不得擅自跨入实现阶段。"
    )

    output = {
        "context": gate_context
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
