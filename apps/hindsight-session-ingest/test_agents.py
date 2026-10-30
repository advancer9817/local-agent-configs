"""Claude Code and Hermes clients: transcripts, titles, Hermes plugin and installer."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import session_documents as documents

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hermes_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, title TEXT, cwd TEXT, git_repo_root TEXT,
                               started_at REAL NOT NULL);
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT,
                               timestamp REAL, active INTEGER NOT NULL DEFAULT 1, compacted INTEGER NOT NULL DEFAULT 0,
                               _compressed_summary INTEGER NOT NULL DEFAULT 0, display_kind TEXT);
    """)
    db.execute("INSERT INTO sessions VALUES ('s1','desktop','部署/验证 Hermes','/work','/work',1767225600)")
    rows = [
        ("user", "first request", 1, 0, 1, 0, None),
        ("assistant", "first answer", 2, 0, 1, 0, None),
        ("user", "[CONTEXT COMPACTION] summary", 3, 1, 0, 1, None),
        ("user", "rewound request", 4, 0, 0, 0, None),
        ("user", "[System: model changed]", 5, 1, 0, 0, "model_switch"),
        ("assistant", "", 6, 1, 0, 0, None),
        ("tool", "tool output", 7, 1, 0, 0, None),
        ("assistant", json.dumps([{"type": "text", "text": "block answer"}]), 8, 1, 0, 0, None),
        ("user", "steer note", 9, 1, 0, 0, "steer"),
        ("assistant", "token: abcdefghijklmnop", 10, 1, 0, 0, None),
    ]
    db.executemany("INSERT INTO messages (session_id,role,content,timestamp,active,compacted,_compressed_summary,"
                   "display_kind) VALUES ('s1',?,?,?,?,?,?,?)", rows)
    db.commit()
    db.close()


class AgentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.hook = load("agents_hook", HERE / "hindsight-hook.py")

    def tearDown(self):
        self.tmp.cleanup()

    def test_hermes_session_keeps_compacted_originals_and_drops_system_rows(self):
        db = self.root / "state.db"
        hermes_db(db)
        payload, text = self.hook.hermes_payload({"session_id": "s1", "hermes_state_db": str(db)})
        self.assertEqual(text, "user: first request\n\nassistant: first answer\n\nassistant: block answer\n\n"
                               "user: steer note\n\nassistant: token: [REDACTED]")
        self.assertEqual(payload["cwd"], "/work")
        self.assertEqual(payload["session_title"], "部署/验证 Hermes")
        self.assertTrue(payload["session_started_at"].startswith("2026-01-01T00:00:00"))

    def test_hermes_upload_uses_session_title_and_follows_renames(self):
        db = self.root / "state.db"
        hermes_db(db)
        state = self.root / "state" / "s.json"
        payload, text = self.hook.hermes_payload({"session_id": "s1", "hermes_state_db": str(db),
                                                  "source_id": "machine"})
        with patch.object(self.hook, "post_session", return_value={}) as post:
            self.hook.upload_turn(payload, "hermes", text, "s1", state)
            self.assertEqual(post.call_args.args[0]["title"], "部署／验证 Hermes")
            self.assertEqual(post.call_args.args[0]["agent"], "hermes")
            payload["session_title"] = "Renamed session"
            self.hook.upload_turn(payload, "hermes", text + "\n\nuser: more", "s1", state)
            self.assertEqual(post.call_args.args[0]["title"], "Renamed session")

    def test_untitled_non_codex_sessions_fall_back_to_the_first_request(self):
        title = documents.local_title("sid", "user: 帮我排查 Claude 钩子没有上传\n\nassistant: ok", {}, "claude")
        self.assertEqual(title, "排查 Claude 钩子没有上传")
        self.assertEqual(documents.local_title("sid", "user: hi\n\nassistant: ok", {}, "hermes"), "会话记录与处理结论")
        with self.assertRaises(ValueError):
            documents.local_title("missing-codex-thread", "user: hi", {}, "codex")

    def test_claude_transcript_title_and_meta_rows(self):
        path = self.root / "claude.jsonl"
        rows = [
            {"type": "user", "isMeta": True, "message": {"role": "user", "content": "Caveat: local command"}},
            {"type": "user", "message": {"role": "user", "content": "Fix the hook"}},
            {"type": "user", "message": {"role": "user", "content": "<command-name>/theme</command-name>"}},
            {"type": "user", "message": {"role": "user", "content": "<local-command-stdout>ok</local-command-stdout>"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "hidden"}, {"type": "tool_use", "name": "Bash"}]}},
            {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "out"}]}},
            {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Fixed."}]}},
            {"type": "ai-title", "aiTitle": "Hook fix", "sessionId": "c1"},
            {"type": "custom-title", "customTitle": "修复 Claude 钩子", "sessionId": "c1"},
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows))
        self.assertEqual(self.hook.transcript({"transcript_path": str(path)}), "user: Fix the hook\n\nassistant: Fixed.")
        self.assertEqual(documents.claude_title(str(path)), "修复 Claude 钩子")

    def test_hermes_recall_context_fits_the_plugin_limit(self):
        result = {"results": [{"text": "x" * 20000}]}
        out = []
        with patch.object(self.hook, "mcp_call", return_value=result), \
                patch.object(sys, "argv", ["hook", "recall", "--agent", "hermes"]), \
                patch.object(sys, "stdin", __import__("io").StringIO(json.dumps({"prompt": "what changed"}))), \
                patch("builtins.print", side_effect=lambda value, **kw: out.append(value)):
            self.hook.main()
        self.assertEqual(len(out[0]), 9000)


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.plugin = load("hindsight_memory", HERE / "hermes-plugin/hindsight-memory/__init__.py")

    def test_config_snapshot_carries_the_same_plugin(self):
        snapshot = HERE.parents[1] / "hermes/plugins/hindsight-memory"
        if not snapshot.is_dir():
            self.skipTest("config snapshot not present")
        for name in ("__init__.py", "plugin.yaml"):
            self.assertEqual((snapshot / name).read_bytes(),
                             (HERE / "hermes-plugin/hindsight-memory" / name).read_bytes(), name)

    def test_recall_returns_context_and_retain_runs_once_per_session(self):
        calls = []

        def run(action, payload, timeout):
            calls.append((action, payload))
            return "context" if action == "recall" else ""
        with patch.object(self.plugin, "_run", side_effect=run), \
                patch.object(self.plugin.HOOK.__class__, "exists", return_value=True):
            self.assertEqual(self.plugin._on_pre_llm_call(user_message="what changed?", session_id="s1"),
                             {"context": "context"})
            self.assertIsNone(self.plugin._on_pre_llm_call(user_message="hi"))
            self.plugin._schedule("s1")
            for thread in list(__import__("threading").enumerate()):
                if thread.name == "hindsight-retain":
                    thread.join(5)
            self.plugin._on_session_end(session_id="s1", completed=True, interrupted=False, failed=False)
        self.assertEqual([c[0] for c in calls], ["recall", "retain"])
        self.assertEqual(calls[1][1]["session_id"], "s1")


