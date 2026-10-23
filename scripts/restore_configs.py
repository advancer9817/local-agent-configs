#!/usr/bin/env python3
"""Restore HOME-relative sanitized templates without relying on caller cwd.

This writes no credentials. Existing targets are backed up; secrets must be
configured separately after restoring a sanitized configuration snapshot.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import sys
import tomllib
from portable_paths import REPO, resolve_templates


def render_text(text: str, home: Path) -> str:
    # TOML literal strings may contain a home path; templates use forward slashes.
    return str(resolve_templates(text, home))


def restore(agent, home, target):
    source = REPO / agent
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = target / 'backups' / ('restore_' + stamp)
    changed = []

    def put(src, dest):
        if dest.exists():
            saved = backup / dest.relative_to(target)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, saved)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == '.json':
            obj = resolve_templates(json.loads(src.read_text()), home)
            text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
        elif src.suffix == '.yaml':
            import yaml
            obj = resolve_templates(yaml.safe_load(src.read_text()), home)
            text = yaml.safe_dump(obj, allow_unicode=True, sort_keys=False)
        elif src.suffix == '.toml':
            text = render_text(src.read_text(), home)
            tomllib.loads(text)
        elif src.suffix == '.md':
            text = render_text(src.read_text(), home)
        else:
            shutil.copy2(src, dest)
            changed.append(str(dest))
            return
        dest.write_text(text, encoding='utf-8')
        changed.append(str(dest))

    if agent == 'claude':
        files = [('settings.json', 'settings.json'),
                 ('settings.local.json', 'settings.local.json'),
                 ('config.json', 'config.json'), ('CLAUDE.md', 'CLAUDE.md'),
                 ('scripts/statusline.sh', 'statusline.sh'),
                 ('installed_plugins.json', 'plugins/installed_plugins.json'),
                 ('known_marketplaces.json', 'plugins/known_marketplaces.json')]
        files += [(str(p.relative_to(source)), str(p.relative_to(source)))
                  for p in (source / 'rules').rglob('*') if p.is_file()]
    elif agent == 'codex':
        files = [(name, name) for name in ('config.toml', 'instructions.md', 'hooks.json')]
    else:
        files = [(name, name) for name in ('config.yaml', 'SOUL.md')]
        for folder in ('memories', 'profiles', 'hindsight'):
            files += [(str(p.relative_to(source)), str(p.relative_to(source)))
                      for p in (source / folder).rglob('*') if p.is_file()]
    for src, dest in files:
        if (source / src).is_file():
            put(source / src, target / dest)

    # Install only the hook implementations actually present in this repository.
    if agent in ('claude', 'codex'):
        shared = home / '.local/lib/hindsight/hindsight-hook.py'
        shared.parent.mkdir(parents=True, exist_ok=True)
        if shared.exists():
            saved = backup / 'shared/hindsight-hook.py'
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(shared, saved)
        shutil.copy2(REPO / 'scripts/hindsight-hook.py', shared)
    else:
        hooks = target / 'agent-hooks'
        hooks.mkdir(parents=True, exist_ok=True)
        for name in ('superpowers-intent-gate.py', 'notify_weixin_ilink.py'):
            src = REPO / 'scripts' / name
            if src.exists():
                put(src, hooks / name)
        gate = home / '.local/bin/gate'
        gate.parent.mkdir(parents=True, exist_ok=True)
        if gate.exists():
            saved = backup / 'shared/gate'
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(gate, saved)
        shutil.copy2(REPO / 'scripts/gate', gate)
        gate.chmod(0o755)
    print(json.dumps({'agent': agent, 'target': str(target),
                      'restored_files': len(changed), 'backup': str(backup),
                      'secrets_restored': False}, ensure_ascii=False))
    print('Sanitized templates only: configure credentials and install missing optional plugins separately.')
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('agent', choices=('claude', 'codex', 'hermes'))
    parser.add_argument('--home', type=Path, default=Path.home(),
                        help='Base for HOME-relative paths (defaults to current user home)')
    parser.add_argument('--target', type=Path,
                        help='Destination config directory; default: <home>/.<agent>')
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    target = args.target.expanduser().resolve() if args.target else home / ('.' + args.agent)
    restore(args.agent, home, target)


if __name__ == '__main__':
    main()
