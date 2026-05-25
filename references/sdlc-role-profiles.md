# SDLC Role Profiles for Hermes Multi-Agent Workflows

Use this when a user wants Hermes profiles to act as named software-development lifecycle agents while dynamically following the orchestrating session's actual wrapper model and retaining distinct role/tool contracts.

## Pattern

Create one Hermes profile per durable role, set `SOUL.md` role instructions and gate boundaries, and, whenever the router invokes a profile, pass the router session's actual `model` / `provider` on the invocation using `-m` and `--provider`. A profile's persisted `config.yaml` model is only its direct-launch fallback; Hermes profiles are independent `HERMES_HOME` directories and do not natively inherit the parent session's temporary `/model` selection. The model is not assigned per role; adapters and gates remain role-specific.

Typical 8-role set:

| Profile | Role | Role/tool contract |
|---|---|---|
| `coord` | Coordinator / delivery orchestration | orchestration, gates, freeze artifact |
| `req` | Requirement analysis | structured requirements and acceptance criteria |
| `design` | Solution design | Claude Code adapter for read-only design analysis when invoked |
| `impl` | Implementation | Codex adapter writes code; verification adapter used by lane/gate contract |
| `qa` | QA and test verification | Claude Code adapter for independent validation when gate runs |
| `review` | Code review | Claude Code adapter for read-only diff review when gate runs |
| `security` | Security review | hard security gate; insufficient evidence is BLOCKED/NEEDS_HUMAN_DECISION |
| `commitint` | Commit and integration | iteration/commit/PR materials, never override gate verdicts |

## Dynamic Invocation Model Policy

Current policy: when the router dispatches a durable profile, the invoked Hermes wrapper must run on the router session's actual current model/provider, rather than relying on a role-specific or stale profile model setting.

| Profile | Wrapper model policy |
|---|---|
| `default` | Orchestrating session; its actual runtime model/provider is the dispatch source |
| `coord`, `req`, `design`, `impl`, `qa`, `review`, `security`, `commitint` | Invoke with `-m <current_model> --provider <current_provider>`; persisted model is fallback only |

Hermes profiles are isolated `HERMES_HOME` directories. Their `config.yaml` files do not dynamically inherit root/default changes or an in-session `/model` switch. At the time of this policy update, the live default fallback is `custom:aca / gpt-5.5`, but dispatched roles must follow whatever actual model/provider is active in the orchestrating session at invocation time.

Important invariants:

- Unified wrapper models do not remove role boundaries, required gates, tool/write policies, or adapter contracts.
- `design`, `qa`, and `review` continue using Claude Code adapter when their contracts require it; `impl` continues using Codex adapter for implementation.
- `security` has no dedicated stronger wrapper model constraint under this policy. If the current default model or available evidence cannot support a reliable security PASS, security must return `BLOCKED` or `NEEDS_HUMAN_DECISION`.
- Model unification must not be interpreted as permission to skip security review, frozen-diff validation, or independent review/QA.

## Commands

Create profiles from the current default profile so credentials, MCP servers, and custom providers are preserved:

```bash
for p in coord req design impl qa review security commitint; do
  hermes profile create --clone --no-alias "$p"
done
```

Initialize direct-launch fallback model configuration from the active default profile while preserving operational turn budgets:

```python
from pathlib import Path
import copy
import yaml

base = Path.home() / ".hermes"
default_model = yaml.safe_load((base / "config.yaml").read_text())["model"]
turns = {
    "coord": 35, "req": 12, "design": 30, "impl": 50,
    "qa": 25, "review": 25, "security": 40, "commitint": 12,
}
for name, max_turns in turns.items():
    path = base / "profiles" / name / "config.yaml"
    cfg = yaml.safe_load(path.read_text())
    cfg["model"] = copy.deepcopy(default_model)
    cfg.setdefault("agent", {})["max_turns"] = max_turns
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
```

