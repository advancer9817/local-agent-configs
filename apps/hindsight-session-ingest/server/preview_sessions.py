"""Read-only production snapshots -> isolated previews; never calls retain or writes source DB."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from artifact_refine import ChatModel
from ingest_jobs import JobStore
from session_documents import redact
from session_refine import SessionRefineError, anchors, clean_session, refine_session, split_session


class MeteredModel:
    def __init__(self, client, directory):
        self.client = client
        self.directory = directory
        self.model, self.base_url = client.model, client.base_url
        self.calls = []

    def complete(self, prompt, **kwargs):
        start = time.monotonic()
        result = self.client.complete(prompt, **kwargs)
        self.calls.append(dict(input_chars=len(prompt) + len(kwargs.get("system", "")),
                               output_chars=len(result), seconds=round(time.monotonic() - start, 2)))
        (self.directory / f"model-response-{len(self.calls)}.md").write_text(redact(result))
        print(json.dumps(dict(model_call=len(self.calls), **self.calls[-1])), flush=True)
        return result


def coverage(required, text):
    found = [value for value in required if value in text]
    return dict(required=len(required), found=len(found),
                missing=[value for value in required if value not in text])


def session_path(root, session_id):
    folder = session_id if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", session_id) else (
        "session-" + hashlib.sha256(session_id.encode()).hexdigest())
    return root / folder


def evaluate(checks, original, note):
    results = []
    for check in checks:
        patterns = check["patterns"]
        subject = note
        if check.get("scope") == "overview":
            subject = note.split("## 主线与当前状态\n\n")[-1]
        results.append(dict(id=check["id"], description=check["description"],
                            source_supported=all(re.search(pattern, original, re.I | re.S) is not None
                                                 for pattern in patterns),
                            note_present=(all(re.search(pattern, subject, re.I | re.S) is not None
                                              for pattern in patterns)
                                          and not any(re.search(pattern, subject, re.I | re.S) is not None
                                                      for pattern in check.get("forbidden_patterns", [])))))
    return results


def compare_page(root, cases):
    sections = []
    for case in cases:
        directory = session_path(root, case["session_id"])
        views = []
        for name, label in (("overview.md", "新稿：主线与当前状态"), ("refined.md", "新稿：全部阶段明细"),
                            ("before.md", "旧整理稿"), ("original.txt", "上传原文（已脱敏）"),
                            ("cleaned.txt", "清洗后原文")):
            path = directory / name
            if path.exists():
                views.append(("<details open>" if name == "overview.md" else "<details>") + "<summary>" + label + "</summary><pre>"
                             + html.escape(path.read_text()) + "</pre></details>")
        refined_chars = case.get("info", {}).get("refined_chars", "未生成")
        summary = (f"原文 {case['original_chars']:,} 字符 · 清洗后 {case['clean_chars']:,}"
                   f" · 旧稿 {case['baseline_chars']:,} · 新稿 {refined_chars}"
                   f" · {case['segment_count']} 段 · {case.get('status', '未运行模型')}")
        metrics = ("<details><summary>评测明细</summary><pre>"
                   + html.escape(json.dumps(case, ensure_ascii=False, indent=2)) + "</pre></details>")
        sections.append("<section><h2>" + html.escape(case["title"]) + "</h2><p>"
                        + html.escape(summary) + "</p>" + "".join(views) + metrics + "</section>")
    page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hindsight 会话提炼对比</title><style>
body{margin:0;color:#202426;background:#f6f7f8;font:15px/1.65 system-ui,sans-serif}
main{max-width:1100px;margin:auto;padding:24px}h1{font-size:25px}h2{font-size:20px}
section{border-top:1px solid #bac4c8;padding:20px 0}summary{cursor:pointer;padding:12px 0;color:#117764}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace,monospace}
details{border-bottom:1px solid #d8dfe1}details[open] pre{padding:16px;background:white}
</style><main><h1>Hindsight 会话提炼对比</h1>""" + "".join(sections) + "</main></html>"
    (root / "index.html").write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session", action="append", required=True, help="Session ID or unambiguous prefix")
    parser.add_argument("--run-model", action="store_true", help="Generate previews using configured server LLM")
    parser.add_argument("--rubric", type=Path, help="Private JSON mapping session prefixes to required-point checks")
    parser.add_argument("--attempts", type=int, choices=(1, 2, 3), default=3)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.chmod(0o700)
    if args.output.resolve() == args.source_db.parent.resolve():
        parser.error("Output must not be the source database directory")
    source = sqlite3.connect(args.source_db.resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        rows = []
        for prefix in args.session:
            matches = source.execute("SELECT * FROM documents WHERE kind='session' AND session_id LIKE ?",
                                     (prefix + "%",)).fetchall()
            if len(matches) != 1:
                raise ValueError("Session prefix must match exactly one snapshot")
            rows.append(dict(matches[0]))
    finally:
        source.close()
    client = ChatModel.from_environment() if args.run_model else None
    if args.run_model and client is None:
        raise RuntimeError("Preview model is not configured")
    store = JobStore(args.output / "preview.sqlite")
    rubric = json.loads(args.rubric.read_text()) if args.rubric else {}
    results = []
    for row in rows:
        session_id = row["session_id"]
        directory = session_path(args.output, session_id)
        directory.mkdir(exist_ok=True, mode=0o700)
        for stale in directory.glob("model-response-*.md"):
            stale.unlink()
        for stale in ("refined.md", "overview.md"):
            (directory / stale).unlink(missing_ok=True)
        metadata = json.loads(row["request"])
        title = redact(str(metadata.get("original_title") or metadata.get("title") or session_id))
        original = redact(row["original"].decode("utf-8"))
        text = clean_session(original)
        baseline = redact(row["refined_text"] or "")
        (directory / "original.txt").write_text(original)
        (directory / "cleaned.txt").write_text(text)
        (directory / "before.md").write_text(baseline)
        required = list(dict.fromkeys(value for part in split_session(text) for value in anchors(part)))
        case = dict(session_id=session_id, title=title, original_chars=len(original), clean_chars=len(text),
                    segment_count=len(split_session(text)), baseline_chars=len(baseline),
                    baseline_refine_status=json.loads(row["refine_info"] or "{}").get("refine_status"),
                    baseline_coverage=coverage(required, baseline))
        checks = next((value for prefix, value in rubric.items() if session_id.startswith(prefix)), [])
        if checks:
            case["baseline_key_points"] = evaluate(checks, original, baseline)
        if args.run_model:
            model = MeteredModel(client, directory)
            job = store.put(row["bank_id"], row["owner"], "session", row["document_id"], "session.txt",
                            original.encode(), {})
            failures = []
            for attempt in range(args.attempts):
                try:
                    note, info = refine_session(text, model, title, store, job)
                    break
                except SessionRefineError as error:
                    failures.append(error.info)
                    print(json.dumps(dict(session_id=session_id, attempt=attempt + 1,
                                          failure=error.info), ensure_ascii=False), flush=True)
            else:
                note, info = None, failures[-1]
            case["refinement_attempts"] = attempt + 1
            case["attempt_failures"] = failures
            if note is not None:
                (directory / "refined.md").write_text(note)
                (directory / "overview.md").write_text(note.partition("## 主线与当前状态\n\n")[2] or note)
                case.update(status="prepared_not_retained", info=info, new_coverage=coverage(required, note))
                if checks:
                    case["new_key_points"] = evaluate(checks, original, note)
                    if any(check["source_supported"] and not check["note_present"]
                           for check in case["new_key_points"]):
                        case["status"] = "review_failed_not_retained"
                calls = len(model.calls)
                same, replay = refine_session(text, model, title, store, job)
                case["replay_no_model_calls"] = same == note and len(model.calls) == calls
                case["replay_cache_hits"] = replay["cache_hits"]
            else:
                case.update(status="degraded_not_retained", info=info)
            case["model_calls"] = model.calls
        results.append(case)
        (directory / "metrics.json").write_text(json.dumps(case, ensure_ascii=False, indent=2))
        print(json.dumps({key: value for key, value in case.items()
                          if key not in ("baseline_coverage", "new_coverage", "model_calls")}, ensure_ascii=False),
              flush=True)
        (args.output / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
        compare_page(args.output, results)
    if args.run_model and any(
            case["status"] != "prepared_not_retained"
            or any(check["source_supported"] and not check["note_present"]
                   for check in case.get("new_key_points", []))
            for case in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
