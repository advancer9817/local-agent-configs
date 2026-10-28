"""Run with the Hindsight venv: PYTHONPATH=..:. python -m unittest test_artifact_refine."""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import artifact_refine  # noqa: E402
from artifact_refine import condense, refine_artifact, split_parts, unsupported_literals  # noqa: E402

LONG = "# 部署记录\n\n" + "\n".join(
    f"- 第 {i} 步：在 /opt/app/v2 执行 deploy.sh，端口 18888，版本 1.1.0，耗时 {i * 7} 秒" for i in range(1, 40))


class FakeModel:
    model = "fake"

    def __init__(self, reply):
        self.reply, self.calls = reply, 0

    def complete(self, prompt):
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class RefineTest(unittest.TestCase):
    def test_accepts_grounded_shorter_output(self):
        text, info = condense(LONG, FakeModel("```markdown\n# 部署记录\n- 在 /opt/app/v2 执行 deploy.sh（1.1.0，端口 18888），共 39 步\n```"))
        self.assertEqual(info["refine_status"], "llm")
        self.assertTrue(text.startswith("# 部署记录"))

    def test_rejects_fabricated_literals(self):
        with self.assertRaises(RuntimeError):
            condense(LONG, FakeModel("# 部署记录\n- 在 /opt/app/v3 执行，总耗时 5460 秒"))

    def test_model_errors_fail_and_short_inputs_still_use_llm(self):
        with self.assertRaises(RuntimeError):
            condense(LONG, FakeModel(TimeoutError()))
        self.assertEqual(condense("# 短\n- 内容", FakeModel("# 短\n- 内容"))[1]["refine_status"], "llm")
        with self.assertRaises(RuntimeError):
            condense(LONG, None)

    def test_unsafe_part_rejects_the_entire_document(self):
        replies = iter(["# 部署记录\n- 在 /opt/app/v2 执行 deploy.sh，端口 18888，共 39 步",
                        "- 在 /opt/app/v9 执行 deploy.sh，端口 18888"])
        model = FakeModel("")
        model.complete = lambda prompt: next(replies)
        second = LONG.replace("# 部署记录", "## 回滚")
        with unittest.mock.patch.object(artifact_refine, "PART_CHARS", len(LONG) + 10):
            with self.assertRaises(RuntimeError):
                condense(LONG + "\n" + second, model)

    def test_literal_check_ignores_formatting(self):
        self.assertEqual(unsupported_literals("合计 1,485，见第 3 页", "合计 1485 第 3 页"), [])
        self.assertEqual(unsupported_literals("IP 10.0.0.2", "IP 10.0.0.1"), ["10.0.0.2"])
        source = "地址 http://35.236.134.50:18888/mcp/bank/（经隧道）。"
        self.assertEqual(unsupported_literals("入口 http://35.236.134.50:18888/mcp/bank/。", source), [])
        self.assertEqual(unsupported_literals("状态 /thinking/finished", "`thinking` / `finished`"), ["/thinking/finished"])
        self.assertEqual(unsupported_literals("见 /hooks/deploy.sh", "hooks 目录与 run.sh"), ["/hooks/deploy.sh"])

    def test_split_parts_respects_limit(self):
        parts = split_parts("\n".join(f"## 节 {i}\n" + "字" * 900 for i in range(10)), limit=2000)
        self.assertTrue(all(len(p) <= 2000 for p in parts))
        self.assertEqual("".join(parts).count("## 节"), 10)

    def test_split_preserves_order_before_oversized_paragraph(self):
        text = "# First\nstart\n## Second\n" + "x" * 90
        parts = split_parts(text, limit=30)
        self.assertTrue(parts[0].startswith("# First"))
        self.assertLess("".join(parts).index("start"), "".join(parts).index("Second"))

    def test_parses_original_redacts_and_caches(self):
        html = ("<html><head><title>说明</title></head><body><nav>菜单</nav><h1>说明</h1>"
                + "".join(f"<p>步骤 {i}：token=abcdef{i} 运行 /usr/bin/tool{i}</p>" for i in range(30))
                + "</body></html>").encode()
        model = FakeModel("# 说明\n- 依次运行 /usr/bin/tool1 与 /usr/bin/tool2 等工具")
        with tempfile.TemporaryDirectory() as cache:
            text, info = refine_artifact("page.html", html, "", model, "说明", cache)
            again, _ = refine_artifact("page.html", html, "", model, "说明", cache)
        self.assertEqual(info["artifact_parser"], "artifact_digest")
        self.assertEqual(info["refine_status"], "llm")
        self.assertEqual(text, again)
        self.assertEqual(model.calls, 1)

    def test_redacted_markdown_upload_is_used_as_text(self):
        text, info = refine_artifact("x.redacted.md", LONG.encode(), "", FakeModel(LONG))
        self.assertEqual((text, info["artifact_parser"]), (LONG, "source-text"))


try:
    import hindsight_session_metadata as extension
except ImportError:
    extension = None


@unittest.skipIf(extension is None, "requires the Hindsight venv")
class ExtensionTest(unittest.TestCase):
    def test_validator_only_checks_identity_and_never_refines(self):
        from ingest_safety import artifact_identity
        ext = extension.SessionDocumentMetadata({})
        self.assertFalse(hasattr(ext, "_refine"))
        item = {"document_id": artifact_identity("machine", "/report.html"), "content": "approved text",
                "metadata": {"document_kind": "session-artifact", "ingest_version": "6",
                             "source_id": "machine", "source_path": "/report.html", "title": "Repeated Title"}}
        ctx = SimpleNamespace(contents=[item], document_id=None)
        result = asyncio.run(ext.validate_retain(ctx))
        self.assertEqual(result.contents[0], item)

    def test_same_display_title_does_not_collide_across_sources(self):
        from ingest_safety import artifact_identity
        ext = extension.SessionDocumentMetadata({})
        items = [{"document_id": artifact_identity("machine", path), "content": "approved text",
                  "metadata": {"document_kind": "session-artifact", "ingest_version": "6",
                               "source_id": "machine", "source_path": path, "title": "Same Title"}}
                 for path in ("/a/report.html", "/b/report.html")]
        result = asyncio.run(ext.validate_retain(SimpleNamespace(contents=items, document_id=None)))
        self.assertNotEqual(result.contents[0]["document_id"], result.contents[1]["document_id"])

    def test_legacy_session_survives_second_validation_in_worker(self):
        from unittest.mock import AsyncMock
        ext = extension.SessionDocumentMetadata({})
        ext._matching_document = AsyncMock(return_value=None)
        ext._check_collision = AsyncMock(return_value=None)
        item = {"document_id": "旧标题", "content": "user: hi",
                "metadata": {"document_kind": "agent-session", "ingest_version": "5", "source_id": "machine",
                             "session_id": "s1", "original_title": "旧标题", "legacy_document_id": "旧标题"}}
        first = asyncio.run(ext.validate_retain(SimpleNamespace(contents=[item], document_id=None))).contents
        # The API validates on submit; the worker validates the enriched payload again.
        second = asyncio.run(ext.validate_retain(SimpleNamespace(contents=first, document_id=None))).contents
        self.assertEqual(second[0]["document_id"], "旧标题")
        self.assertEqual(second[0]["metadata"]["ingest_version"], "5")


if __name__ == "__main__":
    unittest.main()
