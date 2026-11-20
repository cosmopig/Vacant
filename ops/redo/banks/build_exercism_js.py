#!/usr/bin/env python3
"""Build and verify the Exercism JavaScript task bank for ops/redo/redo.py.

Stdlib-only Python 3.11+.

Usage:
    python3 ops/redo/banks/build_exercism_js.py          # build bank + write manifest
    python3 ops/redo/banks/build_exercism_js.py --check  # verify existing bank against manifest
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_SRC = pathlib.Path.home() / "dev/ops/ref/src/exercism-javascript"
DEFAULT_CACHE = pathlib.Path.home() / "dev/ops/ref/cache/exercism_js"
DEFAULT_BANK = pathlib.Path.home() / "dev/ops/ref/bm_tasks/exercism_js"
DEFAULT_MANIFEST = REPO_ROOT / "ops/redo/banks/exercism_js.json"

ORDER_SALT = ":redo-js-2026-11-20"
TARGET_COUNT = 34
TEST_TIMEOUT_S = 120
INSTRUCTION_LINE = (
    "Read goal.md and contract.md in this directory and do what they say. "
    "Use your tools to write the file.\n"
)

RULE_DESCRIPTION = (
    "Source: exercism/javascript exercises/practice/*. "
    "Require .meta/config.json, .meta/proof.ci.js (reference), exactly one *.spec.js test file, "
    "exactly one solution stub .js file, and .docs/instructions.md. "
    "Exclude exercises requiring npm dependencies/devDependencies beyond the repo root "
    "package.json devDependencies (jest/babel toolchain) or network access. "
    "Enable Exercism CI test markers in *.spec.js (\\bx(test|it)\\( -> test(, \\bxdescribe\\( -> describe(, "
    "matching scripts/helpers.mjs without altering test.skip/describe.skip). "
    "Validate offline via `npm test --silent` using the repo's babel.config.js, jest.config.js, and shared "
    "node_modules cache: (a) reference solution passes (exit 0, >=1 test passed), "
    "(b) starter stub fails at least one test (exit != 0, status ok). "
    "Order survivors ascending by sha256(slug + ':redo-js-2026-11-20') and take the first 34."
)

_NETWORK_RE = re.compile(
    r"""(?:from\s+['"](?:node:)?(?:http|https|http2|net|dgram|dns|tls|inspector)['"]"""
    r"""|require\(\s*['"](?:node:)?(?:http|https|http2|net|dgram|dns|tls|inspector)['"]\s*\)"""
    r"""|\bfetch\s*\(|\bWebSocket\b|\bXMLHttpRequest\b)"""
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_JEST_TESTS_RE = re.compile(r"^Tests:\s+(.*)$", re.M)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: pathlib.Path) -> str:
    return sha256_bytes(p.read_bytes())


def order_key(slug: str) -> str:
    return hashlib.sha256((slug + ORDER_SALT).encode("utf-8")).hexdigest()


def git_rev_parse(repo: pathlib.Path) -> str:
    r = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return r.stdout.strip()


def enable_spec_tests(spec_text: str) -> str:
    # Mirror exercism/javascript scripts/helpers.mjs lines 308-313, using word boundaries
    # so words inside comments like "(extest code)" are not rewritten.
    text = re.sub(r"\bx(test|it)\(", "test(", spec_text)
    text = re.sub(r"\bxdescribe\(", "describe(", text)
    return text


def parse_jest_counts(out: str) -> tuple[int | None, int | None, int | None]:
    clean = _ANSI_RE.sub("", out)
    m = None
    for m in _JEST_TESTS_RE.finditer(clean):
        pass
    if not m:
        return None, None, None
    line = m.group(1)
    mt = re.search(r"(\d+)\s+total\b", line)
    total = int(mt.group(1)) if mt else None
    mp = re.search(r"(\d+)\s+passed\b", line)
    mf = re.search(r"(\d+)\s+failed\b", line)
    passed = int(mp.group(1)) if mp else (0 if mf else None)
    failed = int(mf.group(1)) if mf else (0 if mp else None)
    return passed, failed, total


def installed_dev_versions(src_dir: pathlib.Path, cache_dir: pathlib.Path) -> dict[str, str]:
    root_pkg = json.loads((src_dir / "package.json").read_text(encoding="utf-8"))
    nm = cache_dir / "node_modules"
    out: dict[str, str] = {}
    for dep in sorted(root_pkg.get("devDependencies", {})):
        p = nm / dep / "package.json"
        if not p.is_file():
            raise RuntimeError(f"Shared cache missing devDependency {dep!r} at {p}")
        out[dep] = json.loads(p.read_text(encoding="utf-8"))["version"]
    return out


def tool_versions() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, argv in [("node", ["node", "-v"]), ("npm", ["npm", "-v"])]:
        r = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=15)
        out[name] = r.stdout.strip()
    return out


