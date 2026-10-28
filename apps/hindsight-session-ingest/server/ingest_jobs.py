"""Latest-version ingestion queue. Native Hindsight retain remains the persistence boundary.

One row per (bank, document). A newer upload overwrites any unprocessed older
version; only the latest version is parsed, refined and retained.
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import time
import uuid

from artifact_refine import condense, parse_original, refine_archive
from ingest_safety import PIPELINE_VERSION
from session_documents import redact

MAX_ATTEMPTS = 3
ACTIVE = ("pending", "processing", "retrying", "submitting", "retaining")
TERMINAL = ("completed", "failed", "cancelled", "not_found")
# Recall context injected by our own hook is history, not new conversation.
NOISE = [
    re.compile(r"\[Hindsight 历史背景[^\n]*\n.*?(?=\n\n(?:user|assistant): |$)", re.S),
    re.compile(r"<(external_codex_git_state|environment_context|codex_apps_client_time_context|system-reminder)\b.*?</\1>", re.S),
]


def clean_session(text):
    for pattern in NOISE:
        text = pattern.sub("", text)
    return redact(re.sub(r"\n{3,}", "\n\n", text)).strip()


def revision_key(kind, data, metadata, auto_commit):
    # Session provenance does not change an artifact; a different session may mention it again.
    identity = {key: value for key, value in metadata.items()
                if key not in ("session_id", "parent_session_id", "parent_title")}
    return hashlib.sha256(json.dumps(
        [PIPELINE_VERSION, kind, hashlib.sha256(data).hexdigest(), identity, bool(auto_commit)],
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class JobStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS documents (
                bank_id TEXT NOT NULL, document_id TEXT NOT NULL, job_id TEXT UNIQUE NOT NULL,
                owner TEXT NOT NULL, kind TEXT NOT NULL, session_id TEXT, filename TEXT NOT NULL,
                original BLOB NOT NULL, revision TEXT NOT NULL, request TEXT NOT NULL,
                status TEXT NOT NULL, stage TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                next_at REAL NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL,
                parsed_text TEXT, refined_text TEXT, refine_info TEXT, error TEXT,
                retain_id TEXT NOT NULL, inflight_id TEXT, auto_commit INTEGER NOT NULL,
                PRIMARY KEY (bank_id, document_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS documents_ready ON documents(status,next_at)")
            db.execute("CREATE INDEX IF NOT EXISTS documents_session ON documents(bank_id,session_id)")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def put(self, bank_id, owner, kind, document_id, filename, data, metadata, *, auto_commit=True):
        """Store the latest version. Identical content is a no-op unless it previously failed."""
        payload = dict(metadata, job_kind=kind, pipeline_version=PIPELINE_VERSION)
        revision = revision_key(kind, data, payload, auto_commit)
        now = time.time()
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE bank_id=? AND document_id=?",
                             (bank_id, document_id)).fetchone()
            if row is not None and row["owner"] != owner:
                raise PermissionError("Document belongs to another owner")
            if row is not None and row["revision"] == revision:
                if row["status"] == "failed":
                    db.execute("""UPDATE documents SET status='pending', stage='received', attempts=0,
                        next_at=0, error=NULL, retain_id=?, updated=? WHERE job_id=?""",
                               (str(uuid.uuid4()), now, row["job_id"]))
            else:
                # A version already handed to native retain keeps running; the new one waits for it.
                inflight = None
                if row is not None:
                    inflight = row["retain_id"] if row["status"] in ("submitting", "retaining") else row["inflight_id"]
                values = dict(
                    bank_id=bank_id, document_id=document_id, job_id=str(uuid.uuid4()), owner=owner,
                    kind=kind, session_id=metadata.get("session_id"), filename=filename, original=data,
                    revision=revision, request=json.dumps(payload, ensure_ascii=False), status="pending",
                    stage="received", attempts=0, next_at=0, created=row["created"] if row else now,
                    updated=now, parsed_text=None, refined_text=None, refine_info=None, error=None,
                    retain_id=str(uuid.uuid4()), inflight_id=inflight, auto_commit=int(auto_commit))
                db.execute("INSERT OR REPLACE INTO documents (" + ",".join(values) + ") VALUES ("
                           + ",".join("?" for _ in values) + ")", tuple(values.values()))
            row = db.execute("SELECT * FROM documents WHERE bank_id=? AND document_id=?",
                             (bank_id, document_id)).fetchone()
        return dict(row)

    def get(self, job_id, bank_id, owner):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE job_id=? AND bank_id=? AND owner=?",
                             (job_id, bank_id, owner)).fetchone()
        return dict(row) if row else None

    def list(self, bank_id, owner, status=None, session_id=None, limit=100):
        query, args = "SELECT * FROM documents WHERE bank_id=? AND owner=?", [bank_id, owner]
        if status:
            query, args = query + " AND status=?", args + [status]
        if session_id:
            query, args = query + " AND session_id=?", args + [session_id]
        with self.connect() as db:
            rows = db.execute(query + " ORDER BY updated DESC LIMIT ?", (*args, limit)).fetchall()
        return [dict(row) for row in rows]

    def update(self, job_id, **fields):
        """Write only while job_id is still the latest version; False means superseded."""
        allowed = {"status", "stage", "attempts", "next_at", "parsed_text", "refined_text", "refine_info",
                   "error", "auto_commit", "retain_id", "inflight_id"}
        if not fields or not set(fields) <= allowed:
            raise ValueError("Unsupported job update")
        fields["updated"] = time.time()
        with self.connect() as db:
            cursor = db.execute("UPDATE documents SET " + ",".join(f"{field}=?" for field in fields)
                                + " WHERE job_id=?", (*fields.values(), job_id))
        return cursor.rowcount == 1

    def next(self):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE status IN (?,?,?,?,?) AND next_at<=? "
                             "ORDER BY next_at, updated LIMIT 1", (*ACTIVE, time.time())).fetchone()
        return dict(row) if row else None

    def retry(self, job_id, bank_id, owner):
        with self.connect() as db:
            cursor = db.execute("""UPDATE documents SET status='pending', stage='received', attempts=0,
                next_at=0, error=NULL, retain_id=?, updated=? WHERE job_id=? AND bank_id=? AND owner=?
                AND status='failed'""", (str(uuid.uuid4()), time.time(), job_id, bank_id, owner))
        if cursor.rowcount != 1:
            raise ValueError("Only failed documents can be retried")
        return self.get(job_id, bank_id, owner)

    def commit(self, job_id, bank_id, owner):
        """Second confirmation for bootstrap archives; ordinary uploads auto-commit."""
        job = self.get(job_id, bank_id, owner)
        if job is None:
            raise KeyError(job_id)
        if job["auto_commit"]:
            return job
        if job["status"] != "prepared":
            raise ValueError("Only prepared documents may be committed")
        self.update(job_id, auto_commit=1, status="pending", stage="commit", next_at=0)
        return self.get(job_id, bank_id, owner)

    @staticmethod
    def public(job, preview=False):
        result = {key: job[key] for key in ("job_id", "document_id", "filename", "status", "stage", "attempts", "error")}
        result.update(operation_id=job["job_id"], operation_type="server_ingest", kind=job["kind"],
                      session_id=job["session_id"], updated=job["updated"],
                      refine_info=json.loads(job["refine_info"] or "{}"))
        if preview:
            result["parsed_text"] = job["parsed_text"] or ""
            result["refined_text"] = job["refined_text"] or ""
        return result


class IngestProcessor:
    def __init__(self, store, adapter, model):
        self.store, self.adapter, self.model = store, adapter, model

    async def prepare(self, job):
        """Return (refined, info). Sessions skip the model; documents must pass it."""
        kind = job["kind"]
        if kind == "session":
            text = clean_session(job["original"].decode("utf-8"))
            return text, {"artifact_parser": "session-text", "refine_status": "not_applicable"}
        evidence = None
        if job["parsed_text"] is not None:
            parsed = job["parsed_text"]
            parser = json.loads(job["refine_info"] or "{}").get("artifact_parser", "source-text")
            evidence = json.loads(parsed) if kind == "archive" else None
        elif kind == "archive":
            evidence = []
            for index, source in enumerate(json.loads(job["original"])["sources"], 1):
                data = base64.b64decode(source["data"], validate=True)
                text, _ = await asyncio.to_thread(parse_original, source["filename"], data, "")
                text = redact(text)
                if not text.strip():
                    raise RuntimeError("An archive source has no useful content")
                evidence.append({"id": "S" + str(index), "title": source.get("title", source["filename"]),
                                 "project": source.get("project", ""), "agent": source.get("agent", ""),
                                 "source_snapshot_time": source.get("modified", ""), "text": text})
            parsed, parser = json.dumps(evidence, ensure_ascii=False), "archive-sources"
        else:
            parsed, parser = await asyncio.to_thread(parse_original, job["filename"], job["original"], "")
            parsed = redact(parsed)
        # Keep the parse so a model retry does not parse again.
        self.store.update(job["job_id"], parsed_text=parsed, refine_info=json.dumps({"artifact_parser": parser}))
        job.update(parsed_text=parsed, refine_info=json.dumps({"artifact_parser": parser}))
        if not parsed.strip():
            return "", {"artifact_parser": parser}
        self.store.update(job["job_id"], stage="refine")
        if evidence is not None:
            refined, info = await asyncio.to_thread(refine_archive, evidence, self.model)
        else:
            title = next((line[2:].strip() for line in parsed.splitlines() if line.startswith("# ")), job["filename"])
            refined, info = await asyncio.to_thread(condense, parsed, self.model, title)
        info.update(artifact_parser=parser, digest_chars=len(parsed), refined_chars=len(refined))
        return refined, info

    def fail(self, job, error):
        attempts = job["attempts"] + 1
        self.store.update(job["job_id"], status="failed" if attempts >= MAX_ATTEMPTS else "retrying",
                          attempts=attempts, next_at=time.time() + min(60, 2 ** attempts),
                          error=error, retain_id=str(uuid.uuid4()))

    async def step(self):
        job = self.store.next()
        if job is None:
            return False
        jid = job["job_id"]
        try:
            if job["status"] == "retaining":
                result = await self.adapter.status(job, job["retain_id"])
                if result["status"] == "completed":
                    self.store.update(jid, status="completed", stage="done", error=None)
                elif result["status"] in TERMINAL:
                    self.fail(job, "Hindsight retain " + result["status"])
                else:
                    self.store.update(jid, next_at=time.time() + 2)
                return True
            if job["inflight_id"]:
                # Two retains of one document must not run at once; let the older one finish.
                result = await self.adapter.status(job, job["inflight_id"])
                if result["status"] not in TERMINAL:
                    self.store.update(jid, next_at=time.time() + 2)
                    return True
                self.store.update(jid, inflight_id=None)
            if job["status"] != "submitting":
                if job["refined_text"] is None:
                    self.store.update(jid, status="processing", stage="parse")
                    refined, info = await self.prepare(job)
                    if not refined.strip():
                        self.store.update(jid, status="skipped", stage="empty", error=None)
                        return True
                    if not self.store.update(jid, refined_text=refined, refine_info=json.dumps(info), error=None):
                        return True  # superseded while the model was running
                    job.update(refined_text=refined, refine_info=json.dumps(info))
                if not job["auto_commit"]:
                    self.store.update(jid, status="prepared", stage="awaiting_confirmation")
                    return True
                if not self.store.update(jid, status="submitting", stage="retain"):
                    return True
            # Fixed operation UUID: resubmitting after a crash returns the original operation.
            await self.adapter.submit(job)
            self.store.update(jid, status="retaining", stage="retain", next_at=0, error=None)
        except Exception as error:
            self.fail(job, type(error).__name__)
        return True

    async def run(self):
        while True:
            try:
                worked = await self.step()
            except Exception:
                logging.getLogger(__name__).exception("Ingestion coordinator could not advance its queue")
                await asyncio.sleep(2)
                continue
            await asyncio.sleep(0.1 if worked else 1)
