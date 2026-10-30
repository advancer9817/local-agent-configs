"""Light session editing keeps complete context instead of an evidence-only checklist."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from artifact_refine import condense_session, SESSION_SYSTEM, unsupported_literals


class Model:
    model = "fixture"

    def __init__(self, response):
        self.response, self.prompts = response, []

    def complete(self, prompt, **kwargs):
        self.prompts.append((prompt, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


SOURCE = ("user: Add analysis using page filters; keep existing interfaces.\n\n"
          "assistant: Fetch data in the workflow, calculate in code, then write the report.\n\n"
          "user: Also support questions.\n\n"
          "assistant: Report generation and questions use separate routes. "
          "79 tests passed, code limit is 30000 characters. Import and live verification remain pending.\n\n"
          "assistant: Download /output/workflow.zip and preview http://localhost:8091/report.html.\n\n"
          "user: Improve readability without changing the business rules.")
NOTE = ("# Workflow\n\nUser requires analysis and questions without changing interfaces or business rules.\n\n"
        "Fetch in the workflow, calculate in code; separate reports and questions.\n\n"
        "Assistant reports 79 tests passed; 30000 character limit. Import and live verification pending.\n\n"
        "/output/workflow.zip\nhttp://localhost:8091/report.html")


class SessionRefineTest(unittest.TestCase):
    def test_one_call_sees_the_entire_session_and_keeps_reported_results(self):
        model = Model(NOTE)
        result, info = condense_session(SOURCE, model, "Workflow")
        self.assertEqual(result, NOTE)
        self.assertEqual(len(model.prompts), 1)
        self.assertIn(SOURCE, model.prompts[0][0])
        self.assertEqual(model.prompts[0][1]["system"], SESSION_SYSTEM)
        self.assertNotIn("json_output", model.prompts[0][1])
        self.assertEqual(info["refine_status"], "llm_session")
        self.assertIn("Assistant reports 79 tests", result)
        self.assertIn("verification pending", result)

    def test_edit_primitive_never_truncates_its_supplied_source(self):
        source = SOURCE * 400
        model = Model(NOTE)
        result, _ = condense_session(source, model)
        self.assertEqual(len(model.prompts), 1)
        self.assertIn(source, model.prompts[0][0])
        self.assertEqual(result, NOTE)

    def test_failures_cannot_be_published_as_raw_text(self):
        for response in ("", "long" * len(SOURCE), RuntimeError("private provider detail"),
                         "# Report\nAssistant reports 999 tests passed.",
                         "# Report\nUse /different/path/file.zip"):
            with self.subTest(response_type=type(response).__name__):
                with self.assertRaises(RuntimeError) as error:
                    condense_session(SOURCE, Model(response))
                self.assertNotIn("private", str(error.exception))

    def test_missing_model_blocks_publication(self):
        with self.assertRaises(RuntimeError):
            condense_session(SOURCE, None)

    def test_section_numbers_are_not_treated_as_new_decimal_facts(self):
        result, info = condense_session(SOURCE, Model("## 6.2 Verification\n\nLive verification pending."))
        self.assertEqual(result, "## Verification\n\nLive verification pending.")
        self.assertEqual(info["refine_status"], "llm_session")

    def test_one_literal_correction_is_allowed_but_never_unbounded_retries(self):
        class Correcting(Model):
            def complete(self, prompt, **kwargs):
                self.prompts.append((prompt, kwargs))
                return "# Workflow\n\nAssistant reports 999 tests." if len(self.prompts) == 1 else NOTE
        model = Correcting(None)
        result, info = condense_session(SOURCE, model)
        self.assertEqual(result, NOTE)
        self.assertEqual(len(model.prompts), 2)
        self.assertIn("999", model.prompts[1][0])
        self.assertTrue(info["refine_corrected"])
        broken = Model("# Workflow\n\nAssistant reports 999 tests.")
        with self.assertRaises(RuntimeError):
            condense_session(SOURCE, broken)
        self.assertEqual(len(broken.prompts), 2)

    def test_converted_path_is_restored_only_when_the_source_contains_the_same_file(self):
        source = SOURCE + "\nassistant: Download /mnt/c/Users/test/output/workflow.zip."
        note = "# Workflow\n\nDownload C:\\Users\\test\\output\\workflow.zip"
        result, info = condense_session(source, Model(note))
        self.assertIn("/mnt/c/Users/test/output/workflow.zip", result)
        self.assertNotIn("C:\\", result)
        self.assertEqual(info["refine_status"], "llm_session")
        with self.assertRaises(RuntimeError):
            condense_session(source, Model(note.replace("workflow.zip", "invented.zip")))

    def test_fences_are_removed_and_credentials_cannot_enter_the_note(self):
        result, info = condense_session(SOURCE, Model("```markdown\n" + NOTE + "\n```"))
        self.assertEqual(result, NOTE)
        self.assertEqual(info["refine_status"], "llm_session")
        with self.assertRaises(RuntimeError):
            condense_session(SOURCE, Model("password=abcdefghijklmnop"))

    def test_empty_source_never_calls_the_model(self):
        model = Model(NOTE)
        self.assertEqual(condense_session("", model)[0], "")
        self.assertEqual(model.prompts, [])

    def test_explicit_cli_host_port_pair_is_not_a_fabricated_endpoint(self):
        source = "Run worker --http-host 127.0.0.1 --http-port 18889."
        self.assertEqual(unsupported_literals("127.0.0.1:18889", source, allow_cli_endpoints=True), [])
        self.assertEqual(unsupported_literals("127.0.0.1:18889", source), ["127.0.0.1:18889"])
        self.assertEqual(unsupported_literals("127.0.0.1:18890", source, allow_cli_endpoints=True),
                         ["127.0.0.1:18890"])


if __name__ == "__main__":
    unittest.main()
