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
import hashlib
import json
import pathlib
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from vacant.codebench import LCB_BANKS, LiveCodeBenchLoader  # noqa: E402

PROBE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "lcb_probe_solutions.json"
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
    probes = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    covered = [r["task_id"] for r in records if r["task_id"] in probes]
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
        "probe_coverage": f"{len(covered)}/{len(records)}",
        "probe_task_ids": sorted(covered),
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
