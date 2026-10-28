"""Install the portable upload hook on an already connected Windows/Linux client."""
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
from datetime import datetime

source = Path(__file__).resolve().parent
target = Path.home() / ".local/lib/hindsight"
config = Path.home() / ".config/hindsight/connection.json"
if not config.exists():
    raise SystemExit("This installer requires the client's existing Hindsight connection.json.")
target.mkdir(parents=True, exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
for name in ["hindsight-hook.py", "session_documents.py", "ingest_safety.py"]:
    destination = target / name
    if destination.exists():
        shutil.copy2(destination, destination.with_suffix(destination.suffix + ".bak-" + stamp))
    shutil.copy2(source / name, destination)
hooks_path = Path.home() / ".codex/hooks.json"
if hooks_path.exists():
    shutil.copy2(hooks_path, hooks_path.with_suffix(".json.bak-" + stamp))
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
else:
    hooks = {}
for event, action, timeout in [("UserPromptSubmit", "recall", 45), ("Stop", "retain", 180)]:
    groups = hooks.setdefault("hooks", {}).setdefault(event, [])
    command = [sys.executable, str(target / "hindsight-hook.py"), action, "--agent", "codex"]
    if os.name == "nt":
        import subprocess
        command = subprocess.list2cmdline(command)
    else:
        command = shlex.join(command)
    entry = {"type": "command", "command": command, "timeout": timeout}
    found = False
    for group in groups:
        for index, old in enumerate(group.get("hooks", [])):
            if "hindsight-hook.py" in old.get("command", ""):
                group["hooks"][index] = entry
                found = True
    if not found:
        groups.append({"hooks": [entry]})
hooks_path.parent.mkdir(parents=True, exist_ok=True)
hooks_path.write_text(json.dumps(hooks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Updated Hindsight session titles, session metadata and artifact upload. Existing connection preserved.")
