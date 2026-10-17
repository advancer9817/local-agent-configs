#!/usr/bin/env python3
"""Offline, encrypted, sequential Hermes handoff (Python 3.10+).

Default commands never use the network or commit. --publish and --pull are
explicit Git authorization. --home denotes a Hermes root; --lane NAME opts
into exactly root/profiles/NAME (default uses the root itself).

Only authenticated allowlisted files are restored; connection settings and
credentials remain local. Stop all Hermes clients/services first. Key files
must be exchanged out of band, never through Git or chat.
"""
import argparse
from contextlib import ExitStack, contextmanager, closing
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile

from cryptography.fernet import Fernet, InvalidToken
import yaml

SCHEMA = 1
MAX_FILES = 5000
MAX_BYTES = 512 * 1024 * 1024
MAX_CIPHER = 700 * 1024 * 1024
ALIASES = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,47}\Z')
SHARED = {
    'agent': {'max_turns': 'int', 'tool_use_enforcement': 'bool'},
    'compression': {'enabled': 'bool', 'threshold': 'ratio', 'target_ratio': 'ratio'},
    'memory': {k: 'bool' if k in ('memory_enabled', 'user_profile_enabled', 'write_approval') else 'int'
               for k in ('memory_enabled', 'user_profile_enabled', 'memory_char_limit',
                         'user_char_limit', 'nudge_interval', 'flush_min_turns', 'write_approval')},
    'display': {'show_reasoning': 'bool', 'show_cost': 'bool', 'verbose': 'bool', 'personality': 'str'},
}
ROOT_FILES = {'SOUL.md', 'memories/MEMORY.md', 'memories/USER.md'}
BLOCKED = {'venv', 'env', '__pycache__', 'node_modules', 'auth', 'auth.json',
           'credentials', 'credentials.json', 'cookies', 'cookies.json', 'token',
           'token.json', 'tokens.json', 'secrets', 'secrets.json', 'cc-switch'}


class Payload(dict):
    def __init__(self):
        super().__init__()
        self.modes = {}


class HandoffError(Exception):
    """Safe error: messages must never interpolate raw user data or Git stderr."""


def require(condition, message):
    if not condition:
        raise HandoffError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_alias(value):
    require(isinstance(value, str) and ALIASES.fullmatch(value), 'Invalid device/lane alias.')
    return value


def no_symlinks(path):
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        require(not item.is_symlink(), 'Symlink in destination/local path; refusing.')
    return path


def safe_component(name):
    lower = name.lower()
    return (not name.startswith('.') and lower not in BLOCKED and
            not lower.endswith(('.pem', '.key', '.p12', '.pfx', '.pyc')) and
            not re.search(r'(^|[-_.])(auth|token|tokens|secret|secrets|credential|credentials|cookies)([-_.]|$)', lower))


