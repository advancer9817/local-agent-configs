# SDLC Role Profiles for Hermes Multi-Agent Workflows

Use this when a user wants Hermes profiles to act as named software-development lifecycle agents with different models and role prompts.

## Pattern

Create one Hermes profile per durable role, then set each profile's `model.provider`, `model.default`, and `SOUL.md` role instructions.

Typical 8-role set:

| Profile | Role | Model class |
|---|---|---|
| `coord` | Coordinator / delivery orchestration | strongest planner/reasoner |
| `req` | Requirement analysis | cheap/fast structured-output model |
| `design` | Solution design | Hermes wrapper that delegates real analysis/design to Claude Code CLI |
| `impl` | Implementation | Hermes/Codex wrapper: Codex CLI writes code, Claude Code CLI validates/tests |
| `qa` | QA and test verification | Hermes wrapper that delegates real verification to Claude Code CLI |
| `review` | Code review | Hermes wrapper that delegates real diff review to Claude Code CLI |
| `security` | Security review | strongest security/reasoning model |
| `commitint` | Commit and integration | cheap/fast for summaries; escalate failures |

## Commands

Create profiles from the current default profile so credentials, MCP servers, and custom providers are preserved:

```bash
for p in coord req design impl qa review security commitint; do
  hermes profile create --clone --no-alias "$p"
done
```

Set model configuration by editing each profile's config:

```python
from pathlib import Path
import yaml

profiles = {
    "coord": ("custom:apikeyfun", "claude-sonnet-4-7-thinking"),
    "req": ("deepseek", "deepseek-v4-flash"),
    # design/review/qa are Hermes wrappers; their SOUL.md must call Claude Code CLI.
    "design": ("custom:apikeyfun", "claude-sonnet-4-7-thinking"),
    # impl is a Hermes wrapper; its SOUL.md must call Codex CLI for development and Claude Code CLI for validation.
    "impl": ("openai-codex", "gpt-5.5"),
    "qa": ("custom:apikeyfun", "claude-sonnet-4-7-thinking"),
    "review": ("custom:apikeyfun", "claude-sonnet-4-7-thinking"),
    "security": ("custom:apikeyfun", "claude-opus-4-7-thinking"),
    "commitint": ("deepseek", "deepseek-v4-flash"),
}

base = Path.home() / ".hermes" / "profiles"
for name, (provider, model) in profiles.items():
    path = base / name / "config.yaml"
    cfg = yaml.safe_load(path.read_text())
    cfg.setdefault("model", {})
    cfg["model"].update({"provider": provider, "default": model, "base_url": ""})
    cfg.setdefault("agent", {})["max_turns"] = 80 if name not in {"req", "commitint"} else 50
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
```

Write each role's `SOUL.md` with: role boundary, responsibilities, explicit constraints, fixed output fields, and escalation rules.

## Verification

Use `-p`, not `HERMES_PROFILE`, when verifying profile-specific config:

```bash
hermes profile list
for p in coord req design impl qa review security commitint; do
  hermes -p "$p" config | grep -E 'Config:|Model:|Max turns:'
done
```

`HERMES_PROFILE=<name> hermes config` may still show the default config depending on invocation path; `hermes -p <name>` is the reliable CLI form.

## Usage

```bash
hermes -p coord
hermes -p req chat -q "把这个需求整理成验收标准：..."
hermes -p design chat -q "根据需求和代码结构设计技术方案：..."
hermes -p impl chat -q "根据已批准方案实现：..."
hermes -p review chat -q "审查当前 git diff：..."
```

Recommended iteration order:

1. `coord` creates iteration context and decides whether security review is needed.
2. `req` defines requirements, acceptance criteria, non-goals.
3. `design` calls Claude Code CLI to analyze the codebase and write solution design, file-level plan, test strategy.
4. `impl` calls Codex CLI to implement code and tests.
5. `impl` or `qa` calls Claude Code CLI to validate the Codex-produced diff by running appropriate tests/lint/typecheck/build.
6. If Claude Code validation fails, feed the failure report back to `impl`/Codex for fixes, then re-run Claude Code validation.
7. `review` calls Claude Code CLI to review the final diff.
8. `impl`/Codex fixes blockers.
9. `review`/Claude Code re-reviews.
10. `security` reviews if auth, data, files, dependencies, config, or external API risk exists.
11. `commitint` checks diff scope, validation commands, commit/PR text.
12. `coord` summarizes and gates submit/merge.

Hard policy: design and review must delegate to Claude Code; implementation must use Codex for development and Claude Code for validation. Codex must not self-approve its own code.
