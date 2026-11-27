#!/usr/bin/env python3
"""Build the 37-task external-exam bank (exam37) from ctl_cal18 + ctl_hard19.

Layout per task under <out>/<task>/:
  workspace/            -- goal.md, contract.md (test-file instructions stripped), helper files;
                           NO test files (*_test.py / test_*.py) so the worker sees no tests.
  gate_visible/         -- the acceptance (visible) half <name>_test.py from ctl_cal18 / ctl_hard19.
  hidden/               -- the independent grading half <name>_test.py (unchanged).
  scorer.py             -- staged_scorer for hidden/ (unchanged).
  instruction.txt       -- task prompt (unchanged).
  exams/{XM,XMV,PB,EX}/ -- placeholder directories to be populated by import_exams.py.

Verifies for every task:
  - workspace/ contains zero test files;
  - empty workspace fails both gate_visible and hidden (scorer.py);
  - reference solution (when ref-src is available) passes both gate_visible and hidden.

Usage:
    python3 ops/redo/banks/build_exam37.py
    python3 ops/redo/banks/build_exam37.py --out ~/dev/ops/ref/bm_tasks/exam37
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

DEFAULT_CAL18 = pathlib.Path("~/dev/ops/ref/bm_tasks/ctl_cal18")
DEFAULT_HARD19 = pathlib.Path("~/dev/ops/ref/bm_tasks/ctl_hard19")
DEFAULT_REF_SRC = pathlib.Path("~/dev/ops/ref/src/exercism-python/exercises/practice")
DEFAULT_OUT = pathlib.Path("~/dev/ops/ref/bm_tasks/exam37")

EXAM_KINDS: tuple[str, ...] = ("XM", "XMV", "PB", "EX")

# Tail bullet in Exercism contract.md pointing the worker at *_test.py (removed in no-tests scenario).
_CONTRACT_TESTS_TAIL_RE = re.compile(
    r"\n- The tests for this task are in `[^`]+`\. The tests are correct; don't change them\. Run them\n"
    r"  with:\n\n      python3 -m pytest -q [^\n]+\n\n  or, without pytest:\n\n      python3 -m unittest [^\n]+\n?$"
)


def expand(p: pathlib.Path | str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(str(p)))).resolve()


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _is_test_filename(name: str) -> bool:
    return name.endswith("_test.py") or (name.startswith("test_") and name.endswith(".py"))


def _strip_contract_test_hint(text: str) -> tuple[str, bool]:
    new_text, n = _CONTRACT_TESTS_TAIL_RE.subn("\n", text)
    if n:
        return new_text.rstrip() + "\n", True
    return text, False


def _solution_filename(task_ws: pathlib.Path, task_id: str) -> str:
    cm = task_ws / "contract.md"
    if cm.is_file():
        m = re.search(r"Write your solution to `([^`]+\.py)`", cm.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return f"{task_id.removeprefix('ex_')}.py"


def _run_gate_visible(ws_dir: pathlib.Path, gate_dir: pathlib.Path, timeout_s: float = 30.0) -> tuple[bool, int, int, str]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="exam37-gv-"))
    try:
        work = tmp / "w"
        shutil.copytree(ws_dir, work, symlinks=True)
        mods: list[str] = []
        for f in sorted(gate_dir.iterdir()):
            if f.is_file():
                shutil.copy2(f, work / f.name)
                if _is_test_filename(f.name):
                    mods.append(f.stem)
        if not mods:
            return False, 0, 0, "no_gate_tests"
        runner = (
            "import json, sys, unittest\n"
            "sys.path.insert(0, '.')\n"
            "total = bad = skipped = 0\n"
            "for mod in sys.argv[1:]:\n"
            "    try:\n"
            "        s = unittest.TestLoader().loadTestsFromName(mod)\n"
            "    except BaseException as e:\n"
            "        print('@@R@@' + json.dumps({'ok': False, 'p': 0, 't': 0, 'err': repr(e)})); sys.exit(0)\n"
            "    r = unittest.TestResult(); s.run(r)\n"
            "    total += r.testsRun\n"
            "    bad += len(r.failures) + len(r.errors) + len(r.unexpectedSuccesses)\n"
            "    skipped += len(r.skipped)\n"
            "p = total - bad - skipped\n"
            "ok = total > 0 and bad == 0 and skipped == 0\n"
            "print('@@R@@' + json.dumps({'ok': ok, 'p': p, 't': total, 'err': None}))\n"
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
            [sys.executable, "-B", "-c", runner, *mods],
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


def _load_bank_task_order(bank_dir: pathlib.Path) -> list[str]:
    mf = bank_dir / "MANIFEST.json"
    if mf.is_file():
        m = json.loads(mf.read_text(encoding="utf-8"))
        if isinstance(m.get("task_order"), list) and m["task_order"]:
            return [str(t) for t in m["task_order"]]
    return sorted(p.name for p in bank_dir.iterdir() if p.is_dir() and (p / "workspace").is_dir())


def build_exam37(
    *,
    cal18_dir: pathlib.Path,
    hard19_dir: pathlib.Path,
    out_dir: pathlib.Path,
    ref_src_dir: pathlib.Path | None = None,
    bank_id: str = "exam37",
) -> dict[str, Any]:
    sources: list[tuple[str, pathlib.Path, str]] = []
    seen: set[str] = set()
    for label, sdir in (("ctl_cal18", cal18_dir), ("ctl_hard19", hard19_dir)):
        if not sdir.is_dir():
            raise SystemExit(f"missing source bank: {sdir}")
        for task_id in _load_bank_task_order(sdir):
            if task_id in seen:
                raise SystemExit(f"duplicate task across source banks: {task_id}")
            seen.add(task_id)
            sources.append((task_id, sdir / task_id, label))

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    task_records: dict[str, Any] = {}
    task_order: list[str] = []

    for task_id, src_task, src_label in sources:
        src_ws = src_task / "workspace"
        src_hid = src_task / "hidden"
        src_scorer = src_task / "scorer.py"
        if not (src_ws.is_dir() and src_hid.is_dir() and src_scorer.is_file()):
            raise SystemExit(f"{task_id}: incomplete source task in {src_task}")

        dst_task = out_dir / task_id
        dst_ws = dst_task / "workspace"
        dst_gv = dst_task / "gate_visible"
        dst_hid = dst_task / "hidden"
        dst_ws.mkdir(parents=True)
        dst_gv.mkdir(parents=True)
        dst_hid.mkdir(parents=True)
        for kind in EXAM_KINDS:
            (dst_task / "exams" / kind).mkdir(parents=True, exist_ok=True)

        # Copy instruction.txt, scorer.py, hidden/
        if (src_task / "instruction.txt").is_file():
            shutil.copy2(src_task / "instruction.txt", dst_task / "instruction.txt")
        shutil.copy2(src_scorer, dst_task / "scorer.py")
        os.chmod(dst_task / "scorer.py", 0o755)
        for f in sorted(src_hid.iterdir()):
            if f.is_file():
                shutil.copy2(f, dst_hid / f.name)

        # Split workspace: test files move to gate_visible/, non-test files stay in workspace/.
        gate_tests: list[str] = []
        contract_stripped = False
        for f in sorted(src_ws.iterdir()):
            if not f.is_file():
                continue
            if _is_test_filename(f.name):
                shutil.copy2(f, dst_gv / f.name)
                gate_tests.append(f.name)
            elif f.name == "contract.md":
                cleaned, stripped = _strip_contract_test_hint(f.read_text(encoding="utf-8"))
                contract_stripped = stripped
                (dst_ws / f.name).write_text(cleaned, encoding="utf-8")
            else:
                shutil.copy2(f, dst_ws / f.name)

        if not gate_tests:
            raise SystemExit(f"{task_id}: no acceptance test file found in {src_ws}")

        # Verify workspace has NO test files.
        remaining_tests = [p.name for p in dst_ws.rglob("*.py") if _is_test_filename(p.name)]
        if remaining_tests:
            raise SystemExit(f"{task_id}: test files remained in workspace: {remaining_tests}")

        # Verify negative control: empty workspace fails both gate_visible and hidden.
        stub_gv_ok, _, _, _ = _run_gate_visible(dst_ws, dst_gv)
        stub_hid = _run_scorer(dst_task, dst_ws)
        if stub_gv_ok or stub_hid.get("pass"):
            raise SystemExit(f"{task_id}: empty workspace unexpectedly passed (gv={stub_gv_ok}, hid={stub_hid})")

        # Verify positive control: reference solution (if available) passes both gate_visible and hidden.
        sol_name = _solution_filename(dst_ws, task_id)
        slug = task_id.removeprefix("ex_").replace("_", "-")
        example_file = (ref_src_dir / slug / ".meta" / "example.py") if ref_src_dir is not None else None
        ref_ver: dict[str, Any]
        if example_file is not None and example_file.is_file():
            tmp_ref = pathlib.Path(tempfile.mkdtemp(prefix="exam37-ref-"))
            try:
                shutil.copytree(dst_ws, tmp_ref / "w")
                shutil.copy2(example_file, tmp_ref / "w" / sol_name)
                r_gv_ok, r_gv_p, r_gv_t, r_gv_err = _run_gate_visible(tmp_ref / "w", dst_gv)
                r_hid = _run_scorer(dst_task, tmp_ref / "w")
                if not r_gv_ok or r_gv_t <= 0:
                    raise SystemExit(
                        f"{task_id}: reference failed gate_visible: ok={r_gv_ok} {r_gv_p}/{r_gv_t} err={r_gv_err}"
                    )
                if not r_hid.get("pass") or not r_hid.get("tests_total"):
                    raise SystemExit(f"{task_id}: reference failed hidden: {r_hid}")
                ref_ver = {
                    "status": "passed",
                    "example_sha256": sha256_file(example_file),
                    "gate_visible_passed": r_gv_p,
                    "gate_visible_total": r_gv_t,
                    "hidden_passed": r_hid["tests_passed"],
                    "hidden_total": r_hid["tests_total"],
                }
            finally:
                shutil.rmtree(tmp_ref, ignore_errors=True)
        else:
            ref_ver = {"status": "skipped"}

        task_order.append(task_id)
        task_records[task_id] = {
            "source_bank": src_label,
            "solution_file": sol_name,
            "gate_visible_files": sorted(gate_tests),
            "hidden_files": sorted(p.name for p in dst_hid.iterdir() if p.is_file()),
            "contract_test_hint_stripped": contract_stripped,
            "verification": {
                "workspace_has_no_tests": True,
                "stub_fails_both": True,
                "reference": ref_ver,
            },
        }
        print(
            f"OK  {task_id:<26s} src={src_label:<10s} gv={gate_tests[0]:<30s} "
            f"ref={ref_ver['status']}  stub=fail/fail"
        )

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
        "schema": "vacant.redo.exam_bank/1",
        "bank_id": bank_id,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sources": {
            "ctl_cal18": str(cal18_dir),
            "ctl_hard19": str(hard19_dir),
        },
        "exam_kinds": list(EXAM_KINDS),
        "n_tasks": len(task_order),
        "task_order": task_order,
        "tasks": task_records,
        "files_sha256": files_sha,
    }
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {bank_id} ({len(task_order)} tasks, {len(files_sha)} files) -> {out_dir}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the 37-task external-exam bank (exam37).")
    ap.add_argument("--cal18", default=str(DEFAULT_CAL18))
    ap.add_argument("--hard19", default=str(DEFAULT_HARD19))
    ap.add_argument("--ref-src", default=str(DEFAULT_REF_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--bank-id", default="exam37")
    a = ap.parse_args(argv)

    ref_src = expand(a.ref_src)
    if not ref_src.is_dir():
        ref_src = None

    build_exam37(
        cal18_dir=expand(a.cal18),
        hard19_dir=expand(a.hard19),
        out_dir=expand(a.out),
        ref_src_dir=ref_src,
        bank_id=a.bank_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
