"""Hermes handoff acceptance tests: all state/network effects are temporary."""
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile

from cryptography.fernet import Fernet
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'hermes_handoff.py'


def git(repo, *args, ok=True):
    result = subprocess.run(['git', '-C', str(repo), *args], text=True,
                            capture_output=True, timeout=20)
    if ok and result.returncode:
        raise AssertionError('fixture git failed: ' + result.stderr)
    return result


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'Fixture')
        git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'ITERATION.md').write_text('fixture\n')
        git(self.repo, 'add', 'ITERATION.md')
        git(self.repo, 'commit', '-m', 'fixture')
        self.a = self.root / 'company'
        self.b = self.root / 'home'
        for home in (self.a, self.b):
            home.mkdir()
            (home / 'memories').mkdir()
            (home / 'skills' / 'sample' / 'references').mkdir(parents=True)
            (home / 'SOUL.md').write_text('fixture soul')
            (home / 'memories' / 'MEMORY.md').write_text('fixture memory')
            (home / 'memories' / 'USER.md').write_text('fixture user')
            (home / 'skills' / 'sample' / 'SKILL.md').write_text('fixture skill')
            (home / 'skills' / 'sample' / 'references' / 'guide.md').write_text('fixture guide')
            (home / 'config.yaml').write_text(yaml.safe_dump({
                'model': {'api_key': 'FAKE_' + home.name},
                'mcp_servers': {'local': {'url': 'http://fixture.invalid'}},
                'agent': {'max_turns': 10}, 'memory': {'memory_enabled': True}}))
            (home / '.env').write_text('FAKE_SECRET=not-real')
            (home / 'auth.json').write_text('{"fake":"credential"}')
            with closing(sqlite3.connect(home / 'state.db', isolation_level=None)) as db:
                db.execute('CREATE TABLE chat(id INTEGER PRIMARY KEY, text TEXT)')
                db.execute('INSERT INTO chat(text) VALUES (?)', ('fake chat ' + home.name,))

    def cli(self, home, *args, repo=None, ok=True, lane='default'):
        self.assertTrue(SCRIPT.is_file(), 'handoff CLI has not been implemented')
        env = os.environ.copy()
        env.pop('HERMES_HOME', None)
        result = subprocess.run([sys.executable, str(SCRIPT), '--repo', str(repo or self.repo),
                                 '--home', str(home), '--lane', lane, *args],
                                text=True, capture_output=True, timeout=30, env=env)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('FAKE_', result.stdout + result.stderr)
        self.assertNotIn('fake chat', result.stdout + result.stderr)
        return result

    def init_pair(self, repo_b=None):
        self.cli(self.a, 'init', '--device', 'company')
        self.cli(self.b, 'init', '--device', 'home', '--key-file', str(self.a / '.handoff' / 'key'), repo=repo_b)

    def depart(self):
        self.init_pair()
        self.cli(self.a, 'depart', '--bootstrap')

    def receipt(self, home):
        return json.loads((home / '.handoff' / 'default' / 'receipt.json').read_text())

    def head(self, repo=None):
        return json.loads(((repo or self.repo) / 'handoff' / 'default' / 'head.json').read_text())

    def dbtext(self, home):
        with closing(sqlite3.connect(home / 'state.db', isolation_level=None)) as db:
            return db.execute('SELECT text FROM chat ORDER BY id').fetchall()

    def mutate_db(self, home):
        with closing(sqlite3.connect(home / 'state.db', isolation_level=None)) as db:
            db.execute('INSERT INTO chat(text) VALUES (?)', ('fake changed chat',))

    def forge(self, edit):
        enc = self.repo / 'handoff' / 'default' / 'latest.enc'
        f = Fernet((self.a / '.handoff' / 'key').read_bytes())
        with zipfile.ZipFile(io.BytesIO(f.decrypt(enc.read_bytes()))) as z:
            files = {i.filename: z.read(i) for i in z.infolist()}
        files = edit(files)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as z:
            for name, data in files.items():
                z.writestr(name, data)
        enc.write_bytes(f.encrypt(output.getvalue()))
        head = self.head()
        head['cipher_sha256'] = hashlib.sha256(enc.read_bytes()).hexdigest()
        (enc.parent / 'head.json').write_text(json.dumps(head))

    def test_roundtrip_preserves_local_credentials_and_full_chat(self):
        self.depart()
        before = (self.b / 'config.yaml').read_text()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.assertEqual(self.dbtext(self.b), self.dbtext(self.a))
        config = yaml.safe_load((self.b / 'config.yaml').read_text())
        self.assertEqual(config['model']['api_key'], 'FAKE_home')
        self.assertEqual(config['mcp_servers'], yaml.safe_load(before)['mcp_servers'])
        self.assertEqual((self.b / '.env').read_text(), 'FAKE_SECRET=not-real')
        self.mutate_db(self.b)
        self.cli(self.b, 'depart')
        self.cli(self.a, 'arrive')
        self.assertEqual(self.dbtext(self.a), self.dbtext(self.b))
        self.assertEqual(self.receipt(self.a)['phase'], 'active')
        self.assertTrue(list((self.b / '.handoff' / 'backups').iterdir()))

    def test_second_depart_without_arrive_is_rejected(self):
        self.depart()
        self.cli(self.a, 'depart', ok=False)

    def test_depart_requires_explicit_bootstrap(self):
        self.init_pair()
        self.cli(self.a, 'depart', ok=False)

    def test_initial_arrive_requires_bootstrap(self):
        self.depart()
        self.cli(self.b, 'arrive', ok=False)

    def test_active_arrive_same_generation_preserves_local_work(self):
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.mutate_db(self.b)
        expected = self.dbtext(self.b)
        result = self.cli(self.b, 'arrive')
        self.assertIn('no-op', result.stdout)
        self.assertEqual(self.dbtext(self.b), expected)

    def test_frozen_db_drift_blocks_arrive(self):
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.cli(self.b, 'depart')
        self.mutate_db(self.a)
        expected = self.dbtext(self.a)
        self.cli(self.a, 'arrive', ok=False)
        self.assertEqual(self.dbtext(self.a), expected)
        self.assertEqual(self.receipt(self.a)['phase'], 'departed')

    def test_sqlite_checkpoint_is_not_semantic_drift(self):
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.cli(self.b, 'depart')
        with closing(sqlite3.connect(self.a / 'state.db', isolation_level=None)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self.cli(self.a, 'arrive')

    def test_secret_only_drift_is_ignored(self):
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.cli(self.b, 'depart')
        config = yaml.safe_load((self.a / 'config.yaml').read_text())
        config['model']['api_key'] = 'FAKE_rotated'
        (self.a / 'config.yaml').write_text(yaml.safe_dump(config))
        self.cli(self.a, 'arrive')
        self.assertEqual(yaml.safe_load((self.a / 'config.yaml').read_text())['model']['api_key'], 'FAKE_rotated')

    def test_wrong_key_leaves_target_unchanged(self):
        self.depart()
        (self.b / '.handoff' / 'key').write_bytes(Fernet.generate_key())
        before = self.dbtext(self.b)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual(self.dbtext(self.b), before)
        self.assertFalse((self.b / '.handoff' / 'default' / 'receipt.json').exists())

    def test_cipher_tamper_is_rejected(self):
        self.depart()
        p = self.repo / 'handoff' / 'default' / 'latest.enc'
        data = p.read_bytes()
        p.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        before = self.dbtext(self.b)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual(self.dbtext(self.b), before)

    def test_authenticated_path_traversal_is_rejected(self):
        self.depart()
        def edit(files):
            manifest = json.loads(files['manifest.json'])
            payload = b'escape'
            files['../escape'] = payload
            manifest['files'].append({'path': '../escape', 'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)})
            files['manifest.json'] = json.dumps(manifest).encode()
            return files
        self.forge(edit)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertFalse((self.root / 'escape').exists())

    def test_authenticated_manifest_hash_mismatch_is_rejected(self):
        self.depart()
        def edit(files):
            files['SOUL.md'] = b'bad'
            return files
        self.forge(edit)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual((self.b / 'SOUL.md').read_text(), 'fixture soul')

    def test_authenticated_generation_mismatch_is_rejected(self):
        self.depart()
        def edit(files):
            manifest = json.loads(files['manifest.json'])
            manifest['generation'] = str(uuid.uuid4())
            files['manifest.json'] = json.dumps(manifest).encode()
            return files
        self.forge(edit)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)

    def test_destination_symlink_ancestor_is_rejected(self):
        self.depart()
        outside = self.root / 'outside'
        outside.mkdir()
        for p in (self.b / 'memories').iterdir():
            p.unlink()
        (self.b / 'memories').rmdir()
        (self.b / 'memories').symlink_to(outside, target_is_directory=True)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_secret_symlinks_and_sessions_not_exported(self):
        self.init_pair()
        (self.a / 'skills' / 'sample' / 'leak').symlink_to(self.a / '.env')
        (self.a / 'skills' / 'sample' / '.env').write_text('FAKE_nested')
        (self.a / 'skills' / 'sample' / 'auth.json').write_text('FAKE_nested')
        (self.a / 'sessions').mkdir()
        (self.a / 'sessions' / 'dump.json').write_text('fake duplicate chat')
        self.cli(self.a, 'depart', '--bootstrap')
        f = Fernet((self.a / '.handoff' / 'key').read_bytes())
        data = f.decrypt((self.repo / 'handoff' / 'default' / 'latest.enc').read_bytes())
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertNotIn('skills/sample/leak', z.namelist())
            self.assertNotIn('skills/sample/.env', z.namelist())
            self.assertNotIn('skills/sample/auth.json', z.namelist())
            self.assertNotIn('sessions/dump.json', z.namelist())
            self.assertNotIn(b'FAKE_', z.read('config.shared.json'))
        head = self.head()
        self.assertEqual(set(head), {'schema', 'generation', 'parent', 'device', 'timestamp', 'hermes_version', 'cipher_sha256'})

    def test_missing_source_db_does_not_delete_target_db(self):
        (self.a / 'state.db').unlink()
        self.depart()
        before = self.dbtext(self.b)
        self.cli(self.b, 'arrive', '--bootstrap')
        self.assertEqual(self.dbtext(self.b), before)

    def test_only_receipt_managed_files_are_deleted(self):
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        unrelated = self.a / 'skills' / 'local-only.md'
        unrelated.write_text('local skill')
        (self.b / 'skills' / 'sample' / 'SKILL.md').unlink()
        self.cli(self.b, 'depart')
        self.cli(self.a, 'arrive', ok=False)  # scope changed while frozen
        unrelated.unlink()
        # unrelated pre-existing files survive bootstrap and later managed deletion
        self.cli(self.a, 'arrive')
        self.assertFalse((self.a / 'skills' / 'sample' / 'SKILL.md').exists())

    def test_open_sqlite_fd_blocks_restore(self):
        self.depart()
        child = subprocess.Popen([sys.executable, '-c',
            'import sys,time; f=open(sys.argv[1],"rb"); print("ready",flush=True); time.sleep(60)',
            str(self.b / 'state.db')], stdout=subprocess.PIPE, text=True)
        self.addCleanup(child.stdout.close)
        self.addCleanup(child.wait)
        self.addCleanup(child.terminate)
        self.assertEqual(child.stdout.readline().strip(), 'ready')
        before = self.dbtext(self.b)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual(self.dbtext(self.b), before)

    def test_lock_rejects_concurrency(self):
        self.init_pair()
        (self.a / '.handoff' / 'lock').write_text('fixture lock')
        self.cli(self.a, 'depart', '--bootstrap', ok=False)

    def test_key_permissions_and_private_import(self):
        self.cli(self.a, 'init', '--device', 'company')
        key = self.a / '.handoff' / 'key'
        self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(key.parent.stat().st_mode), 0o700)
        key.chmod(0o644)
        self.cli(self.b, 'init', '--device', 'home', '--key-file', str(key), ok=False)

    def test_alias_and_lane_path_traversal_rejected(self):
        self.cli(self.a, 'init', '--device', '../home', ok=False)
        self.cli(self.a, 'status', lane='../other', ok=False)

    def test_lane_opt_in_does_not_read_other_profiles(self):
        profile = self.a / 'profiles' / 'work'
        profile.mkdir(parents=True)
        (profile / 'SOUL.md').write_text('work soul')
        self.cli(self.a, 'init', '--device', 'company', lane='work')
        self.cli(self.a, 'depart', '--bootstrap', lane='work')
        f = Fernet((self.a / '.handoff' / 'key').read_bytes())
        with zipfile.ZipFile(io.BytesIO(f.decrypt((self.repo / 'handoff' / 'work' / 'latest.enc').read_bytes()))) as z:
            self.assertEqual(z.read('SOUL.md'), b'work soul')
            self.assertFalse(any(p.startswith('profiles/') for p in z.namelist()))

    def make_remote(self):
        remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--bare', str(remote)], capture_output=True, check=True)
        git(self.repo, 'remote', 'add', 'origin', str(remote))
        git(self.repo, 'push', '-u', 'origin', 'main')
        git(remote, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        b_repo = self.root / 'repo-b'
        subprocess.run(['git', 'clone', str(remote), str(b_repo)], capture_output=True, check=True)
        git(b_repo, 'config', 'user.name', 'Fixture')
        git(b_repo, 'config', 'user.email', 'fixture@example.invalid')
        return remote, b_repo

    def test_publish_pull_real_bare_remote_roundtrip(self):
        remote, b_repo = self.make_remote()
        self.init_pair(b_repo)
        self.cli(self.a, 'depart', '--bootstrap', '--publish')
        self.cli(self.b, 'arrive', '--bootstrap', '--pull', repo=b_repo)
        self.mutate_db(self.b)
        self.cli(self.b, 'depart', '--publish', repo=b_repo)
        self.cli(self.a, 'arrive', '--pull')
        self.assertEqual(self.dbtext(self.a), self.dbtext(self.b))
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD').stdout, git(remote, 'rev-parse', 'refs/heads/main').stdout)
        changed = git(self.repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').stdout.splitlines()
        self.assertEqual(set(changed), {'ITERATION.md', 'handoff/default/head.json', 'handoff/default/latest.enc'})
        self.assertEqual(git(self.repo, 'status', '--porcelain').stdout, '')

    def test_dirty_repo_blocks_publish_before_snapshot(self):
        self.make_remote()
        self.cli(self.a, 'init', '--device', 'company')
        (self.repo / 'dirty.txt').write_text('fixture')
        self.cli(self.a, 'depart', '--bootstrap', '--publish', ok=False)
        self.assertFalse((self.repo / 'handoff' / 'default' / 'head.json').exists())
        self.assertFalse((self.a / '.handoff' / 'default' / 'receipt.json').exists())

    def test_local_ahead_blocks_publish_and_pull(self):
        self.make_remote()
        self.cli(self.a, 'init', '--device', 'company')
        (self.repo / 'ITERATION.md').write_text('other commit')
        git(self.repo, 'add', 'ITERATION.md')
        git(self.repo, 'commit', '-m', 'unrelated local work')
        self.cli(self.a, 'depart', '--bootstrap', '--publish', ok=False)
        self.cli(self.a, 'arrive', '--bootstrap', '--pull', ok=False)
        self.assertFalse((self.repo / 'handoff' / 'default' / 'head.json').exists())

    def test_push_failure_remains_departed_and_explicit_retry(self):
        remote, _ = self.make_remote()
        self.cli(self.a, 'init', '--device', 'company')
        hook = remote / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o700)
        result = self.cli(self.a, 'depart', '--bootstrap', '--publish', ok=False)
        receipt = self.receipt(self.a)
        self.assertEqual(receipt['phase'], 'departed')
        self.assertTrue(receipt['pending_publish'])
        self.assertIn('depart --publish', result.stdout + result.stderr)
        generation = receipt['last_generation']
        hook.unlink()
        self.cli(self.a, 'depart', '--publish')
        self.assertEqual(self.receipt(self.a)['last_generation'], generation)
        self.assertFalse(self.receipt(self.a)['pending_publish'])
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD').stdout, git(remote, 'rev-parse', 'refs/heads/main').stdout)

    def test_plaintext_head_metadata_tamper_is_rejected(self):
        self.depart()
        before = self.dbtext(self.b)
        original = self.head()
        for field, value in [('device', 'impostor'), ('timestamp', '2099-01-01'),
                             ('hermes_version', 'tampered')]:
            with self.subTest(field=field):
                head = dict(original)
                head[field] = value
                (self.repo / 'handoff' / 'default' / 'head.json').write_text(json.dumps(head))
                self.cli(self.b, 'arrive', '--bootstrap', ok=False)
                self.assertEqual(self.dbtext(self.b), before)

    def test_manifest_binds_every_non_circular_head_field(self):
        self.depart()
        f = Fernet((self.a / '.handoff' / 'key').read_bytes())
        with zipfile.ZipFile(io.BytesIO(f.decrypt((self.repo / 'handoff' / 'default' / 'latest.enc').read_bytes()))) as z:
            manifest = json.loads(z.read('manifest.json'))
        expected = {k: v for k, v in self.head().items() if k != 'cipher_sha256'}
        self.assertEqual(manifest.get('head'), expected)

    def test_same_device_first_arrival_is_rejected(self):
        self.cli(self.a, 'init', '--device', 'company')
        self.cli(self.b, 'init', '--device', 'company', '--key-file', str(self.a / '.handoff' / 'key'))
        self.cli(self.a, 'depart', '--bootstrap')
        before = self.dbtext(self.b)
        result = self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertIn('device', result.stderr)
        self.assertEqual(self.dbtext(self.b), before)

    def test_nested_shared_config_is_rejected_before_restore(self):
        self.depart()
        def edit(files):
            payload = json.dumps({'agent': {'max_turns': {'secret': 'FAKE_nested'}}}).encode()
            files['config.shared.json'] = payload
            manifest = json.loads(files['manifest.json'])
            for entry in manifest['files']:
                if entry['path'] == 'config.shared.json':
                    entry.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            files['manifest.json'] = json.dumps(manifest).encode()
            return files
        self.forge(edit)
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)
        self.assertEqual(self.dbtext(self.b), [('fake chat home',)])

    def test_duplicate_zip_paths_are_rejected(self):
        self.depart()
        enc = self.repo / 'handoff' / 'default' / 'latest.enc'
        f = Fernet((self.a / '.handoff' / 'key').read_bytes())
        output = io.BytesIO(f.decrypt(enc.read_bytes()))
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(output, 'a') as z:
                z.writestr('SOUL.md', b'duplicate')
        enc.write_bytes(f.encrypt(output.getvalue()))
        head = self.head()
        head['cipher_sha256'] = hashlib.sha256(enc.read_bytes()).hexdigest()
        (enc.parent / 'head.json').write_text(json.dumps(head))
        self.cli(self.b, 'arrive', '--bootstrap', ok=False)

    def test_init_cannot_replace_existing_key(self):
        self.cli(self.a, 'init', '--device', 'company')
        before = (self.a / '.handoff' / 'key').read_bytes()
        other = self.root / 'other-key'
        other.write_bytes(Fernet.generate_key())
        other.chmod(0o600)
        self.cli(self.a, 'init', '--device', 'company', '--key-file', str(other), ok=False)
        self.assertEqual((self.a / '.handoff' / 'key').read_bytes(), before)

    def test_restore_failure_rolls_back_files_and_receipt(self):
        self.depart()
        (self.a / 'SOUL.md').write_text('frozen soul')  # package remains original
        (self.b / 'SOUL.md').write_text('destination soul')
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('handoff_fault', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        h = module.Handoff(self.repo, self.b, 'default')
        before_db = (self.b / 'state.db').read_bytes()
        before_config = (self.b / 'config.yaml').read_bytes()
        real_replace = module.os.replace
        failed = False
        def fail_once(source, dest):
            nonlocal failed
            if Path(dest) == self.b / 'memories' / 'MEMORY.md' and not failed:
                failed = True
                raise OSError('fixture disk failure')
            return real_replace(source, dest)
        with patch.object(module.os, 'replace', side_effect=fail_once):
            with self.assertRaises(module.HandoffError):
                h.arrive(bootstrap=True)
        self.assertTrue(failed)
        self.assertEqual((self.b / 'SOUL.md').read_text(), 'destination soul')
        self.assertEqual((self.b / 'config.yaml').read_bytes(), before_config)
        self.assertEqual((self.b / 'state.db').read_bytes(), before_db)
        self.assertFalse((self.b / '.handoff' / 'default' / 'receipt.json').exists())
        self.assertTrue(list((self.b / '.handoff' / 'backups').iterdir()))

    def test_preexisting_unmanaged_skill_survives_bootstrap(self):
        self.depart()
        local = self.b / 'skills' / 'only-home.md'
        local.write_text('private local skill')
        self.cli(self.b, 'arrive', '--bootstrap')
        self.assertEqual(local.read_text(), 'private local skill')
        self.assertNotIn('skills/only-home.md', self.receipt(self.b)['managed_paths'])

    def test_default_depart_makes_no_git_commit(self):
        before = git(self.repo, 'rev-parse', 'HEAD').stdout
        self.depart()
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD').stdout, before)
        self.assertEqual((self.repo / 'ITERATION.md').read_text(), 'fixture\n')

    def test_executable_skill_retains_mode_after_arrival(self):
        tool = self.a / 'skills' / 'sample' / 'run.sh'
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o700)
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        restored = self.b / 'skills' / 'sample' / 'run.sh'
        self.assertTrue(restored.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(subprocess.run([str(restored)]).returncode, 0)

    def test_literal_boolean_config_compatibility(self):
        config = yaml.safe_load((self.a / 'config.yaml').read_text())
        config['agent']['tool_use_enforcement'] = 'false'
        (self.a / 'config.yaml').write_text(yaml.safe_dump(config))
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        self.assertIs(yaml.safe_load((self.b / 'config.yaml').read_text())['agent']['tool_use_enforcement'], False)

    def test_package_limit_fits_existing_large_session_store(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('handoff_size', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertGreaterEqual(module.MAX_BYTES, 300 * 1024 * 1024)

    def test_unknown_unreadable_process_still_blocks(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('handoff_private_proc', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        proc = self.root / '999997'
        proc.mkdir()
        (proc / 'status').write_text('Name:\tpython\nState:\tS (sleeping)\n')
        (proc / 'comm').write_text('python\n')
        (proc / 'cmdline').write_bytes(b'python\0unknown.py\0')
        real_iterdir, real_read = module.Path.iterdir, module.Path.read_bytes
        def fake_iterdir(path):
            return iter([proc]) if path == Path('/proc') else real_iterdir(path)
        def fake_read(path):
            if path == proc / 'environ':
                raise PermissionError('fixture')
            return real_read(path)
        with patch.object(module.Path, 'iterdir', fake_iterdir), patch.object(module.Path, 'read_bytes', fake_read):
            with self.assertRaises(module.HandoffError):
                module.check_quiescent(self.a)

    def test_systemd_user_session_manager_is_not_a_writer(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('handoff_manager', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        proc = self.root / '999998'
        proc.mkdir()
        (proc / 'status').write_text('Name:\tsystemd\nState:\tS (sleeping)\n')
        (proc / 'comm').write_text('systemd\n')
        (proc / 'cmdline').write_bytes(b'/usr/lib/systemd/systemd\0--user\0')
        real_iterdir = module.Path.iterdir
        def fake_iterdir(path):
            return iter([proc]) if path == Path('/proc') else real_iterdir(path)
        with patch.object(module.Path, 'iterdir', fake_iterdir):
            module.check_quiescent(self.a)

    def test_zombie_process_does_not_block_offline_check(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('handoff_zombie', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        proc = self.root / '999999'
        proc.mkdir()
        (proc / 'status').write_text('Name:\tpython\nState:\tZ (zombie)\n')
        real_iterdir = module.Path.iterdir
        def fake_iterdir(path):
            return iter([proc]) if path == Path('/proc') else real_iterdir(path)
        with patch.object(module.Path, 'iterdir', fake_iterdir):
            module.check_quiescent(self.a)

    def test_fts_database_roundtrip(self):
        with closing(sqlite3.connect(self.a / 'state.db', isolation_level=None)) as db:
            db.execute('CREATE VIRTUAL TABLE notes_fts USING fts5(content)')
            db.execute('INSERT INTO notes_fts(content) VALUES (?)', ('测试会话 search fixture',))
        self.depart()
        self.cli(self.b, 'arrive', '--bootstrap')
        with closing(sqlite3.connect(self.b / 'state.db', isolation_level=None)) as db:
            self.assertEqual(db.execute("SELECT content FROM notes_fts WHERE notes_fts MATCH 'search'").fetchone(), ('测试会话 search fixture',))

    def test_diagnostic_works_before_initialization(self):
        result = self.cli(self.a, 'doctor')
        self.assertIn('not initialized', result.stdout)
        self.assertFalse((self.a / '.handoff' / 'key').exists())

    def test_snapshot_closes_connections_before_return(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('handoff_fd', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        temp = self.root / 'snapshot-stage'
        temp.mkdir()
        module.snapshot(self.a, temp)
        held = []
        for fd in Path('/proc/self/fd').iterdir():
            try:
                target = os.readlink(fd)
            except FileNotFoundError:
                continue
            if target.startswith(str(self.a / 'state.db')) or target.startswith(str(temp / 'state.db')):
                held.append(target)
        self.assertEqual(held, [])

    def test_status_doctor_do_not_emit_sensitive_content(self):
        self.init_pair()
        self.cli(self.a, 'status')
        self.cli(self.a, 'doctor')


if __name__ == '__main__':
    unittest.main()
