#!/usr/bin/env python3
"""Build the polyglot3 bank (C++ / Go / Rust Exercism exercises from Aider-AI/polyglot-benchmark; split per test function).

Pre-registered in decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md (candidate 2). Reuses build_cc40 helpers
(scorer template, sha256). Each task: workspace/{stub files, native test file with the *visible* tests, solution_test.py wrapper,
goal.md, contract.md}, hidden/{solution_test.py (hidden mode), hidden_native (the native test file with only hidden tests)}, scorer.py.

Usage: build_polyglot3.py --src <polyglot-benchmark checkout> --out /opt/ctlwork/bm_tasks/polyglot3 --manifest M [--workers 3]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import pathlib
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_cc40 as B  # noqa: E402

SEED = 20261127
MAX_TASKS = 40
MIN_TESTS = 10
LANGS = ["cpp", "go", "rust"]

WRAPPER = r'''"""Tests for this exercise (@LANG@). Runs the language's own test suite once and reports one result per original test function:
@N@ test methods here. Run with `python3 -m unittest solution_test` (or run the native command in contract.md)."""
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LANG = "@LANG@"
_DEST = "@DEST@"
_HIDDEN_SRC = @HIDDEN_SRC@
_EXPECT_SHA = "@SHA@"
_NAMES = @NAMES@
_FILTERS = @FILTERS@
_NAME = "@EXNAME@"
_state = {"res": None}
_ENV = {"PATH": "/opt/polytools/rust/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
        "GOPROXY": "off", "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local", "CARGO_NET_OFFLINE": "true"}
_SKIP = {".git", "node_modules", "target", "__pycache__", ".polycache"}


def _run(cmd, cwd, env, timeout):
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out.decode("utf-8", "replace"), False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, 9)
        except OSError:
            pass
        out, _ = p.communicate()
        return None, out.decode("utf-8", "replace"), True


def _execute():
    tmp = tempfile.mkdtemp(prefix="poly-")
    env = dict(_ENV, HOME=tmp, GOCACHE=os.path.join(tmp, "gocache"), GOPATH=os.path.join(tmp, "gopath"), CARGO_HOME=os.path.join(tmp, "cargo"))
    try:
        w = os.path.join(tmp, "w")
        shutil.copytree(_HERE, w, symlinks=True, ignore=shutil.ignore_patterns(*_SKIP))
        dest = os.path.join(w, _DEST)
        if _HIDDEN_SRC:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copyfile(os.path.join(_HERE, _HIDDEN_SRC), dest)
        else:
            if not os.path.isfile(dest) or hashlib.sha256(open(dest, "rb").read()).hexdigest() != _EXPECT_SHA:
                return {"fatal": "the test file %s was modified or is missing" % _DEST}
        res = {}
        if _LANG == "rust":
            rc, out, to = _run(["cargo", "test", "--offline", "--", "--include-ignored", "--test-threads=4"], w, env, 240)
            for m in re.finditer(r"^test (\S+) \.\.\. (ok|FAILED|ignored)", out, re.M):
                res[m.group(1)] = m.group(2) == "ok"
            res["_out"] = out[-1500:]
            res["_timeout"] = to
        elif _LANG == "go":
            rc, out, to = _run(["go", "test", "-v", "-timeout", "120s", "./..."], w, env, 240)
            for m in re.finditer(r"^--- (PASS|FAIL|SKIP): (\S+)", out, re.M):
                res[m.group(2)] = m.group(1) == "PASS"
            res["_out"] = out[-1500:]
            res["_timeout"] = to
        else:
            exe = os.path.join(w, "polybin")
            srcs = [os.path.join(w, f) for f in os.listdir(w) if f.endswith(".cpp") and f != "polybin.cpp"]
            main_o = _catch_main(w, env)
            if main_o is None:
                return {"_out": "could not build the Catch main", "_timeout": False}
            cmd = ["g++", "-std=c++17", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-DEXERCISM_RUN_ALL_TESTS", "-I", w, "-o", exe] + srcs + [main_o]
            rc, out, to = _run(cmd, w, env, 240)
            if rc != 0:
                res["_out"] = ("compile error: " + out)[-1500:]
                res["_timeout"] = to
                res["_compile_error"] = True
            else:
                res["_out"] = ""
                for name, flt in zip(_NAMES, _FILTERS):
                    rc2, out2, to2 = _run([exe, flt], w, env, 20)
                    res[name] = (rc2 == 0)
                    if rc2 != 0:
                        res["_out"] += "--- %s: %s\n" % (name, "timeout (20s)" if to2 else out2[-300:])
                res["_out"] = res["_out"][-1500:]
                res["_timeout"] = False
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _catch_main(w, env):
    """tests-main.cpp (CATCH_CONFIG_MAIN) compiled once per catch.hpp content; cached under /var/tmp."""
    src = os.path.join(w, "test", "tests-main.cpp")
    hdr = os.path.join(w, "test", "catch.hpp")
    if not (os.path.isfile(src) and os.path.isfile(hdr)):
        return None
    key = hashlib.sha256(open(src, "rb").read() + open(hdr, "rb").read()).hexdigest()[:16]
    cache = "/var/tmp/poly_catch_main_%s.o" % key
    if not os.path.isfile(cache):
        tmpo = cache + ".%d.tmp" % os.getpid()
        rc, out, to = _run(["g++", "-std=c++17", "-c", "-I", os.path.join(w, "test"), "-o", tmpo, src], w, env, 240)
        if rc != 0:
            return None
        os.replace(tmpo, cache)
    return cache


def _results():
    if _state["res"] is None:
        _state["res"] = _execute()
    return _state["res"]


def _check(tc, name):
    r = _results()
    if "fatal" in r:
        tc.fail(r["fatal"])
    if name in r and isinstance(r[name], bool) and r[name]:
        return
    if r.get("_compile_error"):
        tc.fail(r["_out"])
    tc.fail("test %s did not pass%s\n%s" % (name, " (timed out)" if r.get("_timeout") else "", r.get("_out", "")))


class SolutionTest(unittest.TestCase):
    pass


def _mk(name):
    def t(self):
        _check(self, name)
    return t


for _i, _n in enumerate(_NAMES):
    setattr(SolutionTest, "test_%02d_%s" % (_i, re.sub(r"\W+", "_", _n)[:60]), _mk(_n))

if __name__ == "__main__":
    unittest.main()
'''

GOAL = "# {title}\n\n{body}\n"
CONTRACTS = {
    "cpp": """# Contract