def make_offline_package_json(slug: str, src_ex_pkg: dict[str, Any]) -> str:
    pkg = {
        "name": src_ex_pkg.get("name", f"@exercism/javascript-{slug}"),
        "private": True,
        "license": src_ex_pkg.get("license", "MIT"),
        "scripts": {
            "test": "jest",
        },
    }
    return json.dumps(pkg, indent=2) + "\n"


def render_goal_md(ex_dir: pathlib.Path) -> str:
    docs = ex_dir / ".docs"
    parts = [(docs / "instructions.md").read_text(encoding="utf-8").rstrip("\n")]
    append_p = docs / "instructions.append.md"
    if append_p.is_file():
        append_txt = append_p.read_text(encoding="utf-8").strip("\n")
        if append_txt:
            parts.append(append_txt)
    return "\n\n".join(parts) + "\n"


def render_contract_md(
    sol_file: str,
    spec_file: str,
    stub_text: str,
    extra_files: list[str],
) -> str:
    lines = [
        "# Contract",
        "",
        f"Write your solution to `{sol_file}` in the root of this workspace. A starter stub is already",
        "present; replace the stub implementation and keep the exported names, because the tests import them:",
        "",
        "```javascript",
        stub_text.rstrip("\n"),
        "```",
        "",
        f"- Put all of your code in `{sol_file}`. Do not install or add new npm packages; only use",
        "  standard JavaScript / Node.js built-ins and the preconfigured test toolchain.",
        "- Do not change the names of exported functions, classes, or constants, as they are",
        "  referenced by the unit tests.",
    ]
    if extra_files:
        joined = ", ".join(f"`{f}`" for f in extra_files)
        lines.append(f"- Supporting workspace files ({joined}) are provided; do not remove or modify them.")
    lines += [
        f"- The tests for this task are in `{spec_file}`. The tests are correct; do not change them.",
        "  Run them offline with:",
        "",
        "      npm test",
        "",
        "  or quietly with:",
        "",
        "      npm test --silent",
        "",
    ]
    return "\n".join(lines)


def populate_workspace(
    ex_dir: pathlib.Path,
    src_dir: pathlib.Path,
    cache_nm: pathlib.Path,
    ws_dir: pathlib.Path,
    *,
    sol_file: str,
    spec_file: str,
    editor_files: list[str],
    has_data_dir: bool,
    use_reference: bool = False,
) -> None:
    ws_dir.mkdir(parents=True, exist_ok=True)
    slug = ex_dir.name
    ex_pkg = json.loads((ex_dir / "package.json").read_text(encoding="utf-8"))
    (ws_dir / "package.json").write_text(make_offline_package_json(slug, ex_pkg), encoding="utf-8")
    shutil.copyfile(src_dir / "babel.config.js", ws_dir / "babel.config.js")
    shutil.copyfile(src_dir / "jest.config.js", ws_dir / "jest.config.js")

    spec_raw = (ex_dir / spec_file).read_text(encoding="utf-8")
    (ws_dir / spec_file).write_text(enable_spec_tests(spec_raw), encoding="utf-8")

    stub_text = (ex_dir / sol_file).read_text(encoding="utf-8")
    if use_reference:
        proof_text = (ex_dir / ".meta" / "proof.ci.js").read_text(encoding="utf-8")
        # Match exercism/javascript scripts/helpers.mjs line 326
        proof_text = proof_text.replace("from '../", "from './")
        (ws_dir / sol_file).write_text(proof_text, encoding="utf-8")
    else:
        (ws_dir / sol_file).write_text(stub_text, encoding="utf-8")

    extra_names: list[str] = []
    for ef in editor_files:
        dst = ws_dir / ef
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ex_dir / ef, dst)
        extra_names.append(ef)
    if has_data_dir:
        shutil.copytree(ex_dir / "data", ws_dir / "data")
        extra_names.append("data/")

    if not use_reference:
        (ws_dir / "goal.md").write_text(render_goal_md(ex_dir), encoding="utf-8")
        (ws_dir / "contract.md").write_text(
            render_contract_md(sol_file, spec_file, stub_text, extra_names),
            encoding="utf-8",
        )

    os.symlink(str(cache_nm.resolve()), ws_dir / "node_modules")


