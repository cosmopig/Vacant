#!/usr/bin/env python3
"""Build split-test banks (ctl16 and ctl_smoke4) for the evidence-controller experiment.

Splits each task's `*_test.py` test methods into two deterministic halves with fixed
seed 20261127:
  - acceptance half -> <out>/<task>/workspace/<name>_test.py (visible to worker & controller)
  - grading half    -> <out>/<task>/hidden/<name>_test.py + <out>/<task>/scorer.py
                       (compatible with ops/redo/redo.py's staged_scorer)

Outputs <out>/MANIFEST.json with per-file sha256 hashes, split lists, and verification
results (reference solution passes both halves when available; stub fails both).

Usage:
    python3 ops/redo/banks/build_ctl16.py
    python3 ops/redo/banks/build_ctl16.py --smoke4
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

SEED = 20261127
DEFAULT_POOL = pathlib.Path("~/dev/ops/ref/bm_tasks/exercism_py_pool")
DEFAULT_REF_SRC = pathlib.Path("~/dev/ops/ref/src/exercism-python/exercises/practice")
DEFAULT_OUT_CTL16 = pathlib.Path("~/dev/ops/ref/bm_tasks/ctl16")
DEFAULT_OUT_SMOKE4 = pathlib.Path("~/dev/ops/ref/bm_tasks/ctl_smoke4")

# Frozen 16 tasks from decisions/DECISION_20261127_EVIDENCE_CONTROLLER.md
CTL16_TASKS: list[str] = [
    "ex_kindergarten_garden",
    "ex_ocr_numbers",
    "ex_circular_buffer",
    "ex_high_scores",
    "ex_simple_cipher",
    "ex_binary",
    "ex_octal",
    "ex_yacht",
    "ex_luhn",
    "ex_sublist",
    "ex_say",
    "ex_dnd_character",
    "ex_twelve_days",
    "ex_atbash_cipher",
    "ex_queen_attack",
    "ex_prime_factors",
]

# 4 unused pool tasks NOT in CTL16 (and not in unused/hard/polyglot), all >= 8 tests
SMOKE4_TASKS: list[str] = [
    "ex_matrix",
    "ex_point_mutations",
    "ex_series",
    "ex_rotational_cipher",
]

SCORER_TEMPLATE = r'''#!/usr/bin/env python3
"""Independent hidden-half scorer compatible with ops/redo/redo.py staged_scorer."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache"}

_RUNNER = r"""
import json, sys, traceback, unittest
sys.path.insert(0, ".")
out = {"run": 0, "failures": 0, "errors": 0, "skipped": 0, "unexpected_successes": 0, "load_error": None}
for mod in sys.argv[1:]:
    try:
        suite = unittest.TestLoader().loadTestsFromName(mod)
    except BaseException:
        out["load_error"] = traceback.format_exc(limit=3)[-600:]
        break
    res = unittest.TestResult()
    suite.run(res)
    out["run"] += res.testsRun
    out["failures"] += len(res.failures)
    out["errors"] += len(res.errors)
    out["skipped"] += len(res.skipped)
    out["unexpected_successes"] += len(res.unexpectedSuccesses)
sys.stdout.flush()
print("\n@@CTL_SCORE@@" + json.dumps(out))
"""


def main() -> int:
    if len(sys.argv) < 3:
        print(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 0, "status": "bad_args"}))
        return 1
    hidden = pathlib.Path(sys.argv[1]).resolve()
    ws = pathlib.Path(sys.argv[2]).resolve()
    timeout_s = float(os.environ.get("SUITE_TIMEOUT_S", "60"))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ctl-score-"))
    try:
        work = tmp / "w"
        shutil.copytree(ws, work, symlinks=True, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        hidden_tests: list[str] = []
        for src in sorted(hidden.iterdir()):
            if src.is_file():
                shutil.copy2(src, work / src.name)
                if src.name.endswith("_test.py") or src.name.startswith("test_"):
                    hidden_tests.append(src.stem)
        if not hidden_tests:
            print(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 0, "status": "no_hidden_tests"}))
            return 0
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-c", _RUNNER, *hidden_tests],
                cwd=str(work),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            out = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            print(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 0, "status": "timeout"}))
            return 0
        if "@@CTL_SCORE@@" not in out:
            print(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 0, "status": "runner_no_output"}))
            return 0
        r = json.loads(out.rsplit("@@CTL_SCORE@@", 1)[1].strip().splitlines()[0])
        if r.get("load_error"):
            print(json.dumps({"pass": False, "tests_passed": 0, "tests_total": 0, "status": "load_error"}))
            return 0
        total = int(r["run"])
        bad = int(r["failures"]) + int(r["errors"]) + int(r["unexpected_successes"])
        skipped = int(r["skipped"])
        passed = max(0, total - bad - skipped)
        ok = total > 0 and bad == 0 and skipped == 0
        print(json.dumps({"pass": ok, "tests_passed": passed, "tests_total": total, "status": "ok"}))
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def expand(p: pathlib.Path | str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(str(p)))).resolve()


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _node_line_range(node: ast.AST) -> tuple[int, int]:
    start = node.lineno
    decs = getattr(node, "decorator_list", None) or []
    if decs:
        start = min(start, *(d.lineno for d in decs))
    end = getattr(node, "end_lineno", start)
    assert end is not None
    return start, end