class InstallerTest(unittest.TestCase):
    def test_hooks_replace_only_hindsight_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            installer = load("installer", HERE / "install.py")
            path = Path(tmp) / "settings.json"
            other = {"type": "command", "command": "bash other.sh"}
            path.write_text(json.dumps({"model": "x", "hooks": {"Stop": [
                {"hooks": [other]}, {"hooks": [{"type": "command", "command": "python old/hindsight-hook.py retain"}]}]}}))
            self.assertEqual(installer.upsert_hooks(path, "claude"), "updated")
            config = json.loads(path.read_text())
            self.assertEqual(config["model"], "x")
            self.assertEqual(config["hooks"]["Stop"][0]["hooks"], [other])
            self.assertIn("retain --agent claude", config["hooks"]["Stop"][1]["hooks"][0]["command"])
            self.assertIn("recall --agent claude", config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"])
            self.assertEqual(installer.upsert_hooks(path, "claude"), "unchanged")
            self.assertEqual(len(list(Path(tmp).glob("settings.json.bak-*"))), 1)

    def test_connection_is_created_privately_from_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            installer = load("installer2", HERE / "install.py")
            installer.CONNECTION = Path(tmp) / "connection.json"
            token = Path(tmp) / "token"
            token.write_text("hs_test\n")
            opts = type("Opts", (), {"api_url": "http://127.0.0.1:18888/", "bank": "bank",
                                     "token_file": str(token)})()
            installer.ensure_connection(opts)
            value = json.loads(installer.CONNECTION.read_text())
            self.assertEqual(value["mcp_url"], "http://127.0.0.1:18888/mcp/bank/")
            self.assertEqual(value["mcp_token"], "hs_test")
            if os.name != "nt":
                self.assertEqual(installer.CONNECTION.stat().st_mode & 0o777, 0o600)
            opts.api_url = "http://example.com:1"
            with self.assertRaises(SystemExit):
                installer.ensure_connection(opts)


if __name__ == "__main__":
    unittest.main()