Implement the exercise in `{stem}.h` and `{stem}.cpp` (both exist as stubs; keep the names the tests use).
C++17, standard library only.

- The tests for this task are in `{stem}_test.cpp` (Catch2, with `test/catch.hpp` and `test/tests-main.cpp`). The tests are correct;
  don't change them or anything under `test/`. Build and run them with:

      g++ -std=c++17 -Wall -Wextra -Wpedantic -Werror -DEXERCISM_RUN_ALL_TESTS -o polybin {stem}_test.cpp {stem}.cpp test/tests-main.cpp && ./polybin

  (the same suite is also run by `python3 -m unittest solution_test`, one test method per Catch test case).
- Warnings are errors in that build.
""",
    "go": """# Contract

Implement the exercise in the existing Go source files of this directory (stubs; keep the names the tests use). Standard library only, no network.

- The tests are in `{tests}`. The tests are correct; don't change them. Run them with:

      go test ./...

  (the same suite is also run by `python3 -m unittest solution_test`, one test method per Go test function).
""",
    "rust": """# Contract

Implement the exercise in `src/lib.rs` (a stub; keep the names the tests use). Standard library only, no network; do not change `Cargo.toml`.

- The tests are in `tests/{stem}.rs`. The tests are correct; don't change them. Run them with:

      cargo test

  (the same suite is also run by `python3 -m unittest solution_test`, one test method per test function).
