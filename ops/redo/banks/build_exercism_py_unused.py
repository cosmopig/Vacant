#!/usr/bin/env python3
"""Build and verify the exercism_py_unused task bank for ops/redo/redo.py.

Usage:
    python3 ops/redo/banks/build_exercism_py_unused.py
    python3 ops/redo/banks/build_exercism_py_unused.py --check
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

REPO_URL = "https://github.com/exercism/python"
DEFAULT_SRC = pathlib.Path("~/dev/ops/ref/src/exercism-python")
DEFAULT_POLYGLOT = pathlib.Path("~/dev/ops/ref/bm_tasks/polyglot_py")
DEFAULT_OUT = pathlib.Path("~/dev/ops/ref/bm_tasks/exercism_py_unused")
DEFAULT_MANIFEST = pathlib.Path(__file__).resolve().with_name("exercism_py_unused.json")

ORDER_SALT = ":redo-unused-2026-11-20"
TAKE_N = 40
INSTRUCTION_TEXT = (
    "Read goal.md and contract.md in this directory and do what they say. "
    "Use your tools to write the file.\n"
)

SELECTION_RULE_TEXT = (
    "1. Candidate = practice exercise under exercises/practice/* whose slug is NOT one of "
    "the 34 polyglot_py slugs (stripping 'pg_' from ~/dev/ops/ref/bm_tasks/polyglot_py dirs "
    "and mapping '_' to '-'), has .meta/example.py, a *_test.py test file, a stub file, and "
    ".docs/instructions.md. "
    "2. Exclude if the tests, helper modules, or example import anything outside the Python "
    "standard library or local exercise modules, or use network/filesystem APIs outside the "
    "exercise directory. "
    "3. Validation in isolated temp copies using system python3 (stdlib only): "
    "(a) .meta/example.py copied to the stub's module name passes `python3 -B -m unittest <test>` "
    "with >0 tests run; "
    "(b) the original stub fails at least one test under `python3 -B -m unittest <test>`. "
    "Exclude exercises failing (a) or (b) and log the reason. "
    "4. Order all remaining slugs ascending by sha256(slug + ':redo-unused-2026-11-20') "
    "(UTF-8 hex digest) and take the first 40."
)

NETWORK_MODULES = frozenset({
    "ftplib",
    "http",
    "imaplib",
    "nntplib",
    "poplib",
    "smtplib",
    "socket",
    "ssl",
    "telnetlib",
    "urllib",
    "xmlrpc",
})

EXTERNAL_IO_MODULES = frozenset({
    "glob",
    "pathlib",
    "shutil",
    "subprocess",
    "tempfile",
})


def expand(p: pathlib.Path | str) -> pathlib.Path:
    return pathlib.Path(os.path.expandvars(os.path.expanduser(str(p)))).resolve()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: pathlib.Path) -> str:
    return sha256_bytes(p.read_bytes())


def git_commit_sha(repo_dir: pathlib.Path) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return res.stdout.strip()


def load_polyglot_slugs(polyglot_dir: pathlib.Path) -> list[str]:
    if not polyglot_dir.is_dir():
        raise SystemExit(f"polyglot bank directory not found: {polyglot_dir}")
    slugs = sorted(
        p.name.removeprefix("pg_").replace("_", "-")
        for p in polyglot_dir.iterdir()
        if p.is_dir() and p.name.startswith("pg_")
    )
    if len(slugs) != 34:
        raise SystemExit(f"expected 34 polyglot slugs in {polyglot_dir}, found {len(slugs)}")
    return slugs


def identify_exercise_files(ex_dir: pathlib.Path) -> tuple[dict[str, Any] | None, str | None]:
    example = ex_dir / ".meta" / "example.py"
    instructions = ex_dir / ".docs" / "instructions.md"
    if not example.is_file():
        return None, "missing .meta/example.py"
    if not instructions.is_file():
        return None, "missing .docs/instructions.md"

    top_py = sorted(p.name for p in ex_dir.iterdir() if p.is_file() and p.suffix == ".py")
    cfg_path = ex_dir / ".meta" / "config.json"
    cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    files_cfg = cfg.get("files", {}) if isinstance(cfg, dict) else {}

    cfg_tests = [f for f in files_cfg.get("test", []) if (ex_dir / f).is_file()]
    cfg_sols = [f for f in files_cfg.get("solution", []) if (ex_dir / f).is_file()]

    tests = cfg_tests or [f for f in top_py if f.endswith("_test.py")]
    sols = cfg_sols or [f for f in top_py if not f.endswith("_test.py")]

    if len(tests) != 1:
        return None, f"expected 1 test file, found {tests}"
    if len(sols) != 1:
        return None, f"expected 1 stub file, found {sols}"

    test_name = tests[0]
    stub_name = sols[0]
    if not test_name.endswith("_test.py"):
        return None, f"test file does not match *_test.py: {test_name}"
    if not (ex_dir / test_name).is_file() or not (ex_dir / stub_name).is_file():
        return None, f"missing test or stub file: {test_name}, {stub_name}"

    helpers = sorted(f for f in top_py if f not in (test_name, stub_name))
    append_doc = ex_dir / ".docs" / "instructions.append.md"
    return {
        "example": example,
        "instructions": instructions,
        "instructions_append": append_doc if append_doc.is_file() else None,
        "stub_name": stub_name,
        "test_name": test_name,
        "helpers": helpers,
    }, None


def check_imports_and_io(ex_dir: pathlib.Path, info: dict[str, Any]) -> str | None:
    stdlib = sys.stdlib_module_names
    local_mods = {
        pathlib.Path(name).stem
        for name in [info["stub_name"], info["test_name"], *info["helpers"]]
    }
    to_check = [
        ex_dir / info["test_name"],
        *(ex_dir / h for h in info["helpers"]),
        info["example"],
    ]
    for fp in to_check:
        src = fp.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(fp))
        except SyntaxError as exc:
            return f"syntax_error in {fp.name}: {exc}"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in NETWORK_MODULES:
                        return f"network_import:{fp.name}:{alias.name}"
                    if top in EXTERNAL_IO_MODULES:
                        return f"external_io_import:{fp.name}:{alias.name}"
                    if top not in stdlib and top not in local_mods:
                        return f"non_stdlib_import:{fp.name}:{alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    if top in NETWORK_MODULES:
                        return f"network_import:{fp.name}:{node.module}"
                    if top in EXTERNAL_IO_MODULES:
                        return f"external_io_import:{fp.name}:{node.module}"
                    if top not in stdlib and top not in local_mods:
                        return f"non_stdlib_import:{fp.name}:{node.module}"
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    return f"builtin_open:{fp.name}:L{node.lineno}"
                if isinstance(node.func, ast.Attribute) and node.func.attr in (
                    "read_text",
                    "read_bytes",
                    "write_text",
                    "write_bytes",
                ):
                    return f"file_io_method:{fp.name}:{node.func.attr}:L{node.lineno}"
    return None


def _run_unittest_copy(
    solution_src: pathlib.Path,
    ex_dir: pathlib.Path,
    info: dict[str, Any],
    timeout_s: float,
) -> tuple[int | None, str]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="exbank-val-"))
    try:
        shutil.copy2(solution_src, tmp / info["stub_name"])
        shutil.copy2(ex_dir / info["test_name"], tmp / info["test_name"])
        for h in info["helpers"]:
            shutil.copy2(ex_dir / h, tmp / h)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
        try:
            res = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", info["test_name"]],
                cwd=str(tmp),
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            combined = (res.stdout or "") + (res.stderr or "")
            return res.returncode, combined
        except subprocess.TimeoutExpired:
            return None, f"timeout after {timeout_s}s"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def validate_exercise(
    slug: str,
    ex_dir: pathlib.Path,
    info: dict[str, Any],
    timeout_s: float,
) -> tuple[str, str | None, str | None]:
    """Return (slug, stage_failed_or_None, reason_or_None)."""
    rc_a, out_a = _run_unittest_copy(info["example"], ex_dir, info, timeout_s)
    if rc_a is None:
        return slug, "validation_a", f"example.py unittest {out_a}"
    if rc_a != 0:
        tail = " | ".join(out_a.strip().splitlines()[-4:])
        return slug, "validation_a", f"example.py unittest exited {rc_a}: {tail[:300]}"
    if "Ran 0 tests" in out_a:
        return slug, "validation_a", "example.py unittest ran 0 tests"

    rc_b, out_b = _run_unittest_copy(ex_dir / info["stub_name"], ex_dir, info, timeout_s)
    if rc_b is None:
        return slug, "validation_b", f"original stub unittest {out_b}"
    if rc_b == 0:
        tail = " | ".join(out_b.strip().splitlines()[-3:])
        return slug, "validation_b", f"original stub passed all tests (rc=0): {tail[:300]}"
    return slug, None, None


def render_goal_md(info: dict[str, Any]) -> str:
    inst = info["instructions"].read_text(encoding="utf-8")
    if not inst.endswith("\n"):
        inst += "\n"
    if info["instructions_append"] is not None:
        app = info["instructions_append"].read_text(encoding="utf-8")
        if not app.endswith("\n"):
            app += "\n"
        return inst + app
    return inst


def render_contract_md(ex_dir: pathlib.Path, info: dict[str, Any]) -> str:
    stub_name = info["stub_name"]
    test_name = info["test_name"]
    helpers = info["helpers"]
    stub_text = (ex_dir / stub_name).read_text(encoding="utf-8").rstrip("\n")

    test_files = [test_name, *helpers]
    if len(test_files) == 1:
        test_list_md = f"`{test_files[0]}`"
    else:
        test_list_md = " and ".join(f"`{name}`" for name in test_files)

    return (
        "# Contract\n"
        "\n"
        f"Write your solution to `{stub_name}` in the root of this workspace. The file does not exist\n"
        "yet; create it. Start from this skeleton and keep these names, because the tests import them:\n"
        "\n"
        "```python\n"
        f"{stub_text}\n"
        "```\n"
        "\n"
        f"- Put all of your code in `{stub_name}`. Only use the Python standard library; do not\n"
        "  install packages.\n"
        "- Don't change the names of existing functions or classes, as they may be referenced from\n"
        "  other code like unit tests.\n"
        f"- The tests for this task are in {test_list_md}. The tests are correct; don't change them. Run them\n"
        "  with:\n"
        "\n"
        f"      python3 -m pytest -q {test_name}\n"
        "\n"
        "  or, without pytest:\n"
        "\n"
        f"      python3 -m unittest {test_name}\n"
    )


def collect_bank_hashes(bank_dir: pathlib.Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    if not bank_dir.is_dir():
        return hashes
    for root, dirs, files in os.walk(bank_dir):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for fname in sorted(files):
            fp = pathlib.Path(root) / fname
            rel = fp.relative_to(bank_dir).as_posix()
            hashes[rel] = sha256_file(fp)
    return dict(sorted(hashes.items()))


def build_bank(
    src_dir: pathlib.Path,
    polyglot_dir: pathlib.Path,
    out_dir: pathlib.Path,
    manifest_path: pathlib.Path,
    timeout_s: float,
    workers: int,
) -> int:
    practice_dir = src_dir / "exercises" / "practice"
    if not practice_dir.is_dir():
        raise SystemExit(f"exercises/practice not found under {src_dir}")

    commit_sha = git_commit_sha(src_dir)
    polyglot_slugs = load_polyglot_slugs(polyglot_dir)
    polyglot_set = set(polyglot_slugs)

    all_practice = sorted(p.name for p in practice_dir.iterdir() if p.is_dir())
    exclusions: list[dict[str, str]] = []
    ready_for_val: dict[str, dict[str, Any]] = {}
    excluded_polyglot_count = 0

    for slug in all_practice:
        if slug in polyglot_set:
            excluded_polyglot_count += 1
            exclusions.append({
                "slug": slug,
                "stage": "rule_1_polyglot_overlap",
                "reason": "already present in polyglot_py (34 tasks)",
            })
            continue
        ex_dir = practice_dir / slug
        info, err = identify_exercise_files(ex_dir)
        if err is not None or info is None:
            exclusions.append({
                "slug": slug,
                "stage": "rule_1_required_files",
                "reason": err or "missing required files",
            })
            continue
        io_err = check_imports_and_io(ex_dir, info)
        if io_err is not None:
            exclusions.append({
                "slug": slug,
                "stage": "rule_2_stdlib_and_io",
                "reason": io_err,
            })
            continue
        ready_for_val[slug] = info

    eligible_slugs: list[str] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            slug: pool.submit(validate_exercise, slug, practice_dir / slug, info, timeout_s)
            for slug, info in ready_for_val.items()
        }
        for slug in sorted(ready_for_val):
            _, fail_stage, fail_reason = futs[slug].result()
            if fail_stage is not None:
                exclusions.append({
                    "slug": slug,
                    "stage": f"rule_3_{fail_stage}",
                    "reason": fail_reason or "validation failed",
                })
            else:
                eligible_slugs.append(slug)

    exclusions.sort(key=lambda x: (x["stage"], x["slug"]))

    ordered = sorted(
        (
            {
                "slug": slug,
                "task_id": f"ex_{slug.replace('-', '_')}",
                "order_sha256": sha256_bytes((slug + ORDER_SALT).encode("utf-8")),
            }
            for slug in eligible_slugs
        ),
        key=lambda row: (row["order_sha256"], row["slug"]),
    )
    for idx, row in enumerate(ordered, 1):
        row["rank"] = idx

    if len(ordered) < TAKE_N:
        raise SystemExit(f"only {len(ordered)} eligible exercises; need {TAKE_N}")

    chosen = ordered[:TAKE_N]

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for row in chosen:
        slug = row["slug"]
        task_id = row["task_id"]
        ex_dir = practice_dir / slug
        info = ready_for_val[slug]
        tdir = out_dir / task_id
        ws = tdir / "workspace"
        ws.mkdir(parents=True, exist_ok=True)

        (tdir / "instruction.txt").write_text(INSTRUCTION_TEXT, encoding="utf-8")
        (ws / "goal.md").write_text(render_goal_md(info), encoding="utf-8")
        (ws / "contract.md").write_text(render_contract_md(ex_dir, info), encoding="utf-8")
        shutil.copyfile(ex_dir / info["test_name"], ws / info["test_name"])
        for h in info["helpers"]:
            shutil.copyfile(ex_dir / h, ws / h)

    files_sha256 = collect_bank_hashes(out_dir)

    # Safety assertion: example.py must never appear anywhere in the bank.
    leaked = [rel for rel in files_sha256 if "example.py" in rel]
    if leaked:
        raise SystemExit(f"FATAL: example.py leaked into bank: {leaked}")

    manifest = {
        "schema": "vacant.redo.bank/1",
        "bank_id": "exercism_py_unused",
        "bank_dir": "~/dev/ops/ref/bm_tasks/exercism_py_unused",
        "source": {
            "repo": REPO_URL,
            "clone_dir": "~/dev/ops/ref/src/exercism-python",
            "commit_sha": commit_sha,
            "subdir": "exercises/practice",
        },
        "excluded_bank": {
            "path": "~/dev/ops/ref/bm_tasks/polyglot_py",
            "count": len(polyglot_slugs),
            "slugs": polyglot_slugs,
        },
        "selection_rule": {
            "text": SELECTION_RULE_TEXT,
            "order_formula": "sha256(slug + ':redo-unused-2026-11-20')",
            "order_salt": ORDER_SALT,
            "take": TAKE_N,
            "validation_timeout_s": timeout_s,
            "validation_python": sys.version.split()[0],
        },
        "counts": {
            "practice_exercises_total": len(all_practice),
            "excluded_polyglot_overlap": excluded_polyglot_count,
            "non_polyglot_candidates": len(all_practice) - excluded_polyglot_count,
            "excluded_post_polyglot": len(exclusions) - excluded_polyglot_count,
            "eligible_after_validation": len(ordered),
            "selected": len(chosen),
            "bank_files_total": len(files_sha256),
        },
        "exclusions": exclusions,
        "chosen_slugs": [row["slug"] for row in chosen],
        "chosen_tasks": [row["task_id"] for row in chosen],
        "ordered_eligible": ordered,
        "files_sha256": files_sha256,
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Built {len(chosen)} tasks ({len(files_sha256)} files) at {out_dir} "
        f"from {commit_sha[:12]}; manifest -> {manifest_path}"
    )
    return 0


def check_bank(out_dir: pathlib.Path, manifest_path: pathlib.Path) -> int:
    if not manifest_path.is_file():
        print(f"FAIL: manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    if not out_dir.is_dir():
        print(f"FAIL: bank directory not found: {out_dir}", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    want: dict[str, str] = manifest.get("files_sha256", {})
    have = collect_bank_hashes(out_dir)

    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    mismatched = sorted(k for k in (set(want) & set(have)) if want[k] != have[k])
    leaked = sorted(k for k in have if "example.py" in k)

    ok = not (missing or extra or mismatched or leaked)
    if missing:
        print(f"FAIL: {len(missing)} missing files (e.g. {missing[:5]})", file=sys.stderr)
    if extra:
        print(f"FAIL: {len(extra)} unexpected files (e.g. {extra[:5]})", file=sys.stderr)
    if mismatched:
        print(f"FAIL: {len(mismatched)} hash mismatches (e.g. {mismatched[:5]})", file=sys.stderr)
    if leaked:
        print(f"FAIL: example.py present in bank: {leaked}", file=sys.stderr)
    if ok:
        print(
            f"CHECK_OK: {len(have)}/{len(want)} files match manifest hashes in {out_dir} "
            f"(tasks={len(manifest.get('chosen_tasks', []))}, commit={manifest['source']['commit_sha'][:12]})"
        )
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=pathlib.Path, default=DEFAULT_SRC)
    ap.add_argument("--polyglot", type=pathlib.Path, default=DEFAULT_POLYGLOT)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--check", action="store_true", help="Verify bank files match manifest sha256 hashes.")
    args = ap.parse_args(argv)

    out_dir = expand(args.out)
    manifest_path = expand(args.manifest)
    if args.check:
        return check_bank(out_dir, manifest_path)
    return build_bank(
        src_dir=expand(args.src),
        polyglot_dir=expand(args.polyglot),
        out_dir=out_dir,
        manifest_path=manifest_path,
        timeout_s=args.timeout,
        workers=args.workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