def run_npm_test(ws_dir: pathlib.Path, home_dir: pathlib.Path) -> tuple[int | None, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home_dir),
        "LANG": "C.UTF-8",
    }
    try:
        r = subprocess.run(
            ["npm", "test", "--silent"],
            cwd=str(ws_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=TEST_TIMEOUT_S,
        )
        return r.returncode, r.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, "timeout"


def evaluate_exercise(
    slug: str,
    src_dir: pathlib.Path,
    cache_nm: pathlib.Path,
    root_dev_deps: set[str],
    root_deps: set[str],
) -> dict[str, Any]:
    ex_dir = src_dir / "exercises" / "practice" / slug
    cfg_p = ex_dir / ".meta" / "config.json"
    if not cfg_p.is_file():
        return {"slug": slug, "ok": False, "reason": "missing .meta/config.json"}
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    files = cfg.get("files", {})
    sols = files.get("solution", [])
    tests = files.get("test", [])
    editor = files.get("editor", [])

    if not (ex_dir / ".meta" / "proof.ci.js").is_file():
        return {"slug": slug, "ok": False, "reason": "missing .meta/proof.ci.js"}
    if not (ex_dir / ".docs" / "instructions.md").is_file():
        return {"slug": slug, "ok": False, "reason": "missing .docs/instructions.md"}
    if len(sols) != 1 or not sols[0].endswith(".js") or not (ex_dir / sols[0]).is_file():
        return {"slug": slug, "ok": False, "reason": f"invalid solution stub list: {sols!r}"}
    specs = sorted(p.name for p in ex_dir.glob("*.spec.js"))
    if len(tests) != 1 or len(specs) != 1 or tests[0] != specs[0]:
        return {"slug": slug, "ok": False, "reason": f"expected single *.spec.js, got tests={tests!r} specs={specs!r}"}

    pkg_p = ex_dir / "package.json"
    if not pkg_p.is_file():
        return {"slug": slug, "ok": False, "reason": "missing package.json"}
    ex_pkg = json.loads(pkg_p.read_text(encoding="utf-8"))
    extra_deps = sorted(
        (set(ex_pkg.get("dependencies", {})) - root_deps)
        | (set(ex_pkg.get("devDependencies", {})) - root_dev_deps)
    )
    if extra_deps:
        return {"slug": slug, "ok": False, "reason": f"extra npm dependencies beyond root: {extra_deps}"}

    sol_file = sols[0]
    spec_file = specs[0]
    spec_txt = (ex_dir / spec_file).read_text(encoding="utf-8")
    proof_txt = (ex_dir / ".meta" / "proof.ci.js").read_text(encoding="utf-8")
    if _NETWORK_RE.search(spec_txt) or _NETWORK_RE.search(proof_txt):
        return {"slug": slug, "ok": False, "reason": "uses network API in spec or reference"}

    has_data_dir = (ex_dir / "data").is_dir()

    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"redo-js-val-{slug}-"))
    try:
        # (a) Reference solution must pass
        ws_ref = tmp / "ref"
        populate_workspace(
            ex_dir, src_dir, cache_nm, ws_ref,
            sol_file=sol_file, spec_file=spec_file, editor_files=editor,
            has_data_dir=has_data_dir, use_reference=True,
        )
        rc_ref, out_ref = run_npm_test(ws_ref, tmp)
        p_ref, f_ref, t_ref = parse_jest_counts(out_ref)
        if rc_ref != 0 or not (p_ref is not None and p_ref > 0 and (f_ref or 0) == 0):
            return {
                "slug": slug,
                "ok": False,
                "reason": f"reference failed validation (rc={rc_ref}, passed={p_ref}, failed={f_ref}, total={t_ref})",
            }

        # (b) Stub must fail at least one test
        ws_stub = tmp / "stub"
        populate_workspace(
            ex_dir, src_dir, cache_nm, ws_stub,
            sol_file=sol_file, spec_file=spec_file, editor_files=editor,
            has_data_dir=has_data_dir, use_reference=False,
        )
        rc_stub, out_stub = run_npm_test(ws_stub, tmp)
        p_stub, f_stub, t_stub = parse_jest_counts(out_stub)
        if rc_stub is None:
            return {"slug": slug, "ok": False, "reason": f"stub validation timed out/errored: {out_stub[:120]}"}
        if rc_stub == 0:
            return {"slug": slug, "ok": False, "reason": "stub unexpectedly passed spec (rc=0)"}
        if f_stub is not None and f_stub < 1:
            return {"slug": slug, "ok": False, "reason": f"stub did not fail any test (failed={f_stub})"}

        return {
            "slug": slug,
            "ok": True,
            "order_sha256": order_key(slug),
            "sol_file": sol_file,
            "spec_file": spec_file,
            "editor_files": editor,
            "has_data_dir": has_data_dir,
            "ref_passed": p_ref,
            "ref_total": t_ref,
            "stub_failed": f_stub,
            "stub_total": t_stub,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def hash_bank_tree(bank_dir: pathlib.Path, task_names: list[str]) -> dict[str, str]:
    """Return deterministic {relative_posix_path: 'sha256:<hex>' | 'link:<target>'} for all bank files."""
    files: dict[str, str] = {}
    for task in sorted(task_names):
        tdir = bank_dir / task
        if not tdir.is_dir():
            continue
        for root, dirs, filenames in os.walk(tdir):
            root_p = pathlib.Path(root)
            # Record symlinked directories (e.g. node_modules) without recursing into them
            keep_dirs = []
            for d in sorted(dirs):
                dp = root_p / d
                if dp.is_symlink():
                    rel = dp.relative_to(bank_dir).as_posix()
                    files[rel] = "link:" + os.readlink(dp)
                else:
                    keep_dirs.append(d)
            dirs[:] = keep_dirs
            for fn in sorted(filenames):
                fp = root_p / fn
                rel = fp.relative_to(bank_dir).as_posix()
                if fp.is_symlink():
                    files[rel] = "link:" + os.readlink(fp)
                else:
                    files[rel] = sha256_file(fp)
    return dict(sorted(files.items()))


def cmd_build(args: argparse.Namespace) -> int:
    src_dir = pathlib.Path(args.src).expanduser().resolve()
    cache_dir = pathlib.Path(args.cache).expanduser().resolve()
    cache_nm = cache_dir / "node_modules"
    bank_dir = pathlib.Path(args.bank).expanduser().resolve()
    manifest_path = pathlib.Path(args.manifest).expanduser().resolve()

    if not (src_dir / "exercises" / "practice").is_dir():
        print(f"ERROR: source repo not found at {src_dir}", file=sys.stderr)
        return 2
    if not (cache_nm / ".bin" / "jest").exists():
        print(f"ERROR: shared node_modules cache not ready at {cache_nm}", file=sys.stderr)
        return 2

    commit_sha = git_rev_parse(src_dir)
    root_pkg = json.loads((src_dir / "package.json").read_text(encoding="utf-8"))
    root_dev_deps = set(root_pkg.get("devDependencies", {}))
    root_deps = set(root_pkg.get("dependencies", {}))
    dev_versions = installed_dev_versions(src_dir, cache_dir)
    tools = tool_versions()

    practice_dir = src_dir / "exercises" / "practice"
    all_slugs = sorted(p.name for p in practice_dir.iterdir() if p.is_dir())
    print(f"Validating {len(all_slugs)} practice exercises from {src_dir} ({commit_sha[:12]})...", flush=True)

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {
            ex.submit(evaluate_exercise, slug, src_dir, cache_nm, root_dev_deps, root_deps): slug
            for slug in all_slugs
        }
        done = 0
        for fut in concurrent.futures.as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            if done % 20 == 0 or done == len(all_slugs):
                print(f"  validated {done}/{len(all_slugs)}", flush=True)

    results.sort(key=lambda r: r["slug"])
    exclusions = [{"slug": r["slug"], "reason": r["reason"]} for r in results if not r["ok"]]
    survivors = [r for r in results if r["ok"]]
    survivors.sort(key=lambda r: (r["order_sha256"], r["slug"]))

    if len(survivors) < TARGET_COUNT:
        print(f"ERROR: only {len(survivors)} survivors (< {TARGET_COUNT})", file=sys.stderr)
        return 1

    chosen = survivors[:TARGET_COUNT]
    chosen_slugs = [r["slug"] for r in chosen]
    chosen_tasks = [f"js_{slug}" for slug in chosen_slugs]

    print(
        f"Validation done: {len(survivors)}/{len(all_slugs)} survived, "
        f"{len(exclusions)} excluded. Building first {TARGET_COUNT} tasks into {bank_dir}...",
        flush=True,
    )

    if bank_dir.exists():
        shutil.rmtree(bank_dir)
    bank_dir.mkdir(parents=True, exist_ok=True)

    chosen_meta: list[dict[str, Any]] = []
    for r in chosen:
        slug = r["slug"]
        task = f"js_{slug}"
        tdir = bank_dir / task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "instruction.txt").write_text(INSTRUCTION_LINE, encoding="utf-8")
        populate_workspace(
            practice_dir / slug,
            src_dir,
            cache_nm,
            tdir / "workspace",
            sol_file=r["sol_file"],
            spec_file=r["spec_file"],
            editor_files=r["editor_files"],
            has_data_dir=r["has_data_dir"],
            use_reference=False,
        )
        chosen_meta.append({
            "task": task,
            "slug": slug,
            "order_sha256": r["order_sha256"],
            "solution_file": r["sol_file"],
            "spec_file": r["spec_file"],
            "editor_files": r["editor_files"],
            "has_data_dir": r["has_data_dir"],
            "validation": {
                "ref_passed": r["ref_passed"],
                "ref_total": r["ref_total"],
                "stub_failed": r["stub_failed"],
                "stub_total": r["stub_total"],
            },
        })

    bank_files = hash_bank_tree(bank_dir, chosen_tasks)
    # Safety check: never include any reference solution file
    for rel in bank_files:
        if "proof.ci.js" in rel or ".meta/" in rel:
            raise AssertionError(f"Refusing to emit reference/meta file in bank: {rel}")

    manifest = {
        "schema": "vacant.redo.bank/1",
        "bank_id": "exercism_js",
        "source_repo": "https://github.com/exercism/javascript",
        "source_dir": str(src_dir),
        "source_commit_sha": commit_sha,
        "shared_node_modules_dir": str(cache_nm),
        "node_modules_strategy": "symlink",
        "node_modules_rationale": (
            "Each task workspace contains a `node_modules` symlink pointing to the single shared cache. "
            "This lets `npm test` resolve `./node_modules/.bin/jest`, `babel-jest`, "
            "`@exercism/babel-preset-javascript`, `@jest/globals`, and `core-js` offline with zero extra "
            "env vars, while redo.py skips `node_modules` in workspace snapshots/archives and restores the "
            "origin symlink during `kind='command'` acceptance."
        ),
        "runtime_versions": tools,
        "dev_dependencies_versions": dev_versions,
        "order_formula": f"sha256(slug + {ORDER_SALT!r})",
        "rule": RULE_DESCRIPTION,
        "counts": {
            "total_practice": len(all_slugs),
            "excluded": len(exclusions),
            "survivors": len(survivors),
            "chosen": len(chosen_slugs),
        },
        "exclusions": exclusions,
        "chosen_slugs": chosen_slugs,
        "chosen_tasks": chosen_tasks,
        "chosen_details": chosen_meta,
        "bank_files": bank_files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest {manifest_path} ({len(bank_files)} entries).")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    src_dir = pathlib.Path(args.src).expanduser().resolve()
    cache_dir = pathlib.Path(args.cache).expanduser().resolve()
    bank_dir = pathlib.Path(args.bank).expanduser().resolve()
    manifest_path = pathlib.Path(args.manifest).expanduser().resolve()

    errors: list[str] = []

    if not manifest_path.is_file():
        print(f"FAIL: manifest missing: {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # 1. Check source repo commit SHA if present
    if (src_dir / ".git").exists():
        got_sha = git_rev_parse(src_dir)
        if got_sha != manifest["source_commit_sha"]:
            errors.append(f"source_commit_sha mismatch: repo={got_sha} manifest={manifest['source_commit_sha']}")
    else:
        errors.append(f"source repo missing at {src_dir}")

    # 2. Check shared node_modules cache versions
    try:
        got_vers = installed_dev_versions(src_dir, cache_dir)
        if got_vers != manifest["dev_dependencies_versions"]:
            errors.append("dev_dependencies_versions mismatch between shared cache and manifest")
    except Exception as e:
        errors.append(f"shared cache check failed: {e}")

    # 3. Check ordering determinism
    slugs = manifest["chosen_slugs"]
    tasks = manifest["chosen_tasks"]
    if len(slugs) != TARGET_COUNT or tasks != [f"js_{s}" for s in slugs]:
        errors.append(f"chosen_slugs/chosen_tasks count or naming mismatch (len={len(slugs)})")
    keys = [order_key(s) for s in slugs]
    if keys != sorted(keys):
        errors.append("chosen_slugs are not sorted by sha256(slug + ':redo-js-2026-11-20')")

    # 4. Check bank directory contents match manifest bank_files byte-for-byte
    if not bank_dir.is_dir():
        errors.append(f"bank dir missing: {bank_dir}")
    else:
        actual_dirs = sorted(p.name for p in bank_dir.iterdir())
        expected_dirs = sorted(tasks)
        if actual_dirs != expected_dirs:
            errors.append(f"bank dir entries mismatch: extra={set(actual_dirs)-set(expected_dirs)} missing={set(expected_dirs)-set(actual_dirs)}")
        actual_files = hash_bank_tree(bank_dir, actual_dirs)
        expected_files = manifest["bank_files"]
        for rel, exp in expected_files.items():
            got = actual_files.get(rel)
            if got != exp:
                errors.append(f"file mismatch {rel}: expected={exp} actual={got}")
        extra = sorted(set(actual_files) - set(expected_files))
        if extra:
            errors.append(f"unexpected extra files in bank: {extra[:10]}")
        for rel in actual_files:
            if "proof.ci.js" in rel or ".meta/" in rel:
                errors.append(f"forbidden reference/meta file present in bank: {rel}")

    if errors:
        for e in errors:
            print(f"FAIL  {e}", file=sys.stderr)
        print(f"VERDICT: CHECK_FAIL ({len(errors)} error(s))", file=sys.stderr)
        return 1

    print(
        f"OK    source={manifest['source_commit_sha'][:12]} "
        f"tasks={len(tasks)} files={len(manifest['bank_files'])} "
        f"exclusions={len(manifest['exclusions'])}"
    )
    print("VERDICT: CHECK_OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build/verify the exercism_js redo task bank.")
    ap.add_argument("--check", action="store_true", help="Verify existing bank and manifest without rebuilding.")
    ap.add_argument("--src", default=str(DEFAULT_SRC), help="Path to exercism/javascript git clone.")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE), help="Path to shared node_modules cache dir.")
    ap.add_argument("--bank", default=str(DEFAULT_BANK), help="Output bank directory.")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Output manifest JSON path.")
    ap.add_argument("--jobs", type=int, default=6, help="Parallel validation workers (default: 6).")
    args = ap.parse_args(argv)
    return cmd_check(args) if args.check else cmd_build(args)


if __name__ == "__main__":
    sys.exit(main())
