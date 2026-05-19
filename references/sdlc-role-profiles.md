# SDLC Role Profiles for Hermes Multi-Agent Workflows

Use this when a user wants Hermes profiles to act as named software-development lifecycle agents with different models and role prompts.

## Pattern

Create one Hermes profile per durable role, then set each profile's `model.provider`, `model.default`, and `SOUL.md` role instructions.

Typical 8-role set:

| Profile | Role | Model class |
|---|---|---|
| `coord` | Coordinator / delivery orchestration | strong planner, no thinking needed |
| `req` | Requirement analysis | cheap/fast structured-output model |
| `design` | Solution design | Hermes wrapper that delegates real analysis/design to Claude Code CLI |
| `impl` | Implementation | Hermes/Codex wrapper: Codex CLI writes code, Claude Code CLI validates/tests |
| `qa` | QA and test verification | Hermes wrapper that delegates real verification to Claude Code CLI |
| `review` | Code review | Hermes wrapper that delegates real diff review to Claude Code CLI |
| `security` | Security review | strongest security/reasoning model — do NOT downgrade |
| `commitint` | Commit and integration | cheap/fast for summaries; escalate failures |

## Model Assignment (Proven Configuration)

Current production assignment, optimised for price / quality / latency balance:

| Profile | Provider | Model | Reasoning |
|---|---|---|---|
| `default` | `custom:apikeyfun` | `claude-sonnet-4-6` | Router + daily non-coding tasks; Sonnet quality without thinking overhead |
| `coord` | `custom:apikeyfun` | `claude-sonnet-4-6` | Orchestration is mostly linear; thinking adds latency without benefit |
| `req` | `deepseek` | `deepseek-v4-flash` | Pure text/structured output; fast and cheap, no code needed |
| `design` | `custom:apikeyfun` | `claude-sonnet-4-6` | Hermes is dispatch layer only; Claude Code CLI does the real reasoning |
| `impl` | `openai-codex` | `gpt-5.5` | Hard-wired to Codex CLI; cannot change |
| `qa` | `custom:apikeyfun` | `claude-sonnet-4-6` | QA needs real analysis (failure root-cause, test strategy); Haiku is too shallow |
| `review` | `custom:apikeyfun` | `claude-sonnet-4-6` | Hermes is dispatch layer; Claude Code CLI does the real review |
| `security` | `custom:apikeyfun` | `claude-opus-4-7-thinking` | Highest-risk role; never downgrade |
| `commitint` | `deepseek` | `deepseek-v4-flash` | Commit messages and PR text; fast and cheap is fine |

### Decision Logic (for future re-evaluation)

**When to keep thinking models:** only when the Hermes profile itself must do deep multi-step reasoning with no external agent to delegate to. Currently only `security` qualifies.

**When thinking is wasteful:** design / review / qa — these profiles are dispatch wrappers. The real reasoning happens inside Claude Code CLI. Paying for thinking tokens at the Hermes layer adds latency and cost with no quality gain.

**When to use Haiku:** only for pure dispatch/routing with no analytical output. QA is NOT a pure dispatcher — it synthesises failure analysis and quality conclusions, so Sonnet is the floor.

**When to use DeepSeek flash:** text-only tasks with no code reasoning: req (structured requirements), commitint (commit/PR text). Both are fast, cheap, and produce high-quality structured output.

**security is a hard floor:** never downgrade security to a non-thinking model or a cheaper tier. It is the last line of defence before production changes.

### reasoning_effort alignment

When using non-thinking models (claude-sonnet-4-6), set `reasoning_effort: medium` in the profile config. The `high` setting is only meaningful for thinking-capable models and wastes tokens otherwise.

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
    "coord":     ("custom:apikeyfun", "claude-sonnet-4-6",        "medium", 90),
    "req":       ("deepseek",         "deepseek-v4-flash",         "medium", 50),
    # design/review/qa are Hermes wrappers; their SOUL.md must call Claude Code CLI.
    "design":    ("custom:apikeyfun", "claude-sonnet-4-6",         "medium", 80),
    # impl is a Hermes wrapper; SOUL.md must call Codex CLI for dev, Claude Code CLI for validation.
    "impl":      ("openai-codex",     "gpt-5.5",                   "medium", 80),
    "qa":        ("custom:apikeyfun", "claude-sonnet-4-6",         "medium", 80),
    "review":    ("custom:apikeyfun", "claude-sonnet-4-6",         "medium", 80),
    "security":  ("custom:apikeyfun", "claude-opus-4-7-thinking",  "high",   60),
    "commitint": ("deepseek",         "deepseek-v4-flash",         "medium", 50),
}

base = Path.home() / ".hermes" / "profiles"
for name, (provider, model, reasoning, max_turns) in profiles.items():
    path = base / name / "config.yaml"
    cfg = yaml.safe_load(path.read_text())
    cfg.setdefault("model", {}).update({"provider": provider, "default": model, "base_url": ""})
    cfg.setdefault("agent", {}).update({"max_turns": max_turns, "reasoning_effort": reasoning})
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
```

Write each role's `SOUL.md` with: role boundary, responsibilities, explicit constraints, fixed output fields, and escalation rules.

## Changing a single profile's model

`hermes profile set-model` does not exist. Use `hermes config set` with `-p`:

```bash
# There is no hermes profile set-model command.
# Correct approach: edit the profile config.yaml directly.
python3 -c "
import yaml; from pathlib import Path
p = Path.home() / '.hermes/profiles/coord/config.yaml'
cfg = yaml.safe_load(p.read_text())
cfg['model']['default'] = 'claude-sonnet-4-6'
cfg['agent']['reasoning_effort'] = 'medium'
p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
print('done')
"
```

Or use the `patch` file-editing tool to do a targeted string replacement in the profile's config.yaml.

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
