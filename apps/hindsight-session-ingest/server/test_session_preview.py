"""The offline report checks key points independently from numeric anchor coverage."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from preview_sessions import coverage, evaluate, session_path


class PreviewTest(unittest.TestCase):
    def test_key_points_report_source_support_separately(self):
        rubric = [{"id": "tests", "description": "Preserve reported regression result",
                   "patterns": ["79", "passed"]}]
        result = evaluate(rubric, "Assistant reports 79 tests passed.", "Tests were run.")
        self.assertTrue(result[0]["source_supported"])
        self.assertFalse(result[0]["note_present"])
        result = evaluate(rubric, "No test result recorded.", "79 tests passed.")
        self.assertFalse(result[0]["source_supported"])
        self.assertTrue(result[0]["note_present"])

    def test_anchor_coverage_lists_misses_instead_of_hiding_them(self):
        result = coverage(["79", "/output/report.md"], "Assistant reports 79 tests.")
        self.assertEqual(result["found"], 1)
        self.assertEqual(result["missing"], ["/output/report.md"])

    def test_overview_check_cannot_pass_due_to_an_old_detailed_section(self):
        rubric = [{"id": "current", "description": "Latest state", "scope": "overview",
                   "patterns": ["preserve prior note"]}]
        result = evaluate(rubric, "preserve prior note",
                          "Old detail: preserve prior note\n\n## 主线与当前状态\n\nNo current status.")
        self.assertTrue(result[0]["source_supported"])
        self.assertFalse(result[0]["note_present"])

    def test_explicit_obsolete_policy_can_fail_an_otherwise_matching_note(self):
        rubric = [{"id": "policy", "description": "No obsolete fallback", "patterns": ["prior note"],
                   "forbidden_patterns": ["publish raw fallback"]}]
        result = evaluate(rubric, "prior note", "Keep prior note but publish raw fallback.")
        self.assertFalse(result[0]["note_present"])

    def test_untrusted_session_id_cannot_escape_preview_root(self):
        root = Path("/output")
        self.assertEqual(session_path(root, "session-one"), root / "session-one")
        self.assertEqual(session_path(root, "../../private").parent, root)
        self.assertEqual(session_path(root, "/etc").parent, root)


if __name__ == "__main__":
    unittest.main()
