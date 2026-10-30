import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from fastapi import FastAPI
from fastapi.testclient import TestClient
from artifact_refine import SESSION_REFINE_VERSION, model_object, refine_archive
from ingest_extension import SessionIngestExtension, HindsightAdapter
from ingest_safety import artifact_identity, session_identity


class HttpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.memory = SimpleNamespace(
            _authenticate_tenant=AsyncMock(return_value="public"),
            _refuse_bank_wide_if_scoped=AsyncMock(),
            _check_retain_writes=AsyncMock(),
        )
        self.ext = SessionIngestExtension({"spool_dir": self.tmp.name, "token": "test-token", "bank_id": "b"})
        app = FastAPI()
        app.include_router(self.ext.get_router(self.memory), prefix="/ext")
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test-token"}
        self.url = "/ext/ingest/banks/b"

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def upload(self, text="user: hi\n\nassistant: hello", files=None, manifest=None):
        manifest = manifest or {"source_id": "machine", "session_id": "sid", "agent": "codex", "title": "测试",
                                "artifacts": [{"filename": name, "source_path": "/w/" + name} for name, _ in files or []]}
        parts = [("session", ("session.txt", text.encode()))] if text is not None else []
        parts += [("file" + str(i), (name, data)) for i, (name, data) in enumerate(files or [])]
        return self.client.post(self.url + "/sessions", headers=self.headers,
                                data={"manifest": json.dumps(manifest)}, files=parts)

    def test_requires_authentication_and_bank_scope(self):
        self.assertEqual(self.client.get(self.url + "/capabilities").status_code, 401)
        self.assertEqual(self.client.get("/ext/ingest/banks/other/capabilities", headers=self.headers).status_code, 403)
        self.assertEqual(self.client.get(self.url + "/capabilities", headers=self.headers).status_code, 200)

    def test_session_and_artifacts_in_one_request_use_server_identities(self):
        response = self.upload(files=[("note.md", b"# Note\n\nUseful body.")])
        self.assertEqual(response.status_code, 200, response.text)
        accepted = response.json()["accepted"]
        self.assertEqual([job["kind"] for job in accepted], ["session", "artifact"])
        self.assertEqual(accepted[0]["document_id"], session_identity("machine", "sid"))
        self.assertEqual(accepted[1]["document_id"], artifact_identity("machine", "/w/note.md"))
        self.assertTrue(all(job["status"] == "pending" for job in accepted))
        preview = self.client.get(self.url + "/jobs/" + accepted[1]["job_id"] + "?preview=true", headers=self.headers).json()
        self.assertNotIn("original", preview)
        self.assertNotIn("request", preview)

    def test_repeated_turn_replaces_the_same_session_document(self):
        first = self.upload().json()["accepted"][0]
        second = self.upload("user: hi\n\nassistant: hello\n\nuser: more").json()["accepted"][0]
        self.assertEqual(first["document_id"], second["document_id"])
        self.assertNotEqual(first["job_id"], second["job_id"])
        jobs = self.client.get(self.url + "/jobs", headers=self.headers).json()["jobs"]
        self.assertEqual(len(jobs), 1)

    def test_session_edit_version_keeps_the_original_upload_and_document_identity(self):
        text = "user: Build the workflow.\n\nassistant: Delivered; platform verification pending."
        response = self.upload(text)
        self.assertEqual(response.status_code, 200)
        with self.ext.store.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE kind='session'").fetchone()
        self.assertEqual(row["document_id"], session_identity("machine", "sid"))
        self.assertEqual(row["original"], text.encode())
        self.assertEqual(json.loads(row["request"])["session_refine_version"], str(SESSION_REFINE_VERSION))

    def test_failed_documents_are_reported_and_retryable(self):
        job = self.upload().json()["accepted"][0]
        self.ext.store.update(job["job_id"], status="failed", error="RuntimeError")
        failed = self.upload(text=None).json()["failed"]
        self.assertEqual([item["job_id"] for item in failed], [job["job_id"]])
        retried = self.client.post(self.url + "/jobs/" + job["job_id"] + "/retry", headers=self.headers)
        self.assertEqual(retried.json()["status"], "pending")
        self.assertEqual(self.client.post(self.url + "/jobs/" + job["job_id"] + "/retry",
                                          headers=self.headers).status_code, 409)

    def test_degraded_session_is_visible_and_retryable_with_safe_preview(self):
        job = self.upload("user: token=abcdefghijk\n\nassistant: hello").json()["accepted"][0]
        self.ext.store.update(job["job_id"], status="degraded", error="SessionRefineError")
        failed = self.upload(text=None).json()["failed"]
        self.assertEqual(failed[0]["status"], "degraded")
        preview = self.client.get(self.url + "/jobs/" + job["job_id"] + "?preview=true",
                                  headers=self.headers).json()
        self.assertNotIn("abcdefghijk", preview["original_text"])
        response = self.client.post(self.url + "/jobs/" + job["job_id"] + "/retry", headers=self.headers)
        self.assertEqual(response.json()["status"], "pending")

    def test_rejects_missing_identity_and_unsupported_files(self):
        self.assertEqual(self.upload(manifest={"session_id": "sid", "title": "t"}).status_code, 400)
        self.assertEqual(self.upload(files=[("tool.exe", b"MZ")]).status_code, 400)

    def test_cannot_commit_before_preparation(self):
        job = self.upload().json()["accepted"][0]
        response = self.client.post(self.url + "/jobs/" + job["job_id"] + "/commit", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")

    def test_archive_uses_persistent_server_job_and_deduplicates(self):
        payload = {"source_id": "machine", "batch_id": "batch", "sources": [{
            "id": "source", "filename": "source.html", "data": base64.b64encode(b"<h1>Title</h1><p>Body.</p>").decode()}]}
        first = self.client.post(self.url + "/archives", headers=self.headers, json=payload)
        again = self.client.post(self.url + "/archives", headers=self.headers, json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["job_id"], again.json()["job_id"])
        self.assertEqual(first.json()["status"], "pending")


class ArchiveModel:
    model = "fixture"

    def __init__(self, check):
        self.check, self.calls = check, 0

    def complete(self, prompt, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return json.dumps({"title": "History", "claims": [{"text": "Migration remains pending.", "sources": ["S1"]}]})
        return json.dumps(self.check)


class ArchiveTest(unittest.TestCase):
    def test_accepts_only_a_complete_json_fence_not_arbitrary_surrounding_text(self):
        evidence = [{"id": "S1", "text": "Migration remains pending. " * 20}]
        model = ArchiveModel({"safe": True, "missing": [], "unsupported": [], "scope_issues": []})
        complete = model.complete
        model.complete = lambda *args, **kwargs: "```json\n" + complete(*args, **kwargs) + "\n```"
        body, _ = refine_archive(evidence, model)
        self.assertIn("[S1]", body)
        with self.assertRaises(ValueError):
            model_object('Explanation first\n{"safe":true}')

    def test_requires_explicit_independent_verification(self):
        evidence = [{"id": "S1", "text": "Migration remains pending. " * 20}]
        model = ArchiveModel({"safe": True, "missing": [], "unsupported": [], "scope_issues": []})
        body, info = refine_archive(evidence, model)
        self.assertIn("[S1]", body)
        self.assertEqual(info["refine_status"], "llm_verified")
        self.assertEqual(model.calls, 2)
        for check in ({"safe": True}, {"safe": False, "missing": [], "unsupported": ["invented"], "scope_issues": []}):
            with self.assertRaises(RuntimeError):
                refine_archive(evidence, ArchiveModel(check))


class AdapterTest(unittest.TestCase):
    def test_session_item_is_a_replace_without_private_fields(self):
        job = {"job_id": "jid", "document_id": "doc", "filename": "session.txt", "original": b"x",
               "refined_text": "user: hi", "refine_info": "{}",
               "request": json.dumps({"_schema": "public", "_api_key_id": "k", "job_kind": "session",
                                      "source_agent": "codex", "legacy_document_id": "old"})}
        item = HindsightAdapter.item(job)
        self.assertEqual(item["update_mode"], "replace")
        self.assertEqual(item["content"], "user: hi")
        self.assertFalse(any(key.startswith("_") for key in item["metadata"]))
        self.assertNotIn("legacy_document_id", item["metadata"])


if __name__ == "__main__":
    unittest.main()
