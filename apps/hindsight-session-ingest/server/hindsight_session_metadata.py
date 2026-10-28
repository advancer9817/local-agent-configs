"""Enrich incoming session documents from every client before they are retained."""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

from hindsight_api.extensions.operation_validator import (
    OperationValidationError, OperationValidatorExtension, ValidationResult,
)
from ingest_safety import artifact_identity, session_identity
from session_documents import clean_title, fallback_title, load_state, now, original_title, save_state, user_topics

LEGACY_SCHEMA_VERSION = "5"


class SessionDocumentMetadata(OperationValidatorExtension):
    _pool = None

    async def _ensure_pool(self):
        if self._pool is not None:
            return
        if not hasattr(self, "_pool_lock"):
            self._pool_lock = asyncio.Lock()
        async with self._pool_lock:
            if self._pool is None:
                await self.on_startup()

    async def on_startup(self):
        import asyncpg
        runtime = json.loads(Path("/opt/hindsight-research/runtime.json").read_text())
        self._pool = await asyncpg.create_pool(runtime["HINDSIGHT_API_DATABASE_URL"], min_size=0, max_size=2)

    async def on_shutdown(self):
        if self._pool is not None:
            await self._pool.close()

    async def _matching_document(self, bank_id, metadata):
        await self._ensure_pool()
        if bank_id != "mcore-active-snapshot":
            raise OperationValidationError("Original-title adapter is configured only for this bank.", 409)
        sid = metadata.get("session_id")
        if not sid:
            return None
        if metadata.get("document_kind") == "session-artifact":
            row = await self._pool.fetchrow(
                "SELECT id FROM documents WHERE bank_id=$1 AND retain_params->'metadata'->>'session_id'=$2 "
                "AND retain_params->'metadata'->>'document_kind'='session-artifact' "
                "AND retain_params->'metadata'->>'source_path'=$3",
                bank_id, sid, metadata.get("source_path"),
            )
        else:
            rows = await self._pool.fetch(
                "SELECT id FROM documents WHERE bank_id=$1 AND retain_params->'metadata'->>'session_id'=$2 "
                "AND (retain_params->'metadata'->>'document_kind'='agent-session' OR id LIKE 'agent-session-%')",
                bank_id, sid,
            )
            if len(rows) > 1:
                raise OperationValidationError("Multiple documents share this session; resolve them before uploading.", 409)
            row = rows[0] if rows else None
        return row["id"] if row else None

    async def _check_collision(self, bank_id, name, metadata):
        await self._ensure_pool()
        row = await self._pool.fetchrow(
            "SELECT retain_params->'metadata' AS metadata FROM documents WHERE bank_id=$1 AND id=$2",
            bank_id, name,
        )
        if row is None:
            existing = None
        else:
            existing = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"] or {}
        if existing is not None:
            if (existing.get("session_id") != metadata.get("session_id")
                    or existing.get("document_kind") != metadata.get("document_kind")
                    or (metadata.get("document_kind") == "session-artifact"
                        and existing.get("source_path") != metadata.get("source_path"))):
                raise OperationValidationError("The original title belongs to another document; no content was overwritten.", 409)
        await asyncio.to_thread(self._claim_title, bank_id, name, metadata)

    def _claim_title(self, bank_id, title, metadata):
        """Reserve a title across workers before asynchronous ingestion starts."""
        root = Path(self.config.get("identity_dir", "/opt/hindsight-research/original-title-owners"))
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        name = hashlib.sha256((bank_id + "\0" + title).encode()).hexdigest()
        owner = {
            "session_id": metadata.get("session_id"), "document_kind": metadata.get("document_kind"),
            "source_agent": metadata.get("source_agent") or metadata.get("source"),
            "source_path": metadata.get("source_path") if metadata.get("document_kind") == "session-artifact" else None,
        }
        fd = os.open(root / (name + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            saved = load_state(root / (name + ".json"))
            if saved and saved.get("owner") != owner:
                raise OperationValidationError("The original title is already used by another session; change the title instead of overwriting it.", 409)
            save_state(root / (name + ".json"), {"title": title, "owner": owner})

    def _cached_title(self, document_id, content, metadata):
        root = Path(self.config.get("cache_dir", "/opt/hindsight-research/session-document-titles"))
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        identity = hashlib.sha256(document_id.encode()).hexdigest()
        cache = root / (identity + ".json")
        lock_fd = os.open(root / (identity + ".lock"), os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(lock_fd, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            previous = load_state(cache)
            if previous.get("display_title"):
                return previous["display_title"], previous.get("title_source", "cached")
            title = str(metadata.get("original_title") or metadata.get("title") or metadata.get("display_title") or "").strip()
            source = "client_session_title"
            if not title or not re.search(r"[\u3400-\u9fff]", title):
                raise OperationValidationError("The client did not supply the original session title; update the upload hook.", 409)
            save_state(cache, {"display_title": title, "title_source": source, "created_at": now()})
            return title, source

    async def validate_retain(self, ctx):
        enriched = []
        changed = False
        for original in ctx.contents:
            document_id = str(original.get("document_id") or ctx.document_id or "")
            metadata = dict(original.get("metadata") or {})
            kind = metadata.get("document_kind")
            if document_id.startswith("agent-session-"):
                kind = "agent-session"
            elif document_id.startswith("agent-artifact-"):
                kind = "session-artifact"
            if kind not in ("agent-session", "session-artifact"):
                enriched.append(original)
                continue
            if str(metadata.get("ingest_version")) == "6":
                source_id = metadata.get("source_id")
                identity = metadata.get("session_id") if kind == "agent-session" else metadata.get("source_path")
                if not source_id or not identity:
                    raise OperationValidationError("Stable source identity is missing.", 409)
                expected = (session_identity(source_id, identity) if kind == "agent-session"
                            else artifact_identity(source_id, identity))
                if document_id != expected:
                    raise OperationValidationError("Document identity does not match its source.", 409)
                # New clients keep display titles in metadata; never rewrite the primary key.
                item = dict(original)
                item["document_id"] = expected
                item["metadata"] = metadata
                enriched.append(item)
                changed = True
                continue
            item = dict(original)
            metadata["document_kind"] = kind
            bank_id = getattr(ctx, "bank_id", "mcore-active-snapshot")
            existing = await self._matching_document(bank_id, metadata)
            if existing:
                title, source = existing, "original_title"
            elif metadata.get("original_title"):
                title, source = metadata["original_title"], "original_title"
            elif kind == "session-artifact":
                title = metadata.get("title") or metadata.get("display_title") or metadata.get("file_name")
                source = "original_title"
            else:
                title, source = await asyncio.to_thread(
                    self._cached_title, document_id, str(item.get("content") or ""), metadata,
                )
            try:
                title = original_title(title)
            except ValueError as error:
                raise OperationValidationError(str(error), 409) from error
            await self._check_collision(bank_id, title, metadata)
            agent = metadata.get("source_agent") or metadata.get("source") or "unknown"
            # Title-keyed documents stay on schema 5; stamping 6 would make the worker's
            # second validation pass demand a v6 source-derived ID and reject the retain.
            metadata.update({
                "original_title": title, "title": title,
                "display_title": title, "display_title_source": source,
                "source_agent": agent, "document_kind": kind,
                "ingest_version": LEGACY_SCHEMA_VERSION,
            })
            for field in ("legacy_document_id", "parent_document_id"):
                metadata.pop(field, None)
            if kind == "session-artifact" and metadata.get("session_id"):
                metadata["parent_session_id"] = metadata["session_id"]
                parent = await self._matching_document(bank_id, {
                    "session_id": metadata["session_id"], "document_kind": "agent-session",
                })
                if parent:
                    metadata["parent_title"] = parent
            item["document_id"] = title
            item["metadata"] = metadata
            enriched.append(item)
            changed = True
        return ValidationResult.accept_with(contents=enriched) if changed else ValidationResult.accept()

    async def on_retain_complete(self, result):
        """Attach legacy clients' converted files to the canonical original title."""
        operation = getattr(result.request_context, "operation_id", None)
        if self._pool is None or not result.success or not operation:
            return
        row = await self._pool.fetchrow(
            "SELECT task_payload FROM async_operations WHERE bank_id=$1 AND operation_id=$2",
            result.bank_id, operation,
        )
        if row is None:
            return
        task = json.loads(row["task_payload"]) if isinstance(row["task_payload"], str) else row["task_payload"] or {}
        file_metadata = task.get("_file_metadata")
        contents = task.get("contents") or []
        if not file_metadata or len(contents) != 1:
            return
        metadata = contents[0].get("metadata") or {}
        if metadata.get("document_kind") != "session-artifact":
            return
        target = await self._matching_document(result.bank_id, metadata)
        if target:
            await self.context.get_memory_engine().record_document_file(
                result.bank_id, target, storage_key=file_metadata["file_storage_key"],
                original_name=file_metadata["file_original_name"], content_type=file_metadata["file_content_type"],
            )

    async def validate_recall(self, ctx):
        return ValidationResult.accept()

    async def validate_reflect(self, ctx):
        return ValidationResult.accept()
