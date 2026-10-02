"""Read local Codex task metadata when the native recent-task list is incomplete.

No task creation, messages, database writes, project writes, or conversation reads.
The caller must first resolve the local project ID/root with the native project tool.
"""
import argparse
import json
import ntpath
import os
from pathlib import Path
import sqlite3
import sys


class QueryError(ValueError):
    pass


def windows_path(value):
    if not isinstance(value, str) or not value:
        return None
    value = value.replace("/", "\\")
    if value[:8].casefold() == "\\\\?\\unc\\":
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    drive, tail = ntpath.splitdrive(value)
    if drive.startswith("\\\\") and tail in ("", "\\"):
        value, tail = drive + "\\", "\\"
    if not drive or not tail.startswith("\\"):
        return None
    return ntpath.normcase(ntpath.normpath(value))


def read_state(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise QueryError("Unsupported application state schema")
    assignments = data.get("thread-project-assignments")
    orders = data.get("sidebar-project-thread-orders", {})
    if not isinstance(assignments, dict) or not isinstance(orders, dict):
        raise QueryError("Unsupported application project-assignment schema")
    if any(not isinstance(v, dict) for v in assignments.values()):
        raise QueryError("Unsupported thread-project assignment")
    return assignments, orders


def project_ids(state, project_id):
    assignments, orders = state
    assigned = {tid for tid, value in assignments.items()
                if value.get("projectId") == project_id}
    order = orders.get(project_id, {})
    if not isinstance(order, dict):
        raise QueryError("Unsupported sidebar project order")
    sidebar = order.get("threadIds", [])
    if not isinstance(sidebar, list) or any(not isinstance(tid, str) for tid in sidebar):
        raise QueryError("Unsupported sidebar thread IDs")
    return assigned | set(sidebar)


def state_projection(state, project_id, row_ids):
    ids = project_ids(state, project_id)
    return ids, {tid: state[0].get(tid) for tid in ids | set(row_ids)}


def query_tasks(codex_home, project_id, project_root, current_thread_id):
    root = windows_path(project_root)
    if root is None:
        raise QueryError("Project root must be a fully qualified Windows path")
    if not project_id or not current_thread_id:
        raise QueryError("Project ID and current thread ID are required")
    base = Path(codex_home).resolve()
    databases = list(base.glob("state_*.sqlite"))
    if len(databases) != 1:
        raise QueryError("Expected exactly one local state database; do not guess a version")
    state_path = base / ".codex-global-state.json"
    state_before = read_state(state_path)
    assigned_ids = project_ids(state_before, project_id)
    if len(assigned_ids) > 50:
        raise QueryError("More than 50 project-assigned tasks; bounded query is incomplete")
    con = sqlite3.connect(databases[0].as_uri() + "?mode=ro", uri=True, timeout=5)
    try:
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA query_only=ON")
        columns = {row[1] for row in con.execute("PRAGMA table_info(threads)")}
        if not {"id", "cwd", "archived"}.issubset(columns) or not ({"name", "title"} & columns):
            raise QueryError("Unsupported task-index schema")
        title = "COALESCE(NULLIF(name, ''), title)" if {"name", "title"}.issubset(columns) else ("name" if "name" in columns else "title")
        project_column = "project_id" if "project_id" in columns else "NULL"
        con.create_function("windows_path", 1, windows_path, deterministic=True)
        ids = sorted(assigned_ids | {current_thread_id})
        placeholders = ",".join("?" for _ in ids)
        sql = (f"SELECT id, {title} AS title, cwd, archived, {project_column} AS project_id "
               f"FROM threads WHERE windows_path(cwd)=? OR {project_column}=? "
               f"OR id IN ({placeholders}) ORDER BY id LIMIT 51")
        params = [root, project_id, *ids]
        con.execute("BEGIN")
        rows = [dict(row) for row in con.execute(sql, params)]
        con.rollback()
        if len(rows) > 50:
            raise QueryError("More than 50 matching tasks; bounded query is incomplete")
        # Check only metadata relevant to this project, not timestamps or other chats.
        again = [dict(row) for row in con.execute(sql, params)]
        state_after = read_state(state_path)
        row_ids = {row["id"] for row in rows}
        if rows != again or state_projection(state_before, project_id, row_ids) != state_projection(state_after, project_id, row_ids):
            raise QueryError("Project task metadata changed during the query; re-query before creating")
    finally:
        con.close()

    issues = []
    unresolved = sorted(assigned_ids - row_ids)
    if unresolved:
        issues.append("Assigned/sidebar task IDs missing from local index")
    if current_thread_id not in row_ids:
        issues.append("Current task is missing from local index")
    active, archived = [], []
    for row in rows:
        tid = row["id"]
        assignment = state_before[0].get(tid, {})
        app_pid = assignment.get("projectId")
        db_pid = row["project_id"]
        effective_pid = app_pid or db_pid
        cwd_matches = windows_path(row["cwd"]) == root
        current_exception = tid == current_thread_id and cwd_matches and not effective_pid
        item = {"id": tid, "title": row["title"], "cwd": row["cwd"],
                "projectId": effective_pid, "appProjectId": app_pid, "indexProjectId": db_pid,
                "cwdMatches": cwd_matches, "currentTaskException": current_exception,
                "archived": bool(row["archived"])}
        if row["archived"] not in (0, 1):
            issues.append(f"Unknown archive state: {tid}")
        if row["archived"] == 1:
            archived.append(item)
            if tid == current_thread_id:
                issues.append("Current task is archived")
            continue
        active.append(item)
        if not cwd_matches:
            issues.append(f"Project-assigned task has a different cwd: {tid}")
        if app_pid and db_pid and app_pid != db_pid:
            issues.append(f"Conflicting project assignments: {tid}")
        if assignment.get("projectKind") not in (None, "local"):
            issues.append(f"Non-local project assignment: {tid}")
        if effective_pid != project_id and not current_exception:
            issues.append(f"Missing or different project assignment: {tid}")
        if not isinstance(row["title"], str) or not row["title"].strip():
            issues.append(f"Task title unavailable: {tid}")
    return {"success": not issues, "readOnly": True, "complete": not issues,
            "projectId": project_id, "projectRoot": project_root,
            "currentThreadId": current_thread_id, "stateDatabase": databases[0].name,
            "activeThreads": active, "archivedThreads": archived,
            "unresolvedThreadIds": unresolved, "issues": issues,
            "tasksCreated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--current-thread-id", required=True)
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME"))
    args = parser.parse_args()
    try:
        if not args.codex_home:
            raise QueryError("Set CODEX_HOME or pass --codex-home; do not scan user profiles")
        result = query_tasks(args.codex_home, args.project_id, args.project_root, args.current_thread_id)
    except (QueryError, OSError, ValueError, sqlite3.Error) as exc:
        result = {"success": False, "readOnly": True, "complete": False,
                  "tasksCreated": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