def allowed_path(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        return False
    p = PurePosixPath(name)
    if p.is_absolute() or str(p) != name or any(x in ('.', '..') for x in p.parts):
        return False
    if name in ROOT_FILES or name in ('state.db', 'config.shared.json'):
        return True
    return len(p.parts) >= 2 and p.parts[0] in ('skills', 'references') and all(safe_component(x) for x in p.parts)


def private_dir(path):
    no_symlinks(path)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def atomic_write(path, data, mode=0o600):
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temp = tempfile.mkstemp(prefix='.handoff-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        no_symlinks(path)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_regular(path, limit=MAX_BYTES):
    no_symlinks(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as source:
        require(stat.S_ISREG(os.fstat(source.fileno()).st_mode), 'Not a regular file.')
        require(os.fstat(source.fileno()).st_size <= limit, 'File exceeds size limit.')
        data = source.read(limit + 1)
    require(len(data) <= limit, 'File exceeds size limit.')
    return data


def read_json(path):
    return json.loads(read_regular(path, 1024 * 1024))


@contextmanager
def exclusive_lock(path):
    no_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise HandoffError('Another handoff owns a lock; inspect it manually, never kill processes automatically.') from None
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink()


def check_quiescent(home):
    """Refuse open scope FDs or Hermes processes associated with this home."""
    home = no_symlinks(home)
    require(sys.platform.startswith('linux'), 'Offline verification currently requires Linux/WSL; native Windows and other Unix are unsupported.')
    uid = os.getuid()
    prefix = str(home) + '/'
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit() or int(proc.name) == os.getpid():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            state = next((line.split()[1] for line in (proc / 'status').read_text().splitlines() if line.startswith('State:')), None)
            if state == 'Z':
                continue  # Exited zombies have no live address space or open FDs.
            cmd = (proc / 'cmdline').read_bytes().split(b'\0')
            comm = (proc / 'comm').read_text().strip()
            args = [x for x in cmd if x]
            manager = comm == 'systemd' and args in ([b'/usr/lib/systemd/systemd', b'--user'], [b'/lib/systemd/systemd', b'--user'])
            if comm == '(sd-pam)' and args in ([b'(sd-pam)'], [b'(sd-pam) ']):
                ppid = next((line.split()[1] for line in (proc / 'status').read_text().splitlines() if line.startswith('PPid:')), None)
                parent_args = [x for x in (Path('/proc') / ppid / 'cmdline').read_bytes().split(b'\0') if x] if ppid else []
                manager = parent_args in ([b'/usr/lib/systemd/systemd', b'--user'], [b'/lib/systemd/systemd', b'--user'])
            if manager:
                continue  # Dedicated session infrastructure, never agent workers.
            env = (proc / 'environ').read_bytes().split(b'\0')
            hermes = any(re.fullmatch(rb'(hermes|hermes\.py|hermes-cli|run_agent\.py)', os.path.basename(x)) for x in cmd)
            env_home = next((x[len(b'HERMES_HOME='):].decode(errors='replace') for x in env if x.startswith(b'HERMES_HOME=')), None)
            matches = env_home is not None and Path(env_home).absolute() == home
            if env_home is None:
                matches = home == Path.home() / '.hermes'
            # Explicit home argument in service command lines also identifies scope.
            matches = matches or str(home).encode() in cmd
            require(not (hermes and matches), 'Hermes process is running for this home; stop it before handoff.')
            for fd in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(fd).removesuffix(' (deleted)')
                except FileNotFoundError:
                    continue
                require(not (target == str(home) or target.startswith(prefix)), 'Home files are open in another process; stop it before handoff.')
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            if proc.exists():
                raise HandoffError('Cannot verify same-user PID ' + proc.name + ' is offline; refusing.') from None


def load_config(home):
    path = home / 'config.yaml'
    if not path.exists():
        return {}
    value = yaml.safe_load(read_regular(path))
    require(value is None or isinstance(value, dict), 'Local config must be a mapping.')
    return value or {}


def validate_shared(value):
    require(isinstance(value, dict), 'Shared config must be a mapping.')
    for section, fields in value.items():
        require(section in SHARED and isinstance(fields, dict), 'Shared config section is not allowlisted.')
        for name, item in fields.items():
            require(name in SHARED[section], 'Shared config field is not allowlisted.')
            kind = SHARED[section][name]
            valid = ((kind == 'bool' and type(item) is bool) or
                     (kind == 'int' and type(item) is int and 0 <= item <= 100000000) or
                     (kind == 'ratio' and type(item) in (int, float) and math.isfinite(item) and 0 < item <= 1) or
                     (kind == 'str' and type(item) is str and len(item) <= 4096))
            require(valid, 'Shared config field has an invalid scalar type/value.')
    return value


def shared_config(home):
    config = load_config(home)
    result = {}
    for section, names in SHARED.items():
        fields = config.get(section, {})
        if fields is None:
            continue
        require(isinstance(fields, dict), 'Local shared config section must be a mapping.')
        selected = {k: fields[k] for k in names if k in fields}
        for key, value in selected.items():
            if names[key] == 'bool' and type(value) is str and value.lower() in ('true', 'false'):
                selected[key] = value.lower() == 'true'
        if selected:
            result[section] = selected
    return validate_shared(result)


def collect_files(home):
    result = Payload()
    for name in sorted(ROOT_FILES):
        path = home / name
        if path.is_symlink():
            continue
        # A symlink ancestor is skipped without reading it.
        if any(x.is_symlink() for x in path.parents if x != home.parent):
            continue
        if path.is_file():
            result[name] = read_regular(path)
    for rootname in ('skills', 'references'):
        root = home / rootname
        if root.is_symlink() or not root.exists():
            continue
        for current, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if safe_component(d) and not (Path(current) / d).is_symlink())
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(home).as_posix()
                if allowed_path(relative) and not path.is_symlink() and path.is_file():
                    result[relative] = read_regular(path)
                    require(len(result) <= MAX_FILES and sum(map(len, result.values())) <= MAX_BYTES, 'Export exceeds package limits.')
    result['config.shared.json'] = canonical(shared_config(home))
    result.modes = {name: (0o700 if name.startswith(('skills/', 'references/')) and (home / name).stat().st_mode & stat.S_IXUSR else 0o600) for name in result if name != 'config.shared.json'}
    result.modes['config.shared.json'] = 0o600
    return result


def sqlite_snapshot(source, dest):
    no_symlinks(source)
    no_symlinks(source.parent / (source.name + '-wal'))
    no_symlinks(source.parent / (source.name + '-shm'))
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=5)) as src:
        with closing(sqlite3.connect(dest)) as target:
            src.backup(target)
            require(target.execute('PRAGMA integrity_check').fetchone() == ('ok',), 'SQLite snapshot integrity check failed.')
    dest.chmod(0o600)


