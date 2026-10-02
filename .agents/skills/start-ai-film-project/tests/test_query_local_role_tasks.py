import copy
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/query_local_role_tasks.py"
spec = importlib.util.spec_from_file_location("local_role_query", SCRIPT)
query = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query)
ROOT = r"D:\作品\2026-09-21_30s_v1"
PID = "test-project"


class LocalQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="xiaomo-role-query-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.db = self.base / "state_5.sqlite"
        self.state = {"thread-project-assignments": {}, "sidebar-project-thread-orders": {PID: {"threadIds": []}}}
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, name TEXT, title TEXT, cwd TEXT, project_id TEXT, archived INTEGER)")
        self.add("a", "A｜制片统筹")

    def save(self):
        (self.base / ".codex-global-state.json").write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")

    def add(self, tid, title, cwd=ROOT, assignment=PID, db_pid=None, archived=0):
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?)", (tid, title, "old title", cwd, db_pid, archived))
        if assignment:
            self.state["thread-project-assignments"][tid] = {"projectId": assignment, "projectKind": "local"}
            if assignment == PID:
                self.state["sidebar-project-thread-orders"][PID]["threadIds"].append(tid)
        self.save()

    def run_query(self):
        return query.query_tasks(self.base, PID, ROOT, "a")

    def test_more_than_fifty_unrelated_recent_tasks_does_not_hide_old_roles(self):
        for index in range(70):
            self.add(f"unrelated-{index}", "B｜编剧开发", cwd=r"D:\其他", assignment="other")
        self.add("older-b", "B｜编剧开发")
        result = self.run_query()
        self.assertTrue(result["complete"])
        self.assertEqual({row["id"] for row in result["activeThreads"]}, {"a", "older-b"})

    def test_null_database_project_id_uses_application_assignment(self):
        self.add("b", "B｜编剧开发")
        result = self.run_query()
        self.assertTrue(result["complete"])
        self.assertEqual(result["activeThreads"][1]["projectId"], PID)

    def test_long_windows_path_and_case_are_same_project(self):
        self.add("b", "B｜编剧开发", cwd="\\\\?\\" + ROOT.lower() + "\\")
        self.assertTrue(self.run_query()["complete"])
        self.assertEqual(query.windows_path(r"\\?\UNC\server\share\folder"), query.windows_path(r"\\SERVER\SHARE\folder"))
        self.assertEqual(query.windows_path(r"\\?\unc\server\share\folder"), query.windows_path(r"\\SERVER\SHARE\folder"))
        self.assertEqual(query.windows_path(r"\\server\share"), query.windows_path("\\\\SERVER\\SHARE\\"))

    def test_lowercase_unc_unassigned_task_is_not_invisible(self):
        root = r"\\server\share\film"
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("UPDATE threads SET cwd=? WHERE id='a'", (root,))
        self.add("b", "B｜编剧开发", cwd=r"\\?\unc\server\share\film", assignment=None)
        result = query.query_tasks(self.base, PID, root, "a")
        self.assertFalse(result["complete"])
        self.assertEqual({item["id"] for item in result["activeThreads"]}, {"a", "b"})

    def test_wrong_project_on_same_path_is_not_ignored(self):
        self.add("b", "B｜编剧开发", assignment="other")
        result = self.run_query()
        self.assertFalse(result["complete"])
        self.assertEqual(len(result["activeThreads"]), 2)

    def test_current_task_without_assignment_is_only_exception(self):
        self.state["thread-project-assignments"].pop("a")
        self.save()
        self.assertTrue(self.run_query()["complete"])
        self.assertTrue(self.run_query()["activeThreads"][0]["currentTaskException"])
        self.add("b", "B｜编剧开发", assignment=None)
        self.assertFalse(self.run_query()["complete"])

    def test_assigned_task_in_different_folder_blocks_creation(self):
        self.add("b", "B｜编剧开发", cwd=ROOT + "-other")
        self.assertFalse(self.run_query()["complete"])

    def test_database_and_application_disagree(self):
        self.add("b", "B｜编剧开发", db_pid="other")
        self.assertFalse(self.run_query()["complete"])

    def test_duplicate_roles_are_both_returned_for_caller(self):
        self.add("b1", "B｜编剧开发")
        self.add("b2", "B｜编剧开发")
        result = self.run_query()
        self.assertEqual([t["title"] for t in result["activeThreads"]].count("B｜编剧开发"), 2)

    def test_archived_role_separated_and_not_active(self):
        self.add("old-b", "B｜编剧开发", archived=1)
        result = self.run_query()
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["activeThreads"]), 1)
        self.assertEqual(result["archivedThreads"][0]["id"], "old-b")

    def test_missing_assigned_id_is_incomplete(self):
        self.state["sidebar-project-thread-orders"][PID]["threadIds"].append("missing")
        self.save()
        self.assertFalse(self.run_query()["complete"])

    def test_unknown_current_task_not_assumed_new(self):
        result = query.query_tasks(self.base, PID, ROOT, "unknown")
        self.assertFalse(result["complete"])

    def test_too_many_project_candidates_rejected(self):
        for index in range(50):
            self.add(f"b-{index}", "B｜编剧开发")
        with self.assertRaises(query.QueryError):
            self.run_query()

    def test_unknown_schema_rejected(self):
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute("ALTER TABLE threads RENAME TO old_threads")
        with self.assertRaises(query.QueryError):
            self.run_query()

    def test_multiple_database_versions_not_guessed(self):
        (self.base / "state_6.sqlite").write_bytes(b"")
        with self.assertRaises(query.QueryError):
            self.run_query()

    def test_application_assignment_change_during_query_rejected(self):
        before = query.read_state(self.base / ".codex-global-state.json")
        after = copy.deepcopy(before)
        after[0]["a"]["projectId"] = "different"
        with patch.object(query, "read_state", side_effect=[before, after]):
            with self.assertRaises(query.QueryError):
                self.run_query()

    def test_unrelated_app_changes_do_not_block_project(self):
        before = query.read_state(self.base / ".codex-global-state.json")
        after = copy.deepcopy(before)
        after[0]["unrelated"] = {"projectId": "other", "projectKind": "local"}
        with patch.object(query, "read_state", side_effect=[before, after]):
            self.assertTrue(self.run_query()["complete"])

    def test_failed_and_successful_queries_do_not_change_files(self):
        snapshot = lambda: {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.base.iterdir() if p.is_file()}
        before = snapshot()
        self.run_query()
        self.assertEqual(snapshot(), before)
        self.assertFalse(query.query_tasks(self.base, PID, ROOT, "unknown")["complete"])
        self.assertEqual(snapshot(), before)

    def test_cli_missing_index_does_not_create_database(self):
        self.db.unlink()
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--codex-home", str(self.base), "--project-id", PID, "--project-root", ROOT, "--current-thread-id", "a"], capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["complete"])
        self.assertFalse(self.db.exists())

    def test_unknown_application_state_returns_json_failure(self):
        (self.base / ".codex-global-state.json").write_text("[]", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--codex-home", str(self.base), "--project-id", PID, "--project-root", ROOT, "--current-thread-id", "a"], capture_output=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["complete"])

    def test_newly_created_task_detected_on_next_query(self):
        self.assertEqual(len(self.run_query()["activeThreads"]), 1)
        self.add("b", "B｜编剧开发")
        self.assertEqual(len(self.run_query()["activeThreads"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
