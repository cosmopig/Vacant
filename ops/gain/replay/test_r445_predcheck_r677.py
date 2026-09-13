#!/usr/bin/env python3
"""round677：`r445_predcheck.py` 的植入缺陷測試（判準 CRITERION_20260903_R677 §三 Q0–Q8）。

零 API、唯讀 r445／r444 的落盤資料（**只讀，所有變造都在 /dev/shm 的副本上**）。
每一條都要看到 FAIL 的那一面——乾淨版 PASS 不算證據（round675 M6 規則）。
rc 一律用 subprocess 實跑取得，不用「函式回傳值長得對」代替。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = HERE / "r445_predcheck.py"
DECISION = REPO / "DECISION_20260903_R445_CONFORM_BANK_EXTENSION.md"
R445 = REPO / "runs" / "g_r445_conform_mbpp_ext"
R444 = REPO / "runs" / "g_r444_conform_mbpp"
WORK = pathlib.Path("/dev/shm/r677/test")

sys.path.insert(0, str(HERE))
import conform_settle as _cs  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def ok(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"    {detail}" if detail else ""))


def run(args: list[str], env_mutant: str | None = None):
    import os
    env = dict(os.environ)
    if env_mutant:
        env["R445_PREDCHECK_MUTANT"] = env_mutant
    p = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True,
                       text=True, cwd=str(REPO), env=env)
    return p.returncode, p.stdout + p.stderr


def status_of(out: str, pe: str) -> str:
    for line in out.splitlines():
        s = line.strip()
        if s.startswith(pe + " "):
            return s.split()[1]
    return "<未印出>"


def snapshot_rows(src: pathlib.Path, dst: pathlib.Path) -> int:
    """只取解析得動的完整列（run 還活著時最後一列可能寫到一半）。"""
    good = []
    for line in src.read_text(encoding="utf-8").splitlines():
        try:
            json.loads(line)
        except Exception:
            break
        good.append(line)
    dst.write_text("\n".join(good) + "\n", encoding="utf-8")
    return len(good)


def make_fixture(name: str, terminal: bool = False) -> pathlib.Path:
    """從 r445 現況做一份靜止副本。terminal=True 時把 summary 的計數
    照 rows 覆算補齊，讓 conform_settle 的 exact 硬擋能通過（那些擋門是對的，
    我們要測的是 predcheck，不是去繞開它）。"""
    d = WORK / name
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    n = snapshot_rows(R445 / "rows.jsonl", d / "rows.jsonl")
    shutil.copy(R445 / "summary.json", d / "summary.json")
    if (R445 / "notes.jsonl").exists():
        shutil.copy(R445 / "notes.jsonl", d / "notes.jsonl")
    if terminal:
        retro_fit(d)
    return d


def retro_fit(d: pathlib.Path) -> None:
    """把 summary 的逐臂計數改成與 rows 一致，並宣告 terminal。"""
    rows = _cs.load_rows(d / "rows.jsonl")
    s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
    for arm in list(s["arms"]):
        blk = _cs.arm_block(_cs.index_by_task(rows, arm))
        s["arms"][arm].update({
            "terminal": True, "complete": True,
            "processed": blk["rows"], "accepted": blk["accepted"],
            "accepted_and_meets_demand": blk["deliv"], "leaked": blk["leaked"],
            "infra_void": 0, "calls": blk["calls_used_sum"],
        })
    s["run_terminal"] = True
    (d / "summary.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def set_calls(d: pathlib.Path, arm: str, calls: int) -> None:
    out = []
    for line in (d / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("arm") == arm:
            r["calls_used"] = calls
        out.append(json.dumps(r, ensure_ascii=False))
    (d / "rows.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    live = make_fixture("live")

    # ── Q0 乾淨跑：八條逐條印出，且不寫入 run 目錄（逐位元比對） ──────────
    before = {p.name: p.read_bytes() for p in sorted(live.iterdir())}
    rc, out = run(["--run", str(live), "--decision", str(DECISION)])
    after = {p.name: p.read_bytes() for p in sorted(live.iterdir())}
    printed = [f"P-E{i}" for i in range(1, 9) if status_of(out, f"P-E{i}") != "<未印出>"]
    ok("Q0a 八條都印出狀態", len(printed) == 8, f"印出 {len(printed)}/8")
    ok("Q0b run 目錄逐位元不變", before == after,
       f"檔案={sorted(before)} 相同={before == after}")
    ok("Q0c 未收官時 rc=0 且標明是中途快照",
       rc == 0 and "WARNING" in out and "中途快照" in out, f"rc={rc}")
    clean_status = {f"P-E{i}": status_of(out, f"P-E{i}") for i in range(1, 9)}
    print(f"      乾淨狀態: {clean_status}")

    # ── Q1 門檻與 DECISION 的綁定有牙齒 ─────────────────────────────────
    # 工具裡沒有門檻數字 ⇒ 「改門檻」的唯一形狀就是改 quote。改了就對不上 DECISION。
    rc1, out1 = run(["--run", str(live), "--decision", str(DECISION)],
                    env_mutant="M-QUOTE")     # 把 P-E4 的 quote 改成 [1.2, 1.9]
    ok("Q1 改門檻字面 ⇒ BROKEN（不是安靜用舊值）",
       status_of(out1, "P-E4") == "BROKEN" and rc1 == 2 and "不在 DECISION" in out1,
       f"P-E4={status_of(out1, 'P-E4')} rc={rc1}")

    # ── Q2 DECISION 少一列 ⇒ BROKEN（安靜量不到・型一） ──────────────────
    dec2 = WORK / "decision_no_pe5.md"
    dec2.write_text("\n".join(l for l in DECISION.read_text(encoding="utf-8").splitlines()
                              if not l.startswith("| P-E5 ")), encoding="utf-8")
    rc2, out2 = run(["--run", str(live), "--decision", str(dec2)])
    ok("Q2 DECISION 少 P-E5 那列 ⇒ BROKEN",
       status_of(out2, "P-E5") == "BROKEN" and rc2 == 2 and "找不到" in out2,
       f"P-E5={status_of(out2, 'P-E5')} rc={rc2}")

    # ── Q3 資料缺 ⇒ BROKEN（安靜量不到・型二） ──────────────────────────
    d3 = make_fixture("no_instrument")
    s3 = json.loads((d3 / "summary.json").read_text(encoding="utf-8"))
    s3.pop("instrument")
    (d3 / "summary.json").write_text(json.dumps(s3, ensure_ascii=False), encoding="utf-8")
    rc3, out3 = run(["--run", str(d3), "--decision", str(DECISION)])
    ok("Q3a summary 無 instrument ⇒ P-E7 BROKEN（不是 PASS）",
       status_of(out3, "P-E7") == "BROKEN" and rc3 == 2 and "不是通過，是量不到" in out3,
       f"P-E7={status_of(out3, 'P-E7')} rc={rc3}")

    d3b = make_fixture("no_instrument_field")
    s3b = json.loads((d3b / "summary.json").read_text(encoding="utf-8"))
    s3b["instrument"].pop("visible_stub_rejected")
    (d3b / "summary.json").write_text(json.dumps(s3b, ensure_ascii=False), encoding="utf-8")
    rc3b, out3b = run(["--run", str(d3b), "--decision", str(DECISION)])
    ok("Q3b instrument 少一個欄位 ⇒ P-E7 BROKEN",
       status_of(out3b, "P-E7") == "BROKEN" and rc3b == 2,
       f"P-E7={status_of(out3b, 'P-E7')}")

    d3c = make_fixture("no_arm")
    s3c = json.loads((d3c / "summary.json").read_text(encoding="utf-8"))
    s3c["arms"].pop("OFF")
    (d3c / "summary.json").write_text(json.dumps(s3c, ensure_ascii=False), encoding="utf-8")
    rc3c, out3c = run(["--run", str(d3c), "--decision", str(DECISION)])
    ok("Q3c 少一臂 ⇒ BROKEN（P-E8 沒有分母就不准判）",
       rc3c == 2 and "OFF" in out3c, f"rc={rc3c}")

    # ── Q4 判定有牙齒：值落在帶外 ⇒ MISS ────────────────────────────────
    d4 = make_fixture("calls_out_of_band")
    set_calls(d4, "CONFORM", 1)          # c/task=1.00，落在 [1.2,1.6] 之外
    rc4, out4 = run(["--run", str(d4), "--decision", str(DECISION)])
    ok("Q4 c/task=1.00 落在 [1.2,1.6] 外 ⇒ MISS（不是 HIT）",
       status_of(out4, "P-E4") == "MISS", f"P-E4={status_of(out4, 'P-E4')}")

    # ── Q5 突變：band 判定是裝飾品 ⇒ Q4 必須抓到 ────────────────────────
    rc5, out5 = run(["--run", str(d4), "--decision", str(DECISION)],
                    env_mutant="M-DECOR")
    ok("Q5 突變（verdict 恆 HIT）之下 Q4 會翻成 HIT ⇒ Q4 有牙齒",
       status_of(out5, "P-E4") == "HIT",
       f"突變下 P-E4={status_of(out5, 'P-E4')}（乾淨下是 MISS）")

    # ── Q6 中止線有牙齒 ─────────────────────────────────────────────────
    d6 = make_fixture("calls_abort")
    set_calls(d6, "CONFORM", 5)          # c/task=5.00 > 4.5
    rc6, out6 = run(["--run", str(d6), "--decision", str(DECISION)])
    ok("Q6 c/task=5.00 > 4.5 ⇒ ABORT_TRIGGERED",
       status_of(out6, "P-E4") == "ABORT_TRIGGERED" and "triggered=True" in out6,
       f"P-E4={status_of(out6, 'P-E4')}")

    # ── Q7 --final 不准帶著沒判的預測過關 ───────────────────────────────
    term = make_fixture("terminal", terminal=True)
    rc7a, out7a = run(["--run", str(term), "--decision", str(DECISION), "--final"])
    ok("Q7a --final + 缺併庫（P-E2/E3 NOT_EVALUATED）⇒ rc≠0",
       rc7a != 0 and "收官不准帶著沒判的預測過關" in out7a,
       f"rc={rc7a} NOT_EVALUATED={sum(1 for i in (2, 3) if status_of(out7a, f'P-E{i}') == 'NOT_EVALUATED')}")
    rc7b, out7b = run(["--run", str(live), "--decision", str(DECISION), "--final"])
    ok("Q7b --final + run 未收官 ⇒ rc≠0",
       rc7b != 0 and "還沒收官" in out7b, f"rc={rc7b}")

    # ── Q7c 併庫接上之後八條全判得出來（端到端，含 P-E2/P-E3） ──────────
    pooled_json = WORK / "pooled_deliv.json"
    pp = subprocess.run(
        [sys.executable, str(HERE / "pooled_paired_ci.py"),
         "--stratum", f"r444={R444}", "--stratum", f"r445={term}",
         "--a-arm", "CONFORM", "--b-arm", "OFF5", "--key", "deliv",
         "--json", str(pooled_json)],
        capture_output=True, text=True, cwd=str(REPO))
    if pooled_json.exists():
        rc7c, out7c = run(["--run", str(term), "--decision", str(DECISION),
                           "--final", "--pooled-json", str(pooled_json)])
        judged = sum(1 for i in range(1, 9)
                     if status_of(out7c, f"P-E{i}") in
                     ("HIT", "MISS", "ABORT_TRIGGERED"))
        ok("Q7c 併庫接上 ⇒ 八條全判得出來且 rc=0",
           judged == 8 and rc7c == 0, f"判得出來 {judged}/8 rc={rc7c}")
        # 推翻條件（判準 §四）：值必須是轉述，不是重算
        pj = json.loads(pooled_json.read_text(encoding="utf-8"))
        want_hw = (pj["pooled"]["ci95_hi_pp"] - pj["pooled"]["ci95_lo_pp"]) / 2.0
        got = json.loads(subprocess.run(
            [sys.executable, str(TOOL), "--run", str(term), "--decision", str(DECISION),
             "--pooled-json", str(pooled_json), "--json", str(WORK / "o.json")],
            capture_output=True, text=True, cwd=str(REPO)).stdout and
            (WORK / "o.json").read_text(encoding="utf-8"))
        vals = {r["id"]: r.get("value") for r in got["predictions"]}
        ok("Q7d P-E2/P-E3 是轉述 pooled_paired_ci 的輸出，不是重算",
           vals["P-E2"] == want_hw and vals["P-E3"] == float(pj["pooled"]["n_discordant"]),
           f"半寬 {vals['P-E2']} vs {want_hw}；n_d {vals['P-E3']} vs {pj['pooled']['n_discordant']}")
    else:
        ok("Q7c 併庫接上 ⇒ 八條全判得出來", False,
           f"pooled_paired_ci 沒產出 JSON：rc={pp.returncode} {pp.stdout[-300:]}")

    # ── Q9 round686：併庫 JSON 的 key 必須是 deliv ────────────────────
    # 缺陷：`pooled_paired_ci.py --key` 的預設是 `meets_demand`（回歸相容），
    # 忘了帶旗標就會產出另一種語意的併庫結果，而 P-E2/P-E3 照吃不誤、rc=0、零警告。
    # `meets_demand` 單獨算會把 CONFORM **拒交掉**、但其實會通過的題也算成功
    # ⇒ 系統性高估拒交臂。事前口徑是 deliv（CRITERION_20260903_R667 §40）。
    # 判準不只寫 rc：要看到 P-E2/P-E3 兩條都被標成 BROKEN。
    wrong_json = WORK / "pooled_WRONGKEY.json"
    subprocess.run(
        [sys.executable, str(HERE / "pooled_paired_ci.py"),
         "--stratum", f"r444={R444}", "--stratum", f"r445={term}",
         "--a-arm", "CONFORM", "--b-arm", "OFF5",      # 故意不帶 --key
         "--json", str(wrong_json)],
        capture_output=True, text=True, cwd=str(REPO))
    wk = json.loads(wrong_json.read_text(encoding="utf-8"))["key"]
    rc9, out9 = run(["--run", str(term), "--decision", str(DECISION),
                     "--final", "--pooled-json", str(wrong_json)])
    broken = [i for i in (2, 3) if status_of(out9, f"P-E{i}") == "BROKEN"]
    ok("Q9a 併庫 JSON 的 key 不是 deliv ⇒ P-E2/P-E3 都 BROKEN 且 rc≠0（不是安靜換一個量）",
       wk == "meets_demand" and broken == [2, 3] and rc9 != 0,
       f"產物 key={wk} BROKEN={broken} rc={rc9}")
    ok("Q9b BROKEN 訊息指名量錯了什麼，不只說失敗",
       "不是 'deliv'" in out9 and "量錯了東西" in out9,
       out9.strip()[:100])

    # ── Q8 r444 口徑的鍵要明講不適用，且鍵名真的存在於 conform_settle ────
    real = _cs.settle(R445, live / "rows.jsonl", "CONFORM", "OFF5", "OFF")["verdicts"]
    import r445_predcheck as _pc
    missing = [k for k in _pc.STALE_R444_KEYS if k not in real]
    ok("Q8a 標成不適用的鍵在 conform_settle 真的存在（不是打錯字）",
       not missing, f"對不上的鍵={missing}")
    ok("Q8b 乾淨輸出有印出 NOT_APPLICABLE 區塊",
       "不適用" in out and "P-C2_le_2.0" in out)
    # 這一條是本輪存在的理由：r444 的鍵與 r445 的判定在同一份資料上給出不同答案
    ok("Q8c 假綠燈是真的：P-C2_le_2.0 對 c/task=1.00 說 true，P-E4 說 MISS",
       (1.00 <= 2.0) and status_of(out4, "P-E4") == "MISS",
       "同一個 c/task=1.00，舊鍵通過、新判定沒中")

    n_pass = sum(1 for _, c, _ in RESULTS if c)
    print(f"\n{n_pass}/{len(RESULTS)} PASS")
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
