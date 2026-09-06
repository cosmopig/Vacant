#!/usr/bin/env python3
"""R454：真跑**指名**——k=3 金鑰、1 把腐化，合票與分析（只在 Mac 跑）。零模型呼叫。

這支在架構裡承重什麼：它是 R449 §三-1 那一行的唯一真跑驗證裝置。

    R449 §三-1（模擬證據）：多數門檻以下，說謊者 **100% 被指名**，
    誠實者 **0% 被誣告**。

R453 把執行搬到兩台真機器，但 k=2 ⇒ quorum=2 ⇒ 全票 ⇒ **指名路徑一次都沒被走到**
（R453 §六 自己寫了這件事，Fable 稽核 §三-3 把它列為第一個限定）。本輪 k=3、
其中一把金鑰依**預註冊的確定性規則**說謊，然後看 `form_verdict` 指名對了沒有。

預註冊：`DECISION_20260906_R454_NAMED_DISSENT_PREREG.md`
（腐化設計、seed、P-1…P-6 的窗口、判定規則都寫在那裡，本檔只負責產生數字）。

紅線
----
- **零模型呼叫**：本檔沒有任何網路路徑。
- **不讀 K3 的側錄檔來決定誰該被指名**：本檔用 `peer_exec_real.corrupt_role`
  從**預註冊的 seed** 重算每一格的角色。讀側錄檔會把「機制指名對了」變成
  「我們把答案告訴機制」。側錄檔只用來做一項**交叉檢查**（K3 實際做的事
  ＝ seed 算出來的事嗎），對不上就 INVALID。
- **判準不重寫**：合票一律走 `peerexec.form_verdict`；早停迴圈沿用
  `peer_exec_real._select_loop`（R453 已用真的 `select_by_quorum` 對過 366/366）。
- **`hidden_check` 只計分**，從既有 cache 讀。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unicodedata

_HERE = pathlib.Path(__file__).resolve()
_REPO = _HERE.parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from ops.gain.replay import peer_exec_real as per  # noqa: E402
from vacant import peerexec as px  # noqa: E402
from vacant.identity import PublicIdentity  # noqa: E402
from vacant.logbook import LogEntry  # noqa: E402

#: 預註冊 §三 寫死的腐化參數。改這三個數字＝改實驗，必須另寫預註冊。
PREREG_SEED = 20260906
PREREG_LIAR_FRAC = 0.15
PREREG_EQUIV_FRAC = 0.03

#: 預註冊 §四 寫死的窗口（跑之前算好的純雜湊算術，見預註冊 §三 那張表）。
W_P1 = 273           # 說謊且能進計票的格數
W_P3 = 58            # 自相矛盾且能進計票的格數
W_P4_SHIP = 340      # 與 r446 runtime 出貨 sha 相符的題數
W_P4_REFUSE = 26     # 拒交題數
W_P6_RATE = 0.995    # K1/K2 跨機一致率下限


def _w(s: str) -> int:
    """字串的**顯示寬度**（CJK 全形算 2 欄）。

    展場收據是要印出來給人看的：`f"{s:<12}"` 補的是「字元數」不是「欄數」，
    中文欄位一定會歪。這支存在的唯一理由就是那張表要對得齊。
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def _pad(s: str, n: int) -> str:
    return s + " " * max(0, n - _w(s))


def _atts_of(cell: dict, eid: str) -> list[px.Attestation]:
    """一格、一把金鑰 ⇒ 它交出來的**所有**證言（自相矛盾者會有兩筆）。"""
    out = []
    if cell.get("entry"):
        out.append(px.Attestation(eid, LogEntry.from_json(cell["entry"])))
    if cell.get("entry_equivocation"):
        out.append(px.Attestation(eid, LogEntry.from_json(cell["entry_equivocation"])))
    return out


