# Hermes local agent configuration backup

This repository contains a sanitized backup of the local Hermes multi-agent / SDLC role setup and user memory files.

## Included

- `config.yaml` — sanitized default Hermes config.
- `SOUL.md` — default router/system role prompt.
- `profiles/<role>/config.yaml` — sanitized role profile configs for coord, req, design, impl, qa, review, security, commitint.
- `profiles/<role>/SOUL.md` — role prompts.
- `memories/MEMORY.md` and `memories/USER.md` — exported durable memory/user profile text.
- `profiles/<role>/memories/*.md` — role-specific memory files when present.
- `PROFILE_LIST.txt` — profile inventory from `hermes profile list`.
- `references/sdlc-role-profiles.md` — SDLC profile layout reference.
- `scripts/restore_to_hermes.sh` — conservative restore helper.

## Not included

- Real `.env` values, OAuth tokens, credential pools, `auth.json`.
- Session transcripts, logs, SQLite state DBs, caches, venvs, source checkout.
- Gateway runtime state.

`.env.example` contains only variable names with `<REDACTED>` placeholders.

## Restore

```bash
cd /path/to/hermes-local-agent-configs
scripts/restore_to_hermes.sh
```

Then manually populate `~/.hermes/.env` from `.env.example` and run:

```bash
hermes profile list
hermes config check
```

## Security note

This repository still contains personal preferences and user memory. Keep it private unless you intentionally remove or generalize the memory files.
