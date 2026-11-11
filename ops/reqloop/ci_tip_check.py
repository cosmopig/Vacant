"""r1399（2026-11-10）：CI tip 收口機械檢查（vq-el4.87）。

把 NOW.md 下一步 #1「下輪開頭一次讀取三分支現 tip 之 per-sha CI json 並收口
（綠＝收口最終證據、紅＝查因；不 poll）」機械化為單一唯讀指令。

為什麼有此檢查（本輪實證的假綠燈洞，H-0 同構：綠燈來自沒量該量的；
I-4：未測量不是通過）：worker/argon 的 per-sha CI 跑在舊祖先
（bb6de7a4/062cd433）上，而該祖先..tip 的 diff 含非簿記檔
（tests/test_reqloop_freeze_check.py）——舊做法「LATEST 綠→收口」對這兩支
不成立；真正成立的是「tip 與 qwen27b tip 之 root tree 恆等（git 內容定址
＝位元組恆等）＋qwen27b tip 之綠 CI 祖先僅差 4 簿記檔」。此區分（自體綠／
簿記延展／peer tree 恆等／未測量）此前無任何機械檢查，全靠散文推斷。

判定（逐分支）：
  TIP_GREEN     tip 有 per-sha json 且綠（green 真＋passed int>0＋failed int==0＋
                errors int==0；r1405 起計數須嚴格 int 且 passed>0——零通過空記錄／
                json bool 計數皆非綠，I-4：未測量不是通過）
  RED           tip 有 per-sha json 但紅——peer 恆等救不了自體紅
  COVERED       tip 無 per-sha，但存在綠 CI 祖先 G（按 commit 時間取最新），
                且 diff G..tip 全部落在簿記集（見下）
  PEER_COVERED  自體未覆蓋，但另一分支 tip 已收口（TIP_GREEN／COVERED）
                且兩 tip 之 root tree hash 恆等
  NO_COVERAGE   存在綠 CI 祖先但自體 diff 含非簿記檔、且無已收口 peer
                ——tip 的碼改動未被任何綠 CI 測量＝缺口（fail-closed，非 UNKNOWN）
  UNKNOWN       無 per-sha json、無綠 CI 祖先、無已收口 peer（未測量≠通過，亦≠紅）

簿記集（diff 中允許的檔案）：STATE.md、NOW.md、ops/STATE.md、ops/loop/NOW.md。
任何產品碼／測試碼檔案皆非簿記。

整體判定：全分支 ∈ {TIP_GREEN, COVERED, PEER_COVERED} → CI_TIP_OK rc=0；
任一 RED／NO_COVERAGE → CI_TIP_BROKEN rc=1；否則（任一 UNKNOWN）→
CI_TIP_UNKNOWN rc=2。BROKEN 優先於 UNKNOWN（有具體缺口比「無數據」更該亮紅）。
零分支輸入（量零分支）→ CI_TIP_BROKEN（vacuous）rc=1——all([]) 恆真；「移除全部測量
對象反而得 OK」是空集綠燈（r1413，vq-el4.9x；I-4 未測量不是通過，r1272 空檔 vacuous／
r1334 零格同族；負控制見 tests/test_reqloop_ci_tip_check.py 負控 (i)）。

紀律：只讀（ci/<sha>.json、ci/state.json、git 只讀子命令）；state.json 一次
讀取、僅加「在跑」註記——在跑≠已綠，不得升格為收口證據；不 poll。
損毀 json 跳過不計入（I-4）。git 命令：rev-parse --verify／rev-parse ^{tree}／
cat-file -e／merge-base --is-ancestor／log -1 --format=%ct／diff --name-only。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

BOOKKEEPING = frozenset({"STATE.md", "NOW.md", "ops/STATE.md", "ops/loop/NOW.md"})
_SHA40 = re.compile(r"^[0-9a-f]{40}$")

DEFAULT_CI_DIR = Path("/home/user1/dev/ops/ci")
DEFAULT_BRANCHES: dict[str, str] = {
    "auto/qwen27b": "/home/user1/dev/Vacant",
    "auto/worker": "/home/user1/dev/wt/worker",
    "auto/argon": "/home/user1/dev/wt/argon",
}

VERDICT_OK = "CI_TIP_OK"
VERDICT_BROKEN = "CI_TIP_BROKEN"
VERDICT_UNKNOWN = "CI_TIP_UNKNOWN"
_CLOSED = ("TIP_GREEN", "COVERED", "PEER_COVERED")


def run_git(wt: Path, *args: str) -> tuple[int, str]:
    """git 只讀子命令（可被測試 monkeypatch）。超時／缺 git → rc=127 不崩潰。"""
    try:
        p = subprocess.run(("git", "-C", str(wt), *args),
                           capture_output=True, text=True, timeout=30)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, f"git 不可用: {e}"


def load_ci_jsons(ci_dir: Path) -> dict[str, dict]:
    """ci/<40hex>.json → {sha: record}；LATEST_*／state.json／損毀 json 跳過（I-4）。"""
    out: dict[str, dict] = {}
    if not ci_dir.is_dir():
        return out
    for p in sorted(ci_dir.glob("*.json")):
        if not _SHA40.match(p.stem):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            out[p.stem] = d
    return out


def _is_int(v: Any) -> bool:
    """嚴格 int（排除 bool——json true/false 非計數；False==0 型混淆不得讀成零）。"""
    return isinstance(v, int) and not isinstance(v, bool)


def is_green(rec: dict[str, Any]) -> bool:
    """綠＝green 真 且 passed 為 int>0 且 failed 為 int==0 且 errors 為 int==0。

    r1405（vq-el4.90）收緊：r1399 初版只驗 green／failed／errors、不驗 passed、計數不驗型——
    記錄 {green:true, passed:0, failed:0, errors:0}（零通過＝未測量任何測試）被讀成綠、
    {failed:false}（json bool，False==0）亦被讀成零失敗＝假綠燈（I-4「a suite that
    reported zero tests fails」、r1272 空檔 vacuous／r1296 null-sha 同族；負控 (h) RED
    實證）。收緊後：passed 缺欄位／錯型／≤0＝非綠；failed／errors 缺欄位／錯型＝非綠
    （fail-closed，I-4：未測量不是通過）。live 記錄 passed≈5145（int）不受影響。"""
    return (
        rec.get("green") is True
        and _is_int(rec.get("passed")) and rec["passed"] > 0
        and _is_int(rec.get("failed")) and rec["failed"] == 0
        and _is_int(rec.get("errors")) and rec["errors"] == 0
    )


def _tip(wt: Path, branch: str) -> str | None:
    rc, out = run_git(wt, "rev-parse", "--verify", branch)
    if rc != 0:
        return None
    lines = [l for l in out.splitlines() if l.strip()]
    return lines[-1] if lines else None


def _tip_tree(wt: Path, ref: str) -> str | None:
    rc, out = run_git(wt, "rev-parse", f"{ref}^{{tree}}")
    if rc != 0:
        return None
    lines = [l for l in out.splitlines() if l.strip()]
    return lines[-1] if lines else None


def latest_green_ancestor(wt: Path, branch: str, ci: dict[str, dict]) -> tuple[int, str] | None:
    """branch tip 的祖先中、有綠 CI 記錄者，按 commit 時間取最新（非 mtime／遍歷序）。"""
    best: tuple[int, str] | None = None
    for sha, rec in ci.items():
        if not is_green(rec):
            continue
        rc, _ = run_git(wt, "cat-file", "-e", f"{sha}^{{commit}}")
        if rc != 0:
            continue
        rc, _ = run_git(wt, "merge-base", "--is-ancestor", sha, branch)
        if rc != 0:
            continue
        rc, out = run_git(wt, "log", "-1", "--format=%ct", sha)
        if rc != 0:
            continue
        lines = [l for l in out.splitlines() if l.strip()]
        if not lines or not lines[-1].isdigit():
            continue
        ts = int(lines[-1])
        if best is None or ts > best[0]:
            best = (ts, sha)
    return best


def _diff_names(wt: Path, a: str, b: str) -> list[str] | None:
    rc, out = run_git(wt, "diff", "--name-only", a, b)
    if rc != 0:
        return None
    return [l for l in out.splitlines() if l.strip()]


def _running_note(ci_dir: Path, branch: str) -> str | None:
    """state.json 一次讀取：running==branch → 註記（在跑≠已綠，不改判定）。"""
    try:
        d = json.loads((ci_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(d, dict) and d.get("running") == branch:
        return "CI 在跑（state.json 一次讀取、不 poll；在跑≠已綠）"
    return None


def evaluate(ci_dir: Path, branch_wts: dict[str, Path]) -> dict[str, Any]:
    """三分支收口判定（唯一入口）。返回 {branches:{...}, verdict, rc}。

    r1413（vq-el4.9x）收緊：零分支輸入＝量零分支 → BROKEN（vacuous）rc=1，fail-closed。
    舊碼 all([]) 恆真 → CI_TIP_OK rc=0＝空集綠燈（I-4 未測量不是通過，r1272 空檔
    vacuous／r1334 零格同族；移除全部測量對象把判定從 UNKNOWN 升成 OK＝H-0「綠燈
    來自沒量該量的」；RED 證據＝tests/test_reqloop_ci_tip_check.py 負控 (i)）。
    其餘判定（TIP_GREEN／COVERED／PEER_COVERED／RED／UNKNOWN 與聚合口徑）逐位不變。"""
    if not branch_wts:
        return {
            "branches": {},
            "verdict": VERDICT_BROKEN,
            "rc": 1,
            "evidence": [
                "vacuous: zero branches —— 檢查量零分支；I-4 未測量不是通過（r1413，vq-el4.9x）"
            ],
        }
    ci = load_ci_jsons(ci_dir)
    results: dict[str, dict[str, Any]] = {}
    had_green_ancestor: dict[str, bool] = {}
    self_covered: dict[str, bool] = {}

    # 遍歷 1：tip＋自體判定（TIP_GREEN／RED／COVERED／未覆蓋）
    for branch, wt in branch_wts.items():
        res: dict[str, Any] = {"branch": branch, "tip": None,
                               "verdict": None, "evidence": []}
        tip = _tip(wt, branch)
        res["tip"] = tip
        if tip is None:
            res["evidence"].append(f"tip 不可解析（git rev-parse {branch} 失敗）")
            had_green_ancestor[branch] = False
            self_covered[branch] = False
            results[branch] = res
            continue
        rec = ci.get(tip)
        if rec is not None:
            if is_green(rec):
                res["verdict"] = "TIP_GREEN"
                res["evidence"].append(
                    f"per-sha {tip[:12]} green（passed={rec.get('passed')} "
                    f"failed={rec.get('failed')} skipped={rec.get('skipped')}）")
            else:
                res["verdict"] = "RED"
                res["evidence"].append(
                    f"per-sha {tip[:12]} 非綠（green={rec.get('green')} "
                    f"failed={rec.get('failed')} errors={rec.get('errors')}）→ 查因")
            had_green_ancestor[branch] = rec is not None and is_green(rec)
            self_covered[branch] = res["verdict"] == "TIP_GREEN"
        else:
            g = latest_green_ancestor(wt, branch, ci)
            if g is None:
                had_green_ancestor[branch] = False
                self_covered[branch] = False
                res["evidence"].append("無 per-sha、無綠 CI 祖先")
            else:
                had_green_ancestor[branch] = True
                ts, gsha = g
                files = _diff_names(wt, gsha, tip)
                if files is None:
                    self_covered[branch] = False
                    res["evidence"].append(f"綠祖先 {gsha[:12]} 存在但 diff 不可解析")
                else:
                    bad = [f for f in files if f not in BOOKKEEPING]
                    if bad:
                        self_covered[branch] = False
                        res["evidence"].append(
                            f"綠祖先 {gsha[:12]}（ct={ts}）..tip diff 含非簿記檔: {bad}")
                    else:
                        self_covered[branch] = True
                        res["verdict"] = "COVERED"
                        res["evidence"].append(
                            f"綠祖先 {gsha[:12]}（ct={ts}）..tip diff 純簿記 "
                            f"{len(files)} 檔: {sorted(files)}")
        results[branch] = res

    # 遍歷 2：peer tree 恆等（僅自體未收口者；peer 必須是 TIP_GREEN／COVERED）
    for branch, res in results.items():
        if res["verdict"] is not None:
            continue
        tip = res["tip"]
        if tip is None:
            continue
        t1 = _tip_tree(branch_wts[branch], tip)
        if not t1:
            continue
        for other, ores in results.items():
            if other == branch or ores["verdict"] not in ("TIP_GREEN", "COVERED"):
                continue
            t2 = _tip_tree(branch_wts[other], ores["tip"])
            if t2 and t1 == t2:
                res["verdict"] = "PEER_COVERED"
                res["evidence"].append(
                    f"peer={other}@{ores['tip'][:12]}（{ores['verdict']}）"
                    f"root tree 恆等 {t1[:12]}…（內容定址＝位元組恆等）")
                break

    # 遍歷 3：未判定者 → NO_COVERAGE（有綠 CI 但沒測到 tip 的碼）或 UNKNOWN
    for branch, res in results.items():
        if res["verdict"] is None:
            if had_green_ancestor.get(branch):
                res["verdict"] = "NO_COVERAGE"
                res["evidence"].append(
                    "存在綠 CI 祖先但 diff 含非簿記檔且無已收口 peer"
                    "＝tip 的碼改動未被任何綠 CI 測量（fail-closed）")
            else:
                res["verdict"] = "UNKNOWN"
                res["evidence"].append("未測量（非紅燈；I-4：未測量不是通過）")

    # 註記：state.json 一次讀取（不改判定）
    for branch, res in results.items():
        note = _running_note(ci_dir, branch)
        if note:
            res["evidence"].append(note)

    verdicts = [r["verdict"] for r in results.values()]
    if all(v in _CLOSED for v in verdicts):
        overall, rc = VERDICT_OK, 0
    elif any(v in ("RED", "NO_COVERAGE") for v in verdicts):
        overall, rc = VERDICT_BROKEN, 1
    else:
        overall, rc = VERDICT_UNKNOWN, 2

    return {"branches": results, "verdict": overall, "rc": rc}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="CI tip 收口機械檢查（唯讀、一次讀取、不 poll）")
    ap.add_argument("--ci-dir", default=str(DEFAULT_CI_DIR),
                    help="CI 結果目錄（預設 ~/dev/ops/ci）")
    ap.add_argument("--branches", default=None,
                    help='JSON {branch: worktree_path}；預設三分支（qwen27b/worker/argon）')
    args = ap.parse_args(argv)
    if args.branches:
        branch_wts = {k: Path(v) for k, v in
                      json.loads(args.branches).items()}
    else:
        branch_wts = {k: Path(v) for k, v in DEFAULT_BRANCHES.items()}
    res = evaluate(Path(args.ci_dir), branch_wts)
    print("ci_tip_check（r1399，vq-el4.87）：CI tip 收口機械檢查"
          "（唯讀、一次讀取、不 poll）")
    for branch in branch_wts:
        r = res["branches"][branch]
        tip = r["tip"] if r["tip"] else "n/a"
        print(f"  {branch}\t{tip[:12]}\t{r['verdict']}")
        for e in r["evidence"]:
            print(f"      - {e}")
    for e in res.get("evidence", []):  # 頂層證據（r1413 vacuous：零分支＝量零分支）
        print(f"  - {e}")
    print(f"VERDICT: {res['verdict']}")
    return res["rc"]


if __name__ == "__main__":
    raise SystemExit(main())
