#!/usr/bin/env python3
"""freeze_i1001 — 預註冊的「釘住的東西」兩張表（工具＋wheel、題目 staged 樹）：凍結時填、發射前在 VM 上核對。

    python3 freeze_i1001.py --fill  <PREREG.md> [--wheel <wheel 檔>] [--staged <staged 目錄>]   # 把表裡每一列換成目前的 sha256（凍結前最後一步）
    python3 freeze_i1001.py --check <PREREG.md> [--wheel <wheel 檔>] [--staged <staged 目錄>]   # 本機：表與目前的檔案逐列一致、檔案沒有多也沒有少
    python3 freeze_i1001.py --check <PREREG.md> --vm [--staged /srv/eval/staged]               # VM：表與 /opt/eval 底下佈署出去的檔案、/srv/eval/staged 一致
    python3 freeze_i1001.py --wheel-vs-git <wheel> [--git-ref HEAD]                            # wheel 裡 vacant_network/ 每個檔與 git 的同一份逐位元相同

這支在架構裡承重什麼：預註冊說「用的是這一組工具、這一批題目」，只有在「凍結的那份表」與「真的在 VM 上跑的那份檔案」逐位元相同時才成立
（第一批：發射前逐支核對 VM 上的工具與凍結 commit 的 sha256、題庫樹雜湊逐一相同）。
兩張表在預註冊裡各自夾在 `TOOLS_SHA256_BEGIN／END`、`STAGED_SHA256_BEGIN／END` 標記之間；`〔凍結時填〕` 一律視為不一致（沒填過的表不能發射）。
freeze_i1001.py 自己不在表裡（自己雜湊自己沒有固定點）；預註冊本身與 RUNBOOK 也不在表裡（它們是文件，不是跑的東西）。
工具表的 wheel 列＝`--wheel` 給的檔（本機）或 `/opt/eval/wheel/*.whl`（VM）。題目表的樹雜湊與 `launch_record.py` 的 `tree()` 逐字同一個算法
（路徑＋NUL＋每檔 sha256 依序串起來）。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import pathlib
import re
import subprocess
import sys
import tarfile
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = ("<!-- TOOLS_SHA256_BEGIN -->", "<!-- TOOLS_SHA256_END -->")
STAGED = ("<!-- STAGED_SHA256_BEGIN -->", "<!-- STAGED_SHA256_END -->")
PLACEHOLDER = "〔凍結時填〕"
LOCAL_ONLY = ("analyze_i1001.py", "autostop_i1001.sh", "build_bundle.sh", "build_manifest.py", "cu_cap_i1001.sh",
              "sync_i1001.sh", "vmsh_i1001.sh", "MANIFEST_REUSED.json")
WHEEL_ROW = "wheel"
STAGED_BANKS = ("lcb_v1", "lcb_v2", "lcb_v3", "dabench", "databench", "polyglot_py")
STAGED_FILES = ("tasks_index.json", "MANIFEST.json")


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_sha(d: pathlib.Path) -> str:
    """與 vm/launch_record.py 的 tree() 逐字同一個算法。"""
    m = hashlib.sha256()
    for f in sorted(d.rglob("*")):
        if f.is_file():
            m.update(str(f.relative_to(d)).encode() + b"\0" + hashlib.sha256(f.read_bytes()).digest())
    return m.hexdigest()


# ── 工具表 ──────────────────────────────────────────────────────────────────────────────────────

def repo_files(root: pathlib.Path) -> list[str]:
    """進 bundle 的（vm/*.py vm/*.sh scorers/*.py stub_model.py bridge/…）＋本機專用的；相對於 root、排序。"""
    out: list[str] = []
    for pat in ("vm/*.py", "vm/*.sh", "scorers/*.py"):
        out += [str(p.relative_to(root)) for p in sorted(root.glob(pat))]
    out += ["stub_model.py", "bridge/native_acceptance_bridge.py"]
    out += list(LOCAL_ONLY)
    return sorted(set(out))


def vm_path(rel: str, vm_bin: pathlib.Path, vm_bridge: pathlib.Path) -> pathlib.Path | None:
    """repo 相對路徑 → VM 上佈署的路徑（build_bundle.sh／deploy_i1001.sh 的對應）；本機專用的 → None。"""
    if rel in LOCAL_ONLY:
        return None
    if rel.startswith("vm/"):
        return vm_bin / rel[3:]
    if rel.startswith("scorers/"):
        return vm_bin / rel
    if rel == "stub_model.py":
        return vm_bin / "stub_model.py"
    if rel == "bridge/native_acceptance_bridge.py":
        return vm_bridge / "native_acceptance_bridge.py"
    raise ValueError(f"no VM mapping for {rel}")


def repo_name_of_deployed(p: pathlib.Path, vm_bin: pathlib.Path, vm_bridge: pathlib.Path) -> str:
    """vm_path 的反向：VM 上的檔 → 表裡的名字。"""
    if vm_bridge in p.parents:
        return "bridge/" + p.relative_to(vm_bridge).as_posix()
    rel = p.relative_to(vm_bin).as_posix()
    if rel.startswith("scorers/") or rel == "stub_model.py":
        return rel
    return "vm/" + rel


def tool_rows(root: pathlib.Path, wheel: pathlib.Path | None, *, vm: bool, vm_bin: pathlib.Path, vm_bridge: pathlib.Path,
              vm_wheel_dir: pathlib.Path) -> dict[str, str | None]:
    """{表裡的名字: 目前的 sha256 或 None（檔案不存在）}。
    本機：名單來自 repo 的檔案清單。VM：名單來自**實際佈署出去的檔案**（VM 上沒有 repo；佈署了表上沒有的檔也要被抓到）。"""
    rows: dict[str, str | None] = {}
    if vm:
        for base in (vm_bin, vm_bridge):
            for p in sorted(base.rglob("*")) if base.is_dir() else []:
                if p.is_file() and "__pycache__" not in p.parts:
                    rows[repo_name_of_deployed(p, vm_bin, vm_bridge)] = sha256(p)
        ws = sorted(vm_wheel_dir.glob("*.whl")) if vm_wheel_dir.is_dir() else []
        wheel = ws[0] if ws else None
    else:
        for rel in repo_files(root):
            p = root / rel
            rows[rel] = sha256(p) if p.is_file() else None
    rows[WHEEL_ROW] = sha256(wheel) if wheel and wheel.is_file() else None
    return rows


# ── 題目表 ──────────────────────────────────────────────────────────────────────────────────────

def staged_rows(staged: pathlib.Path) -> dict[str, str | None]:
    rows: dict[str, str | None] = {}
    for b in STAGED_BANKS:
        rows[b] = tree_sha(staged / b) if (staged / b).is_dir() else None
    for f in STAGED_FILES:
        rows[f] = sha256(staged / f) if (staged / f).is_file() else None
    return rows


# ── 表的讀寫與比對 ──────────────────────────────────────────────────────────────────────────────

def parse_table(text: str, markers: tuple[str, str] = TOOLS) -> dict[str, str]:
    m = re.search(re.escape(markers[0]) + r"(.*?)" + re.escape(markers[1]), text, re.S)
    if not m:
        raise SystemExit(f"找不到 {markers[0]} … {markers[1]}")
    rows: dict[str, str] = {}
    for line in m.group(1).splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] and not cells[0].startswith(("檔案", "名稱", "---")):
            rows[cells[0]] = cells[1]
    return rows


def render_table(rows: dict[str, str | None], head: str) -> str:
    lines = [f"| {head} | sha256 |", "|---|---|"]
    for name in sorted(rows):
        lines.append(f"| `{name}` | `{rows[name] or PLACEHOLDER}` |")
    return "\n".join(lines)


def fill(text: str, rows: dict[str, str | None], markers: tuple[str, str], head: str) -> str:
    pat = re.compile(re.escape(markers[0]) + r".*?" + re.escape(markers[1]), re.S)
    if not pat.search(text):
        raise SystemExit(f"找不到 {markers[0]} … {markers[1]}")
    return pat.sub(lambda _m: f"{markers[0]}\n{render_table(rows, head)}\n{markers[1]}", text)


def outside_tables(text: str) -> str:
    """去掉兩張表之後的正文（凍結時要手填的占位字：例如 Vacant 的來源 commit）。"""
    for b, e in (TOOLS, STAGED):
        text = re.sub(re.escape(b) + r".*?" + re.escape(e), "", text, flags=re.S)
    return text


def check(table: dict[str, str], actual: dict[str, str | None], skip: tuple[str, ...] = ()) -> list[str]:
    """skip：表裡有、但這個環境不檢查的列（VM 上＝本機專用的檔案）。"""
    bad: list[str] = []
    for name, want in table.items():
        if name in skip:
            continue
        if name not in actual:
            bad.append(f"{name}: 表上有、這個環境找不到這個檔（沒佈署？檔案清單變了？）")
        elif want == PLACEHOLDER or not re.fullmatch(r"[0-9a-f]{64}", want):
            bad.append(f"{name}: 表上寫的不是 sha256（{want!r}）——還沒凍結？")
        elif actual[name] is None:
            bad.append(f"{name}: 檔案不存在")
        elif actual[name] != want:
            bad.append(f"{name}: sha256 不同（表 {want[:12]}… ≠ 檔案 {str(actual[name])[:12]}…）")
    for name in actual:
        if name not in table and name not in skip:
            bad.append(f"{name}: 檔案在（清單／佈署）裡、表上沒有這一列")
    return bad


# ── wheel 對 git ────────────────────────────────────────────────────────────────────────────────

def wheel_mismatches(wheel: pathlib.Path, tree: dict[str, bytes]) -> dict:
    """wheel 裡的 `vacant_network/…` 與 git 樹（{路徑: 位元組}）逐檔比；多、缺、不同各列出來。"""
    z = zipfile.ZipFile(wheel)
    names = [n for n in z.namelist() if n.startswith("vacant_network/") and not n.endswith("/") and "__pycache__" not in n]
    return {"wheel": len(names), "git": len(tree), "differ": sorted(n for n in names if tree.get(n) != z.read(n)),
            "missing_in_wheel": sorted(set(tree) - set(names))}


def git_tree(ref: str, repo: pathlib.Path) -> dict[str, bytes]:
    raw = subprocess.run(["git", "-C", str(repo), "archive", ref, "vacant_network"], capture_output=True, check=True).stdout
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        for m in t:
            if m.isfile() and "__pycache__" not in m.name and not m.name.endswith(".pyc"):
                out[m.name] = t.extractfile(m).read()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fill", type=pathlib.Path)
    g.add_argument("--check", type=pathlib.Path)
    g.add_argument("--wheel-vs-git", type=pathlib.Path, dest="wheel_vs_git")
    ap.add_argument("--git-ref", default="HEAD")
    ap.add_argument("--repo", type=pathlib.Path, default=HERE.parents[1])
    ap.add_argument("--wheel", type=pathlib.Path)
    ap.add_argument("--staged", type=pathlib.Path, help="題目 staged 目錄（本機＝scratchpad 那份；VM 上預設 /srv/eval/staged）")
    ap.add_argument("--vm", action="store_true")
    ap.add_argument("--root", type=pathlib.Path, default=HERE)
    ap.add_argument("--vm-bin", type=pathlib.Path, default=pathlib.Path("/opt/eval/bin"))
    ap.add_argument("--vm-bridge", type=pathlib.Path, default=pathlib.Path("/opt/eval/bridge/ops/eval"))
    ap.add_argument("--vm-wheel-dir", type=pathlib.Path, default=pathlib.Path("/opt/eval/wheel"))
    a = ap.parse_args(argv)
    if a.wheel_vs_git:
        res = wheel_mismatches(a.wheel_vs_git, git_tree(a.git_ref, a.repo))
        ok = not res["differ"] and not res["missing_in_wheel"] and res["wheel"] == res["git"]
        print(f"wheel vacant_network/: {res['wheel']} files; git {a.git_ref}: {res['git']} files; differ {len(res['differ'])}; "
              f"missing in wheel {len(res['missing_in_wheel'])} -> {'SAME' if ok else 'NOT THE SAME'}")
        for n in (res["differ"] + res["missing_in_wheel"])[:20]:
            print("  ", n)
        return 0 if ok else 1
    staged = a.staged or (pathlib.Path("/srv/eval/staged") if a.vm else None)
    tools = tool_rows(a.root, a.wheel, vm=a.vm, vm_bin=a.vm_bin, vm_bridge=a.vm_bridge, vm_wheel_dir=a.vm_wheel_dir)
    stg = staged_rows(staged) if staged else None
    if a.fill:
        text = a.fill.read_text(encoding="utf-8")
        text = fill(text, tools, TOOLS, "檔案（相對於 `ops/colab_interactive_20261001/`）")
        missing = [k for k, v in tools.items() if v is None]
        if stg is not None:
            text = fill(text, stg, STAGED, "名稱（題庫＝目錄樹雜湊；其餘＝檔案）")
            missing += [k for k, v in stg.items() if v is None]
        a.fill.write_text(text, encoding="utf-8")
        left = outside_tables(text).count(PLACEHOLDER)
        print(f"filled {len(tools) + len(stg or {}) - len(missing)} rows in {a.fill}" + (f"; STILL PLACEHOLDER: {missing}" if missing else "")
              + (f"; {left} placeholder(s) outside the tables — fill by hand (e.g. the Vacant source commit)" if left else ""))
        return 1 if missing else 0
    text = a.check.read_text(encoding="utf-8")
    bad = check(parse_table(text, TOOLS), tools, skip=LOCAL_ONLY if a.vm else ())
    n = len(parse_table(text, TOOLS))
    if stg is not None:
        bad += [f"staged/{b}" for b in check(parse_table(text, STAGED), stg)]
        n += len(parse_table(text, STAGED))
    for line in outside_tables(text).splitlines():
        if PLACEHOLDER in line:
            bad.append(f"表以外還有沒填的占位字：{line.strip()[:100]}")
    for b in bad:
        print("MISMATCH", b)
    print(f"checked {n} rows ({'VM' if a.vm else 'repo'}): {'OK' if not bad else str(len(bad)) + ' problem(s)'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
