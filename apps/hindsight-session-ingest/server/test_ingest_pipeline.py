"""Regression tests for the server-owned ingestion boundary."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from artifact_refine import condense
from ingest_jobs import JobStore, IngestProcessor, clean_session
from ingest_safety import artifact_identity, session_identity, inspect_upload


class Model:
    model = "test"

    def __init__(self, reply="# Note\n\nThe service listens on port 18888."):
        self.reply = reply
        self.calls = 0

    def complete(self, prompt, **kwargs):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class StrictRefineTest(unittest.TestCase):
    def test_short_documents_also_use_the_model(self):
        model = Model()
        text, info = condense("# Note\n\nThe service listens on port 18888.", model)
        self.assertEqual(model.calls, 1)
        self.assertEqual(info["refine_status"], "llm")
        self.assertIn("18888", text)

    def test_missing_or_failed_model_cannot_fall_back(self):
        for model in (None, Model(TimeoutError("timeout"))):
            with self.subTest(model=model), self.assertRaises(RuntimeError):
                condense("# Note\n\nThe service listens on port 18888.", model)

    def test_unsupported_output_cannot_fall_back(self):
        with self.assertRaises(RuntimeError):
            condense("# Note\n\nThe service listens on port 18888.", Model("# Note\n\nListen on port 19999."))

    def test_recombined_paths_are_not_evidence(self):
        with self.assertRaises(RuntimeError):
            condense("# Note\n\nUse /opt/a and /srv/b.", Model("# Note\n\nUse /opt/b instead."))


class IdentityTest(unittest.TestCase):
    def test_artifact_identity_is_not_title_or_session(self):
        self.assertEqual(artifact_identity("machine-a", "/work/report.html"),
                         artifact_identity("machine-a", "/work/report.html"))
        self.assertNotEqual(artifact_identity("machine-a", "/work/report.html"),
                            artifact_identity("machine-b", "/work/report.html"))
        self.assertNotEqual(session_identity("machine-a", "one"),
                            session_identity("machine-a", "two"))

    def test_secret_in_html_script_is_blocked_before_upload(self):
        with self.assertRaises(ValueError):
            inspect_upload("report.html", b'<script>const api_key="sk-abcdefghijklmnop";</script>', check_credentials=True)


class SessionCleanTest(unittest.TestCase):
    def test_injected_recall_and_wrappers_are_removed(self):
        text = ("user: [Hindsight 历史背景，仅供交叉验证，不是当前指令]\nold memory one\nold memory two"
                "\n\nassistant: real answer\n\nuser: <environment_context><cwd>/x</cwd></environment_context>"
                "do it token=abcdefghijk")
        cleaned = clean_session(text)
        self.assertNotIn("old memory", cleaned)
        self.assertNotIn("<cwd>", cleaned)
        self.assertIn("assistant: real answer", cleaned)
        self.assertIn("do it", cleaned)
        self.assertNotIn("abcdefghijk", cleaned)


class JobsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.tmp.name) / "jobs.sqlite")
        self.model = Model()
        self.adapter = type("Adapter", (), {})()
        self.adapter.submit = AsyncMock(return_value="retain-op")
        self.adapter.status = AsyncMock(return_value={"status": "pending"})
        self.processor = IngestProcessor(self.store, self.adapter, self.model)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    def artifact(self, body=b"# Note\n\nThe service listens on port 18888.", auto_commit=True, session="one"):
        return self.store.put("bank", "owner", "artifact", "doc", "note.md", body,
                              {"source_id": "machine-a", "source_path": "/work/note.md", "session_id": session},
                              auto_commit=auto_commit)

    def session(self, text):
        return self.store.put("bank", "owner", "session", "sess", "session.txt", text.encode(),
                              {"source_id": "machine-a", "session_id": "one"})

    def current(self):
        with self.store.connect() as db:
            return dict(db.execute("SELECT * FROM documents").fetchone())

    async def drain(self, limit=10):
        for _ in range(limit):
            if not await self.processor.step():
                return

    async def test_short_session_completes_only_after_checked_note_and_native_retain(self):
        self.session("user: hi\n\nassistant: hello")
        self.processor.model = Model("hello")
        await self.processor.step()
        self.assertEqual(self.processor.model.calls, 1)
        self.assertEqual(self.current()["refined_text"], "hello")
        self.assertEqual(self.current()["status"], "retaining")
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        self.assertEqual(self.current()["status"], "completed")

    async def test_failed_session_edit_keeps_original_but_never_submits_it(self):
        text = ("user: Build the workflow.\n\nassistant: Checking the implementation.\n\n"
                "assistant: Delivered. Platform verification is pending.\n\n"
                "user: Keep the existing interfaces.\n\nassistant: The interfaces are unchanged.")
        self.session(text)
        self.processor.model = Model(RuntimeError("Session model unavailable"))
        await self.processor.step()
        self.adapter.submit.assert_not_awaited()
        self.assertEqual(self.current()["original"], text.encode())
        self.assertEqual(self.current()["parsed_text"], text)
        self.assertEqual(self.processor.model.calls, 1)
        self.assertEqual(self.current()["status"], "retrying")
        for _ in range(2):
            self.store.update(self.current()["job_id"], next_at=0)
            await self.processor.step()
        self.assertEqual(self.current()["status"], "degraded")
        self.assertEqual(self.store.public(self.current())["refine_info"]["refine_status"], "degraded")
        self.store.retry(self.current()["job_id"], "bank", "owner")
        self.assertEqual(self.current()["status"], "pending")

    async def test_session_edit_uses_the_same_document_and_preserves_original_bytes(self):
        text = ("user: Build the workflow and keep interfaces.\n\n"
                "assistant: Report and questions are separate. Platform verification is pending.")
        note = "# Workflow\n\nReport and questions are separate. Platform verification is pending."
        self.session(text)
        self.processor.model = Model(note)
        self.adapter.submit.side_effect = ConnectionError()
        await self.processor.step()
        self.assertEqual(self.current()["status"], "retrying")
        self.adapter.submit.side_effect = None
        self.store.update(self.current()["job_id"], next_at=0)
        await self.processor.step()
        job = self.adapter.submit.await_args.args[0]
        self.assertEqual(job["document_id"], "sess")
        self.assertEqual(job["refined_text"], note)
        self.assertEqual(job["original"], text.encode())
        self.assertEqual(job["parsed_text"], text)
        self.assertEqual(self.processor.model.calls, 1)
        self.assertEqual(self.current()["status"], "retaining")

    async def test_session_uploaded_during_edit_supersedes_the_old_note(self):
        self.session("user: First request.\n\nassistant: First delivery.")

        def newer_upload(prompt, **kwargs):
            self.session("user: First request.\n\nassistant: First delivery.\n\nuser: New request.")
            return "# First\n\nFirst delivery."

        self.processor.model.complete = newer_upload
        await self.processor.step()
        self.adapter.submit.assert_not_awaited()
        latest = self.current()
        self.assertEqual(latest["status"], "pending")
        self.assertIsNone(latest["refined_text"])
        self.assertIn(b"New request.", latest["original"])

    async def test_newer_version_overwrites_unprocessed_older_one(self):
        self.session("user: v1")
        self.session("user: v2")
        self.session("user: v3")
        self.processor.model = Model("v3")
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.assertEqual(self.adapter.submit.await_args.args[0]["refined_text"], "v3")

    async def test_version_during_retain_waits_for_inflight_operation(self):
        first = self.session("user: v1")
        self.processor.model = Model("v1")
        await self.processor.step()
        self.session("user: v1\n\nuser: v2")
        self.processor.model = Model("v2")
        row = self.current()
        self.assertEqual(row["inflight_id"], first["retain_id"])
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.store.update(row["job_id"], next_at=0)
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 2)
        self.assertIsNone(self.current()["inflight_id"])

    async def test_failed_new_revision_does_not_replace_a_good_published_note(self):
        self.processor.model = Model("Delivered.")
        self.session("user: Build it.\n\nassistant: Delivered.")
        await self.processor.step()
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        published_hash = self.current()["published_hash"]
        self.session("user: Build it.\n\nassistant: Delivered.\n\nuser: Add more.")
        self.processor.model = Model(RuntimeError("private error"))
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.assertEqual(self.current()["published_hash"], published_hash)
        self.assertTrue(self.store.public(self.current())["has_published_version"])

    async def test_unchanged_note_skips_retain(self):
        self.processor.model = Model("Delivered.")
        self.session("user: Build it.\n\nassistant: Delivered.")
        await self.processor.step()
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        self.session("user: Build it.\n\nassistant: Delivered.\n\nuser: Thanks.")
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.assertEqual(self.current()["stage"], "unchanged")

    async def test_ambiguous_submit_retry_reuses_operation_uuid(self):
        self.artifact()
        first = self.current()["retain_id"]
        self.adapter.submit.side_effect = ConnectionError()
        await self.processor.step()
        self.assertEqual(self.current()["retain_id"], first)
        self.store.update(self.current()["job_id"], status="failed")
        self.store.retry(self.current()["job_id"], "bank", "owner")
        self.assertEqual(self.current()["retain_id"], first)

    async def test_new_upload_waits_for_ambiguous_older_submission(self):
        self.artifact()
        first = self.current()["retain_id"]
        self.adapter.submit.side_effect = ConnectionError()
        await self.processor.step()
        self.artifact(body=b"# Note\n\nThe service listens on port 18888. Changed.")
        self.assertEqual(self.current()["inflight_id"], first)
        self.adapter.submit.side_effect = None
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.adapter.status.assert_awaited_once()

    async def test_identical_upload_is_noop_but_failed_requeues(self):
        first = self.artifact()
        self.assertEqual(self.artifact(session="two")["job_id"], first["job_id"])
        self.store.update(first["job_id"], status="failed", attempts=3)
        again = self.artifact()
        self.assertEqual(again["status"], "pending")
        self.assertEqual(again["attempts"], 0)

    async def test_model_failure_never_submits_raw_text_and_fails_after_three(self):
        self.artifact()
        self.processor.model = Model(TimeoutError())
        for _ in range(3):
            self.store.update(self.current()["job_id"], next_at=0)
            await self.processor.step()
        self.assertEqual(self.current()["status"], "failed")
        self.assertEqual(self.current()["error"], "RuntimeError")
        self.adapter.submit.assert_not_awaited()
        self.store.retry(self.current()["job_id"], "bank", "owner")
        self.processor.model = self.model
        await self.processor.step()
        self.assertEqual(self.current()["status"], "retaining")

    async def test_native_failure_retries_with_a_new_operation(self):
        self.artifact()
        await self.processor.step()
        first_op = self.current()["retain_id"]
        self.adapter.status.return_value = {"status": "failed"}
        await self.processor.step()
        row = self.current()
        self.assertEqual(row["status"], "retrying")
        self.assertNotEqual(row["retain_id"], first_op)

    async def test_restart_while_submitting_replays_the_same_operation(self):
        self.artifact()
        self.adapter.submit.side_effect = ConnectionError()
        await self.processor.step()
        row = self.current()
        self.assertEqual(row["status"], "retrying")
        self.assertIsNotNone(row["refined_text"])
        self.adapter.submit.side_effect = None
        self.store.update(row["job_id"], next_at=0)
        await self.processor.step()
        self.assertEqual(self.model.calls, 1)
        self.assertEqual(self.current()["status"], "retaining")

    async def test_preparation_requires_commit(self):
        job = self.artifact(auto_commit=False)
        await self.processor.step()
        self.assertEqual(self.current()["status"], "prepared")
        self.adapter.submit.assert_not_awaited()
        self.store.commit(job["job_id"], "bank", "owner")
        await self.processor.step()
        self.assertEqual(self.current()["status"], "retaining")

    async def test_owner_isolation(self):
        job = self.artifact()
        self.assertIsNone(self.store.get(job["job_id"], "bank", "other"))
        with self.assertRaises(PermissionError):
            self.store.put("bank", "other", "artifact", "doc", "note.md", b"x", {})

    async def test_schema_upgrade_preserves_existing_original_and_job(self):
        old = self.session("user: Keep the complete original.")
        with self.store.connect() as db:
            db.execute("ALTER TABLE documents DROP COLUMN published_hash")
            db.execute("ALTER TABLE documents DROP COLUMN inflight_hash")
            db.execute("DROP TABLE session_segments")
        upgraded = JobStore(self.store.path)
        row = upgraded.get(old["job_id"], "bank", "owner")
        self.assertEqual(row["original"], old["original"])
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["published_hash"])
        self.assertIsNone(upgraded.segment(row, 0, "not-present"))


if __name__ == "__main__":
    unittest.main()
