import importlib.util
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import session_documents as documents


def hook_module():
    spec = importlib.util.spec_from_file_location("boundary_hook", Path(__file__).with_name("hindsight-hook.py"))
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return hook


class BoundaryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = self.root / "state" / "session.json"
        self.hook = hook_module()

    def tearDown(self):
        self.tmp.cleanup()

    def turn(self, text, payload=None, result=None, error=None):
        payload = dict({"source_id": "machine", "cwd": str(self.root), "session_title": "测试会话"}, **(payload or {}))
        with patch.object(self.hook, "post_session", side_effect=error,
                          return_value=result or {"accepted": [], "failed": []}) as post, \
                patch.object(self.hook, "failure") as failure:
            self.hook.retain(payload, "codex", text, "sid", self.state)
        return post, failure

    def test_redaction_removes_private_keys_and_all_known_key_prefixes(self):
        text = "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----\ngsk_abcdefghijklmnopqrstuv"
        redacted = documents.redact(text)
        self.assertNotIn("private-material", redacted)
        self.assertNotIn("gsk_", redacted)

    def test_every_turn_sends_the_complete_session_once(self):
        first = "user: first\n\nassistant: answer"
        post, _ = self.turn(first)
        manifest, text, artifacts = post.call_args.args
        self.assertEqual(text, first)
        self.assertEqual(manifest["title"], "测试会话")
        self.assertNotIn("legacy_document_id", manifest)
        post, _ = self.turn(first)
        post.assert_not_called()
        longer = first + "\n\nuser: next\n\nassistant: more"
        post, _ = self.turn(longer)
        self.assertEqual(post.call_args.args[1], longer)

    def test_raw_transcript_keeps_user_requests_and_all_assistant_messages(self):
        path = self.root / "transcript.jsonl"
        messages = [
            {"role": "user", "content": [{"type": "input_text", "text": "Build the workflow."}]},
            {"role": "assistant", "phase": "commentary",
             "content": [{"type": "output_text", "text": "Checking the implementation."}]},
            {"role": "assistant", "phase": "final_answer",
             "content": [{"type": "output_text", "text": "Delivered. Platform verification is pending."}]},
        ]
        path.write_text("\n".join(json.dumps({"payload": dict(type="message", **message)})
                                  for message in messages))
        text = self.hook.transcript({"transcript_path": str(path)})
        self.assertEqual(text, "user: Build the workflow.\n\n"
                              "assistant: Checking the implementation.\n\n"
                              "assistant: Delivered. Platform verification is pending.")
        post, _ = self.turn(text)
        self.assertEqual(post.call_args.args[1], text)

    def test_failed_upload_records_nothing_so_next_turn_retries(self):
        post, failure = self.turn("user: hi\n\nassistant: hello", error=OSError("offline"))
        failure.assert_called_once()
        self.assertNotIn("sent", documents.load_state(self.state))
        post, _ = self.turn("user: hi\n\nassistant: hello")
        post.assert_called_once()

    def test_legacy_session_keeps_title_document(self):
        documents.save_state(self.state, {"original_title": "旧标题", "schema_version": 5})
        post, _ = self.turn("user: hi\n\nassistant: hello")
        self.assertEqual(post.call_args.args[0]["legacy_document_id"], "旧标题")
        self.assertEqual(documents.load_state(self.state)["schema_version"], 5)

    def test_artifacts_are_raw_bytes_and_only_changed_ones_are_sent(self):
        page = self.root / "page.html"
        page.write_text("<h1>Title</h1><p>Useful body.</p>")
        payload = {"artifacts": [str(page)]}
        with patch.object(documents, "document_text", create=True, side_effect=AssertionError("local parser")):
            post, _ = self.turn("user: make a page\n\nassistant: done", payload)
        manifest, _, artifacts = post.call_args.args
        self.assertEqual(artifacts[0]["data"], page.read_bytes())
        self.assertEqual(manifest["artifacts"][0]["source_path"], str(page.resolve()))
        post, _ = self.turn("user: make a page\n\nassistant: done\n\nuser: ok\n\nassistant: ok", payload)
        self.assertEqual(post.call_args.args[2], [])
        page.write_text("<h1>Title</h1><p>Changed body.</p>")
        post, _ = self.turn("user: make a page\n\nassistant: done\n\nuser: ok\n\nassistant: ok", payload)
        self.assertIsNone(post.call_args.args[1])
        self.assertEqual(len(post.call_args.args[2]), 1)

    def test_credentials_block_the_artifact_but_not_the_session(self):
        secret = self.root / "notes.md"
        secret.write_text('api_key = "abcdefghijklmnop"')
        with patch.dict(os.environ, {"HINDSIGHT_UPLOAD_CREDENTIAL_CHECK": "1"}):
            post, _ = self.turn("user: x\n\nassistant: y", {"artifacts": [str(secret)]})
        self.assertEqual(post.call_args.args[2], [])
        self.assertEqual(post.call_args.args[1], "user: x\n\nassistant: y")

    def test_disabled_credential_detection_sends_original_artifact(self):
        page = self.root / "diagram.html"
        data = b'<script>var token = document.createElementNS(namespace, "svg");</script><h1>Diagram</h1>'
        page.write_bytes(data)
        with patch.dict(os.environ, {"HINDSIGHT_UPLOAD_CREDENTIAL_CHECK": "0"}):
            post, _ = self.turn("user: draw\n\nassistant: done", {"artifacts": [str(page)]})
        self.assertEqual(post.call_args.args[2][0]["data"], data)

    def test_multipart_body_contains_manifest_session_and_files(self):
        body, content_type = self.hook.multipart([("manifest", '{"a": 1}')], [("file0", "a.md", b"# A")])
        boundary = content_type.split("boundary=")[1]
        self.assertTrue(body.endswith(("--" + boundary + "--\r\n").encode()))
        self.assertIn(b'name="file0"; filename="a.md"', body)
        self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(bytes(body)).hexdigest())


if __name__ == "__main__":
    unittest.main()
