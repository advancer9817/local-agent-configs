#!/usr/bin/env python3
"""Repository templates use ./ paths relative to the deployment user's HOME."""
from pathlib import Path
import os
import re
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]


def windows_command():
    """WSL interop may be enabled while Windows PATH injection is disabled."""
    found = shutil.which('cmd.exe')
    if found:
        return Path(found)
    mounts = Path(os.environ.get('WSL_MOUNT_ROOT', '/mnt'))
    candidates = sorted(p for p in mounts.glob('*/Windows/System32/cmd.exe') if p.is_file())
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError('Cannot discover Windows: set WINDOWS_USER_HOME / WINDOWS_SYSTEM_ROOT')


def windows_path(path):
    """Convert an existing WSL path with the platform tool, not drive slicing."""
    result = subprocess.run(['wslpath', '-w', str(path)], check=True,
                            capture_output=True, text=True)
    return result.stdout.strip()


def windows_home():
    override = os.environ.get('WINDOWS_USER_HOME')
    if override:
        return Path(override).expanduser().resolve()
    if os.name == 'nt':
        return Path.home()
    cmd = windows_command()
    profile = subprocess.run([str(cmd), '/d', '/c', 'echo', '%USERPROFILE%'],
                             check=True, capture_output=True, text=True).stdout.strip()
    return Path(subprocess.run(['wslpath', '-u', profile], check=True,
                               capture_output=True, text=True).stdout.strip())


def windows_tool(relative):
    override = os.environ.get('WINDOWS_SYSTEM_ROOT')
    if override:
        root = Path(override)
    elif os.name == 'nt':
        root = Path(os.environ['SystemRoot'])
    else:
        # cmd.exe resides in System32; derive the mounted Windows directory.
        root = windows_command().resolve().parent.parent
    return root / relative


def portable_text(text, home=None, winhome=None):
    """Sanitized export: personal home paths -> explicit HOME-relative paths."""
    home = Path(home or Path.home())
    prefixes = [str(home)]
    if winhome:
        prefixes.append(str(winhome))
        try:
            prefixes.extend([windows_path(winhome), windows_path(winhome).replace('\\', '/')])
        except (OSError, subprocess.SubprocessError):
            pass
    # Normalize the existing single-user snapshots, including escaped JSON paths.
    text = re.sub(r'(?i)(?:\\\\\?\\)?[a-z]:[\\/]+Users[\\/]+[^\\/\s"\x27`]+', '.', text)
    text = re.sub(r'/mnt/[a-z]/Users/[^/\s"\x27`]+', '.', text)
    text = re.sub(r'/home/[^/\s"\x27`]+', '.', text)
    for prefix in sorted(set(prefixes), key=len, reverse=True):
        text = text.replace(prefix, '.')
    return re.sub(r'(?<![\w.])\.\\+(?=[\w.])[^\s\x22\x27`]*',
                  lambda m: m.group().replace('\\', '/').replace('//', '/'), text)


def resolve_templates(value, home):
    """Resolve JSON/YAML strings and dictionary keys without shell expansion.

    Paths in commands must be quoted in templates. Resolution keeps those quotes,
    so spaces in the target home are safe. Network URLs are left untouched.
    """
    home = str(Path(home).resolve())
    if isinstance(value, dict):
        return {resolve_templates(k, home): resolve_templates(v, home)
                for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(v, home) for v in value]
    if not isinstance(value, str):
        return value
    return re.sub(r'(?<![\w./:])\./(?=[\w.])', lambda _: home + '/', value)