""",
}


# ---------------------------------------------------------------- source scanning
def match_close(text: str, i: int, lang: str) -> int:
    """text[i] == '{'; return index just after the matching '}' (skips strings, char literals, comments)."""
    depth, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if two == "//":
            i = text.find("\n", i)
            i = n if i < 0 else i
            continue
        if two == "/*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if lang == "go" and c == "`":
            j = text.find("`", i + 1)
            i = n if j < 0 else j + 1
            continue
        if lang in ("cpp", "rust") and c == "R" and text[i + 1:i + 2] == '"' and lang == "cpp":
            m = re.match(r'R"([^(]*)\(', text[i:])
            if m:
                end = text.find(")" + m.group(1) + '"', i)
                i = n if end < 0 else end + len(m.group(1)) + 2
                continue
        if lang == "rust" and c == "r" and re.match(r'r#*"', text[i:i + 4]) and not text[i - 1:i].isalnum():
            m = re.match(r'r(#*)"', text[i:])
            end = text.find('"' + m.group(1), i + len(m.group(0)))
            i = n if end < 0 else end + 1 + len(m.group(1))
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            i += 1
            continue
        if c == "'":
            m = re.match(r"'(\\.[^']*|[^\\'])'", text[i:i + 12])
            if m:
                i += len(m.group(0))
                continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unbalanced braces")


def cpp_flatten(text: str) -> str:
    """Drop the `#if defined(EXERCISM_RUN_ALL_TESTS)` guards (and their matching #endif) so every TEST_CASE is a plain top-level item."""
    out, stack = [], []
    for line in text.split("\n"):
        s = line.strip()
        if re.match(r"#\s*if(def)?\b", s):
            ours = bool(re.match(r"#\s*(if\s+defined\(?\s*EXERCISM_RUN_ALL_TESTS\s*\)?|ifdef\s+EXERCISM_RUN_ALL_TESTS)\s*$", s))
            stack.append(ours)
            if ours:
                continue
        elif re.match(r"#\s*endif\b", s) and stack:
            if stack.pop():
                continue
        out.append(line)
    return "\n".join(out)


def find_tests(text: str, lang: str) -> list[dict]:
    """Test items: {name, start, end, filter?}. start..end is the whole item text (incl. attributes for Rust)."""
    items = []
    if lang == "cpp":
        for m in re.finditer(r"^[ \t]*TEST_CASE\s*\(", text, re.M):
            g = r"(?:\s|//[^\n]*\n)*"
            lit = r'(?:"(?:[^"\\]|\\.)*"' + g + r")+"
            q = re.compile(r"TEST_CASE" + g + r"\(" + g + "(" + lit + ")" + r"(?:," + g + "(" + lit + "))?" + r"\)").match(
                text, m.start() + m.group(0).index("TEST_CASE"))
            if not q:
                raise ValueError("TEST_CASE header: " + text[m.start():m.start() + 80])
            ob = text.index("{", q.end())
            nm = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', q.group(1)))
            tg = "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', q.group(2) or ""))
            tags = re.findall(r"\[[^\]]+\]", tg)
            flt = tags[0] if len(tags) == 1 else re.sub(r"([,\[\]\\*])", r"\\\1", nm)
            items.append({"name": nm, "start": m.start(), "end": match_close(text, ob, lang), "filter": flt})
    elif lang == "go":
        for m in re.finditer(r"^func (Test\w+)\(t \*testing\.T\)\s*\{", text, re.M):
            items.append({"name": m.group(1), "start": m.start(), "end": match_close(text, m.end() - 1, lang)})
    else:
        for m in re.finditer(r"^[ \t]*#\[test\][ \t]*\n((?:[ \t]*#\[[^\n]*\][ \t]*\n)*)[ \t]*fn (\w+)\s*\(", text, re.M):
            ob = text.index("{", m.end())
            items.append({"name": m.group(2), "start": m.start(), "end": match_close(text, ob, lang)})
    return items


def drop_items(text: str, items: list[dict]) -> str:
    for it in sorted(items, key=lambda x: -x["start"]):
        text = text[:it["start"]] + text[it["end"]:]
    return text


def rust_unignore(text: str) -> str:
    return re.sub(r"^[ \t]*#\[ignore[^\]]*\][ \t]*\n", "", text, flags=re.M)


# ---------------------------------------------------------------- per-exercise preparation
def exercise_files(lang: str, d: pathlib.Path):
    """(stub_files{rel: bytes}, test_rel, example{rel: bytes}) or (None, reason)."""
    cfg = json.loads((d / ".meta" / "config.json").read_text())
    files = cfg.get("files", {})
    tests = files.get("test", [])
    if lang == "go":
        tests = [str(p.relative_to(d)) for p in sorted(d.glob("*_test.go"))]
    if len(tests) != 1:
        return None, f"test_files={len(tests)}"
    test_rel = tests[0]
    if lang == "rust":
        if re.search(r"^\[dependencies\]\s*\n\s*\S", (d / "Cargo.toml").read_text(), re.M):
            return None, "cargo_dependencies"
    ex = {}
    for e in files.get("example", []):
        ep = d / e
        if ep.is_file():
            ex[e] = ep.read_bytes()
    sol = files.get("solution", [])
    if lang == "go":
        sol = [str(p.relative_to(d)) for p in sorted(d.glob("*.go")) if not p.name.endswith("_test.go")]
    if lang == "rust":
        sol = ["src/lib.rs"]
    stubs = {}
    for s in sol:
        sp = d / s
        if sp.is_file():
            stubs[s] = sp.read_bytes()
    # support files (kept unchanged in the workspace)
    support = {}
    if lang == "cpp":
        for p in (d / "test").iterdir():
            support["test/" + p.name] = p.read_bytes()
    elif lang == "go":
        for p in d.glob("*.go"):
            if p.name not in {pathlib.Path(x).name for x in sol} and p.name != pathlib.Path(test_rel).name:
                support[p.name] = p.read_bytes()
        support["go.mod"] = (d / "go.mod").read_bytes()
    else:
        support["Cargo.toml"] = (d / "Cargo.toml").read_bytes()
    if lang == "rust":
        stubs = {"src/lib.rs": (d / "src" / "lib.rs").read_bytes()}
    return {"stubs": stubs, "support": support, "test_rel": test_rel, "example": ex, "cfg": cfg}, None


def example_map(lang: str, stem: str, ex: dict, stubs: dict) -> dict[str, bytes]:
    """Map example files onto the stub paths."""
    out = {}
    for rel, data in ex.items():
        base = pathlib.Path(rel).name
        if lang == "rust":
            out["src/lib.rs"] = data
        else:
            out[stem + pathlib.Path(base).suffix] = data      # example.cpp/.h/.go -> <stem>.cpp/.h/.go
    return out


def instructions(d: pathlib.Path) -> str:
    parts = []
    for n in ("introduction.md", "instructions.md", "instructions.append.md"):
        p = d / ".docs" / n
        if p.is_file():
            parts.append(p.read_text().strip())
    return "\n\n".join(parts)


def build_task(lang: str, d: pathlib.Path, out: pathlib.Path, tid: str) -> tuple[dict | None, str | None]:
    try:
        return _build_task(lang, d, out, tid)
    except (ValueError, KeyError, OSError) as e:
        shutil.rmtree(out / tid, ignore_errors=True)
        return None, "parse_error:" + str(e)[:80]


def _build_task(lang: str, d: pathlib.Path, out: pathlib.Path, tid: str) -> tuple[dict | None, str | None]:
    info, why = exercise_files(lang, d)
    if info is None:
        return None, why
    test_rel = info["test_rel"]
    text = (d / test_rel).read_text(encoding="utf-8")
    stem = d.name.replace("-", "_")
    if lang == "cpp":
        text = cpp_flatten(text)
    if lang == "rust":
        text = rust_unignore(text)
    items = find_tests(text, lang)
    native_n = len(re.findall({"cpp": r"^\s*TEST_CASE\(", "go": r"^func Test\w+\(t \*testing\.T\)", "rust": r"#\[test\]"}[lang], text, re.M))
    if len(items) != native_n:
        return None, f"parse_mismatch({len(items)}!={native_n})"
    names = [it["name"] for it in items]
    if len(set(names)) != len(names):
        return None, "duplicate_test_names"
    if len(items) < MIN_TESTS:
        return None, f"tests<{MIN_TESTS}({len(items)})"
    idx = list(range(len(items)))
    random.Random(f"{SEED}:{lang}:{d.name}").shuffle(idx)
    nv = len(items) // 2
    vis_idx, hid_idx = sorted(idx[:nv]), sorted(idx[nv:])
    vis_items, hid_items = [items[i] for i in vis_idx], [items[i] for i in hid_idx]
    vis_text = drop_items(text, hid_items)
    hid_text = drop_items(text, vis_items)
    td = out / tid
    ws, hid = td / "workspace", td / "hidden"
    ws.mkdir(parents=True)
    hid.mkdir(parents=True)

    def put(path: pathlib.Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    for rel, data in {**info["stubs"], **info["support"]}.items():
        put(ws / rel, data)
    put(ws / test_rel, vis_text)
    put(hid / "hidden_native", hid_text)
    sha_vis = B.sha256_b(vis_text.encode("utf-8"))

    def wrapper(its, hidden: bool):
        return (WRAPPER.replace("@LANG@", lang).replace("@N@", str(len(its))).replace("@DEST@", test_rel)
                .replace("@HIDDEN_SRC@", '"hidden_native"' if hidden else "None").replace("@SHA@", "" if hidden else sha_vis)
                .replace("@NAMES@", json.dumps([i["name"] for i in its])).replace("@FILTERS@", json.dumps([i.get("filter", "") for i in its]))
                .replace("@EXNAME@", d.name))

    put(ws / "solution_test.py", wrapper(vis_items, False))
    put(hid / "solution_test.py", wrapper(hid_items, True))
    title = d.name.replace("-", " ").title()
    put(ws / "goal.md", GOAL.format(title=title, body=instructions(d)))
    put(ws / "contract.md", CONTRACTS[lang].format(stem=stem, tests=test_rel))
    put(td / "instruction.txt", "Read goal.md and contract.md in this directory and do what they say. Use your tools to write the files.\n")
    put(td / "scorer.py", B.scorer_template())
    meta = {"lang": lang, "exercise": d.name, "n_tests": len(items), "n_vis": len(vis_items), "n_hid": len(hid_items), "test_file": test_rel,
            "example_files": sorted(example_map(lang, stem, info["example"], info["stubs"]))}
    (td / "_build.json").write_text(json.dumps({"example": {k: v.decode("utf-8") for k, v in example_map(lang, stem, info["example"], info["stubs"]).items()}}),
                                    encoding="utf-8")
    return meta, None


def real_check(out: pathlib.Path, tid: str) -> dict:
    td = out / tid
    ex = json.loads((td / "_build.json").read_text())["example"]
    res = {}
    for label, files in (("ref", ex), ("stub", {})):
        with tempfile.TemporaryDirectory(prefix="pg3r-") as t:
            w = pathlib.Path(t) / "w"
            shutil.copytree(td / "workspace", w)
            for rel, data in files.items():
                (w / rel).write_text(data, encoding="utf-8")
            p = subprocess.run([sys.executable, "-m", "unittest", "solution_test"], cwd=w, capture_output=True, text=True, timeout=900)
            sp = subprocess.run([sys.executable, str(td / "scorer.py"), str(td / "hidden"), str(w)], capture_output=True, text=True, timeout=900,
                                env={**__import__("os").environ, "SUITE_TIMEOUT_S": "800"})
            try:
                sc = json.loads(sp.stdout.strip().splitlines()[-1])
            except Exception:
                sc = {"pass": False, "tests_passed": 0, "tests_total": 0, "status": "scorer_error:" + sp.stdout[-200:] + sp.stderr[-200:]}
            res[label] = {"visible_ok": p.returncode == 0, "visible_tail": p.stderr[-300:] if p.returncode else "", "hidden_pass": sc["pass"],
                          "hidden": f"{sc['tests_passed']}/{sc['tests_total']}"}
    res["ok"] = bool(res["ref"]["visible_ok"] and res["ref"]["hidden_pass"] and not res["stub"]["visible_ok"] and not res["stub"]["hidden_pass"])
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--select-only", action="store_true")
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="pg3q-"))
    cands, excluded = {l: [] for l in LANGS}, []
    # stage 1: mechanical eligibility (parse, counts) using a throwaway build
    for lang in LANGS:
        for d in sorted((src / lang / "exercises" / "practice").iterdir()):
            if not d.is_dir():
                continue
            meta, why = build_task(lang, d, scratch, f"{lang}_{d.name}")
            if meta is None:
                excluded.append({"lang": lang, "exercise": d.name, "reason": why})
            else:
                cands[lang].append((d, meta))
    shutil.rmtree(scratch, ignore_errors=True)
    # stage 2: validity (reference passes both halves, stub fails both) — done after writing the real bank for the selected set
    print({l: len(v) for l, v in cands.items()}, flush=True)
    return finish(a, src, out, cands, excluded)


