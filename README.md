# Hermes Local Agent Configs

Sanitized backup of this machine's Hermes Agent local configuration.

Exported at: 2026-05-19T17:36:28
Source Hermes home: `/home/advancer/.hermes`

## Contents

- `config.yaml` — sanitized root Hermes config.
- `SOUL.md` — default General Multi-Agent Router prompt.
- `memories/` — sanitized durable memory/user profile markdown.
- `profiles/<role>/config.yaml` and `SOUL.md` — SDLC role profile configs/prompts.
- `PROFILE_LIST.txt` — profile inventory from `hermes profile list`.
- `references/sdlc-role-profiles.md` — role profile reference.
- `.env.example` — env variable names only, all values redacted.
- `scripts/restore_to_hermes.sh` — conservative restore script.

## Security policy

This repo intentionally excludes live secrets and runtime state: `.env`, `auth.json`, OAuth tokens, sessions, logs, caches, SQLite state, and venvs. Any secret-like values in YAML/Markdown are replaced with `<REDACTED>`.

## Restore

```bash
./scripts/restore_to_hermes.sh
```

After restore, manually configure `.env`/auth credentials; they are not stored here.
