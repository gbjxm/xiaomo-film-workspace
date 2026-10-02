#!/usr/bin/env python3
"""Call the optional knowledge bridge through the workflow's local config."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def config_candidates(explicit: str | None) -> list[Path]:
    if explicit:
        return [Path(explicit)]
    rows: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        rows.append(Path(codex_home) / "xiaomo-ai-film-workflow.json")
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        rows.append(Path(user_profile) / ".agents" / "xiaomo-ai-film-workflow.json")
    return rows


def load_workflow_config(explicit: str | None) -> tuple[Path, dict]:
    found = [path.resolve() for path in config_candidates(explicit) if path.is_file()]
    if len(found) != 1:
        raise RuntimeError("无法唯一定位小陌 AI 影视工作流本机配置")
    path = found[0]
    return path, json.loads(path.read_text(encoding="utf-8-sig"))


def _bounded_value(value, depth: int = 0):
    """Keep useful structured diagnostics without relaying arbitrary child output."""
    if depth >= 4:
        return "[诊断层级已截短]"
    if isinstance(value, str):
        return value if len(value) <= 1600 else value[:1600] + "…[诊断已截短]"
    if isinstance(value, dict):
        items = list(value.items())
        result = {str(key)[:120]: _bounded_value(item, depth + 1) for key, item in items[:12]}
        if len(items) > 12:
            result["_truncated"] = True
        return result
    if isinstance(value, list):
        result = [_bounded_value(item, depth + 1) for item in value[:8]]
        return result + (["[诊断条目已截短]"] if len(value) > 8 else [])
    return value


def _child_diagnostic(raw: str, *, stderr: bool) -> dict | None:
    raw = raw.strip()
    if not raw:
        return None
    if len(raw) <= 32768:
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            value = None
        if isinstance(value, dict):
            selected = {
                key: _bounded_value(value[key])
                for key in ("error", "errors", "message", "detail", "reason", "code", "type")
                if key in value
            }
            if selected:
                if len(json.dumps(selected, ensure_ascii=False)) <= 6000:
                    return {"format": "json", "details": selected}
                # The marker is explicit, and still preserves the beginning of the error.
                return {"format": "json_excerpt", "details": json.dumps(selected, ensure_ascii=False)[:6000], "truncated": True}
    if stderr:
        return {"format": "text", "text": raw[:2000], "truncated": len(raw) > 2000}
    # Non-JSON stdout can be a full note or an unrelated success payload. Never echo it.
    return {"format": "unrecognized", "chars": len(raw), "omitted": True}


def child_failure(completed) -> dict:
    diagnostics = {}
    for name in ("stdout", "stderr"):
        detail = _child_diagnostic(getattr(completed, name, "") or "", stderr=name == "stderr")
        if detail:
            diagnostics[name] = detail
    return {"error": "知识调用失败", "child_exit_code": completed.returncode, "child_diagnostics": diagnostics}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--workflow-config")
    parser.add_argument("--query")
    parser.add_argument("--role", choices=("A", "B", "C", "C1", "C2", "D", "E"))
    parser.add_argument("--stage")
    parser.add_argument("--task-type")
    parser.add_argument("--object")
    parser.add_argument("--constraints")
    parser.add_argument("--expected-output")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--review", action="store_true", default=None, help="按必查项提供来源证据包")
    parser.add_argument("--question", action="append")
    parser.add_argument("--material")
    parser.add_argument("--no-cache", action="store_true", default=None)
    parser.add_argument("--include-path", action="append")
    parser.add_argument("--read-request", help="原样传回检索结果中的 continuation JSON；沿用其 scope 和 snapshot")
    args = parser.parse_args()
    try:
        if args.read_request is not None:
            conflicts = [name for name in (
                "query", "role", "stage", "task_type", "object", "constraints", "expected_output",
                "limit", "review", "question", "material", "include_path",
            ) if getattr(args, name) is not None]
            if conflicts:
                raise ValueError("续读沿用原请求范围，不得同时提供：" + ", ".join("--" + name.replace("_", "-") for name in conflicts))
            request = json.loads(args.read_request)
            if not isinstance(request, dict) or request.get("mode") not in {"evidence", "section"}:
                raise ValueError("read-request 必须是 mode 为 evidence 或 section 的 JSON 对象")
            if "scope" not in request or not request.get("snapshot"):
                raise ValueError("read-request 必须保留原 scope 和 snapshot")
        elif not all((args.query, args.role, args.stage)):
            raise ValueError("检索必须提供 --query、--role 和 --stage；续读只需 --read-request")
        workflow_config_path, config = load_workflow_config(args.workflow_config)
        bridge = config.get("knowledgeBridge") or {}
        if bridge.get("enabled") is not True:
            raise RuntimeError("知识桥未启用；请重新运行工作流安装器并显式提供知识树配置")
        knowledge_config = Path(str(bridge.get("configPath", ""))).resolve(strict=True)
        skills_root = Path(str(config.get("skillsRoot", ""))).resolve(strict=True)
        skill_name = str(bridge.get("skillName") or "apply-film-knowledge")
        script_name = "knowledge_review.py" if args.review or args.read_request is not None else "retrieve_knowledge.py"
        retriever = skills_root / skill_name / "scripts" / script_name
        if not retriever.is_file():
            raise RuntimeError(f"知识调用 Skill 不存在：{retriever}")
        command = [sys.executable, "-B", "-X", "utf8", str(retriever), "--config", str(knowledge_config)]
        if args.read_request is not None:
            command.extend(("--read-request", args.read_request))
        else:
            command.extend(("--query", args.query, "--role", "C" if args.role in {"C1", "C2"} else args.role, "--stage", args.stage))
        if args.review:
            for question in args.question or []:
                command.extend(("--question", question))
            if args.material:
                command.extend(("--material", args.material))
        elif args.read_request is None:
            command.extend(("--limit", str(args.limit if args.limit is not None else 1)))
        for flag, value in (
            ("--task-type", args.task_type), ("--object", args.object),
            ("--constraints", args.constraints), ("--expected-output", args.expected_output),
        ):
            if value:
                command.extend((flag, value))
        if args.debug and not args.review and args.read_request is None:
            command.append("--debug")
        for selected_path in args.include_path or []:
            command.extend(("--include-path", selected_path))
        if args.no_cache:
            command.append("--no-cache")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if completed.returncode != 0:
            print(json.dumps(child_failure(completed), ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        try:
            payload = json.loads(completed.stdout)
        except (ValueError, TypeError) as exc:
            raise ValueError("知识调用返回了非 JSON 内容（子进程退出码 0）") from exc
        if not isinstance(payload, dict):
            raise ValueError("知识调用返回值必须为 JSON 对象（子进程退出码 0）")
        if payload.get("error"):
            print(json.dumps(child_failure(completed), ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        payload["workflow_bridge"] = {
            "workflow_config": str(workflow_config_path),
            "enabled": True,
            "skill": skill_name,
        }
        print(json.dumps(
            payload,
            ensure_ascii=False,
            indent=2 if args.debug else None,
            separators=None if args.debug else (",", ":"),
        ))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
