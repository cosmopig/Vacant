"""LCB bank 驗收器（R440 v2 擴建；零 API 呼叫、只讀檔）。

這支在架構裡承重什麼：`build_lcb_bank.py` 負責「造」，這支負責「證明造出來的
東西可以拿去跑」。R440T 已經記過一次教訓——量具覆蓋率 12/91 是沉默上限，
`instrument N/N` 被讀成綠燈，結果兩題（`lcb_3763`／`lcb_3613`）對任何解都
保證失敗。所以驗收要**逐題**做，而且要把「沒驗到的部分」明講出來。

檢查項目（每一項都是 fail-closed，任何一題不過就整體不過）：
  A. 載入器接得上：`LiveCodeBenchLoader(version=...)` sha256／題數／schema 全驗
  B. arity：prompt 裡 `def fn(params)` 的參數個數 == 每一筆測資 args 的長度
     （visible ＋ hidden 都驗）；entry_point 與 def 名字一致
  C. 篡改 fail-closed：改一個 byte 後載入器必須拒收
  D. 量具覆蓋率：多少題有 `lcb_probe_solutions.json` 的手寫參考解（分母要報）
  E. 浮點截斷偵測：expected 是浮點且只存到小數 5 位 ⇒ 與檢查式 1e-6 容忍度
     矛盾（R440T 的兩題就是這樣），列出來當事前排除候選——**只報告不排除**

用法：
    python3 ops/gain/verify_lcb_bank.py --version v2
    python3 ops/gain/verify_lcb_bank.py --version v1 --compare v2
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from vacant.codebench import LCB_BANKS, LiveCodeBenchLoader  # noqa: E402

PROBE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "lcb_probe_solutions.json"
# ⚠ round735（R467）：`PROBE_PATH` 這個名字**只**代表「v1/v2 的手寫解檔」，
#   已經**不再**是算 `probe_coverage` 用的路徑（`tests/test_lcb_bank_v2.py:20` 匯入它，
#   所以名字保留）。原本的缺陷：它被直接拿去算覆蓋率、不隨 `--version` 改，
#   於是 `--version v3` 恆印 `0/189`（v3 的手寫解在 `lcb_v3_probe_solutions.json`），
#   round734 差點把那個 0 讀成「v3 沒驗過尺」——缺陷在報告工具，不在量具。
#
#   修法**不是**在這裡再抄一份 version→檔案 的對照（那只是把漂移搬個位置），
#   而是從 `gain_run.py` **逐字取出它自己在用的那份**：bank→version 的明表、
#   以及 `_canonical_solutions` 裡 `_default = ...` 那個條件式。日後那邊再加一個
#   bank，這支要嘛跟著對、要嘛具名地吵，不會安靜錯。


class ProbeWiringError(RuntimeError):
    """接線壞掉：跟「覆蓋率量到 0」必須分得開（前者是沒量到，後者是量到 0）。"""


def _gain_run():
    return importlib.import_module("ops.gain.gain_run")


def _gain_run_src() -> str:
    return (pathlib.Path(__file__).resolve().parent / "gain_run.py").read_text(encoding="utf-8")


def _bank_version_table() -> dict[str, str]:
    """逐字取出 `gain_run.py` 裡那個 bank→version 明表再 literal_eval。

    memory 鐵律：驗程式碼在什麼條件為真，要用 `ast.get_source_segment` 逐字取出
    真運算式，不准自己改寫一份。
    """
    src = _gain_run_src()
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seg = ast.get_source_segment(src, node)
        if not seg:
            continue
        try:
            d = ast.literal_eval(seg)
        except Exception:
            continue
        if (isinstance(d, dict) and d
                and all(isinstance(k, str) and isinstance(v, str) for k, v in d.items())
                and all(k.startswith("lcb") for k in d)
                and set(d.values()) <= set(LCB_BANKS)):
            hits.append(d)
    uniq = {json.dumps(d, sort_keys=True) for d in hits}
    if len(uniq) != 1:
        raise ProbeWiringError(
            f"PROBE_BANK_MAP_BROKEN: gain_run.py 裡符合 bank->version 形狀的明表有 "
            f"{len(uniq)} 份，預期恰好 1 份（找到：{sorted(uniq)}）")
    return hits[0]


def bank_for_version(version: str) -> str:
    table = _bank_version_table()
    mut = os.environ.get("R467_MUTANT", "")
    if mut == "bad_inverse":
        table = {v: v for v in table.values()}      # 恆等映射：v3->v3（不是 lcb3）
    # 用之前再驗一次形狀：鍵必須是 gain_run 的 `--bank` 值（lcb*），值必須是 LCB_BANKS 的 version。
    bad = [k for k, v in table.items() if not k.startswith("lcb") or v not in LCB_BANKS]
    if bad:
        raise ProbeWiringError(
            f"PROBE_BANK_MAP_BROKEN: bank->version 明表的這些鍵不是合法 bank 名：{sorted(bad)}")
    inv: dict[str, str] = {}
    for bank, ver in table.items():
        if ver in inv:
            raise ProbeWiringError(
                f"PROBE_BANK_MAP_BROKEN: version {ver} 同時對到 {inv[ver]} 與 {bank}")
        inv[ver] = bank
    if version not in inv:
        raise ProbeWiringError(
            f"PROBE_BANK_MAP_BROKEN: gain_run.py 的明表沒有 version={version}"
            f"（有 {sorted(inv)}）——這裡**不做**預設 fallback，安靜挑一個檔比吵一聲糟")
    return inv[version]


def probe_path_for(version: str) -> pathlib.Path:
    """`gain_run._canonical_solutions` 裡 `_default = ...` 那個條件式，逐字取出後 eval。"""
    bank = bank_for_version(version)
    src = _gain_run_src()
    tree = ast.parse(src)
    expr = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_canonical_solutions":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign) and len(sub.targets) == 1
                        and isinstance(sub.targets[0], ast.Name)
                        and sub.targets[0].id == "_default"):
                    expr = ast.get_source_segment(src, sub.value)
    if expr is None:
        raise ProbeWiringError(
            "PROBE_BANK_MAP_BROKEN: gain_run._canonical_solutions 裡找不到 `_default = ...`")
    G = _gain_run()
    ns = {"LCB_PROBE_SOLUTIONS_PATH": G.LCB_PROBE_SOLUTIONS_PATH,
          "LCB_V3_PROBE_SOLUTIONS_PATH": G.LCB_V3_PROBE_SOLUTIONS_PATH,
          "bank": bank}
    # ⚠ 逐字取出的運算式可能跨行（`_default` 那個三元式就是），而 `get_source_segment`
    #   **不含**原本包住它的那層括號 ⇒ 直接 eval 會 SyntaxError。補一層括號再 eval。
    p = pathlib.Path(eval("(" + expr + ")", {"__builtins__": {}}, ns))  # noqa: S307
    mut = os.environ.get("R467_MUTANT", "")
    if mut == "hardcode_v1v2":
        p = pathlib.Path(G.LCB_PROBE_SOLUTIONS_PATH)
    elif mut == "always_v3":
        p = pathlib.Path(G.LCB_V3_PROBE_SOLUTIONS_PATH)
    return p


def resolve_probes(version: str) -> dict:
    """回傳 {bank, path, probes, consistent, error}；接線壞掉時 probes=None（不是 {}）。

    一致性擋門的兩邊**刻意不同源**（memory r695：夾具若把 B 從 A 導出，
    那條擋門結構上不可能被任何夾具看見）：
      左邊＝本檔用 `ast` 從 `_canonical_solutions` 取出的路徑再讀檔；
      右邊＝直接呼叫 `gain_run._canonical_solutions(bank=...)` 這個函式本身。
    """
    try:
        bank = bank_for_version(version)
        path = probe_path_for(version)
        probes = json.loads(path.read_text(encoding="utf-8"))
    except ProbeWiringError as e:
        return {"bank": None, "path": None, "probes": None,
                "consistent": False, "error": str(e)}
    reported = path
    if os.environ.get("R467_MUTANT", "") == "report_mismatch":
        G = _gain_run()
        other = (G.LCB_PROBE_SOLUTIONS_PATH if path.name == G.LCB_V3_PROBE_SOLUTIONS_PATH.name
                 else G.LCB_V3_PROBE_SOLUTIONS_PATH)
        reported = pathlib.Path(other)
    runner_side = _gain_run()._canonical_solutions(bank=bank)
    consistent = json.loads(pathlib.Path(reported).read_text(encoding="utf-8")) == runner_side
    err = None if consistent else (
        f"PROBE_PATH_REPORT_MISMATCH: 回報的 {reported} 的內容與 "
        f"gain_run._canonical_solutions(bank={bank!r}) 不一致")
    return {"bank": bank, "path": str(reported), "probes": probes,
            "consistent": consistent, "error": err}


_DEF_RE = re.compile(r"^def\s+(\w+)\s*\((.*)\)\s*:\s*$", re.M)


def split_params(params: str) -> list[str]:
    """頂層逗號切割（型別註記裡的 List[int]、Dict[str, int] 不能被切開）。"""
    out, depth, cur = [], 0, ""
    for ch in params:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [p for p in out if p and p not in ("/", "*")]


def signature_of(rec: dict) -> tuple[str, list[str]]:
    m = _DEF_RE.search(rec["prompt"])
    if not m:
        raise ValueError(f"{rec['task_id']}：prompt 裡找不到 def 行")
    return m.group(1), split_params(m.group(2))


def check_arity(records: list[dict]) -> tuple[int, list[str]]:
    bad: list[str] = []
    for rec in records:
        fn, params = signature_of(rec)
        if fn != rec["entry_point"]:
            bad.append(f"{rec['task_id']}：def 名 {fn} != entry_point {rec['entry_point']}")
            continue
        want = len(params)
        for kind in ("visible_tests", "hidden_tests"):
            for i, t in enumerate(rec[kind]):
                if len(t["args"]) != want:
                    bad.append(
                        f"{rec['task_id']}：{kind}[{i}] args={len(t['args'])} != 簽名 {want}"
                    )
    return len(records) - len({b.split("：")[0] for b in bad}), bad


_F5 = re.compile(r"^-?\d+\.\d{5}$")


def scan_float_truncation(records: list[dict]) -> list[dict]:
    """expected 是浮點且字面只到小數 5 位 ⇒ 可能與 1e-6 容忍度矛盾（R440T）。"""
    hits = []
    for rec in records:
        n = 0
        for kind in ("visible_tests", "hidden_tests"):
            for t in rec[kind]:
                exp = t["expected"]
                if isinstance(exp, float) and _F5.match(repr(exp)):
                    n += 1
        if n:
            hits.append({"task_id": rec["task_id"], "entry_point": rec["entry_point"],
                         "n_5dp_expected": n})
    return hits


def load_records(version: str) -> list[dict]:
    path = LCB_BANKS[version]["path"]
    return [json.loads(ln) for ln in pathlib.Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def tamper_test(version: str) -> str:
    """複製一份、改一個 byte，載入器必須拒收（不改動原檔）。"""
    src = pathlib.Path(LCB_BANKS[version]["path"])
    with tempfile.TemporaryDirectory() as d:
        dst = pathlib.Path(d) / src.name
        shutil.copy(src, dst)
        raw = bytearray(dst.read_bytes())
        raw[len(raw) // 2] = raw[len(raw) // 2] ^ 0x01
        dst.write_bytes(bytes(raw))
        try:
            LiveCodeBenchLoader(
                path=str(dst),
                expected_sha256=LCB_BANKS[version]["sha256"],
                expected_count=LCB_BANKS[version]["count"],
            )
        except ValueError as e:
            return f"拒收 ✓（{str(e)[:60]}…）"
        return "！！沒有拒收——fail-closed 破了"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v2", choices=sorted(LCB_BANKS))
    ap.add_argument("--compare", default=None, choices=sorted(LCB_BANKS))
    a = ap.parse_args()

    spec = LCB_BANKS[a.version]
    p = pathlib.Path(spec["path"])
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    loader = LiveCodeBenchLoader(version=a.version)
    tasks = list(loader.iter_tasks("verify"))
    records = load_records(a.version)

    ok_n, bad = check_arity(records)
    wiring = resolve_probes(a.version)
    probes = wiring["probes"]
    # 接線壞掉 ⇒ 覆蓋率是 **null**，不是 0/N。「沒量到」跟「量到 0」必須分得開。
    covered = None if probes is None else [r["task_id"] for r in records
                                           if r["task_id"] in probes]
    dates = sorted(r["contest_date"] for r in records)
    by_diff: dict[str, int] = {}
    by_src: dict[str, int] = {}
    for r in records:
        by_diff[r["difficulty"]] = by_diff.get(r["difficulty"], 0) + 1
        by_src[r["source_file"]] = by_src.get(r["source_file"], 0) + 1

    out = {
        "version": a.version,
        "path": str(p),
        "sha256": digest,
        "sha256_matches_pin": digest == spec["sha256"],
        "count": len(records),
        "count_matches_pin": len(records) == spec["count"],
        "loader_tasks": len(tasks),
        "arity_ok": f"{ok_n}/{len(records)}",
        "arity_failures": bad,
        "tamper_fail_closed": tamper_test(a.version),
        "probe_coverage": None if covered is None else f"{len(covered)}/{len(records)}",
        "probe_task_ids": None if covered is None else sorted(covered),
        # round735（R467）新增：把「這個數字是哪個檔算出來的」印在旁邊，
        # 下一輪不必再讀原始碼才解讀得了 `12/189`。
        "probe_solutions_path": wiring["path"],
        "probe_bank_name": wiring["bank"],
        "probe_wiring_consistent": wiring["consistent"],
        "probe_wiring_error": wiring["error"],
        "contest_date_range": [dates[0], dates[-1]] if dates else [],
        "by_difficulty": by_diff,
        "by_source_file": by_src,
        "float_5dp_suspects": scan_float_truncation(records),
    }
    if a.compare:
        other_recs = {r["task_id"]: r for r in load_records(a.compare)}
        mine = {r["task_id"]: r for r in records}
        both = sorted(set(mine) & set(other_recs))
        # 重疊的題目必須**逐欄相同**：v2 只准加題，不准偷偷改到 v1 已經跑過的題目。
        differing = [tid for tid in both
                     if json.dumps(mine[tid], sort_keys=True, ensure_ascii=False)
                     != json.dumps(other_recs[tid], sort_keys=True, ensure_ascii=False)]
        out["vs_" + a.compare] = {
            "overlap": len(both),
            "overlap_records_identical": not differing,
            "overlap_differing": differing,
            "new_here": len(set(mine) - set(other_recs)),
            "missing_here": sorted(set(other_recs) - set(mine)),
        }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    hard_fail = bad or not out["sha256_matches_pin"] or not out["count_matches_pin"] \
        or "拒收" not in out["tamper_fail_closed"] \
        or (a.compare and out["vs_" + a.compare]["overlap_differing"])
    sys.exit(1 if hard_fail else 0)


if __name__ == "__main__":
    main()
