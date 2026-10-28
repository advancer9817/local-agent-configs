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

    def complete(self, prompt):
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

    async def test_session_skips_model_and_completes_after_native_retain(self):
        self.session("user: hi\n\nassistant: hello")
        await self.processor.step()
        self.assertEqual(self.model.calls, 0)
        self.assertEqual(self.current()["status"], "retaining")
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        self.assertEqual(self.current()["status"], "completed")

    async def test_newer_version_overwrites_unprocessed_older_one(self):
        self.session("user: v1")
        self.session("user: v2")
        self.session("user: v3")
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.assertEqual(self.adapter.submit.await_args.args[0]["refined_text"], "user: v3")

    async def test_version_during_retain_waits_for_inflight_operation(self):
        first = self.session("user: v1")
        await self.processor.step()
        self.session("user: v1\n\nuser: v2")
        row = self.current()
        self.assertEqual(row["inflight_id"], first["retain_id"])
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 1)
        self.store.update(row["job_id"], next_at=0)
        self.adapter.status.return_value = {"status": "completed"}
        await self.processor.step()
        self.assertEqual(self.adapter.submit.await_count, 2)
        self.assertIsNone(self.current()["inflight_id"])

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


if __name__ == "__main__":
    unittest.main()
