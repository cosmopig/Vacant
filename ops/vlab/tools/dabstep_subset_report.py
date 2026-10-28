#!/usr/bin/env python3
"""dabstep_subset_report — e001-dabstep 子集統計量具（round 153，主軸 4）。

為什麼需要這支（而不是直接用 report.py）：
- ASSIGNMENT 紅線：引用的數字必須來自 REPORT.json，不是手算。report.py 是共用量具，
  產出的是**整個實驗**（所有 suite 混在一起）的 REPORT.json——但 e001-dabstep 預註冊
  分析計畫（packets/e001_dabstep_analysis.md，round 141）§6 明令**不准把 dabstep 26 對
  跟 polyglot 配對合併池化**。
- report.py 沒有 per-task/per-suite 行。預註冊計畫 §2 已事先授權 fallback：
  「若 report.py 沒有 per-task 行，就從各格 score.json 直接彙整，**並記在結論裡**」。
  本腳本就是那個 fallback 的確定性實作：同一輸入必出同一數字，另一台機器可重跑。
- 本腳本**只做統計與成本**（§2/§3/§5 的數字面）；機制診斷（zero_ran/findings/stop
  事件）是 noncode_cell_audit.py 的活；解讀照預註冊 §5，不在此處發生。

McNemar 公式與 report.py 逐字相同（binomial 雙尾精確）——同一把尺，不發明新尺。

誠實規則：
  - score.json 不存在（格子還在跑）→ pending：不進分母、不進配對、明確列出。
  - score.pass=None → infra：不進分母、明確列出（與 report.py 同義）。
  - 配對 McNemar 只算**兩臂都 scored** 的 pair；缺臂的 pair 列入 incomplete，不計入
    pairs/A_only/C_only/p 值——26 對的檢定力有限，事後補 pair 改變分母，必須可核。
  - 不讀 /srv/eval、不判內容對錯、不解讀「為什麼」。

用法：
  python3 ops/vlab/tools/dabstep_subset_report.py <exp> --suite dabstep
      [--base /srv/vlab/runs] [--arm C] [--out PATH] [--md PATH]
  python3 ops/vlab/tools/dabstep_subset_report.py --selftest

輸出 JSON：{exp, suite, arms, n_cells, n_scored, n_pending, n_infra,
            per_arm{...}, A_vs_C{pairs, A_only, C_only, mcnemar_p_two_sided,
            incomplete[]}, per_pair[...], note}
退出碼：0 正常；1 找不到任何該 suite 的 cell.json；2 selftest 失敗或輸入不可讀。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path


def mcnemar(b: int, c: int) -> float:
    # 與 /srv/vlab/bin/report.py 的 mcnemar() 逐字相同（同一把尺）。
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load_cells(base: Path, exp: str, suite: str) -> list[dict]:
    """讀 runs/<exp>/*/cell.json＋score.json，只留指定 suite。狀態分三類。"""
    root = base / exp
    if not root.is_dir():
        raise SystemExit(f"runs root not found: {root}")
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if ".infra-" in d.name:
            continue  # report.py 語義：模型崩潰重跑後保留的殘格，不算
        try:
            info = json.loads((d / "cell.json").read_text())
        except Exception:
            continue  # 沒有 cell.json（還沒開跑）——連 suite 都無法確認，不計
        if info.get("suite") != suite:
            continue
        try:
            sc = json.loads((d / "score.json").read_text())
            if sc.get("pass") is None:
                state = "infra"
                passed = None
            else:
                state = "scored"
                passed = bool(sc["pass"])
        except FileNotFoundError:
            state, passed = "pending", None
        except Exception:
            state, passed = "infra", None
        m = info.get("metrics") or {}
        out.append({
            "cell": d.name, "arm": info.get("arm"), "task": info.get("task"),
            "agent": info.get("agent"), "rep": info.get("rep"),
            "state": state, "pass": passed,
            "calls": m.get("model_calls", 0),
            "tok": m.get("input_tokens", 0) + m.get("output_tokens", 0),
            "timeout": bool(info.get("timed_out", False)),
            "wall": info.get("wall_s", 0),
            "vacant_home_bytes": info.get("vacant_home_bytes"),
        })
    return out


def report(cells: list[dict], exp: str, suite: str, other_arm: str) -> dict:
    arms = sorted({c["arm"] for c in cells})
    per_arm = {}
    for a in arms:
        cs = [c for c in cells if c["arm"] == a]
        scored = [c for c in cs if c["state"] == "scored"]
        s = sum(c["pass"] for c in scored)
        per_arm[a] = {
            "n_scored": len(scored),
            "n_pending": sum(1 for c in cs if c["state"] == "pending"),
            "n_infra": sum(1 for c in cs if c["state"] == "infra"),
            "pass": s,
            "rate": round(s / len(scored), 4) if scored else None,
            "calls_per_success": round(sum(c["calls"] for c in scored) / s, 2) if s else None,
            "tokens_per_success": round(sum(c["tok"] for c in scored) / s) if s else None,
            "timeouts": sum(c["timeout"] for c in scored),
            "mean_wall_s": round(sum(c["wall"] for c in scored) / len(scored), 1) if scored else None,
            "vacant_home_bytes_total": sum(c["vacant_home_bytes"] or 0 for c in cs),
        }
    paired = None
    per_pair = []
    if "A" in per_arm and other_arm in per_arm:
        by_key = {}
        for c in cells:
            if c["arm"] in ("A", other_arm):
                by_key.setdefault((c["task"], c["agent"], c["rep"]), {})[c["arm"]] = c
        a_only = c_only = 0
        pairs_complete = 0
        incomplete = []
        for k in sorted(by_key, key=lambda x: str(x[0])):
            v = by_key[k]
            if "A" not in v or other_arm not in v:
                missing = [a for a in ("A", other_arm) if a not in v]
                incomplete.append({"task": k[0], "missing_arms": missing})
                continue
            if v["A"]["state"] != "scored" or v[other_arm]["state"] != "scored":
                incomplete.append({"task": k[0],
                                  "states": {"A": v["A"]["state"], other_arm: v[other_arm]["state"]}})
                continue
            pairs_complete += 1
            pa, pc = v["A"]["pass"], v[other_arm]["pass"]
            if pa and not pc:
                a_only += 1
            elif pc and not pa:
                c_only += 1
            per_pair.append({
                "task": k[0], "A_pass": pa, f"{other_arm}_pass": pc,
                "A_wall": v["A"]["wall"], f"{other_arm}_wall": v[other_arm]["wall"],
                "A_tok": v["A"]["tok"], f"{other_arm}_tok": v[other_arm]["tok"],
                "A_timeout": v["A"]["timeout"], f"{other_arm}_timeout": v[other_arm]["timeout"],
                f"{other_arm}_vacant_home_bytes": v[other_arm]["vacant_home_bytes"],
            })
        paired = {
            "pairs": pairs_complete,
            "A_only": a_only,
            f"{other_arm}_only": c_only,
            "mcnemar_p_two_sided": round(mcnemar(a_only, c_only), 4),
            "incomplete": incomplete,
        }
    return {
        "exp": exp, "suite": suite, "arms": arms,
        "n_cells": len(cells),
        "n_scored": sum(1 for c in cells if c["state"] == "scored"),
        "n_pending": sum(1 for c in cells if c["state"] == "pending"),
        "n_infra": sum(1 for c in cells if c["state"] == "infra"),
        "per_arm": per_arm,
        "A_vs_C": paired,
        "per_pair": per_pair,
        "note": ("report.py 無 per-task/per-suite 行；依預註冊計畫 §2（packets/e001_dabstep_analysis.md，"
                 "round 141）從各格 score.json 直接彙整並在此記錄。McNemar 與 report.py 同式。"
                 "pending＝格子未完成，不進分母；incomplete pair 不計入 p 值。"),
    }


def render_md(r: dict) -> str:
    L = [f"# {r['exp']} — {r['suite']} 子集", "",
         f"cells：{r['n_cells']}（scored {r['n_scored']}／pending {r['n_pending']}／infra {r['n_infra']}）", ""]
    L += ["| 臂 | n | 通過 | 率 | 呼叫/成功 | token/成功 | 逾時 | 均牆 s | vacant_home B |",
          "|---|---|---|---|---|---|---|---|---|"]
    for a, s in r["per_arm"].items():
        L.append(f"| {a} | {s['n_scored']} | {s['pass']} | {s['rate']} | {s['calls_per_success']} | "
                 f"{s['tokens_per_success']} | {s['timeouts']} | {s['mean_wall_s']} | {s['vacant_home_bytes_total']} |")
    p = r.get("A_vs_C")
    if p:
        L += ["", f"A_vs_C：配對 {p['pairs']}，只有 A 過 {p['A_only']}、只有 C 過 {p['C_only']}，"
                 f"McNemar p={p['mcnemar_p_two_sided']}"]
        if p["incomplete"]:
            L.append(f"incomplete（不進 p 值）：{json.dumps(p['incomplete'], ensure_ascii=False)}")
    L += ["", r["note"], ""]
    return "\n".join(L)


def _selftest() -> int:
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        exp = "fake"
        root = base / exp
        # 9 格＝5 對：task1 雙過；task2 C-only；task3 A-only；task4 A scored＋C pending（無 score.json）；task5 雙 infra（pass=null）
        _PENDING = object()  # 哨兵：該格只寫 cell.json，不寫 score.json
        cells = [
            ("task1-pi-A-r1", "A", True, 100, 10, 1000),
            ("task1-pi-C-r1", "C", True, 120, 12, 1200, 5000),
            ("task2-pi-A-r1", "A", False, 90, 9, 900),
            ("task2-pi-C-r1", "C", True, 110, 11, 1100, 4000),
            ("task3-pi-A-r1", "A", True, 80, 8, 800),
            ("task3-pi-C-r1", "C", False, 70, 7, 700, 3000),
            ("task4-pi-A-r1", "A", True, 60, 6, 600),
            ("task4-pi-C-r1", "C", _PENDING, 0, 0, 0),
            ("task5-pi-A-r1", "A", None, 50, 5, 500),
            ("task5-pi-C-r1", "C", None, 40, 4, 400, 2000),
        ]
        for row in cells:
            name, arm, passed, wall, calls, tok = row[:6]
            vhb = row[6] if len(row) > 6 else 0
            d = root / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "cell.json").write_text(json.dumps({
                "suite": "dabstep", "task": name.split("-pi-")[0], "agent": "pi", "rep": 1,
                "arm": arm, "wall_s": wall, "timed_out": False, "vacant_sha": None,
                "metrics": {"model_calls": calls, "input_tokens": tok, "output_tokens": 0},
                **({"vacant_home_bytes": vhb} if vhb else {}),
            }))
            if passed is not _PENDING:
                (d / "score.json").write_text(json.dumps({"pass": passed}))  # None → infra（與 report.py 同義）
        r = report(load_cells(base, exp, "dabstep"), exp, "dabstep", "C")
        checks = [
            (r["n_cells"], 10, "n_cells（5 對 × 2 臂）"),
            (r["n_scored"], 7, "n_scored"),
            (r["n_pending"], 1, "n_pending"),
            (r["n_infra"], 2, "n_infra"),
            (r["A_vs_C"]["pairs"], 3, "pairs_complete（task4 缺臂、task5 infra 都排除）"),
            (r["A_vs_C"]["A_only"], 1, "A_only（task3）"),
            (r["A_vs_C"]["C_only"], 1, "C_only（task2）"),
            (r["A_vs_C"]["mcnemar_p_two_sided"], 1.0, "a=1,c=1 → p=1.0（預註冊 §3 自校準值）"),
            (r["per_arm"]["A"]["n_scored"], 4, "A scored"),
            (r["per_arm"]["C"]["n_scored"], 3, "C scored"),
            (r["per_arm"]["C"]["vacant_home_bytes_total"], 14000, "C vacant_home 加總（5000+4000+3000+2000）"),
        ]
        # 第二組：a=2,c=0 → p=0.5（預註冊 §3 自校準值）
        cells2 = [
            ("t1-pi-A-r1", "A", False, 1, 1, 1),
            ("t1-pi-C-r1", "C", True, 1, 1, 1),
            ("t2-pi-A-r1", "A", False, 1, 1, 1),
            ("t2-pi-C-r1", "C", True, 1, 1, 1),
        ]
        root2 = base / "fake2"
        for name, arm, passed, wall, calls, tok in cells2:
            d = root2 / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "cell.json").write_text(json.dumps({
                "suite": "dabstep", "task": name.split("-pi-")[0], "agent": "pi", "rep": 1,
                "arm": arm, "wall_s": wall, "timed_out": False,
                "metrics": {"model_calls": calls, "input_tokens": tok, "output_tokens": 0},
            }))
            (d / "score.json").write_text(json.dumps({"pass": passed}))
        r2 = report(load_cells(base, "fake2", "dabstep"), "fake2", "dabstep", "C")
        checks += [
            (r2["A_vs_C"]["C_only"], 2, "a=2,c=0 組的 C_only"),
            (r2["A_vs_C"]["mcnemar_p_two_sided"], 0.5, "a=2,c=0 → p=0.5（預註冊 §3 自校準值）"),
        ]
        bad = [(got, want, why) for got, want, why in checks if got != want]
        if bad:
            print("SELFTEST FAIL:", bad, file=sys.stderr)
            return 2
        print("SELFTEST PASS（含預註冊 §3 兩組 p 值自校準）")
        return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("exp", nargs="?", help="實驗名（/srv/vlab/runs 下的目錄）")
    ap.add_argument("--suite", default="dabstep", help="只取指定 suite（預設 dabstep）")
    ap.add_argument("--base", default="/srv/vlab/runs", help="runs 根目錄")
    ap.add_argument("--arm", default="C", help="與 A 配對的另一臂（預設 C）")
    ap.add_argument("--out", help="JSON 另存路徑")
    ap.add_argument("--md", help="markdown 另存路徑")
    ap.add_argument("--selftest", action="store_true", help="離線自測後退出")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    if not a.exp:
        ap.error("exp 需要（或 --selftest）")
    cells = load_cells(Path(a.base), a.exp, a.suite)
    if not cells:
        print(f"no {a.suite} cells under {a.base}/{a.exp}", file=sys.stderr)
        return 1
    r = report(cells, a.exp, a.suite, a.arm)
    text = json.dumps(r, ensure_ascii=False, indent=2)
    if a.out:
        Path(a.out).write_text(text + "\n")
    if a.md:
        Path(a.md).write_text(render_md(r))
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
