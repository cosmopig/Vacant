#!/usr/bin/env python3
"""Import frozen external exams into an exam bank (e.g. ~/dev/ops/ref/bm_tasks/exam37).

Copies <exam_dir>/<task>/<kind>/* into <bank_dir>/<task>/exams/<kind>/ for every task in
<bank_dir>. Before modifying <bank_dir>:
  1. Verifies <exam_dir>/MANIFEST.json sha256 entries if MANIFEST.json is present.
  2. Refuses (exit 2) if any bank task is missing from <exam_dir> or lacks any requested kind.

Optionally refreshes <bank_dir>/MANIFEST.json's files_sha256 and records import metadata.

Usage:
    python3 ops/redo/banks/import_exams.py <exam_dir> <bank_dir>
    python3 ops/redo/banks/import_exams.py <exam_dir> <bank_dir> --kinds XM,XMV,PB,EX
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time
from typing import Any

DEFAULT_KINDS: tuple[str, ...] = ("XM", "XMV", "PB", "EX")


class ImportErrorRefused(Exception):
    """Raised when pre-import validation refuses the exam directory."""


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _bank_tasks(bank_dir: pathlib.Path) -> list[str]:
    mf = bank_dir / "MANIFEST.json"
    if mf.is_file():
        m = json.loads(mf.read_text(encoding="utf-8"))
        order = m.get("task_order")
        if isinstance(order, list) and order:
            return [str(t) for t in order]
        tasks = m.get("tasks")
        if isinstance(tasks, dict) and tasks:
            return sorted(str(t) for t in tasks)
    return sorted(p.name for p in bank_dir.iterdir() if p.is_dir() and (p / "workspace").is_dir())


def verify_exam_manifest(exam_dir: pathlib.Path) -> dict[str, Any] | None:
    """Verify <exam_dir>/MANIFEST.json sha256 hashes if present. Raises ImportErrorRefused on mismatch."""
    mf = exam_dir / "MANIFEST.json"
    if not mf.is_file():
        return None
    try:
        manifest = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ImportErrorRefused(f"invalid MANIFEST.json in {exam_dir}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ImportErrorRefused(f"MANIFEST.json in {exam_dir} must be a JSON object")

    # Support standard repo format (`files_sha256: {rel: hex}`) as well as `sha256` / `files` mappings or lists.
    entries: dict[str, str] = {}
    if isinstance(manifest.get("files_sha256"), dict):
        entries = {str(k): str(v) for k, v in manifest["files_sha256"].items()}
    elif isinstance(manifest.get("sha256"), dict):
        entries = {str(k): str(v) for k, v in manifest["sha256"].items()}
    elif isinstance(manifest.get("files"), dict):
        entries = {str(k): str(v) for k, v in manifest["files"].items()}
    elif isinstance(manifest.get("files"), list):
        for item in manifest["files"]:
            if isinstance(item, dict) and "path" in item and "sha256" in item:
                entries[str(item["path"])] = str(item["sha256"])

    mismatches: list[str] = []
    missing_files: list[str] = []
    exam_resolved = exam_dir.resolve()
    for rel, expected in sorted(entries.items()):
        fp = (exam_dir / rel).resolve()
        try:
            fp.relative_to(exam_resolved)
        except ValueError as exc:
            raise ImportErrorRefused(f"MANIFEST path escapes exam_dir: {rel!r}") from exc
        if not fp.is_file():
            missing_files.append(rel)
            continue
        actual = sha256_file(fp)
        if actual.lower() != expected.lower():
            mismatches.append(f"{rel} (expected {expected[:12]}, got {actual[:12]})")

    if missing_files or mismatches:
        parts: list[str] = []
        if missing_files:
            parts.append(f"{len(missing_files)} missing file(s): {missing_files[:5]}")
        if mismatches:
            parts.append(f"{len(mismatches)} sha256 mismatch(es): {mismatches[:5]}")
        raise ImportErrorRefused(f"MANIFEST sha256 verification failed in {exam_dir}: {'; '.join(parts)}")

    return {
        "manifest_path": str(mf),
        "manifest_sha256": sha256_file(mf),
        "verified_files": len(entries),
    }


def _copy_contents(src_dir: pathlib.Path, dst_dir: pathlib.Path) -> int:
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in sorted(src_dir.iterdir()):
        if item.name in ("__pycache__", ".pytest_cache", ".mypy_cache"):
            continue
        target = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache"))
            copied += sum(1 for p in target.rglob("*") if p.is_file())
        elif item.is_file():
            shutil.copy2(item, target)
            copied += 1
    return copied


def import_exams(
    exam_dir: pathlib.Path,
    bank_dir: pathlib.Path,
    *,
    kinds: tuple[str, ...] = DEFAULT_KINDS,
) -> dict[str, Any]:
    """Validate and copy <exam_dir>/<task>/<kind>/* into <bank_dir>/<task>/exams/<kind>/."""
    if not exam_dir.is_dir():
        raise ImportErrorRefused(f"exam_dir does not exist: {exam_dir}")
    if not bank_dir.is_dir():
        raise ImportErrorRefused(f"bank_dir does not exist: {bank_dir}")
    if not kinds:
        raise ImportErrorRefused("kinds must be non-empty")

    tasks = _bank_tasks(bank_dir)
    if not tasks:
        raise ImportErrorRefused(f"no tasks found in bank_dir: {bank_dir}")

    # 1. Verify MANIFEST sha256 if present.
    manifest_check = verify_exam_manifest(exam_dir)

    # 2. Pre-flight: check every bank task and requested kind BEFORE modifying bank_dir.
    missing_tasks: list[str] = []
    missing_kinds: list[str] = []
    empty_kinds: list[str] = []
    for task in tasks:
        t_exam = exam_dir / task
        if not t_exam.is_dir():
            missing_tasks.append(task)
            continue
        for kind in kinds:
            kdir = t_exam / kind
            if not kdir.is_dir():
                missing_kinds.append(f"{task}/{kind}")
            elif not any(p.is_file() for p in kdir.rglob("*") if "__pycache__" not in p.parts):
                empty_kinds.append(f"{task}/{kind}")

    if missing_tasks or missing_kinds or empty_kinds:
        problems: list[str] = []
        if missing_tasks:
            problems.append(f"{len(missing_tasks)} missing task(s): {missing_tasks[:8]}")
        if missing_kinds:
            problems.append(f"{len(missing_kinds)} missing kind dir(s): {missing_kinds[:8]}")
        if empty_kinds:
            problems.append(f"{len(empty_kinds)} empty kind dir(s): {empty_kinds[:8]}")
        raise ImportErrorRefused("refusing exam import — " + "; ".join(problems))

    # 3. Copy <exam_dir>/<task>/<kind>/* -> <bank_dir>/<task>/exams/<kind>/
    counts: dict[str, int] = {k: 0 for k in kinds}
    for task in tasks:
        for kind in kinds:
            src_k = exam_dir / task / kind
            dst_k = bank_dir / task / "exams" / kind
            counts[kind] += _copy_contents(src_k, dst_k)

    # 4. Update bank MANIFEST.json if present.
    mf = bank_dir / "MANIFEST.json"
    if mf.is_file():
        m = json.loads(mf.read_text(encoding="utf-8"))
        files_sha: dict[str, str] = {}
        for root_d, dirs, files in os.walk(bank_dir):
            dirs.sort()
            for fname in sorted(files):
                fp = pathlib.Path(root_d) / fname
                rel = fp.relative_to(bank_dir).as_posix()
                if rel == "MANIFEST.json":
                    continue
                files_sha[rel] = sha256_file(fp)
        m["files_sha256"] = files_sha
        history = m.get("imported_exams")
        if not isinstance(history, list):
            history = []
        history.append({
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "exam_dir": str(exam_dir.resolve()),
            "kinds": list(kinds),
            "files_copied_by_kind": counts,
            "exam_manifest": manifest_check,
        })
        m["imported_exams"] = history
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "bank_dir": str(bank_dir.resolve()),
        "exam_dir": str(exam_dir.resolve()),
        "n_tasks": len(tasks),
        "kinds": list(kinds),
        "files_copied_by_kind": counts,
        "exam_manifest": manifest_check,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import frozen external exams into an exam bank.")
    ap.add_argument("exam_dir", help="Frozen exam directory (<exam_dir>/<task>/<kind>/*)")
    ap.add_argument("bank_dir", help="Target exam bank directory (e.g. ~/dev/ops/ref/bm_tasks/exam37)")
    ap.add_argument(
        "--kinds",
        default=",".join(DEFAULT_KINDS),
        help=f"Comma-separated exam kinds to import (default: {','.join(DEFAULT_KINDS)})",
    )
    a = ap.parse_args(argv)
    kinds = tuple(k.strip() for k in a.kinds.split(",") if k.strip())
    exam_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(a.exam_dir)))
    bank_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(a.bank_dir)))
    try:
        res = import_exams(exam_dir, bank_dir, kinds=kinds)
    except ImportErrorRefused as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
