#!/usr/bin/env python3
"""Regression tests for evidence continuation and bounded bridge diagnostics."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("retrieve_workflow_knowledge.py")
SPEC = importlib.util.spec_from_file_location("tested_knowledge_bridge", SCRIPT)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class KnowledgeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="knowledge-bridge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        scripts = self.root / "apply-film-knowledge" / "scripts"
        scripts.mkdir(parents=True)
        for name in ("knowledge_review.py", "retrieve_knowledge.py"):
            (scripts / name).write_text("# fixture\n", encoding="utf-8")
        self.knowledge_config = self.root / "knowledge-tree.json"
        self.knowledge_config.write_text("{}", encoding="utf-8")
        self.config = {
            "skillsRoot": str(self.root),
            "knowledgeBridge": {"enabled": True, "configPath": str(self.knowledge_config)},
        }
        self.scope = {"role": "B", "roots": ["创作区/B-故事与剧本"]}
        self.request = {"mode": "evidence", "read_id": "example-id", "snapshot": "snapshot", "scope": self.scope}

    def invoke(self, args, *, code=0, stdout='{"evidence": []}', stderr=""):
        out, err = io.StringIO(), io.StringIO()
        child = subprocess.CompletedProcess([], code, stdout, stderr)
        with patch.object(sys, "argv", [str(SCRIPT), *args]), \
                patch.object(bridge, "load_workflow_config", return_value=(self.root / "workflow.json", self.config)), \
                patch.object(bridge.subprocess, "run", return_value=child) as run, \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = bridge.main()
        return status, out.getvalue(), err.getvalue(), run

    def query(self, *extra, **kwargs):
        return self.invoke(["--query", "人物弧光", "--role", "B", "--stage", "故事开发", *extra], **kwargs)

    def read(self, request=None, *extra, **kwargs):
        value = self.request if request is None else request
        return self.invoke(["--read-request", json.dumps(value, ensure_ascii=False), *extra], **kwargs)

    def test_review_stdout_error_is_preserved_with_exit_code(self):
        status, out, err, _ = self.query("--review", code=2, stdout='{"error":"目标路径不在本次范围","detail":{"path":"学习区/课程.md"}}')
        payload = json.loads(err)
        self.assertEqual((status, out, payload["child_exit_code"]), (2, "", 2))
        self.assertEqual(payload["child_diagnostics"]["stdout"]["details"]["error"], "目标路径不在本次范围")
        self.assertEqual(payload["child_diagnostics"]["stdout"]["details"]["detail"]["path"], "学习区/课程.md")

    def test_stderr_structured_error_is_preserved(self):
        status, out, err, _ = self.query(code=3, stdout="", stderr='{"error":{"code":"STALE","message":"快照变化"}}')
        payload = json.loads(err)
        self.assertEqual((status, out, payload["child_exit_code"]), (2, "", 3))
        self.assertEqual(payload["child_diagnostics"]["stderr"]["details"]["error"]["code"], "STALE")

    def test_both_error_channels_are_retained(self):
        status, _, err, _ = self.query(code=7, stdout='{"error":"找不到正文"}', stderr="读取失败的具体路径")
        self.assertEqual(status, 2)
        diagnostics = json.loads(err)["child_diagnostics"]
        self.assertEqual(set(diagnostics), {"stdout", "stderr"})
        self.assertEqual(diagnostics["stderr"]["text"], "读取失败的具体路径")

    def test_arbitrary_stdout_is_not_echoed_and_stderr_is_bounded(self):
        status, out, err, _ = self.query(code=9, stdout="PRIVATE_NOTE_" * 10000, stderr="底层失败" * 2000)
        payload = json.loads(err)
        self.assertEqual((status, out), (2, ""))
        self.assertNotIn("PRIVATE_NOTE", err)
        self.assertTrue(payload["child_diagnostics"]["stdout"]["omitted"])
        self.assertTrue(payload["child_diagnostics"]["stderr"]["truncated"])
        self.assertLess(len(err), 2600)

    def test_success_shaped_stdout_cannot_turn_nonzero_into_success(self):
        status, out, err, _ = self.query(code=5, stdout='{"evidence":["not an error"]}')
        self.assertEqual((status, out, json.loads(err)["child_exit_code"]), (2, "", 5))
        self.assertNotIn("not an error", err)

    def test_oversized_structured_error_is_bounded_and_marked(self):
        error = {"errors": ["error" * 1000] * 8}
        status, out, err, _ = self.query(code=2, stdout=json.dumps(error))
        self.assertEqual((status, out), (2, ""))
        self.assertLess(len(err), 6600)
        self.assertTrue(json.loads(err)["child_diagnostics"]["stdout"].get("omitted"))

    def test_structured_error_excerpt_is_marked(self):
        error = {"errors": ["错误原因" * 400] * 8}
        status, out, err, _ = self.query(code=2, stdout=json.dumps(error, ensure_ascii=False))
        self.assertEqual((status, out), (2, ""))
        detail = json.loads(err)["child_diagnostics"]["stdout"]
        self.assertEqual(detail["format"], "json_excerpt")
        self.assertTrue(detail["truncated"])
        self.assertLess(len(err), 6600)

    def test_valid_success_package_and_bridge_metadata(self):
        status, out, err, run = self.query(stdout='{"evidence":[{"text":"完整方法"}],"context":{"role":"B"}}')
        payload = json.loads(out)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(payload["evidence"][0]["text"], "完整方法")
        self.assertEqual(payload["workflow_bridge"]["skill"], "apply-film-knowledge")
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--limit") + 1], "1")

    def test_success_exit_with_invalid_json_fails_without_echo(self):
        status, out, err, _ = self.query(stdout="PRIVATE_INVALID_JSON")
        self.assertEqual((status, out), (2, ""))
        self.assertIn("非 JSON", json.loads(err)["error"])
        self.assertNotIn("PRIVATE_INVALID_JSON", err)

    def test_success_exit_with_non_object_fails(self):
        status, out, err, _ = self.query(stdout="[]")
        self.assertEqual((status, out), (2, ""))
        self.assertIn("JSON 对象", json.loads(err)["error"])

    def test_error_envelope_with_success_exit_remains_failure(self):
        status, out, err, _ = self.query(stdout='{"error":"错误不能变成证据"}')
        self.assertEqual((status, out, json.loads(err)["child_exit_code"]), (2, "", 0))

    def test_review_context_question_and_material_forwarding(self):
        status, _, err, run = self.query("--review", "--question", "问题一", "--question", "问题二", "--material", "事实", "--constraints", "不增时长", "--no-cache")
        command = run.call_args.args[0]
        self.assertEqual((status, err), (0, ""))
        self.assertTrue(command[4].endswith("knowledge_review.py"))
        self.assertEqual(command.count("--question"), 2)
        self.assertEqual(command[command.index("--constraints") + 1], "不增时长")
        self.assertIn("--no-cache", command)
        self.assertNotIn("--limit", command)

    def test_c1_and_c2_continue_mapping_to_c(self):
        for role in ("C1", "C2"):
            with self.subTest(role=role):
                status, _, _, run = self.invoke(["--query", "镜头", "--role", role, "--stage", "导演"])
                command = run.call_args.args[0]
                self.assertEqual(status, 0)
                self.assertEqual(command[command.index("--role") + 1], "C")

    def test_evidence_request_without_repeated_search_arguments(self):
        status, _, err, run = self.read()
        self.assertEqual((status, err), (0, ""))
        command = run.call_args.args[0]
        self.assertTrue(command[4].endswith("knowledge_review.py"))
        self.assertEqual(json.loads(command[command.index("--read-request") + 1]), self.request)
        self.assertNotIn("--query", command)
        self.assertNotIn("--role", command)
        self.assertNotIn("--stage", command)
        self.assertNotIn("--limit", command)
        self.assertEqual(Path(command[command.index("--config") + 1]), self.knowledge_config.resolve())

    def test_section_request_passes_through_unchanged(self):
        request = {"mode": "section", "path": "创作区/B/方法.md", "heading": "方法", "document_hash": "hash", "snapshot": "snapshot", "scope": self.scope, "offset": 650, "max_chars": 5000}
        status, _, err, run = self.read(request)
        self.assertEqual((status, err), (0, ""))
        command = run.call_args.args[0]
        self.assertEqual(json.loads(command[command.index("--read-request") + 1]), request)

    def test_legacy_null_scope_is_delegated_to_config_validator(self):
        status, _, err, run = self.read({**self.request, "scope": None})
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(run.call_count, 1)

    def test_read_request_allows_no_cache_and_debug(self):
        status, out, err, run = self.read(None, "--no-cache", "--debug")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("--no-cache", run.call_args.args[0])
        self.assertNotIn("--debug", run.call_args.args[0])
        self.assertIn("\n", out)

    def test_read_request_rejects_all_search_or_range_arguments(self):
        conflicts = [
            ["--query", ""], ["--role", "B"], ["--stage", ""], ["--task-type", ""],
            ["--object", ""], ["--constraints", ""], ["--expected-output", ""],
            ["--limit", "1"], ["--review"], ["--question", "新问题"], ["--material", ""],
            ["--include-path", "学习区/课程"],
        ]
        for extra in conflicts:
            with self.subTest(extra=extra):
                status, out, err, run = self.read(None, *extra)
                self.assertEqual((status, out, run.call_count), (2, "", 0))
                self.assertIn(extra[0], json.loads(err)["error"])

    def test_bad_request_is_rejected_before_child_call(self):
        for request in ([], "text", {}, {"mode": "other"}, {"mode": "evidence", "scope": None}, {"mode": "evidence", "snapshot": "s"}):
            with self.subTest(request=request):
                status, out, err, run = self.read(request)
                self.assertEqual((status, out, run.call_count), (2, "", 0))
                self.assertIn("error", json.loads(err))

    def test_empty_request_json_is_rejected(self):
        status, out, err, run = self.invoke(["--read-request", ""])
        self.assertEqual((status, out, run.call_count), (2, "", 0))
        self.assertIn("error", json.loads(err))

    def test_search_still_requires_query_role_and_stage(self):
        for args in ([], ["--query", "人物"], ["--query", "人物", "--role", "B"]):
            with self.subTest(args=args):
                status, out, err, run = self.invoke(args)
                self.assertEqual((status, out, run.call_count), (2, "", 0))
                self.assertIn("--query", json.loads(err)["error"])


if __name__ == "__main__":
    unittest.main()
