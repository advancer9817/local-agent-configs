#!/usr/bin/env python3
"""Offline regression: templates, HOME relocation, quoting, backup and hooks."""
import ast
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
import unittest
import yaml
from portable_paths import REPO, portable_text, resolve_templates


class PortableConfigsTest(unittest.TestCase):
    def test_template_syntax(self):
        files = subprocess.check_output(
            ['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
            cwd=REPO).decode().split('\0')
        for relative in sorted(set(files)):
            path = REPO / relative
            if not relative or not path.is_file():
                continue
            if path.suffix == '.json':
                json.loads(path.read_text())
            elif path.suffix == '.yaml':
                yaml.safe_load(path.read_text())
            elif path.suffix == '.toml':
                tomllib.loads(path.read_text())
            elif path.suffix == '.py':
                ast.parse(path.read_text())
            elif path.suffix == '.sh':
                subprocess.run(['bash', '-n', str(path)], check=True)

    def test_conversion_and_url_preservation(self):
        for value, expected in [
            ('/home/example/.hermes/config.yaml', './.hermes/config.yaml'),
            (r'C:\Users\Someone\.codex\hooks.json', './.codex/hooks.json'),
            (r'\\?\C:\Users\Someone\.codex', './.codex'),
        ]:
            self.assertEqual(portable_text(value), expected)
        url = 'http://35.194.237.91:18888/mcp/mcore-active-snapshot/'
        self.assertEqual(resolve_templates(url, Path.home()), url)

    def test_no_personal_paths_in_config(self):
        pattern = re.compile(r'/home/[^/\s]+|/mnt/[a-z]/Users/|(?i:[a-z]:[\\/]+Users[\\/]+)')
        for folder in ('claude', 'codex', 'hermes'):
            for path in (REPO / folder).rglob('*'):
                if path.suffix not in ('.json', '.yaml', '.toml'):
                    continue
                self.assertIsNone(pattern.search(path.read_text()), str(path.relative_to(REPO)))

    def test_restore_from_other_directory(self):
        scratch = Path(os.environ.get('TMPDIR', str(Path.home() / '.hermes/cache/scratch')))
        scratch.mkdir(parents=True, exist_ok=True)
        base = Path(tempfile.mkdtemp(prefix='config-portable-test-', dir=scratch))
        home = base / 'different user home'
        for agent in ('claude', 'codex', 'hermes'):
            command = ['bash', str(REPO / 'scripts' / f'restore_to_{agent}.sh'),
                       '--home', str(home)]
            result = subprocess.run(command, cwd=base, env=dict(os.environ, PYTHON=sys.executable),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            target = home / ('.' + agent)
            if agent == 'hermes':
                config = yaml.safe_load((target / 'config.yaml').read_text())
            else:
                name = 'settings.json' if agent == 'claude' else 'hooks.json'
                config = json.loads((target / name).read_text())
            if agent == 'codex':
                tomllib.loads((target / 'config.toml').read_text())
            for entries in config.get('hooks', {}).values():
                for entry in entries:
                    for hook in entry.get('hooks', [entry]):
                        args = shlex.split(hook['command'])
                        self.assertFalse(any(x.startswith('./') for x in args), args)
                        for arg in args:
                            if arg.endswith('.py'):
                                self.assertTrue(Path(arg).is_file(), arg)
            if agent == 'claude':
                self.assertEqual(shlex.split(config['statusLine']['command'])[1],
                                 str(target / 'statusline.sh'))
            # Missing credentials must fail open without contacting any service.
            for script in target.glob('agent-hooks/notify_weixin_ilink.py'):
                notification = subprocess.run([sys.executable, str(script)],
                                              input='{}', text=True, timeout=10,
                                              env=dict(os.environ, HOME=str(home), HERMES_HOME=str(target)))
                self.assertEqual(notification.returncode, 0)
            again = subprocess.run(command, cwd=base, env=dict(os.environ, PYTHON=sys.executable),
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertTrue(list((target / 'backups').glob('restore_*')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