Write each role's `SOUL.md` with: role boundary, responsibilities, explicit constraints, fixed output fields, escalation rules, and the statement that dispatched roles receive the invoking router session's actual model/provider through CLI override arguments rather than having role-specific model pinning.

## Invoking roles with the current session model

Profiles contain their own config files and do not dynamically inherit a router session's `/model` switch. For every routed role invocation, pass the invoking session's actual runtime model and provider explicitly:

```bash
hermes -p <profile> chat -m <current_model> --provider <current_provider> -q "<handoff prompt>"
```

`<current_model>` and `<current_provider>` must be the values active in the calling router session, including any temporary session-level switch. A profile's saved `model` mapping is only a fallback for direct/manual profile launch. A persistent change to the default profile may be mirrored into fallback config for usability, but static config synchronization is not the dynamic dispatch mechanism.

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
# Values below must be taken from the invoking router session's active runtime selection.
CURRENT_MODEL="gpt-5.5"
CURRENT_PROVIDER="custom:aca"
hermes -p coord chat -m "$CURRENT_MODEL" --provider "$CURRENT_PROVIDER" -q "编排此任务：..."
hermes -p req chat -m "$CURRENT_MODEL" --provider "$CURRENT_PROVIDER" -q "把这个需求整理成验收标准：..."
hermes -p design chat -m "$CURRENT_MODEL" --provider "$CURRENT_PROVIDER" -q "根据需求和代码结构设计技术方案：..."
hermes -p impl chat -m "$CURRENT_MODEL" --provider "$CURRENT_PROVIDER" -q "根据已批准方案实现：..."
hermes -p review chat -m "$CURRENT_MODEL" --provider "$CURRENT_PROVIDER" -q "审查当前 git diff：..."
```

Recommended iteration order:

### Latency-aware lanes

Use the shortest lane that preserves the required gates:

- **Fast Lane (S0/S1):** default handles directly with necessary verification; do not spawn SDLC profiles by default.
- **Standard Lane (clear S2 bugfix/local feature with no architecture, external/data/permission/config boundary):** `default brief -> impl/Codex + basic self-tests -> freeze -> qa/Claude and review/Claude in parallel -> commitint only when submission materials are requested`. Record reasons when `coord`, `req`, or `design` are skipped.
- **Full Lane (S3/S4, or work touching architecture/external API/MCP/data/permissions/config/dependency/deployment/security triggers):** keep the complete coordinated pipeline below; never reduce required security review for latency.

For Standard Lane only, Codex basic self-tests are implementation evidence, not approval; independent final Claude validation occurs once in `qa`, avoiding a duplicate full Claude validation inside `impl`. For Full Lane, `impl` may use Claude Code for a quick validation before final gates.

1. `coord` creates iteration context and decides whether security review is needed for Full Lane or escalated work.
2. `req` defines requirements, acceptance criteria, non-goals when the task is ambiguous, high-risk, or Full Lane.
3. `design` calls Claude Code CLI to analyze the codebase and write solution design, file-level plan, test strategy when design is required.
4. `impl` calls Codex CLI to implement code and tests.
5. In Standard Lane, `impl` runs basic self-tests then hands off to `qa`; in Full Lane, `impl` may call Claude Code CLI for an early validation pass.
6. If validation fails, feed the failure report back to `impl`/Codex for fixes, then re-run the applicable validation.
7. After a frozen diff, `qa` and `review` call Claude Code against the same freeze artifact in parallel; `security` joins in parallel if required.
8. `impl`/Codex fixes blockers and gates rerun against a new valid freeze artifact if the diff changes.
9. `security` reviews if auth, data, files, dependencies, config, or external API risk exists.
10. `commitint` checks diff scope, validation commands, commit/PR text only when commit/submission material is requested or required.
11. `coord` summarizes and gates submit/merge for Full Lane or escalated work.

Hard policy: design and review must delegate to Claude Code when those roles run; implementation must use Codex for development; Codex must not self-approve its own code. In Standard Lane, Claude final validation is centralized in QA; in Full Lane, Claude validation may also run inside impl as an early check.
