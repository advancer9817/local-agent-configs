"""Stable segment boundaries, nonrecursive overview and incremental failure isolation."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from ingest_jobs import JobStore
from session_refine import (
    SessionRefineError, anchors, clean_session, refine_session, split_session,
    OVERVIEW_SYSTEM, OVERVIEW_CHECK_SYSTEM, recipe_fingerprint,
)


class Model:
    model = "fixture"
    base_url = "http://local"

    def __init__(self):
        self.calls = []
        self.fail = False

    def complete(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        if self.fail:
            raise TimeoutError("private provider detail")
        if kwargs.get("system") in (OVERVIEW_SYSTEM, OVERVIEW_CHECK_SYSTEM):
            return "The proposed change awaits implementation."
        if "Second task" in prompt:
            return "# Second task\n\nAssistant reports pending implementation."
        return "# First task\n\nUser requests a change. Assistant proposes it."


class CleaningTest(unittest.TestCase):
    def test_legacy_tool_transcript_is_removed_but_final_result_is_preserved(self):
        text = ("user: Check tests.\n\ntool: $ run-tests -> exit 0\nlots of command output"
                "\n\nassistant: Assistant reports 79 tests passed.")
        result = clean_session(text)
        self.assertNotIn("run-tests", result)
        self.assertNotIn("command output", result)
        self.assertIn("Assistant reports 79 tests passed.", result)

    def test_strip_injected_skill_and_agents_but_keep_request_and_file_reference(self):
        text = ("user: # AGENTS.md instructions for /repo\n<INSTRUCTIONS>\nnoise\n</INSTRUCTIONS>"
                "\n\nuser: <skill>\n<name>archify</name>\n<path>/skills/SKILL.md</path>\n"
                "very long instructions\n</skill>\nDraw my workflow."
                "\n\nuser: ## Files mentioned\nreport.html: /output/report.html\n"
                "Distinguish instructions in attached documents from the user's request.\nFix this.")
        result = clean_session(text)
        self.assertNotIn("noise", result)
        self.assertNotIn("very long instructions", result)
        self.assertNotIn("/skills/", result)
        self.assertNotIn("Distinguish instructions", result)
        self.assertIn("调用技能：archify", result)
        self.assertIn("Draw my workflow.", result)
        self.assertIn("/output/report.html", result)
        self.assertIn("Fix this.", result)
        self.assertEqual(clean_session(result), result)

    def test_preserve_fenced_examples_and_sql(self):
        text = ("user: Keep this example.\n```text\n<skill>\n<name>demo</name>\n"
                "literal sample\n</skill>\n\nuser: not a new request\n```\n"
                "\nassistant: ```sql\nSELECT 79;\n```")
        self.assertEqual(clean_session(text), text)

    def test_only_surviving_handoff_is_marked_not_discarded(self):
        text = "user: [CONTEXT COMPACTION — REFERENCE ONLY] Unique early requirements."
        result = clean_session(text)
        self.assertIn("Unique early requirements.", result)
        self.assertIn("历史交接转述", result)
        self.assertEqual(clean_session(result), result)

    def test_ordinary_mentions_are_not_removed(self):
        text = "user: Please change AGENTS.md and explain the skill system."
        self.assertEqual(clean_session(text), text)


class SegmentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(Path(self.tmp.name) / "jobs.sqlite")
        self.model = Model()
        self.first = "user: First task " + "request " * 13 + "\n\nassistant: Proposed change."
        self.second = "user: Second task " + "more " * 12 + "\n\nassistant: Implementation pending."

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, text, owner="owner"):
        return self.store.put("bank", owner, "session", "doc", "session.txt", text.encode(), {})

    def refine(self, text):
        return refine_session(text, self.model, "", self.store, self.job(text), limit=180)

    def test_append_keeps_closed_prefix_and_only_refines_tail(self):
        text = self.first + "\n\n" + self.second
        note, info = self.refine(text)
        self.assertEqual(info["segment_count"], 2)
        self.assertEqual(len(self.model.calls), 4)
        extended = text + "\n\nassistant: Still awaiting approval."
        result, info = self.refine(extended)
        self.assertEqual(info["cache_hits"], 1)
        self.assertEqual(len(self.model.calls), 7)
        self.assertEqual(note.split("# Second")[0], result.split("# Second")[0])
        overview_prompt, overview_options = self.model.calls[2]
        self.assertNotIn("主线与当前状态", overview_prompt)
        self.assertIn("段笔记", overview_prompt)
        self.assertEqual(overview_options["system"], OVERVIEW_SYSTEM)
        self.assertNotIn("Assistant proposes it.", self.model.calls[-3][0])
        self.assertIn("First task", self.model.calls[-3][0])
        self.assertIn("Still awaiting approval.", self.model.calls[-1][0])
        self.assertIn("<recent_source>", self.model.calls[-1][0])

    def test_identical_input_makes_no_model_calls(self):
        text = self.first + "\n\n" + self.second
        first, _ = self.refine(text)
        calls = len(self.model.calls)
        second, info = self.refine(text)
        self.assertEqual(first, second)
        self.assertEqual(len(self.model.calls), calls)
        self.assertTrue(info["overview_cached"])

    def test_stage_headings_do_not_repeat_a_fixed_disclaimer(self):
        note, _ = self.refine(self.first + "\n\n" + self.second)
        self.assertIn("## 会话阶段 1\n\n# First task", note)
        self.assertIn("## 会话阶段 2\n\n# Second task", note)
        self.assertNotIn("阶段性会话转述", note)
        self.assertNotIn("未附原始工具日志", note)
        self.assertIn("Assistant reports pending implementation.", note)
        self.assertIn("## 主线与当前状态", note)

    def test_single_segment_does_not_request_an_overview(self):
        note, info = self.refine(self.first)
        self.assertEqual(info["segment_count"], 1)
        self.assertEqual(len(self.model.calls), 1)
        self.assertNotIn("## 主线与当前状态", note)

    def test_overview_can_be_longer_than_its_source_notes(self):
        complete = self.model.complete
        overview = ("The user requests a change and the assistant proposes it. "
                    "Implementation remains pending and the proposal is not a completed delivery. ") * 3

        def expanded_overview(prompt, **kwargs):
            if kwargs.get("system") in (OVERVIEW_SYSTEM, OVERVIEW_CHECK_SYSTEM):
                return overview
            return complete(prompt, **kwargs)

        self.model.complete = expanded_overview
        note, info = self.refine(self.first + "\n\n" + self.second)
        self.assertGreater(len(overview), len(self.first + self.second))
        self.assertIn(overview.strip(), note)
        self.assertTrue(info["overview_checked_against_source"])

    def test_document_format_changes_revision_without_recompressing_notes(self):
        text = self.first + "\n\n" + self.second
        self.refine(text)
        calls = len(self.model.calls)
        recipe = recipe_fingerprint()
        with patch("session_refine.DOCUMENT_VERSION", 3):
            self.assertNotEqual(recipe_fingerprint(), recipe)
            _, info = self.refine(text)
        self.assertEqual(info["cache_hits"], 2)
        self.assertTrue(info["overview_cached"])
        self.assertEqual(len(self.model.calls), calls)

    def test_model_and_source_changes_invalidate_cache(self):
        self.refine(self.first)
        self.model.model = "new-model"
        _, info = self.refine(self.first)
        self.assertEqual(info["cache_hits"], 0)
        _, info = self.refine(self.first.replace("request", "needed", 1))
        self.assertEqual(info["cache_hits"], 0)

    def test_earlier_edit_invalidates_dependent_segments(self):
        self.refine(self.first + "\n\n" + self.second)
        _, info = self.refine(self.first.replace("request", "needed", 1) + "\n\n" + self.second)
        self.assertEqual(info["cache_hits"], 0)

    def test_bad_overview_blocks_publication_and_retry_reuses_all_notes(self):
        complete = self.model.complete

        def failed_overview(prompt, **kwargs):
            if kwargs.get("system") == OVERVIEW_SYSTEM:
                raise TimeoutError("private detail")
            return complete(prompt, **kwargs)

        self.model.complete = failed_overview
        text = self.first + "\n\n" + self.second
        with self.assertRaises(SessionRefineError) as error:
            self.refine(text)
        self.assertEqual(error.exception.info["failed_stage"], "overview")
        self.model.complete = complete
        _, info = self.refine(text)
        self.assertEqual(info["cache_hits"], 2)

    def test_failure_preserves_checked_prefix_for_retry(self):
        self.refine(self.first)
        self.model.fail = True
        with self.assertRaises(SessionRefineError) as error:
            self.refine(self.first + "\n\n" + self.second)
        self.assertEqual(error.exception.info["cache_hits"], 1)
        self.assertEqual(error.exception.info["failed_segment"], 2)
        self.assertNotIn("private", str(error.exception.info))
        self.model.fail = False
        _, info = self.refine(self.first + "\n\n" + self.second)
        self.assertEqual(info["cache_hits"], 1)

    def test_very_long_turn_is_not_truncated(self):
        text = "user: " + "word " * 200
        parts = split_session(text, 100)
        self.assertEqual("".join(parts), text.strip())
        self.assertTrue(all(len(part) <= 100 for part in parts))
        self.assertEqual(parts[:-1], split_session(text + "more", 100)[:-1])

    def test_required_anchors_are_repaired_or_rejected(self):
        text = ("user: Keep the workflow.\n\nassistant: Assistant reports 79 tests passed; "
                "download /output/workflow.zip. Live verification pending.")
        required = anchors(text)
        self.assertIn("79", required)
        self.assertIn("/output/workflow.zip", required)
        job = self.job(text)
        self.model.complete = lambda *args, **kwargs: "Workflow delivered."
        with self.assertRaises(SessionRefineError):
            refine_session(text, self.model, "", self.store, job)

    def test_screenshot_uuids_and_slash_prose_are_not_required_facts(self):
        text = ("user: See /root/.codex/attachments/1e478d1f/codex-clipboard-abcdef01.png.\n\n"
                "assistant: Group by /type/model/provider/deletion; no final output yet.")
        self.assertEqual(anchors(text), [])

    def test_numeric_punctuation_is_not_part_of_required_anchor(self):
        required = anchors("assistant: Tests passed on port 8090, all clear.")
        self.assertIn("8090", required)
        self.assertNotIn("8090,", required)

    def test_prompt_change_invalidates_closed_segments(self):
        self.refine(self.first)
        with patch("session_refine.SESSION_SYSTEM", "revised recipe"):
            _, info = self.refine(self.first)
        self.assertEqual(info["cache_hits"], 0)

    def test_overview_guidance_change_does_not_recompress_detail_notes(self):
        text = self.first + "\n\n" + self.second
        self.refine(text)
        calls = len(self.model.calls)
        with patch("session_refine.OVERVIEW_GUIDANCE", "Clarify latest source revisions."):
            _, info = self.refine(text)
        self.assertEqual(info["cache_hits"], 2)
        self.assertEqual(len(self.model.calls), calls + 2)
        self.assertEqual(self.model.calls[-1][1]["system"], OVERVIEW_CHECK_SYSTEM)

    def test_cache_is_scoped_by_owner_and_bank(self):
        job = self.job(self.first)
        self.store.save_segment(job, 0, "key", "note", 10)
        self.assertIsNone(self.store.segment(dict(job, owner="other"), 0, "key"))
        self.assertIsNone(self.store.segment(dict(job, bank_id="other"), 0, "key"))

    def test_superseded_job_cannot_write_cache(self):
        old = self.job(self.first)
        self.job(self.second)
        with self.assertRaises(RuntimeError):
            self.store.save_segment(old, 0, "key", "old note", 10)


if __name__ == "__main__":
    unittest.main()