def main() -> int:  # noqa: C901, PLR0912, PLR0915
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", default="g_r446_eq5_mbpp")
    ap.add_argument("--specs", default=None)
    ap.add_argument("--pool", default=str(_REPO / "ops/gain/replay/r453"
                                          / "pool_g_r446_eq5_mbpp.json"))
    ap.add_argument("--books", nargs="+", required=True)
    ap.add_argument("--corrupt-id", default="K3",
                    help="預期腐化的那把金鑰的 executor_id")
    ap.add_argument("--seed", type=int, default=PREREG_SEED)
    ap.add_argument("--outdir", default=str(_REPO / "ops/gain/replay/r454"))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0,
                    help="只看前 N 題（冒煙測試用；正式跑一律 0。"
                         "窗口是全跑的窗口，limit 下必然 FAIL——那是預期的）")
    a = ap.parse_args()
    if a.specs is None:
        a.specs = str(_REPO / "ops/gain/replay/cache" / f"suitespec_{a.run}.json")
    outdir = pathlib.Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    specs = per.load_specs(a.specs)
    if a.limit:
        specs = {t: specs[t] for t in sorted(specs)[:a.limit]}
    pool = per.load_pool(a.pool)
    tasks, cands = pool["tasks"], pool["candidates"]

    books = {}
    for path in a.books:
        pub, cells, book = per.load_book_ndjson(path)
        books[pub["executor_id"]] = {"pub": pub, "cells": cells, "book": book,
                                     "path": path}
    k = len(books)
    quorum = k // 2 + 1
    roster = {eid: PublicIdentity.from_hex(b["pub"]["vacant_id"],
                                           b["pub"]["pub_hex"])
              for eid, b in books.items()}
    honest_ids = sorted(e for e in books if e != a.corrupt_id)
    print(f"k={k}，quorum={quorum}，金鑰：{sorted(books)}，"
          f"預期腐化：{a.corrupt_id}，誠實：{honest_ids}", flush=True)

    # ── P-5 鏈驗證（含說謊者的鏈）
    chain = {eid: bool(px.verify_executor_chain(eid, b["book"], roster))
             for eid, b in books.items()}
    chain_len = {eid: len(b["book"]) for eid, b in books.items()}
    print(f"P-5 chain verify: {chain}  鏈長 {chain_len}", flush=True)

    # 承重檔案跨機比對
    file_sha = {f: {eid: (b["pub"].get("file_sha256") or {}).get(f)
                    for eid, b in books.items()}
                for f in per.LOAD_BEARING}
    code_identical = {f: (len({v for v in d.values() if v is not None}) <= 1)
                      for f, d in file_sha.items()}

    # ── 量具白名單（Mac 側，與 R453 逐字同一條路徑）
    from ops.gain.replay import peer_exec_sim as sim  # noqa: PLC0415
    refs = sim.canonical_refs(a.run)
    gauged, gauge_meta, commits, _committer = per.build_gauge_index(
        specs, pool, refs, a.workers)
    (outdir / "r454_gauge.json").write_text(
        json.dumps(gauge_meta, indent=0, sort_keys=True), encoding="utf-8")

    # ── runtime 出貨決定 ＋ hidden（只計分）
    rt = {}
    for line in (_REPO / "runs" / a.run / "rows.jsonl").open(encoding="utf-8"):
        d = json.loads(line)
        rt[d["task_id"]] = d
    facts = json.loads((_REPO / "ops/gain/replay/cache"
                        / f"peerexec_facts_{a.run}.json").read_text())

    # ── 逐格
    rows: list[dict] = []
    verdicts: dict[str, dict[int, px.Verdict]] = {}
    n_cells = 0
    # P-1
    p1_den = p1_hit = 0
    p1_miss: list[dict] = []
    # P-2
    p2_named: list[dict] = []
    # P-3
    p3_den = p3_hit = 0
    p3_miss: list[dict] = []
    # P-6
    p6_den = p6_agree = 0
    p6_diff: list[dict] = []
    p6b_den = p6b_agree = 0
    p6b_diff: list[dict] = []
    n_detail_dissent = 0
    gauge_short_circuit = 0
    cell_errors: list[dict] = []
    role_counts = {"honest": 0, "liar": 0, "equivocator": 0}

    for tid in sorted(specs):
        if tid not in tasks or tid not in cands:
            continue
        ep = tasks[tid].get("entry_point")
        spec = px.as_suite_spec(specs[tid], ep)
        ssha, rsha = spec.suite_sha256, per.sha256_text(spec.render())
        vt: dict[int, px.Verdict] = {}
        for i, code in enumerate(cands[tid]):
            n_cells += 1
            dsha = per.sha256_text(code)
            role = per.corrupt_role(a.seed, tid, i, PREREG_LIAR_FRAC,
                                    PREREG_EQUIV_FRAC)
            role_counts[role] += 1
            atts: list[px.Attestation] = []
            labels: dict[str, bool] = {}
            n_sigs: dict[str, int] = {}
            for eid, b in books.items():
                c = b["cells"].get((tid, i))
                if not c or c.get("error") or not c.get("entry"):
                    cell_errors.append({"executor": eid, "task_id": tid,
                                        "cand": i,
                                        "error": (c or {}).get("error",
                                                               "missing_cell")})
                    continue
                these = _atts_of(c, eid)
                atts.extend(these)
                n_sigs[eid] = len(these)
                labels[eid] = bool(c["visible_ok"])

            v = px.form_verdict(atts, roster, task_id=tid, draft_sha256=dsha,
                                suite_sha256=ssha, quorum=quorum,
                                gauged_suites=gauged, render_sha256=rsha)
            vt[i] = v
            gauged_ok = (v.gauge_status == "ok")
            if not gauged_ok:
                gauge_short_circuit += 1
            if v.detail_dissenters:
                n_detail_dissent += 1

            # P-6：兩把誠實金鑰的可見標籤（全 1840 格，含量具擋下的）
            if all(e in labels for e in honest_ids):
                p6_den += 1
                if len({labels[e] for e in honest_ids}) == 1:
                    p6_agree += 1
                else:
                    p6_diff.append({"task_id": tid, "cand": i,
                                    "labels": {e: labels[e] for e in honest_ids}})
            # P-6b：K3 在 honest 角色格上有沒有外溢
            if role == "honest" and a.corrupt_id in labels and \
                    all(e in labels for e in honest_ids) and \
                    len({labels[e] for e in honest_ids}) == 1:
                p6b_den += 1
                if labels[a.corrupt_id] == labels[honest_ids[0]]:
                    p6b_agree += 1
                else:
                    p6b_diff.append({"task_id": tid, "cand": i, "labels": labels})

            # P-1：說謊格是否恰好指名 {K3}
            if role == "liar" and gauged_ok:
                p1_den += 1
                if tuple(v.dissenters) == (a.corrupt_id,):
                    p1_hit += 1
                else:
                    p1_miss.append({"task_id": tid, "cand": i,
                                    "dissenters": list(v.dissenters),
                                    "visible_ok": v.visible_ok,
                                    "labels": labels,
                                    "rejected": [list(r) for r in v.rejected]})
            # P-3：自相矛盾格
            if role == "equivocator" and gauged_ok:
                p3_den += 1
                honest_lab = ({labels[e] for e in honest_ids}
                              if all(e in labels for e in honest_ids) else set())
                ok = (a.corrupt_id in v.equivocators
                      and (a.corrupt_id, "equivocation") in v.rejected
                      and a.corrupt_id not in v.camp_pass
                      and a.corrupt_id not in v.camp_fail
                      and v.n_admitted == len(honest_ids)
                      and v.visible_ok is not None
                      and len(honest_lab) == 1
                      and v.visible_ok == next(iter(honest_lab)))
                if ok:
                    p3_hit += 1
                else:
                    p3_miss.append({"task_id": tid, "cand": i,
                                    "equivocators": list(v.equivocators),
                                    "rejected": [list(r) for r in v.rejected],
                                    "n_admitted": v.n_admitted,
                                    "visible_ok": v.visible_ok,
                                    "labels": labels})
            # P-2：誠實金鑰被指名？
            named = set(v.dissenters) | set(v.detail_dissenters) | set(v.equivocators)
            for e in honest_ids:
                if e in named:
                    p2_named.append({"task_id": tid, "cand": i, "executor": e,
                                     "dissenters": list(v.dissenters),
                                     "detail_dissenters": list(v.detail_dissenters),
                                     "equivocators": list(v.equivocators)})
            rows.append({
                "task_id": tid, "cand": i, "prereg_role": role,
                "gauge_status": v.gauge_status,
                "votes": {e: labels.get(e) for e in sorted(books)},
                "n_signatures": {e: n_sigs.get(e, 0) for e in sorted(books)},
                "verdict_visible_ok": v.visible_ok,
                "dissenters": list(v.dissenters),
                "detail_dissenters": list(v.detail_dissenters),
                "equivocators": list(v.equivocators),
                "rejected": [list(r) for r in v.rejected],
                "n_admitted": v.n_admitted,
            })
        verdicts[tid] = vt

    # ── 逐題：早停選擇 ＋ 與 r446 runtime 比對（P-4）
    ship_match = ship_mismatch = refuse_match = refuse_mismatch = 0
    excluded_gauge: list[str] = []
    task_rows: list[dict] = []
    for tid in sorted(specs):
        if tid not in tasks or tid not in cands:
            continue
        sel = per._select_loop(tid, cands[tid], verdicts[tid])  # noqa: SLF001
        r = rt.get(tid, {})
        gauge_blocked = str(sel["refusal_reason"] or "").startswith("suite_gate:")
        row = {"task_id": tid, **sel, "runtime_accepted": r.get("accepted"),
               "runtime_sha": r.get("gate_code_sha256"),
               "gauge_blocked": gauge_blocked}
        if gauge_blocked:
            excluded_gauge.append(tid)
        elif r.get("accepted"):
            if (not sel["refused"]) and sel["shipped_sha256"] == r.get(
                    "gate_code_sha256"):
                ship_match += 1
                row["verdict_vs_runtime"] = "match"
            else:
                ship_mismatch += 1
                row["verdict_vs_runtime"] = "MISMATCH"
        else:
            if sel["refused"]:
                refuse_match += 1
                row["verdict_vs_runtime"] = "refuse_match"
            else:
                refuse_mismatch += 1
                row["verdict_vs_runtime"] = "MISMATCH_refuse"
        if not sel["refused"]:
            hid = facts.get(f"{tid}#{sel['shipped_index']}", {}).get("hidden")
            row["delivered_correct"] = bool(hid)
            row["false_delivery"] = not bool(hid)
        task_rows.append(row)

    # ── 交叉檢查：K3 實際做的事 vs seed 重算的角色
    side_check = {"checked": False}
    side_path = pathlib.Path(a.books[0]).parent / f"att_{a.corrupt_id}.corrupt_side.json"
    if side_path.exists():
        side = json.loads(side_path.read_text(encoding="utf-8"))
        mism = []
        for c in side["cells"]:
            want = per.corrupt_role(a.seed, c["task_id"], c["cand_index"],
                                    PREREG_LIAR_FRAC, PREREG_EQUIV_FRAC)
            if want != c["role"]:
                mism.append({"task_id": c["task_id"], "cand": c["cand_index"],
                             "seed_says": want, "side_says": c["role"]})
        side_check = {"checked": True, "n_cells": len(side["cells"]),
                      "seed": side["seed"], "n_role": side["n_role"],
                      "n_flipped": side["n_flipped"],
                      "role_mismatch": len(mism), "examples": mism[:20],
                      "path": str(side_path)}
        print(f"側錄檔交叉檢查：{side['n_role']}，翻轉 {side['n_flipped']} 格，"
              f"角色與 seed 不符 {len(mism)} 格", flush=True)

    # ── 判定
    p1_pass = (p1_den == W_P1 and p1_hit == W_P1)
    p2_pass = (len(p2_named) == 0)
    p3_pass = (p3_den == W_P3 and p3_hit == W_P3)
    p4_pass = (ship_match == W_P4_SHIP and ship_mismatch == 0
               and refuse_match == W_P4_REFUSE and refuse_mismatch == 0)
    p5_pass = all(chain.values())
    p6_rate = (p6_agree / p6_den) if p6_den else 0.0
    p6_pass = (p6_den > 0 and p6_rate >= W_P6_RATE)
    side_ok = (not side_check.get("checked")) or side_check["role_mismatch"] == 0

    if (not p5_pass) or len(cell_errors) > 0.01 * max(1, n_cells * k) or not side_ok:
        decision = "INVALID"
    elif p1_pass and p2_pass and p3_pass and p4_pass and p6_pass:
        decision = "NAMING_HOLDS"
    elif p1_pass and p2_pass and p3_pass and p4_pass and not p6_pass:
        # 預註冊 §五 寫死的第四個標籤：掉進縫裡就給它自己的名字。
        decision = "NAMING_HOLDS_EXCEPT_P6"
    else:
        decision = "NAMING_FAILS"

    preds = {
        "P1_liar_cells_name_K3": {
            "window": f"{W_P1}/{W_P1}", "denominator": p1_den, "hit": p1_hit,
            "misses": p1_miss[:50], "pass": p1_pass,
            "note": "dissenters 必須**恰好**等於 (K3,)，不是「包含 K3」"},
        "P2_honest_keys_never_named": {
            "window": "0", "named_cells": len(p2_named),
            "examples": p2_named[:50], "pass": p2_pass,
            "denominator_cells": n_cells},
        "P3_equivocation_voided_verdict_stands": {
            "window": f"{W_P3}/{W_P3}", "denominator": p3_den, "hit": p3_hit,
            "misses": p3_miss[:50], "pass": p3_pass},
        "P4_shipping_unchanged": {
            "window": f"{W_P4_SHIP}/{W_P4_SHIP} ship + {W_P4_REFUSE}/{W_P4_REFUSE} refuse",
            "ship_match": ship_match, "ship_mismatch": ship_mismatch,
            "refuse_match": refuse_match, "refuse_mismatch": refuse_mismatch,
            "excluded_gauge_blocked": len(excluded_gauge), "pass": p4_pass},
        "P5_all_chains_verify": {
            "window": f"{k}/{k}", "per_key": chain, "chain_len": chain_len,
            "pass": p5_pass,
            "note": ("說謊者的鏈照樣驗得過。鏈驗證證明的是「這些話確實是這把金鑰"
                     "說的、事後沒被改過」，不是「這些話是真的」。")},
        "P6_honest_cross_machine_agreement": {
            "window": f">={W_P6_RATE}", "denominator": p6_den, "agree": p6_agree,
            "rate": round(p6_rate, 6), "diffs": p6_diff[:50], "pass": p6_pass,
            "P6b_corrupt_key_on_honest_cells": {
                "denominator": p6b_den, "agree": p6b_agree,
                "diffs": p6b_diff[:50],
                "pass": (p6b_den > 0 and p6b_agree == p6b_den)}},
    }

    out = {
        "round": "R454", "run": a.run, "k": k, "quorum": quorum,
        "corrupt_id": a.corrupt_id, "honest_ids": honest_ids,
        "prereg": {"seed": a.seed, "liar_frac": PREREG_LIAR_FRAC,
                   "equiv_frac": PREREG_EQUIV_FRAC,
                   "role_counts_recomputed_from_seed": role_counts,
                   "windows": {"P1": W_P1, "P3": W_P3, "P4_ship": W_P4_SHIP,
                               "P4_refuse": W_P4_REFUSE, "P6_rate": W_P6_RATE}},
        "keys": {eid: {"vacant_id": b["pub"]["vacant_id"],
                       "pub_hex": b["pub"]["pub_hex"],
                       "book_head": b["pub"]["book_head"],
                       "platform": b["pub"].get("platform"),
                       "python_version": b["pub"].get("python_version"),
                       "n_signed": b["pub"].get("n_signed"),
                       "wall_s": b["pub"].get("wall_s"),
                       "workers": b["pub"].get("workers"),
                       "corrupt": b["pub"].get("corrupt")}
                 for eid, b in books.items()},
        "code_identical_across_keys": code_identical,
        "file_sha256": file_sha,
        "predictions": preds,
        "decision": decision,
        "gauge_short_circuit_cells": gauge_short_circuit,
        "detail_dissent_cells": n_detail_dissent,
        "detail_dissent_note": ("預註冊 §四 已寫明本設計測不到 detail_dissenters "
                                "通道，預期恆為 0；這裡的數字只是把它照實印出來。"),
        "cell_errors": cell_errors[:200], "n_cell_errors": len(cell_errors),
        "excluded_gauge_blocked": excluded_gauge,
        "corrupt_side_file_crosscheck": side_check,
        "gauge": {kk: vv for kk, vv in gauge_meta.items() if kk != "gauge_records"},
        "delivery_scoring_hidden_only": {
            "delivered_correct": sum(1 for r in task_rows
                                     if r.get("delivered_correct")),
            "false_delivery": sum(1 for r in task_rows if r.get("false_delivery")),
            "refused": sum(1 for r in task_rows if r["refused"]),
            "n_tasks": len(task_rows)},
        "task_rows": task_rows,
    }
    (outdir / "r454_result.json").write_text(
        json.dumps(out, indent=1, sort_keys=True), encoding="utf-8")

    # ── 逐格指名表（1840 列）
    hdr = ["task_id", "cand", "prereg_role", "gauge_status",
           *[f"vote_{e}" for e in sorted(books)],
           *[f"nsig_{e}" for e in sorted(books)],
           "verdict", "dissenters", "detail_dissenters", "equivocators",
           "rejected", "n_admitted"]
    lines = ["\t".join(hdr)]
    for r in rows:
        lines.append("\t".join([
            r["task_id"], str(r["cand"]), r["prereg_role"], r["gauge_status"],
            *[str(r["votes"][e]) for e in sorted(books)],
            *[str(r["n_signatures"][e]) for e in sorted(books)],
            str(r["verdict_visible_ok"]),
            ",".join(r["dissenters"]) or "-",
            ",".join(r["detail_dissenters"]) or "-",
            ",".join(r["equivocators"]) or "-",
            ";".join(f"{x[0]}:{x[1]}" for x in r["rejected"]) or "-",
            str(r["n_admitted"])]))
    (outdir / "r454_naming_table.tsv").write_text("\n".join(lines) + "\n",
                                                  encoding="utf-8")

    # ── 總表
    t = [
        f"R454 真跑指名  run={a.run}  k={k}  quorum={quorum}",
        "金鑰：" + "  ".join(
            f"{e}({b['pub'].get('system')}/{b['pub'].get('python_version')}"
            f"{'/腐化' if b['pub'].get('corrupt') else ''})"
            for e, b in sorted(books.items())),
        f"預註冊角色（從 seed={a.seed} 重算）：{role_counts}",
        "",
        f"P-1 說謊格指名 {{{a.corrupt_id}}}      {p1_hit}/{p1_den}   "
        f"窗口 {W_P1}/{W_P1}   {'PASS' if p1_pass else 'FAIL'}",
        f"P-2 誠實金鑰被誣告        {len(p2_named)}   窗口 0   "
        f"{'PASS' if p2_pass else 'FAIL'}",
        f"P-3 自相矛盾作廢、裁決仍成立 {p3_hit}/{p3_den}   窗口 {W_P3}/{W_P3}   "
        f"{'PASS' if p3_pass else 'FAIL'}",
        f"P-4 出貨決定不變          {ship_match} 相符 / {ship_mismatch} 不符；"
        f"拒交 {refuse_match} 相符 / {refuse_mismatch} 不符；量具擋下 "
        f"{len(excluded_gauge)}   {'PASS' if p4_pass else 'FAIL'}",
        f"P-5 三條鏈皆驗真          {chain}  鏈長 {chain_len}   "
        f"{'PASS' if p5_pass else 'FAIL'}",
        f"P-6 K1/K2 跨機一致        {p6_agree}/{p6_den} ({p6_rate:.4%})   "
        f"窗口 >={W_P6_RATE:.1%}   {'PASS' if p6_pass else 'FAIL'}",
        f"P-6b 腐化金鑰在誠實角色格  {p6b_agree}/{p6b_den}   "
        f"{'PASS' if (p6b_den and p6b_agree == p6b_den) else 'FAIL'}",
        "",
        f"detail_dissenters 格數：{n_detail_dissent}（預註冊已寫明本設計測不到這條通道）",
        f"量具短路格（不進 P-1/P-3 分母）：{gauge_short_circuit}",
        f"格子錯誤（infra/例外）：{len(cell_errors)}",
        f"承重檔案跨金鑰逐位相同：{all(code_identical.values())}  "
        f"{[f for f, v in code_identical.items() if not v]}",
        f"側錄檔 vs seed：{'一致' if side_ok else '不一致 ⇒ INVALID'}"
        f"（{side_check.get('n_role')}）",
        f"計分（hidden 只在這裡）：交付正確 "
        f"{out['delivery_scoring_hidden_only']['delivered_correct']}、假交付 "
        f"{out['delivery_scoring_hidden_only']['false_delivery']}、拒交 "
        f"{out['delivery_scoring_hidden_only']['refused']}",
        "",
        f"判定：{decision}",
    ]
    table = "\n".join(t)
    (outdir / "r454_table.txt").write_text(table + "\n", encoding="utf-8")
    print(table, flush=True)

    # ── 展場收據：挑一格「說謊且被指名」的，完整渲染
    receipt_cell = next((r for r in rows
                         if r["prereg_role"] == "liar"
                         and tuple(r["dissenters"]) == (a.corrupt_id,)), None)
    if receipt_cell is not None:
        tid, ci = receipt_cell["task_id"], receipt_cell["cand"]
        v = verdicts[tid][ci]
        ep = tasks[tid].get("entry_point")
        spec = px.as_suite_spec(specs[tid], ep)
        rec = {
            "round": "R454",
            "what_this_is": ("一格的完整收據：同一份草稿、同一套驗收，三把金鑰各自"
                             "在自己的機器上真跑、各自簽進自己的鏈。其中一票與另外"
                             "兩票不同 ⇒ 那一票被**指名**。"),
            "task_id": tid,
            "candidate_index": ci,
            "draft_sha256": v.draft_sha256,
            "suite_sha256": v.suite_sha256,
            "render_sha256": per.sha256_text(spec.render()),
            "entry_point": ep,
            "keys": {
                eid: {
                    "vacant_id": books[eid]["pub"]["vacant_id"],
                    "pub_hex": books[eid]["pub"]["pub_hex"],
                    "machine": books[eid]["pub"].get("platform"),
                    "python": books[eid]["pub"].get("python_version"),
                    "chain_head": books[eid]["pub"]["book_head"],
                    "chain_len": chain_len[eid],
                    "chain_verifies": chain[eid],
                } for eid in sorted(books)},
            "votes": {eid: {
                "visible_ok": receipt_cell["votes"][eid],
                "first_failing_test": (books[eid]["cells"].get((tid, ci)) or {})
                                      .get("first_failing_test"),
                "n_signatures_this_cell": receipt_cell["n_signatures"][eid],
                "entry_hash": next((h for e, h in v.evidence if e == eid), None),
            } for eid in sorted(books)},
            "verdict": v.as_receipt(),
            "named": {
                "dissenters": list(v.dissenters),
                "detail_dissenters": list(v.detail_dissenters),
                "equivocators": list(v.equivocators),
                "rejected": [list(r) for r in v.rejected],
            },
            "honest_boundary": [
                "鏈驗證證明的是「這些話確實是這把金鑰說的、事後沒被改過」，"
                "不是「這些話是真的」——被指名那把金鑰的鏈也驗得過。",
                "指名靠的是多數決。腐化數超過 ⌊(k−1)/2⌋ 時裁決會翻轉、指名也會"
                "跟著翻轉，機制無法知道自己在門檻哪一邊（R449 §三-1）。",
                "只在不會被抓時才說謊的執行器，本輪沒有測（R449 §三-2 模擬偵測率 0.000）。",
                "驗收套件本身腐化，這個機制零保護（R449 §四）。",
            ],
        }
        (outdir / "r454_exhibition_receipt.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8")

        bar = "═" * 74
        txt = [
            bar,
            "  Vacant 執行收據 · R454 · 一格的完整可究責紀錄",
            bar,
            f"  題目          {tid}   (entry_point: {ep})",
            f"  草稿          第 {ci} 份，sha256 {v.draft_sha256[:32]}…",
            f"  驗收套件      sha256 {v.suite_sha256[:32]}…",
            f"  渲染出來的碼  sha256 {rec['render_sha256'][:32]}…",
            f"  量具狀態      {v.gauge_status}",
            "",
            "  三把金鑰各自跑、各自簽：",
            "  " + _pad("金鑰", 6) + _pad("機器", 34) + _pad("票", 10)
            + _pad("卡在第幾條", 14) + _pad("鏈頭", 20) + "鏈驗證",
        ]
        for eid in sorted(books):
            b = books[eid]["pub"]
            vote = receipt_cell["votes"][eid]
            fft = (books[eid]["cells"].get((tid, ci)) or {}).get("first_failing_test")
            nsig = receipt_cell["n_signatures"][eid]
            mach = str(b.get("platform"))[:32]
            txt.append("  " + _pad(eid, 6) + _pad(mach, 34)
                       + _pad("通過" if vote else "不通過", 10)
                       + _pad(str(fft) if fft is not None else "—", 14)
                       + _pad(str(b["book_head"])[:16], 20)
                       + ("驗得過" if chain[eid] else "驗不過")
                       + (f"   ⚠ 這一格簽了 {nsig} 筆" if nsig > 1 else ""))
        txt += [
            "",
            f"  法定人數      {v.quorum} / {k}（採信 {v.n_admitted} 票）",
            f"  裁決          可見驗收{'通過' if v.visible_ok else '不通過'}"
            f"（通過 {v.n_pass} 票 / 不通過 {v.n_fail} 票）",
            f"  ▸ 被指名      {', '.join(v.dissenters) or '（無）'}"
            f"   ← 少數方，簽章可歸屬",
            f"    自相矛盾    {', '.join(v.equivocators) or '（無）'}",
            f"    不採信      "
            f"{'; '.join(f'{x[0]}:{x[1]}' for x in v.rejected) or '（無）'}",
        ]
        if v.visible_ok is False and receipt_cell["votes"].get(a.corrupt_id) is True:
            txt += [
                "",
                f"  如果只有 {a.corrupt_id} 一把金鑰（k=1，＝ CONFORM 的單一執行器）：",
                "  這份草稿會被判「通過」而出貨，而且收據上看不出任何異狀。",
                "  多出來的兩把金鑰買到的不是「更準」，是**這一票不同意可以指到人**。",
            ]
        txt += [
            "",
            "  這張收據證明什麼、不證明什麼：",
            "  ✓ 這三句話確實分別是這三把金鑰說的，而且事後沒有被改過。",
            "  ✓ 有一把金鑰說的跟另外兩把不一樣，而它是**誰**，有簽章可以指。",
            "  ✗ 鏈驗得過**不等於**話是真的——被指名那把金鑰的鏈同樣驗得過。",
            "  ✗ 指名靠多數決：腐化的金鑰超過一半時，被指名的會是誠實的那一方。",
            "  ✗ 驗收套件本身是爛的，這個機制看不出來（所有票都會誠實地通過）。",
            bar,
        ]
        (outdir / "r454_exhibition_receipt.txt").write_text(
            "\n".join(txt) + "\n", encoding="utf-8")
        print("\n" + "\n".join(txt), flush=True)
    else:
        print("⚠ 找不到任何「說謊且被指名」的格子，沒有產出展場收據", flush=True)

    print(f"\n落盤：{outdir}/r454_result.json、r454_naming_table.tsv、"
          f"r454_table.txt、r454_exhibition_receipt.{{json,txt}}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
