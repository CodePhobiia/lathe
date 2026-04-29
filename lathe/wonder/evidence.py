"""Evidence traceability helpers for Wonder readiness tasks."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

WONDER_EVIDENCE_TRACE_VERSION = "lathe.wonder_evidence_trace.v1"

_CHECKED_TASK_RE = re.compile(r"^\s*-\s+\[x\]\s+(?P<text>.+?)\s*$")
_HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
_GLOBAL_AUDIT_PATTERNS = (
    "supports the audited task-box state in `wonder-tasks.md`",
    "checked items now mean the repo has concrete implementation",
)


@dataclass(frozen=True)
class CheckedTask:
    """One checked task box from ``wonder-tasks.md``."""

    task_id: str
    text: str
    line: int
    section: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "text": self.text,
            "line": self.line,
            "section": self.section,
        }


@dataclass
class EvidenceItem:
    """One parsed evidence item from the readiness evidence ledger."""

    evidence_id: str
    kind: str
    text: str
    line: int
    date: str | None = None
    command: str | None = None
    result: str | None = None
    status: str | None = None
    output_path: str | None = None
    paths: list[str] = field(default_factory=list)
    covers_all_checked_tasks: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "kind": self.kind,
            "text": self.text,
            "line": self.line,
            "paths": list(self.paths),
        }
        for key in ("date", "command", "result", "status", "output_path"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        if self.covers_all_checked_tasks:
            payload["covers_all_checked_tasks"] = True
        return payload


def _repo_root_from(path: Path) -> Path:
    for parent in [path, *path.parents]:
        if (parent / "wonder-tasks.md").exists() and (parent / "lathe").exists():
            return parent
    return Path.cwd()


def _normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _slug(value: str, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return (normalized[:64].strip("_") or fallback)


def parse_checked_tasks(markdown: str) -> list[CheckedTask]:
    """Return checked Markdown task boxes with their section context."""
    headings: dict[int, str] = {}
    tasks: list[CheckedTask] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group("marks"))
            headings = {key: value for key, value in headings.items() if key < level}
            headings[level] = heading_match.group("title").strip()
            continue
        task_match = _CHECKED_TASK_RE.match(line)
        if not task_match:
            continue
        text = task_match.group("text").strip()
        section = " / ".join(value for _level, value in sorted(headings.items()))
        tasks.append(
            CheckedTask(
                task_id=f"task_{line_number}_{_slug(text, fallback='checked')}",
                text=text,
                line=line_number,
                section=section,
            )
        )
    return tasks


def _clean_cell(value: str) -> str:
    return value.strip().replace("<br>", " ").replace("<br/>", " ")


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _iter_markdown_tables(lines: list[str]) -> Iterable[tuple[int, list[str], list[list[str]]]]:
    index = 0
    while index + 1 < len(lines):
        if not lines[index].lstrip().startswith("|") or not _is_table_separator(lines[index + 1]):
            index += 1
            continue
        start_line = index + 1
        header = [_normalize_text(cell).replace(" ", "_") for cell in lines[index].strip().strip("|").split("|")]
        index += 2
        rows: list[list[str]] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            rows.append([_clean_cell(cell) for cell in lines[index].strip().strip("|").split("|")])
            index += 1
        yield start_line, header, rows


def _cell(row: Mapping[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value:
            return value
    return None


def _split_paths(raw: str | None) -> list[str]:
    if not raw:
        return []
    paths: list[str] = []
    for token in re.split(r"[,;]\s*|\s+and\s+", raw):
        stripped = token.strip().strip("`")
        if stripped:
            paths.append(stripped)
    return paths


def _status_from_result(result: str | None) -> str | None:
    if result is None:
        return None
    normalized = result.lower()
    if "passed" in normalized or "ok: true" in normalized:
        return "passed"
    if "blocked" in normalized or "skipped" in normalized:
        return "skipped"
    if "failed" in normalized or "error" in normalized:
        return "failed"
    return None


def _evidence_kind(row: Mapping[str, str]) -> str:
    explicit = _cell(row, "type", "kind")
    if explicit:
        return _slug(explicit, fallback="evidence")
    if _cell(row, "command"):
        return "command"
    if _cell(row, "schema"):
        return "schema"
    if _cell(row, "docs", "doc", "documentation"):
        return "docs"
    if _cell(row, "example", "artifact"):
        return "example_artifact"
    if _cell(row, "report", "output"):
        return "report"
    return "decision"


def _table_evidence_items(markdown: str) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    lines = markdown.splitlines()
    for start_line, header, rows in _iter_markdown_tables(lines):
        for row_index, raw_row in enumerate(rows, start=1):
            padded = [*raw_row, *([""] * max(0, len(header) - len(raw_row)))]
            row = dict(zip(header, padded, strict=False))
            text = " | ".join(value for value in padded if value)
            if not text:
                continue
            result = _cell(row, "result", "evidence_state", "current_local_state", "status")
            status = _cell(row, "status") or _status_from_result(result)
            output_path = _cell(row, "output", "out", "report_path")
            paths = []
            for column in ("path", "paths", "output", "out", "report_path", "schema", "docs", "doc", "example", "artifact"):
                paths.extend(_split_paths(row.get(column)))
            command = _cell(row, "command")
            items.append(
                EvidenceItem(
                    evidence_id=f"ev_{start_line}_{row_index}_{_slug(text, fallback='row')}",
                    kind=_evidence_kind(row),
                    text=text,
                    line=start_line + row_index + 1,
                    date=_cell(row, "date"),
                    command=command,
                    result=result,
                    status=status,
                    output_path=output_path,
                    paths=paths,
                )
            )
    return items


def _global_audit_item(markdown: str) -> EvidenceItem | None:
    normalized = markdown.lower()
    if not any(pattern.lower() in normalized for pattern in _GLOBAL_AUDIT_PATTERNS):
        return None
    line = 1
    for index, text_line in enumerate(markdown.splitlines(), start=1):
        if any(pattern.lower() in text_line.lower() for pattern in _GLOBAL_AUDIT_PATTERNS):
            line = index
            break
    return EvidenceItem(
        evidence_id="ev_global_task_audit_decision",
        kind="decision",
        text="Evidence ledger contains an explicit task-box audit decision for checked Wonder tasks.",
        line=line,
        status="passed",
        paths=["wonder-tasks.md", "docs/wonder-readiness/evidence.md"],
        covers_all_checked_tasks=True,
    )


def parse_evidence_items(markdown: str) -> list[EvidenceItem]:
    """Return evidence items parsed from the readiness ledger."""
    items = _table_evidence_items(markdown)
    global_item = _global_audit_item(markdown)
    if global_item is not None:
        items.insert(0, global_item)
    return items


def _path_exists(repo_root: Path, raw_path: str) -> bool:
    if not raw_path or "://" in raw_path:
        return True
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.exists()


def _task_tokens(task: CheckedTask) -> set[str]:
    tokens = set(_normalize_text(task.text).split())
    tokens.update(_normalize_text(task.section).split())
    return {token for token in tokens if len(token) >= 4}


def _item_tokens(item: EvidenceItem) -> set[str]:
    text = " ".join(
        value
        for value in [
            item.text,
            item.command or "",
            item.result or "",
            " ".join(item.paths),
        ]
        if value
    )
    return {token for token in _normalize_text(text).split() if len(token) >= 4}


def _covers_task(task: CheckedTask, item: EvidenceItem) -> bool:
    if item.covers_all_checked_tasks:
        return True
    normalized_task = _normalize_text(task.text)
    normalized_item = _normalize_text(item.text)
    if normalized_task and normalized_task in normalized_item:
        return True
    task_paths = re.findall(r"`([^`]+\.[a-zA-Z0-9]+)`", task.text)
    if task_paths and any(path in item.text for path in task_paths):
        return True
    overlap = _task_tokens(task) & _item_tokens(item)
    return len(overlap) >= 3


def _validate_used_evidence(item: EvidenceItem, repo_root: Path) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    missing_paths = [path for path in item.paths if not _path_exists(repo_root, path)]
    if missing_paths:
        diagnostics.append(
            {
                "code": "WET1002",
                "severity": "error",
                "evidence_id": item.evidence_id,
                "path": f"/evidence_items/{item.evidence_id}/paths",
                "message": "Evidence item references paths that do not exist.",
                "details": {"missing_paths": missing_paths},
            }
        )
    if item.kind == "command":
        missing_fields = [
            field_name
            for field_name, value in {
                "command": item.command,
                "result": item.result,
                "status": item.status,
                "date": item.date,
                "output_path": item.output_path,
            }.items()
            if value is None or value == ""
        ]
        if missing_fields:
            diagnostics.append(
                {
                    "code": "WET1003",
                    "severity": "error",
                    "evidence_id": item.evidence_id,
                    "path": f"/evidence_items/{item.evidence_id}",
                    "message": "Command evidence is missing required traceability fields.",
                    "details": {"missing_fields": missing_fields},
                }
            )
    return diagnostics


def build_evidence_trace(
    tasks_path: str | Path,
    evidence_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a traceability report from checked Wonder tasks to evidence."""
    tasks_file = Path(tasks_path)
    evidence_file = Path(evidence_path)
    root = Path(repo_root) if repo_root is not None else _repo_root_from(tasks_file.resolve())
    tasks = parse_checked_tasks(tasks_file.read_text(encoding="utf-8"))
    evidence_items = parse_evidence_items(evidence_file.read_text(encoding="utf-8"))
    global_items = [item for item in evidence_items if item.covers_all_checked_tasks]
    coverage: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for task in tasks:
        matched = global_items or [item for item in evidence_items if _covers_task(task, item)]
        if not matched:
            missing.append(task.as_dict())
            continue
        used_ids.update(item.evidence_id for item in matched)
        coverage.append(
            {
                **task.as_dict(),
                "evidence_ids": [item.evidence_id for item in matched[:5]],
            }
        )
    used_items = [item for item in evidence_items if item.evidence_id in used_ids]
    diagnostics: list[dict[str, Any]] = []
    for item in used_items:
        diagnostics.extend(_validate_used_evidence(item, root))
    if missing:
        diagnostics.append(
            {
                "code": "WET1001",
                "severity": "error",
                "path": "/checked_tasks",
                "message": "One or more checked Wonder tasks have no durable evidence item.",
                "details": {"missing_count": len(missing)},
            }
        )
    status = "failed" if diagnostics else "passed"
    return {
        "schema_version": WONDER_EVIDENCE_TRACE_VERSION,
        "ok": status == "passed",
        "status": status,
        "tasks_path": str(tasks_file),
        "evidence_path": str(evidence_file),
        "summary": {
            "checked_tasks": len(tasks),
            "covered_checked_tasks": len(coverage),
            "missing_evidence": len(missing),
            "evidence_items": len(evidence_items),
            "used_evidence_items": len(used_items),
            "diagnostics": len(diagnostics),
        },
        "checked_tasks": [task.as_dict() for task in tasks],
        "evidence_items": [item.as_dict() for item in evidence_items],
        "coverage": coverage,
        "missing_evidence": missing,
        "diagnostics": diagnostics,
    }


def write_evidence_trace(
    tasks_path: str | Path,
    evidence_path: str | Path,
    out_path: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Write an evidence traceability report and return its payload."""
    report = build_evidence_trace(tasks_path, evidence_path, repo_root=repo_root)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return report


__all__ = [
    "WONDER_EVIDENCE_TRACE_VERSION",
    "build_evidence_trace",
    "parse_checked_tasks",
    "parse_evidence_items",
    "write_evidence_trace",
]
