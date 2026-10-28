"""Upload boundaries and stable identities. This module never summarizes content."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

PIPELINE_VERSION = 3
MAX_SOURCE_BYTES = 20_000_000
SUFFIXES = {".md", ".txt", ".rst", ".csv", ".json", ".html", ".htm", ".pdf", ".docx", ".pptx", ".xlsx"}
OFFICE = {".docx", ".pptx", ".xlsx"}
SECRET = re.compile(
    r"(?i)Bearer\s+[A-Za-z0-9_./+=-]{8,}|\b(?:sk-|ghp_|github_pat_|gsk_)[A-Za-z0-9_-]{12,}"
    r"|-----BEGIN [^-]*PRIVATE KEY-----"
    r"""|(?:api[_-]?key|(?:auth|access|refresh|mcp)[_-]?token|token|password|secret)["']?\s*[=:]\s*["']?(?!\[REDACTED\])[^\s"'<>;,}]{6,}"""
)


def _identity(kind, *parts):
    return kind + "-" + hashlib.sha256("\0".join(parts).encode()).hexdigest()


def artifact_identity(source_id, source_path):
    return _identity("agent-artifact-v6", source_id, source_path)


def session_identity(source_id, session_id):
    return _identity("agent-session-v6", source_id, session_id)


def inspect_upload(filename, data):
    """Fail closed on detected secrets or formats that cannot be safely inspected locally.

    Office inspection covers all XML members, including hidden sheets and notes.
    It is a credential preflight, not a document parser or a full DLP guarantee.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in SUFFIXES or not 0 < len(data) <= MAX_SOURCE_BYTES:
        raise ValueError("Unsupported document type or size")
    if suffix == ".pdf":
        raise ValueError("PDF requires an explicit safe export before upload; local inspection is unavailable")
    if suffix in OFFICE:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 2000 or sum(item.file_size for item in members) > 8_000_000:
                raise ValueError("Office package exceeds safety limits")
            for member in members:
                if member.is_dir():
                    continue
                raw = archive.read(member)
                # Embedded binaries/macros can conceal content the preflight cannot inspect.
                if not member.filename.endswith((".xml", ".rels")):
                    raise ValueError("Office package has uninspectable embedded content; export a safe text copy")
                source = raw.decode("utf-8-sig")
                tree = ET.fromstring(source)
                if SECRET.search(source) or SECRET.search("".join(tree.itertext())):
                    raise ValueError("Credentials detected; export a redacted copy before upload")
    else:
        text = data.decode("utf-8-sig")
        if "\0" in text or SECRET.search(text):
            raise ValueError("Binary content or credentials detected; export a redacted copy before upload")
    return data
