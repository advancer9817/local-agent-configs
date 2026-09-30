"""Tests for external-agents plugin."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure plugin directory is in sys.path
PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

import __init__ as ext_plugin
import git_tracker
import runner
import schemas


class TestExternalAgentsPlugin(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="agent_test_")
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_schemas_structure(self):
        """Verify schemas adhere to tool specification."""
        for schema in [schemas.CLAUDE_CODE_EXEC, schemas.CODEX_EXEC]:
            self.assertIn("name", schema)
            self.assertIn("description", schema)
            self.assertIn("parameters", schema)
            self.assertEqual(schema["parameters"]["type"], "object")
            self.assertIn("prompt", schema["parameters"]["properties"])
            self.assertIn("prompt", schema["parameters"]["required"])

    def test_redact_secrets(self):
        """Verify secrets and keys are stripped from output."""
        raw = "Error with api key sk-123456789012345678901234567890 and token ghp_abcdefghijklmnopqrstuvwx"
        clean = runner.redact_secrets(raw)
        self.assertNotIn("sk-123456789012345678901234567890", clean)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwx", clean)
        self.assertIn("[REDACTED]", clean)

    def test_find_executable(self):
        """Verify executable resolution detects local claude and codex."""
        claude_path = runner.find_executable("claude")
        codex_path = runner.find_executable("codex")
        self.assertIsNotNone(claude_path)
        self.assertIsNotNone(codex_path)
        self.assertTrue(Path(claude_path).exists())
        self.assertTrue(Path(codex_path).exists())

    def test_git_tracker_non_git_repo(self):
        """Verify git tracker handles non-git directories gracefully."""
        self.assertFalse(git_tracker.is_git_repo(self.temp_path))
        state = git_tracker.get_git_state(self.temp_path)
        self.assertFalse(state["is_git"])
        diff = git_tracker.get_git_diff(self.temp_path, state)
        self.assertFalse(diff["is_git"])
        self.assertFalse(diff["has_changes"])

    def test_git_tracker_with_git_repo(self):
        """Verify git tracker captures status, files changed, and diffs."""
        # Initialize a git repo
        subprocess.run(["git", "init", str(self.temp_path)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.temp_path), "config", "user.name", "TestUser"], check=True)
        subprocess.run(["git", "-C", str(self.temp_path), "config", "user.email", "test@test.com"], check=True)

        # Baseline empty state
        self.assertTrue(git_tracker.is_git_repo(self.temp_path))
        baseline = git_tracker.get_git_state(self.temp_path)
        self.assertTrue(baseline["is_git"])

        # Create initial commit
        test_file = self.temp_path / "hello.py"
        test_file.write_text("print('hello')\n")
        subprocess.run(["git", "-C", str(self.temp_path), "add", "hello.py"], check=True)
        subprocess.run(["git", "-C", str(self.temp_path), "commit", "-m", "init"], check=True)

        # Baseline before modification
        baseline = git_tracker.get_git_state(self.temp_path)

        # Simulate agent edits: modify hello.py and add new_file.txt
        test_file.write_text("print('hello world')\nprint('new line')\n")
        new_file = self.temp_path / "new_file.txt"
        new_file.write_text("test content")

        diff_res = git_tracker.get_git_diff(self.temp_path, baseline)
        self.assertTrue(diff_res["has_changes"])
        self.assertTrue(any("hello.py" in f for f in diff_res["files_changed"]))
        self.assertTrue(any("new_file.txt" in f for f in diff_res["files_changed"]))
        self.assertTrue(len(diff_res["diff_stat"]) > 0)

    def test_codex_rejects_non_git_repo(self):
        """Codex execution must refuse to run if workdir is not a git repo."""
        res = runner.execute_codex(prompt="fix bugs", workdir=str(self.temp_path))
        self.assertFalse(res["success"])
        self.assertIn("not a Git repository", res["error"])

    def test_tool_handlers_validation(self):
        """Tool handlers should validate required prompt parameter."""
        res_claude = json.loads(ext_plugin.handle_claude_code_exec({}))
        self.assertFalse(res_claude["success"])
        self.assertIn("required", res_claude["error"])

        res_codex = json.loads(ext_plugin.handle_codex_exec({}))
        self.assertFalse(res_codex["success"])
        self.assertIn("required", res_codex["error"])

    def test_slash_command_empty_prompt(self):
        """Slash command should return usage help if prompt is empty."""
        msg_claude = ext_plugin.handle_claude_slash("")
        self.assertIn("用法: /claude", msg_claude)

        msg_codex = ext_plugin.handle_codex_slash("   ")
        self.assertIn("用法: /codex", msg_codex)

    def test_plugin_register_ctx(self):
        """Verify register(ctx) registers tools and commands properly."""
        mock_ctx = MagicMock()
        ext_plugin.register(mock_ctx)

        # Should register 2 tools
        self.assertEqual(mock_ctx.register_tool.call_count, 2)
        tool_names = [call.kwargs.get("name") for call in mock_ctx.register_tool.call_args_list]
        self.assertIn("claude_code_exec", tool_names)
        self.assertIn("codex_exec", tool_names)

        # Should register 2 slash commands
        self.assertEqual(mock_ctx.register_command.call_count, 2)
        cmd_names = [call.kwargs.get("name") for call in mock_ctx.register_command.call_args_list]
        self.assertIn("claude", cmd_names)
        self.assertIn("codex", cmd_names)


if __name__ == "__main__":
    unittest.main()
