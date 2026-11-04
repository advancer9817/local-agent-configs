"""Install Hindsight per-turn recall and upload for Codex, Claude Code and Hermes on Windows/Linux.

python3 install.py                       # every agent found on this machine
python3 install.py --agents claude,hermes
python3 install.py --api-url http://127.0.0.1:18888 --bank BANK --token-file FILE   # first install

Existing hooks, plugins and connection settings are kept; every changed file is backed up first.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from datetime import datetime

SOURCE = Path(__file__).resolve().parent
TARGET = Path.home() / ".local/lib/hindsight"
CONNECTION = Path(os.environ.get("HINDSIGHT_CONNECTION_FILE", str(Path.home() / ".config/hindsight/connection.json")))
FILES = ["hindsight-hook.py", "session_documents.py", "ingest_safety.py"]
PLUGIN = "hindsight-memory"
ALLOWED = ("http://127.0.0.1:", "http://35.194.237.91:")
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def homes():
    return {"codex": Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"),
            "claude": Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"),
            "hermes": Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")}


def backup(path, directory=None):
    if path.exists():
        copy = (directory or path.parent) / (path.name + ".bak-" + STAMP)
        copy.parent.mkdir(parents=True, exist_ok=True)
        if path.is_dir():
            shutil.copytree(path, copy, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(path, copy)


def write_text(path, text, private=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp-" + STAMP)
    temporary.write_text(text, encoding="utf-8")
    if private and os.name != "nt":
        temporary.chmod(0o600)
    os.replace(temporary, path)


def ensure_connection(opts):
    if CONNECTION.exists() and not opts.api_url:
        return
    if not (opts.api_url and opts.bank):
        raise SystemExit("connection.json is missing: pass --api-url and --bank (and a token).")
    token = os.environ.get("HINDSIGHT_TOKEN", "")
    if opts.token_file:
        token = Path(opts.token_file).read_text(encoding="utf-8").strip()
    if not token and sys.stdin.isatty():
        token = getpass.getpass("Hindsight access token (hs_...): ").strip()
    if not token:
        raise SystemExit("A token is required: --token-file, HINDSIGHT_TOKEN or the interactive prompt.")
    api = opts.api_url.rstrip("/")
    if not api.startswith(ALLOWED):
        raise SystemExit("The API URL host is not in the hook allowlist.")
    value = {"api_url": api, "bank_id": opts.bank, "mcp_url": api + "/mcp/" + opts.bank + "/",
             "mcp_token": token, "timeout": 30}
    backup(CONNECTION)
    write_text(CONNECTION, json.dumps(value, ensure_ascii=False, indent=2) + "\n", private=True)
    print("Wrote " + str(CONNECTION) + " (token not shown).")


def hook_command(action, agent):
    command = [sys.executable, str(TARGET / "hindsight-hook.py"), action, "--agent", agent]
    return subprocess.list2cmdline(command) if os.name == "nt" else shlex.join(command)


def upsert_hooks(path, agent):
    """Codex hooks.json and Claude settings.json share one shape; only hindsight entries are replaced."""
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    original = json.dumps(config, sort_keys=True)
    events = [("UserPromptSubmit", "recall", 45), ("Stop", "retain", 180)]
    if agent == "codex":
        # Interrupted turns never reach Stop; Codex reports them through its own event.
        events.append(("Interrupt", "retain", 180))
    for event, action, timeout in events:
        groups = config.setdefault("hooks", {}).setdefault(event, [])
        entry = {"type": "command", "command": hook_command(action, agent), "timeout": timeout}
        found = False
        for group in groups:
            for index, old in enumerate(group.get("hooks", [])):
                if "hindsight-hook.py" in old.get("command", ""):
                    # Keep Codex entries intact so upgrades preserve approved hook hashes.
                    if agent != "codex":
                        group["hooks"][index] = entry
                    found = True
        if not found:
            groups.append({"hooks": [entry]})
    if json.dumps(config, sort_keys=True) == original:
        return "unchanged"
    backup(path)
    write_text(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return "updated"


def enable_hermes_plugin(home):
    config = home / "config.yaml"
    try:
        import yaml
        enabled = ((yaml.safe_load(config.read_text(encoding="utf-8")) or {}).get("plugins") or {}).get("enabled") or []
        if PLUGIN in enabled:
            return "already enabled"
    except Exception:
        pass
    hermes = shutil.which("hermes")
    if hermes:
        backup(config)
        env = dict(os.environ, HERMES_HOME=str(home))
        done = subprocess.run([hermes, "plugins", "enable", PLUGIN], stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=180, env=env)
        if done.returncode == 0:
            return "enabled (" + " ".join(done.stdout.split())[-160:] + ")"
    return "NOT enabled: run `hermes plugins enable " + PLUGIN + "`, then restart Hermes"


def install_hermes(home):
    destination = home / "plugins" / PLUGIN
    # Hermes loads every directory under plugins/, so the old copy is kept outside it.
    backup(destination, TARGET / "backups")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(SOURCE / "hermes-plugin" / PLUGIN, destination, ignore=shutil.ignore_patterns("__pycache__"))
    return enable_hermes_plugin(home)


def main():
    parser = argparse.ArgumentParser(description="Install Hindsight per-turn recall and upload hooks.")
    parser.add_argument("--agents", help="comma separated: codex,claude,hermes (default: those installed here)")
    parser.add_argument("--api-url")
    parser.add_argument("--bank")
    parser.add_argument("--token-file")
    opts = parser.parse_args()
    found = homes()
    agents = opts.agents.split(",") if opts.agents else [name for name, path in found.items() if path.is_dir()]
    unknown = set(agents) - set(found)
    if unknown:
        raise SystemExit("Unknown agents: " + ", ".join(sorted(unknown)))
    ensure_connection(opts)
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        backup(TARGET / name)
        shutil.copy2(SOURCE / name, TARGET / name)
    for agent in agents:
        if agent == "codex":
            status = upsert_hooks(found["codex"] / "hooks.json", "codex")
            if status == "updated":
                status += "; approve the changed hooks in Codex if it asks"
        elif agent == "claude":
            status = upsert_hooks(found["claude"] / "settings.json", "claude")
        else:
            status = install_hermes(found["hermes"])
        print(agent + ": " + status)
    print("Hook scripts installed in " + str(TARGET) + ". New sessions use them; restart running agents to be sure.")


if __name__ == "__main__":
    main()
