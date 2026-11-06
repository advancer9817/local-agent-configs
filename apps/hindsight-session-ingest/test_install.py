import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class InstallTests(unittest.TestCase):
    @staticmethod
    def isolated_env(home):
        env = dict(os.environ, HOME=str(home), USERPROFILE=str(home))
        for key in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "HERMES_HOME", "HINDSIGHT_CONNECTION_FILE"):
            env.pop(key, None)
        return env

    def test_upgrade_preserves_previously_approved_hook_definitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            connection = home / '.config/hindsight/connection.json'
            connection.parent.mkdir(parents=True)
            connection.write_text('{}')
            hooks_path = home / '.codex/hooks.json'
            hooks_path.parent.mkdir()
            hooks = {'hooks': {
                'Stop': [{'hooks': [{'type': 'command',
                    'command': '/bin/python3 /approved/hindsight-hook.py retain --agent codex',
                    'timeout': 60, 'async': False}]}],
                'UserPromptSubmit': [{'hooks': [{'type': 'command',
                    'command': '/bin/python3 /approved/hindsight-hook.py recall --agent codex',
                    'timeout': 45}]}],
                'SessionStart': [{'hooks': [{'type': 'command', 'command': 'existing-hook'}]}]
            }}
            hooks_path.write_text(json.dumps(hooks))
            subprocess.run([sys.executable, str(Path(__file__).with_name('install.py'))],
                           env=self.isolated_env(home),
                           check=True, capture_output=True)
            installed = json.loads(hooks_path.read_text())
            interrupt = installed['hooks'].pop('Interrupt')
            self.assertEqual(installed, hooks)
            self.assertEqual(len(interrupt), 1)
            self.assertTrue(interrupt[0]['hooks'][0]['command'].endswith('hindsight-hook.py retain --agent codex'))
            self.assertTrue((home / '.local/lib/hindsight/hindsight-hook.py').is_file())

    def test_claude_settings_get_no_interrupt_hook(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            connection = home / '.config/hindsight/connection.json'
            connection.parent.mkdir(parents=True)
            connection.write_text('{}')
            (home / '.claude').mkdir()
            subprocess.run([sys.executable, str(Path(__file__).with_name('install.py')), '--agents', 'claude'],
                           env=self.isolated_env(home),
                           check=True, capture_output=True)
            events = json.loads((home / '.claude/settings.json').read_text())['hooks']
            self.assertEqual(sorted(events), ['Stop', 'UserPromptSubmit'])


if __name__ == '__main__':
    unittest.main()