# Invariant precondition tests that must stay in BOTH halves so a None-stub cannot pass either half.
SHARED_INVARIANT_TESTS: frozenset[str] = frozenset({"test_unique_return_values"})


def split_test_source(
    src: str, *, task_id: str, seed: int = SEED
) -> tuple[str, str, list[str], list[str], list[str]]:
    """Split a unittest file's test_* methods into (acceptance_src, hidden_src, acc_names, hid_names, shared_names).

    Preserves all imports, module-level code, classes, setUp/tearDown, non-test helper methods,
    and any SHARED_INVARIANT_TESTS (e.g. sublist's test_unique_return_values) in both halves.
    When multiple test classes exist (e.g. simple_cipher), splits each class's test_* methods
    independently so neither half leaves an empty class and both cover every class.
    """
    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)

    # Collect groups: (group_name, [(qual_name, start_line, end_line), ...])
    groups: list[tuple[str, list[tuple[str, int, int]]]] = []
    top_tests: list[tuple[str, int, int]] = []
    shared_names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods: list[tuple[str, int, int]] = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                    if item.name in SHARED_INVARIANT_TESTS:
                        shared_names.append(f"{node.name}.{item.name}")
                        continue
                    s, e = _node_line_range(item)
                    methods.append((f"{node.name}.{item.name}", s, e))
            if methods:
                groups.append((node.name, methods))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            if node.name in SHARED_INVARIANT_TESTS:
                shared_names.append(node.name)
                continue
            s, e = _node_line_range(node)
            top_tests.append((node.name, s, e))
    if top_tests:
        groups.append(("__module__", top_tests))

    if not groups:
        raise ValueError(f"{task_id}: no test_* methods found")

    acc_names: list[str] = []
    hid_names: list[str] = []
    drop_for_acc: set[int] = set()
    drop_for_hid: set[int] = set()

    for gname, items in groups:
        if len(items) < 2:
            raise ValueError(f"{task_id}: test group {gname} has only {len(items)} test(s), cannot split")
        rng = random.Random(f"{seed}:{task_id}:{gname}")
        idxs = list(range(len(items)))
        rng.shuffle(idxs)
        mid = len(items) // 2
        acc_idx = set(idxs[:mid])
        hid_idx = set(idxs[mid:])
        for i, (qname, s, e) in enumerate(items):
            if i in acc_idx:
                acc_names.append(qname)
                drop_for_hid.update(range(s, e + 1))
            else:
                assert i in hid_idx
                hid_names.append(qname)
                drop_for_acc.update(range(s, e + 1))

    acc_src = "".join(ln for lineno, ln in enumerate(lines, start=1) if lineno not in drop_for_acc)
    hid_src = "".join(ln for lineno, ln in enumerate(lines, start=1) if lineno not in drop_for_hid)

    # Sanity check: both halves parse cleanly and contain the exact expected test counts.
    ast.parse(acc_src)
    ast.parse(hid_src)
    assert set(acc_names).isdisjoint(set(hid_names))
    return acc_src, hid_src, acc_names, hid_names, shared_names