def finish(a, src, out, cands, excluded):
    # validity first on every parse-eligible exercise (in a throwaway bank), then apply the preregistered selection rule
    vbank = pathlib.Path(tempfile.mkdtemp(prefix="pg3v-"))
    valid: dict[str, list] = {l: [] for l in LANGS}
    checks = {}

    def work(lang, d):
        tid = f"pg3_{lang}_{d.name.replace('-', '_')}"
        meta, why = build_task(lang, d, vbank, tid)
        rc = real_check(vbank, tid)
        return lang, d, tid, meta, rc

    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(work, lang, d) for lang in LANGS for d, _ in cands[lang]]
        for fu in futs:
            lang, d, tid, meta, rc = fu.result()
            checks[tid] = rc
            print(tid, rc["ok"], rc["ref"]["hidden"], rc["stub"]["hidden"], flush=True)
            if rc["ok"]:
                valid[lang].append((d, meta))
            else:
                excluded.append({"lang": lang, "exercise": d.name, "reason": "validity", "real_check": rc})
    shutil.rmtree(vbank, ignore_errors=True)
    # selection rule 4
    total = sum(len(v) for v in valid.values())
    sel = {}
    if total <= MAX_TASKS:
        sel = {l: list(v) for l, v in valid.items()}
    else:
        cap = 0
        for c in range(1, MAX_TASKS + 1):
            if sum(min(c, len(v)) for v in valid.values()) <= MAX_TASKS:
                cap = c
        for l, v in valid.items():
            n = len(v)
            sel[l] = list(v) if n <= cap else [v[(i * n) // cap] for i in range(cap)]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, tasks = {}, []
    for lang in LANGS:
        for d, meta in sel[lang]:
            tid = f"pg3_{lang}_{d.name.replace('-', '_')}"
            m2, why = build_task(lang, d, out, tid)
            assert m2 is not None, why
            tdir = out / tid
            (tdir / "_build.json").unlink()   # reference solution must not sit in the bank the agent can reach
            files.update({str(p.relative_to(out)): B.sha256_b(p.read_bytes()) for p in sorted(tdir.rglob("*")) if p.is_file()})
            tasks.append({"task": tid, **m2, "real_check": checks[tid]})
    man = {"bank_id": out.name, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": SEED,
           "source": "Aider-AI/polyglot-benchmark", "source_commit": subprocess.run(["git", "-C", str(src), "log", "-1", "--format=%H"], capture_output=True,
                                                                                    text=True).stdout.strip(),
           "n_parse_eligible": {l: len(cands[l]) for l in LANGS}, "n_valid": {l: len(valid[l]) for l in LANGS}, "n_tasks": len(tasks), "tasks": tasks,
           "excluded": excluded, "files_sha256": files}
    pathlib.Path(a.manifest).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.manifest).write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    print("built", len(tasks), {l: len(sel[l]) for l in LANGS})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