def db_digest(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        require(db.execute('PRAGMA integrity_check').fetchone() == ('ok',), 'SQLite integrity check failed.')
        return sha('\n'.join(db.iterdump()).encode('utf-8'))


def semantic_digest(files, database=None):
    inventory = {name: {'sha256': sha(data), 'mode': getattr(files, 'modes', {}).get(name, 0o600)} for name, data in files.items() if name != 'state.db'}
    inventory['state.db'] = db_digest(database) if database else None
    return sha(canonical(inventory))


def snapshot(home, temp):
    files = collect_files(home)
    db = home / 'state.db'
    database = None
    if db.exists() or db.is_symlink():
        database = temp / 'state.db'
        sqlite_snapshot(db, database)
    digest = semantic_digest(files, database)
    if database:
        files['state.db'] = read_regular(database)
        files.modes['state.db'] = 0o600
    require(len(files) <= MAX_FILES and sum(map(len, files.values())) <= MAX_BYTES, 'Export exceeds package limits.')
    return files, digest


def validate_uuid(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value, 'Invalid generation identifier.')


def validate_head(head):
    require(isinstance(head, dict) and set(head) == {'schema', 'generation', 'parent', 'device', 'timestamp', 'hermes_version', 'cipher_sha256'}, 'Invalid head schema.')
    require(type(head['schema']) is int and head['schema'] == SCHEMA, 'Unsupported head schema.')
    validate_uuid(head['generation'])
    if head['parent'] is not None:
        validate_uuid(head['parent'])
    safe_alias(head['device'])
    require(all(isinstance(head[k], str) and len(head[k]) <= 128 for k in ('timestamp', 'hermes_version', 'cipher_sha256')), 'Invalid head metadata.')
    require(re.fullmatch('[0-9a-f]{64}', head['cipher_sha256']), 'Invalid ciphertext hash.')
    return head


def package(files, generation, parent, metadata):
    manifest = {'schema': SCHEMA, 'generation': generation, 'parent': parent,
                'head': metadata,
                'database': 'present' if 'state.db' in files else 'absent',
                'files': [{'path': name, 'sha256': sha(data), 'size': len(data), 'mode': files.modes.get(name, 0o600)} for name, data in sorted(files.items())]}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json', canonical(manifest))
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return out.getvalue()


def unpack(cipher, key, head):
    require(sha(cipher) == head['cipher_sha256'], 'Ciphertext hash mismatch; target unchanged.')
    try:
        data = Fernet(key).decrypt(cipher)
    except InvalidToken:
        raise HandoffError('Authentication/decryption failed; target unchanged. Check the out-of-band key.') from None
    require(len(data) <= MAX_BYTES + 2 * 1024 * 1024, 'Package exceeds size limit.')
    files = Payload()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        require(len(entries) <= MAX_FILES + 1 and len(set(names)) == len(names), 'Duplicate paths or excessive file count.')
        require(sum(entry.file_size for entry in entries) <= MAX_BYTES + 1024 * 1024, 'Expanded package exceeds size limit.')
        for entry in entries:
            mode = entry.external_attr >> 16
            require(not entry.is_dir() and not stat.S_ISLNK(mode), 'Package symlinks/directories are forbidden.')
            require(entry.filename == 'manifest.json' or allowed_path(entry.filename), 'Package contains an unsafe/non-allowlisted path.')
            require(entry.file_size >= 0, 'Invalid ZIP size.')
        require('manifest.json' in names, 'Missing manifest.')
        manifest = json.loads(archive.read('manifest.json'))
        require(isinstance(manifest, dict) and set(manifest) == {'schema', 'generation', 'parent', 'head', 'database', 'files'}, 'Invalid manifest schema.')
        require(manifest['head'] == {k: v for k, v in head.items() if k != 'cipher_sha256'}, 'Authenticated head metadata mismatch; target unchanged.')
        require(type(manifest['schema']) is int and manifest['schema'] == SCHEMA and manifest['generation'] == head['generation'] and manifest['parent'] == head['parent'], 'Manifest/head generation mismatch.')
        require(isinstance(manifest['files'], list), 'Invalid manifest inventory.')
        inventory = []
        for item in manifest['files']:
            require(isinstance(item, dict) and set(item) == {'path', 'sha256', 'size', 'mode'}, 'Invalid inventory entry.')
            name = item['path']
            require(allowed_path(name) and name not in inventory, 'Unsafe/duplicate inventory path.')
            inventory.append(name)
            require(type(item['size']) is int and item['size'] >= 0 and isinstance(item['sha256'], str), 'Invalid inventory size/hash.')
            require(name in names, 'Missing inventory file.')
            payload = archive.read(name)
            require(len(payload) == item['size'] and sha(payload) == item['sha256'], 'File integrity check failed; target unchanged.')
            require(type(item['mode']) is int and item['mode'] in (0o600, 0o700) and (item['mode'] == 0o600 or name.startswith(('skills/', 'references/'))), 'Unsafe file mode.')
            files[name] = payload
            files.modes[name] = item['mode']
        require(set(inventory) == set(names) - {'manifest.json'}, 'Inventory/archive mismatch.')
        require(manifest['database'] == ('present' if 'state.db' in files else 'absent'), 'Database presence mismatch.')
        require('config.shared.json' in files, 'Missing shared config.')
        validate_shared(json.loads(files['config.shared.json']))
    return files


class Handoff:
    def __init__(self, repo, home, lane):
        self.lane = safe_alias(lane)
        self.repo = no_symlinks(Path(repo).absolute())
        self.base = no_symlinks(Path(home).absolute())
        self.home = no_symlinks(self.base if lane == 'default' else self.base / 'profiles' / lane)
        self.private = self.base / '.handoff'
        self.local = self.private / lane
        self.shared = self.repo / 'handoff' / lane
        self.receipt_path = self.local / 'receipt.json'

    def initialized(self):
        require((self.local / 'device.json').is_file(), 'Run init --device ALIAS first.')
        private_dir(self.private)
        private_dir(self.local)
        keypath = self.private / 'key'
        require(keypath.stat().st_mode & 0o077 == 0 and keypath.stat().st_uid == os.getuid(), 'Local key must be owned by you and private (chmod 600).')
        key = read_regular(keypath, 1000).strip()
        Fernet(key)
        return key

    def init(self, device, key_file=None):
        safe_alias(device)
        require(self.home.is_dir(), 'Selected Hermes home/profile must already exist.')
        private_dir(self.private)
        private_dir(self.local)
        with exclusive_lock(self.private / 'lock'):
            require(not (self.local / 'device.json').exists(), 'Lane already initialized; refusing to reassign device.')
            keypath = self.private / 'key'
            if key_file:
                source = no_symlinks(Path(key_file).absolute())
                info = source.stat()
                require(stat.S_ISREG(info.st_mode) and info.st_mode & 0o077 == 0 and info.st_uid == os.getuid(), 'Imported key file must be owned by you and private (chmod 600).')
                key = read_regular(source, 1000).strip()
                Fernet(key)
                if keypath.exists():
                    require(read_regular(keypath).strip() == key, 'Existing local key differs; refusing overwrite.')
                else:
                    atomic_write(keypath, key + b'\n')
            elif not keypath.exists():
                atomic_write(keypath, Fernet.generate_key() + b'\n')
            self.initialized_key_check()
            atomic_write(self.local / 'device.json', canonical({'device': device}))
        print('Initialized. Key remains local/private; exchange its file out of band, never Git/chat.')
        print('Private key file: ' + str(self.private / 'key'))

    def initialized_key_check(self):
        p = self.private / 'key'
        require(p.stat().st_mode & 0o077 == 0, 'Local key permissions are not private.')
        Fernet(read_regular(p, 1000).strip())

    def head(self):
        path = self.shared / 'head.json'
        return validate_head(read_json(path)) if path.exists() or path.is_symlink() else None

    def receipt(self):
        if not self.receipt_path.exists():
            return None
        value = read_json(self.receipt_path)
        require(isinstance(value, dict) and value.get('phase') in ('active', 'departed') and isinstance(value.get('managed_paths'), list), 'Invalid local receipt.')
        validate_uuid(value.get('last_generation'))
        require(all(allowed_path(x) for x in value['managed_paths']), 'Unsafe managed path in receipt.')
        return value

    def save_receipt(self, value):
        atomic_write(self.receipt_path, canonical(value))

    @contextmanager
    def locks(self):
        with ExitStack() as stack:
            stack.enter_context(exclusive_lock(self.private / 'lock'))
            stack.enter_context(exclusive_lock(self.repo / 'handoff' / '.lock'))
            yield

    def git(self, *args):
        env = os.environ.copy()
        env['GIT_TERMINAL_PROMPT'] = '0'
        result = subprocess.run(['git', '-C', str(self.repo), *args], capture_output=True,
                                text=True, timeout=60, env=env)
        require(result.returncode == 0, 'Git operation failed (details suppressed to protect credentials).')
        return result.stdout.strip()

    def clean(self):
        text = self.git('status', '--porcelain=v1', '--untracked-files=all')
        entries = text.splitlines()
        require(all(line.endswith('handoff/.lock') and line.startswith('?? ') for line in entries), 'Git worktree/index is dirty; commit or remove unrelated changes manually first.')

    def upstream(self):
        upstream = self.git('rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{upstream}')
        branch = self.git('symbolic-ref', '--short', 'HEAD')
        remote = self.git('config', '--get', 'branch.' + branch + '.remote')
        target = self.git('config', '--get', 'branch.' + branch + '.merge')
        require(remote and not remote.startswith('-') and remote != '.' and target.startswith('refs/heads/'), 'Configure a tracking remote branch first.')
        return upstream, remote, target

    def preflight(self):
        self.clean()
        upstream, remote, _ = self.upstream()
        self.git('fetch', '--quiet', remote)
        ahead = int(self.git('rev-list', '--count', upstream + '..HEAD'))
        require(ahead == 0, 'Local HEAD is ahead/diverged; refusing to publish others\' commits or pull over local work.')
        self.git('merge', '--ff-only', '--no-edit', upstream)
        self.clean()

    def publish(self, receipt):
        """Retry only the exact recorded tool commit; no new snapshot/commit."""
        upstream, remote, target = self.upstream()
        self.clean()
        self.git('fetch', '--quiet', remote)
        require(self.git('rev-parse', 'HEAD') == receipt.get('publish_commit'), 'Pending publish HEAD changed; resolve manually.')
        remote_head = self.git('rev-parse', upstream)
        require(remote_head in (receipt.get('publish_base'), receipt.get('publish_commit')), 'Remote changed after pending departure; resolve manually, never force push.')
        require(self.head()['generation'] == receipt['last_generation'], 'Pending shared generation changed; resolve manually.')
        try:
            self.git('push', '--quiet', remote, 'HEAD:' + target)
            self.git('fetch', '--quiet', remote)
            require(self.git('rev-parse', upstream) == receipt['publish_commit'], 'Remote verification failed.')
        except (HandoffError, subprocess.SubprocessError):
            raise HandoffError('Publish failed or unverified: departed/pending retained. Explicit retry: depart --publish. Do not resume Hermes here.') from None
        receipt['pending_publish'] = False
        self.save_receipt(receipt)

    def depart(self, bootstrap=False, publish=False):
        key = self.initialized()
        with self.locks():
            check_quiescent(self.home)
            receipt = self.receipt()
            if receipt and receipt['phase'] == 'departed':
                if publish and receipt.get('pending_publish') and receipt.get('publish_commit'):
                    with tempfile.TemporaryDirectory(dir=self.private) as tmp:
                        _, digest = snapshot(self.home, Path(tmp))
                    require(digest == receipt['baseline'], 'Frozen local state drifted; pending publish refused.')
                    self.publish(receipt)
                    print('Published existing departed generation; remain offline on this device.')
                    return
                raise HandoffError('Already departed; arrive from the peer before departing again.')
            if publish:
                self.preflight()
            head = self.head()
            if receipt:
                require(not bootstrap and head and head['generation'] == receipt['last_generation'], 'Shared generation changed or bootstrap conflicts; sequential handoff required.')
            else:
                require(bootstrap and head is None, 'First departure requires --bootstrap with no existing shared head.')
            generation = str(uuid.uuid4())
            parent = head['generation'] if head else None
            device = safe_alias(read_json(self.local / 'device.json')['device'])
            try:
                version = importlib.metadata.version('hermes-agent')
            except importlib.metadata.PackageNotFoundError:
                version = 'unknown'
            metadata = {'schema': SCHEMA, 'generation': generation, 'parent': parent,
                        'device': device, 'timestamp': datetime.now(timezone.utc).isoformat(),
                        'hermes_version': version}
            with tempfile.TemporaryDirectory(prefix='snapshot-', dir=self.private) as tmp:
                files, digest = snapshot(self.home, Path(tmp))
                check_quiescent(self.home)
                # Re-read semantic state to detect concurrent file/database mutation.
                with tempfile.TemporaryDirectory(dir=self.private) as verify:
                    _, after = snapshot(self.home, Path(verify))
                require(after == digest, 'Local state changed during snapshot; refusing departure.')
                cipher = Fernet(key).encrypt(package(files, generation, parent, metadata))
            metadata['cipher_sha256'] = sha(cipher)
            base_commit = self.git('rev-parse', 'HEAD') if publish else None
            atomic_write(self.shared / 'latest.enc', cipher)
            atomic_write(self.shared / 'head.json', canonical(metadata))
            receipt = {'last_generation': generation, 'phase': 'departed', 'baseline': digest,
                       'managed_paths': sorted(files), 'pending_publish': publish,
                       'publish_base': base_commit, 'publish_commit': None}
            self.save_receipt(receipt)
            if publish:
                try:
                    iteration = self.repo / 'ITERATION.md'
                    previous = read_regular(iteration) if iteration.exists() else b''
                    entry = ('\n\n## Hermes handoff ' + metadata['timestamp'] + '\n'
                             '- Encrypted sequential handoff: lane ' + self.lane + ', device ' + device + '.\n'
                             '- Generation ' + generation + '; no plaintext history or key in Git.\n')
                    atomic_write(iteration, previous + entry.encode())
                    self.git('add', '--', 'handoff/' + self.lane + '/latest.enc',
                             'handoff/' + self.lane + '/head.json', 'ITERATION.md')
                    self.git('commit', '-m', 'chore: encrypted Hermes handoff ' + self.lane)
                    receipt['publish_commit'] = self.git('rev-parse', 'HEAD')
                    self.save_receipt(receipt)
                    self.publish(receipt)
                except (HandoffError, subprocess.SubprocessError):
                    if receipt.get('publish_commit'):
                        raise HandoffError('Publish failed or unverified: departed/pending retained. Explicit retry: depart --publish. Do not resume Hermes here.') from None
                    raise HandoffError('Commit failed: departed/pending retained. Resolve Git index/worktree manually; do not resume Hermes or force another snapshot.') from None
            print('Departed' + (' and verified published.' if publish else ' (local only; not committed/pushed).'))
            print('Remain offline here. Attachments, project files, sessions dumps and cron/auth/runtime files are NOT synchronized.')
            if 'state.db' not in files:
                print('Source state.db absent; peer database will be preserved, not cleared.')

    def restore(self, files, head, receipt):
        shared = validate_shared(json.loads(files['config.shared.json']))
        config = load_config(self.home)
        for section, values in shared.items():
            existing = config.get(section)
            require(existing is None or isinstance(existing, dict), 'Local config section cannot be safely merged.')
            merged = dict(existing or {})
            merged.update(values)
            config[section] = merged
        targets = {k: v for k, v in files.items() if k != 'config.shared.json'}
        targets['config.yaml'] = yaml.safe_dump(config, sort_keys=False, allow_unicode=True).encode()
        old_managed = set(receipt['managed_paths']) if receipt else set()
        deleted = old_managed - set(files) - {'state.db', 'config.shared.json'}
        touched = set(targets) | deleted
        for name in touched | {'state.db-wal', 'state.db-shm'}:
            no_symlinks(self.home / name)
            require(not (self.home / name).exists() or (self.home / name).is_file(), 'Destination conflicts with non-file path.')
        with tempfile.TemporaryDirectory(prefix='restore-stage-', dir=self.private) as tmp:
            stage = Path(tmp)
            for name, data in targets.items():
                atomic_write(stage / name, data, files.modes.get(name, 0o600))
                require(sha(read_regular(stage / name)) == sha(data), 'Staged write verification failed.')
            if 'state.db' in targets:
                db_digest(stage / 'state.db')
            backup = self.private / 'backups' / str(uuid.uuid4())
            private_dir(backup)
            with tempfile.TemporaryDirectory(dir=self.private) as snap:
                backup_files, _ = snapshot(self.home, Path(snap))
            backup_files.pop('config.shared.json', None)
            if (self.home / 'config.yaml').exists():
                backup_files['config.yaml'] = read_regular(self.home / 'config.yaml')
            original = {name: backup_files.get(name) for name in touched}
            original_modes = {name: stat.S_IMODE((self.home / name).stat().st_mode) for name in touched if (self.home / name).exists()}
            for name, data in backup_files.items():
                atomic_write(backup / name, data, original_modes.get(name, 0o600))
                require(sha(read_regular(backup / name)) == sha(data), 'Backup verification failed.')
            atomic_write(backup / 'backup.json', canonical({'schema': SCHEMA, 'generation': head['generation'], 'original_paths': sorted(backup_files)}))
            if 'state.db' in backup_files:
                db_digest(backup / 'state.db')
            check_quiescent(self.home)
            changed = []
            try:
                if 'state.db' in targets:
                    for side in ('state.db-wal', 'state.db-shm'):
                        (self.home / side).unlink(missing_ok=True)
                for name in sorted(touched):
                    dest = self.home / name
                    no_symlinks(dest)
                    changed.append(name)
                    if name in targets:
                        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        os.replace(stage / name, dest)
                    else:
                        dest.unlink(missing_ok=True)
                with tempfile.TemporaryDirectory(dir=self.private) as verify:
                    _, baseline = snapshot(self.home, Path(verify))
                self.save_receipt({'last_generation': head['generation'], 'phase': 'active',
                                   'baseline': baseline, 'managed_paths': sorted(files),
                                   'pending_publish': False})
            except Exception:
                try:
                    if 'state.db' in targets:
                        for side in ('state.db-wal', 'state.db-shm'):
                            (self.home / side).unlink(missing_ok=True)
                    for name in reversed(changed):
                        if original[name] is None:
                            (self.home / name).unlink(missing_ok=True)
                        else:
                            atomic_write(self.home / name, original[name], original_modes.get(name, 0o600))
                except Exception:
                    raise HandoffError('Restore and rollback failed; backup retained locally. Keep Hermes stopped and recover manually.') from None
                raise HandoffError('Restore failed; original files rolled back, backup retained, receipt unchanged.') from None
        print('Arrived; verified local backup retained under .handoff/backups/. Local credentials/connections preserved.')
        print('Attachments and project files are NOT synchronized; canonical chat database only, no sessions dump merge.')
        if 'state.db' not in files:
            print('Source state.db absent; local database preserved.')

    def arrive(self, bootstrap=False, pull=False):
        key = self.initialized()
        with self.locks():
            check_quiescent(self.home)
            if pull:
                self.preflight()
            head = self.head()
            require(head is not None, 'No shared head exists.')
            receipt = self.receipt()
            if receipt:
                if receipt['phase'] == 'active' and receipt['last_generation'] == head['generation']:
                    print('arrive no-op: already active on this generation; local work preserved.')
                    return
                require(not bootstrap and receipt['phase'] == 'departed' and head['parent'] == receipt['last_generation'], 'Non-sequential handoff/active conflict; manual reconciliation required, no force restore.')
                require(not receipt.get('pending_publish'), 'Pending publish must be resolved before arrival.')
                with tempfile.TemporaryDirectory(dir=self.private) as tmp:
                    _, digest = snapshot(self.home, Path(tmp))
                require(digest == receipt['baseline'], 'Frozen local state drifted; refusing overwrite.')
            else:
                require(bootstrap, 'First arrival requires explicit --bootstrap and private full-scope backup.')
                require(head['device'] != read_json(self.local / 'device.json')['device'], 'Same device identity on first arrival; initialize the peer with a distinct device alias.')
            files = unpack(read_regular(self.shared / 'latest.enc', MAX_CIPHER), key, head)
            self.restore(files, head, receipt)

    def status(self):
        self.initialized()
        receipt = self.receipt()
        head = self.head()
        print(canonical({'lane': self.lane, 'phase': receipt['phase'] if receipt else 'unbootstrapped',
                         'last_generation': receipt['last_generation'] if receipt else None,
                         'shared_generation': head['generation'] if head else None,
                         'pending_publish': bool(receipt and receipt.get('pending_publish'))}).decode())

    def doctor(self):
        if not (self.local / 'device.json').exists():
            require(sys.platform.startswith('linux'), 'This tool supports Linux/WSL only.')
            require(self.home.is_dir(), 'Selected Hermes home/profile does not exist.')
            shared_config(self.home)
            self.git('rev-parse', '--show-toplevel')
            print('doctor: not initialized; dependencies, home and shared config OK. Run init --device ALIAS, then doctor again with Hermes stopped.')
            return
        self.initialized()
        with self.locks():
            check_quiescent(self.home)
            with tempfile.TemporaryDirectory(dir=self.private) as tmp:
                files, _ = snapshot(self.home, Path(tmp))
            head = self.head()
            if head:
                unpack(read_regular(self.shared / 'latest.enc', MAX_CIPHER), self.initialized(), head)
        print('doctor OK: offline, private key, allowlisted config, database ' + ('integrity OK.' if 'state.db' in files else 'absent.'))
        print('Attachments/project files not synchronized. Other profiles and local credentials are excluded.')


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    result.add_argument('--home', type=Path, default=Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))))
    result.add_argument('--lane', default='default', help='default = root; NAME = exactly root/profiles/NAME')
    sub = result.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--device', required=True)
    init.add_argument('--key-file', type=Path)
    sub.add_parser('status')
    depart = sub.add_parser('depart')
    depart.add_argument('--bootstrap', action='store_true')
    depart.add_argument('--publish', action='store_true')
    arrive = sub.add_parser('arrive')
    arrive.add_argument('--bootstrap', action='store_true')
    arrive.add_argument('--pull', action='store_true')
    sub.add_parser('doctor')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        h = Handoff(args.repo, args.home, args.lane)
        if args.command == 'init':
            h.init(args.device, args.key_file)
        elif args.command == 'depart':
            h.depart(args.bootstrap, args.publish)
        elif args.command == 'arrive':
            h.arrive(args.bootstrap, args.pull)
        elif args.command == 'status':
            h.status()
        else:
            h.doctor()
        return 0
    except HandoffError as error:
        print('ERROR: ' + str(error), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, zipfile.BadZipFile,
            yaml.YAMLError, subprocess.SubprocessError):
        print('ERROR: Local/package/Git validation failed; sensitive details suppressed. Keep Hermes stopped and inspect private backups/status.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