def _solution_filename(task_ws: pathlib.Path, task_id: str) -> str:
    cm = task_ws / "contract.md"
    if cm.is_file():
        m = re.search(r"Write your solution to `([^`]+\.py)`", cm.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return f"{task_id.removeprefix('ex_')}.py"


def _run_acceptance(ws_dir: pathlib.Path, test_name: str, timeout_s: float = 30.0) -> tuple[bool, int, int, str]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="ctl-acc-val-"))
    try:
        work = tmp / "w"
        shutil.copytree(ws_dir, work, symlinks=True)
        runner = (
            "import json, sys, unittest\n"
            "sys.path.insert(0, '.')\n"
            "try:\n"
            "    s = unittest.TestLoader().loadTestsFromName(sys.argv[1])\n"
            "except BaseException as e:\n"
            "    print('@@R@@' + json.dumps({'ok': False, 'p': 0, 't': 0, 'err': repr(e)})); sys.exit(0)\n"
            "r = unittest.TestResult(); s.run(r)\n"
            "bad = len(r.failures) + len(r.errors) + len(r.unexpectedSuccesses)\n"
            "p = r.testsRun - bad - len(r.skipped)\n"
            "ok = r.testsRun > 0 and bad == 0 and len(r.skipped) == 0\n"
            "print('@@R@@' + json.dumps({'ok': ok, 'p': p, 't': r.testsRun, 'err': None}))\n"
        )
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
        proc = subprocess.run(
            [sys.executable, "-B", "-c", runner, pathlib.Path(test_name).stem],
            cwd=str(work),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if "@@R@@" not in out:
            return False, 0, 0, f"no_output:{out[-200:]}"
        d = json.loads(out.rsplit("@@R@@", 1)[1].strip().splitlines()[0])
        return bool(d["ok"]), int(d["p"]), int(d["t"]), str(d.get("err") or "ok")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run_scorer(task_out: pathlib.Path, ws_dir: pathlib.Path, timeout_s: float = 30.0) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(task_out / "scorer.py"), str(task_out / "hidden"), str(ws_dir)],
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    out = (proc.stdout or "").strip()
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {"pass": False, "tests_passed": 0, "tests_total": 0, "status": f"bad_scorer_output:{out[-200:]}"}


def build_bank(
    tasks: list[str],
    *,
    pool_dir: pathlib.Path,
    ref_src_dir: pathlib.Path | None,
    out_dir: pathlib.Path,
    bank_id: str,
    seed: int = SEED,
) -> dict[str, Any]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    task_records: dict[str, Any] = {}
    for task_id in tasks:
        src_task = pool_dir / task_id
        src_ws = src_task / "workspace"
        if not src_ws.is_dir():
            raise SystemExit(f"missing task in pool: {src_ws}")

        test_files = sorted(src_ws.glob("*_test.py"))
        if len(test_files) != 1:
            raise SystemExit(f"{task_id}: expected 1 *_test.py, found {[p.name for p in test_files]}")
        test_path = test_files[0]
        test_name = test_path.name
        sol_name = _solution_filename(src_ws, task_id)

        acc_src, hid_src, acc_names, hid_names, shared_names = split_test_source(
            test_path.read_text(encoding="utf-8"), task_id=task_id, seed=seed
        )

        dst_task = out_dir / task_id
        dst_ws = dst_task / "workspace"
        dst_hid = dst_task / "hidden"
        dst_ws.mkdir(parents=True)
        dst_hid.mkdir(parents=True)

        # Copy instruction.txt
        if (src_task / "instruction.txt").is_file():
            shutil.copy2(src_task / "instruction.txt", dst_task / "instruction.txt")

        # Copy workspace files, replacing *_test.py with acceptance half
        for f in sorted(src_ws.iterdir()):
            if not f.is_file():
                continue
            if f.name == test_name:
                (dst_ws / test_name).write_text(acc_src, encoding="utf-8")
            else:
                shutil.copy2(f, dst_ws / f.name)
                if f.suffix == ".py":
                    # Any extra helper .py is also copied into hidden/
                    shutil.copy2(f, dst_hid / f.name)

        # Write hidden grading half and scorer.py
        (dst_hid / test_name).write_text(hid_src, encoding="utf-8")
        scorer_path = dst_task / "scorer.py"
        scorer_path.write_text(SCORER_TEMPLATE, encoding="utf-8")
        os.chmod(scorer_path, 0o755)

        # Verification 1: Stub (original empty workspace, plus stub file if available) must FAIL both halves.
        stub_acc_ok, stub_acc_p, stub_acc_t, _ = _run_acceptance(dst_ws, test_name)
        stub_hid = _run_scorer(dst_task, dst_ws)
        if stub_acc_ok or stub_hid.get("pass"):
            raise SystemExit(f"{task_id}: empty workspace unexpectedly passed (acc={stub_acc_ok}, hid={stub_hid})")

        slug = task_id.removeprefix("ex_").replace("_", "-")
        stub_file = (ref_src_dir / slug / sol_name) if ref_src_dir is not None else None
        if stub_file is not None and stub_file.is_file():
            tmp_stub = pathlib.Path(tempfile.mkdtemp(prefix="ctl-stub-"))
            try:
                shutil.copytree(dst_ws, tmp_stub / "w")
                shutil.copy2(stub_file, tmp_stub / "w" / sol_name)
                s_acc_ok, _, _, _ = _run_acceptance(tmp_stub / "w", test_name)
                s_hid = _run_scorer(dst_task, tmp_stub / "w")
                if s_acc_ok or s_hid.get("pass"):
                    raise SystemExit(f"{task_id}: original stub unexpectedly passed (acc={s_acc_ok}, hid={s_hid})")
            finally:
                shutil.rmtree(tmp_stub, ignore_errors=True)

        # Verification 2: Reference/example solution (if available) must PASS both halves.
        example_file = (ref_src_dir / slug / ".meta" / "example.py") if ref_src_dir is not None else None
        ref_ver: dict[str, Any]
        if example_file is not None and example_file.is_file():
            tmp_ref = pathlib.Path(tempfile.mkdtemp(prefix="ctl-ref-"))
            try:
                shutil.copytree(dst_ws, tmp_ref / "w")
                shutil.copy2(example_file, tmp_ref / "w" / sol_name)
                r_acc_ok, r_acc_p, r_acc_t, r_acc_err = _run_acceptance(tmp_ref / "w", test_name)
                r_hid = _run_scorer(dst_task, tmp_ref / "w")
                expected_acc = len(acc_names) + len(shared_names)
                expected_hid = len(hid_names) + len(shared_names)
                if not r_acc_ok or r_acc_t != expected_acc:
                    raise SystemExit(
                        f"{task_id}: reference failed acceptance half: ok={r_acc_ok} {r_acc_p}/{r_acc_t} "
                        f"(expected {expected_acc}) err={r_acc_err}"
                    )
                if not r_hid.get("pass") or r_hid.get("tests_total") != expected_hid:
                    raise SystemExit(
                        f"{task_id}: reference failed hidden half: {r_hid} (expected {expected_hid})"
                    )
                ref_ver = {
                    "status": "passed",
                    "example_sha256": sha256_file(example_file),
                    "acceptance_passed": r_acc_p,
                    "acceptance_total": r_acc_t,
                    "hidden_passed": r_hid["tests_passed"],
                    "hidden_total": r_hid["tests_total"],
                }
            finally:
                shutil.rmtree(tmp_ref, ignore_errors=True)
        else:
            ref_ver = {"status": "skipped"}

        task_records[task_id] = {
            "test_file": test_name,
            "solution_file": sol_name,
            "total_tests": len(acc_names) + len(hid_names) + len(shared_names),
            "acceptance_tests": acc_names,
            "hidden_tests": hid_names,
            "shared_invariant_tests": shared_names,
            "verification": {
                "stub_fails_both": True,
                "reference": ref_ver,
            },
        }
        sh_note = f" (+{len(shared_names)} inv)" if shared_names else ""
        print(
            f"OK  {task_id:<26s} split={len(acc_names):2d} acc / {len(hid_names):2d} hid{sh_note}  "
            f"ref={ref_ver['status']}  stub=fail/fail"
        )

    # Collect per-file sha256 across the entire output directory.
    files_sha: dict[str, str] = {}
    for root_d, dirs, files in os.walk(out_dir):
        dirs.sort()
        for fname in sorted(files):
            fp = pathlib.Path(root_d) / fname
            rel = fp.relative_to(out_dir).as_posix()
            if rel == "MANIFEST.json":
                continue
            files_sha[rel] = sha256_file(fp)

    manifest = {
        "schema": "vacant.redo.ctl_bank/1",
        "bank_id": bank_id,
        "seed": seed,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_pool": str(pool_dir),
        "n_tasks": len(tasks),
        "task_order": list(tasks),
        "tasks": task_records,
        "files_sha256": files_sha,
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {bank_id} ({len(tasks)} tasks, {len(files_sha)} files) -> {out_dir}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build split-test banks ctl16 / ctl_smoke4.")
    ap.add_argument("--pool", default=str(DEFAULT_POOL))
    ap.add_argument("--ref-src", default=str(DEFAULT_REF_SRC))
    ap.add_argument("--out", default=None)
    ap.add_argument("--bank-id", default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--smoke4", action="store_true", help="Build ctl_smoke4 instead of ctl16.")
    ap.add_argument("--tasks", nargs="+", help="Explicit task directory names (e.g. ex_matrix ...).")
    a = ap.parse_args(argv)

    if a.tasks:
        tasks = list(a.tasks)
        bank_id = a.bank_id or "custom_ctl"
        out_dir = expand(a.out or (DEFAULT_OUT_SMOKE4 if a.smoke4 else DEFAULT_OUT_CTL16))
    elif a.smoke4:
        tasks = list(SMOKE4_TASKS)
        bank_id = a.bank_id or "ctl_smoke4"
        out_dir = expand(a.out or DEFAULT_OUT_SMOKE4)
    else:
        tasks = list(CTL16_TASKS)
        bank_id = a.bank_id or "ctl16"
        out_dir = expand(a.out or DEFAULT_OUT_CTL16)

    ref_src = expand(a.ref_src)
    if not ref_src.is_dir():
        ref_src = None

    build_bank(
        tasks,
        pool_dir=expand(a.pool),
        ref_src_dir=ref_src,
        out_dir=out_dir,
        bank_id=bank_id,
        seed=a.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
