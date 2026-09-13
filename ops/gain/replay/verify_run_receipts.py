#!/usr/bin/env python3
"""逐 run 驗收據鏈：創世→鏈頭連續、每筆 Ed25519 簽章有效、條數與 rows 對得上。

這支在架構裡承重什麼：收據是 Vacant 對外唯一「不用信任我」的東西。R460R／R529
的 run 目錄裡各臂都落了 `receipts_<ARM>.ndjson` ＋ `receipts_<ARM>.pub.json`，
但**落盤 ≠ 驗得起來**（`CRITERION_20260903_R666` 就是為了這個差別寫的）。
本檔是稽核端：不讀模型、不讀 cache，只拿鏈檔與公鑰重算。

與 `vacant/logbook.py::Logbook.verify_chain` 的關係：那支回一個 bool，
**壞在哪一筆看不出來**。本檔逐字重跑它的同一套規則（同一個
`_signed_bytes`／`_entry_hash`，不是另寫一份），差別只在**逐筆記錄失敗原因**
——任何一條失敗都要指得出 seq、type、原因，而不是只報一個 False。
兩邊的結論必須一致：`chain_ok` 與 `logbook_verify_chain` 兩個欄位都輸出，
不一致本身就是 `verdict=BROKEN`（那代表本檔漂掉了，不是鏈壞了）。

條數對帳（每題每臂一個 verdict）：
  · `harness_verdict`／`conform_verdict` 的條數 == 該臂在 `rows.jsonl` 的列數；
  · verdict 的 `task_id` 集合 == 該臂 rows 的 `task_id` 集合（不是只比個數）；
  · `*_attempt` 條數 ≥ verdict 條數（多輪臂會多；少於就是漏寫）。
⚠ **沒有收據檔的臂不是失敗**：OFF／OFF5 本來就沒有收據這回事，
  記成 `arms_without_receipts` 而不是 BROKEN——「沒量到」≠「量到 0」。

用法：
    python3 ops/gain/replay/verify_run_receipts.py \\
        --glob 'runs/g_r460r[123]_*' --json ops/gain/replay/r460r/receipts_verify.json
    python3 ops/gain/replay/verify_run_receipts.py --selftest
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from vacant.crypto import pub_to_hex  # noqa: E402
from vacant.identity import Identity, PublicIdentity  # noqa: E402
from vacant.logbook import (EMPTY_PREV_HASH, GENESIS_STREAM_ID,  # noqa: E402
                            Logbook, _signed_bytes)

def _rel(p: pathlib.Path) -> str:
    """相對 repo 根的路徑；不在 repo 底下（selftest 的 tmpdir）就給絕對路徑。"""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


#: 收據的事件別 → 它對帳的那一邊。`*_verdict` 每題一筆，`*_attempt` 每輪一筆。
VERDICT_TYPES = ("harness_verdict", "conform_verdict")
ATTEMPT_TYPES = ("harness_attempt", "conform_attempt")


def verify_chain_detailed(book: Logbook, who: PublicIdentity) -> list[dict]:
    """逐筆重跑 `Logbook.verify_chain` 的規則，回**失敗清單**（空＝全過）。

    規則逐字照抄那一支（seq 連續、prev_hash 串對、stream/branch 一致、簽章過），
    只是不提早 return，好讓一條壞鏈把所有壞點都吐出來。
    """
    fails: list[dict] = []
    if not book.entries:
        return fails
    genesis = book.entries[0]
    if genesis.stream_id != GENESIS_STREAM_ID:
        fails.append({"seq": genesis.seq, "type": genesis.type,
                      "reason": "genesis_stream_id_not_sentinel",
                      "got": genesis.stream_id, "want": GENESIS_STREAM_ID})
    expected_stream = genesis.hash()
    expected_branch = genesis.branch_id
    prev_hash = EMPTY_PREV_HASH
    expected_seq = 1
    for e in book.entries:
        if e.seq != expected_seq:
            fails.append({"seq": e.seq, "type": e.type, "reason": "seq_not_contiguous",
                          "got": e.seq, "want": expected_seq})
        if e.prev_hash != prev_hash:
            fails.append({"seq": e.seq, "type": e.type, "reason": "prev_hash_broken",
                          "got": e.prev_hash, "want": prev_hash})
        if e.seq > 1 and e.stream_id != expected_stream:
            fails.append({"seq": e.seq, "type": e.type, "reason": "stream_id_mismatch",
                          "got": e.stream_id, "want": expected_stream})
        if e.seq > 1 and e.branch_id != expected_branch:
            fails.append({"seq": e.seq, "type": e.type, "reason": "branch_id_mismatch",
                          "got": e.branch_id, "want": expected_branch})
        try:
            sig_ok = who.verify(
                _signed_bytes(e.stream_id, e.branch_id, e.seq, e.prev_hash,
                              e.ts_ms, e.type, e.payload),
                bytes.fromhex(e.sig))
        except Exception as exc:                                  # noqa: BLE001
            sig_ok, exc_s = False, repr(exc)
        else:
            exc_s = None
        if not sig_ok:
            fails.append({"seq": e.seq, "type": e.type, "reason": "bad_signature",
                          "sig": e.sig[:32] + "…", "exception": exc_s,
                          "task_id": (e.payload or {}).get("task_id")
                          if isinstance(e.payload, dict) else None})
        prev_hash = e.hash()
        expected_seq += 1
    return fails


def verify_arm(run: pathlib.Path, arm: str, rows: list[dict]) -> dict:
    """一個 run 的一條臂鏈。回一列報表（含失敗原文）。"""
    chain = run / f"receipts_{arm}.ndjson"
    pub = run / f"receipts_{arm}.pub.json"
    rec: dict = {"run": run.name, "arm": arm,
                 "chain_file": _rel(chain),
                 "entries_n": 0, "verified_n": 0, "failed_n": 0,
                 "chain_ok": None, "logbook_verify_chain": None,
                 "stream_id": None, "head": None,
                 "type_counts": {}, "failures": [], "verdict": "UNVERIFIABLE"}
    if not pub.exists():
        rec["failures"].append({"reason": "pubkey_file_missing", "path": str(pub)})
        return rec
    meta = json.loads(pub.read_text(encoding="utf-8"))
    who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
    rec["vacant_id"] = meta["vacant_id"]
    book = Logbook.load(chain)
    rec["entries_n"] = len(book)
    if not book.entries:
        rec["failures"].append({"reason": "empty_chain"})
        return rec
    fails = verify_chain_detailed(book, who)
    bad_seqs = {f["seq"] for f in fails}
    rec["failures"] += fails
    rec["failed_n"] = len(bad_seqs)
    rec["verified_n"] = len(book) - len(bad_seqs)
    rec["chain_ok"] = not fails
    rec["logbook_verify_chain"] = bool(book.verify_chain(who))
    if rec["chain_ok"] != rec["logbook_verify_chain"]:
        rec["failures"].append({"reason": "detailed_vs_logbook_disagree",
                                "detailed": rec["chain_ok"],
                                "logbook": rec["logbook_verify_chain"]})
    rec["stream_id"] = book.stream_id()
    rec["head"] = book.head()
    rec["genesis_hash_is_stream_id"] = (book.entries[0].hash() == book.stream_id())
    counts: dict[str, int] = {}
    for e in book.entries:
        counts[e.type] = counts.get(e.type, 0) + 1
    rec["type_counts"] = dict(sorted(counts.items()))

    # ── 條數對帳：每題每臂一個 verdict ────────────────────────────────
    arm_rows = [r for r in rows if r.get("arm") == arm]
    vt = [e for e in book.entries if e.type in VERDICT_TYPES]
    at = [e for e in book.entries if e.type in ATTEMPT_TYPES]
    rec["rows_n"] = len(arm_rows)
    rec["verdict_n"] = len(vt)
    rec["attempt_n"] = len(at)
    if len(vt) != len(arm_rows):
        rec["failures"].append({"reason": "verdict_count_ne_rows",
                                "verdict_n": len(vt), "rows_n": len(arm_rows)})
    v_ids = {(e.payload or {}).get("task_id") for e in vt}
    r_ids = {r.get("task_id") for r in arm_rows}
    if v_ids != r_ids:
        rec["failures"].append({"reason": "verdict_task_ids_ne_rows",
                                "only_in_receipts": sorted(x for x in v_ids - r_ids
                                                           if x is not None),
                                "only_in_rows": sorted(x for x in r_ids - v_ids
                                                       if x is not None)})
    if len(vt) != len(v_ids):
        rec["failures"].append({"reason": "duplicate_verdict_for_task",
                                "verdict_n": len(vt), "distinct_task_ids": len(v_ids)})
    if len(at) < len(vt):
        rec["failures"].append({"reason": "attempt_fewer_than_verdict",
                                "attempt_n": len(at), "verdict_n": len(vt)})
    rec["verdict"] = "OK" if not rec["failures"] else "BROKEN"
    return rec


def verify_run(run: pathlib.Path) -> list[dict]:
    rows_p = run / "rows.jsonl"
    rows = ([json.loads(l) for l in rows_p.open(encoding="utf-8") if l.strip()]
            if rows_p.exists() else [])
    arms = sorted(p.name[len("receipts_"):-len(".ndjson")]
                  for p in run.glob("receipts_*.ndjson"))
    out = [verify_arm(run, a, rows) for a in arms]
    seen = {r.get("arm") for r in out}
    for rec in out:
        rec["arms_without_receipts"] = sorted(
            {r.get("arm") for r in rows} - seen - {None})
    return out


def run_glob(pattern: str) -> dict:
    dirs = sorted(d for d in ROOT.glob(pattern) if d.is_dir())
    rows: list[dict] = []
    for d in dirs:
        rows += verify_run(d)
    broken = [r for r in rows if r["verdict"] != "OK"]
    return {
        "glob": pattern, "runs_n": len(dirs), "chains_n": len(rows),
        "entries_total": sum(r["entries_n"] for r in rows),
        "verified_total": sum(r["verified_n"] for r in rows),
        "failed_total": sum(r["failed_n"] for r in rows),
        "broken_chains_n": len(broken),
        "verdict": "OK" if rows and not broken else
                   ("UNVERIFIABLE" if not rows else "BROKEN"),
        "note": ("每一列＝一個 run 的一條臂鏈。`verified_n` 數的是**逐筆都過**的 "
                 "entry；`failures` 是原文（seq／type／原因），不是摘要。"
                 "`chain_ok` 是本檔逐筆重跑的結論、`logbook_verify_chain` 是 "
                 "`vacant/logbook.py` 那支的 bool——兩者必須一致，不一致算 BROKEN。"),
        "chains": rows,
    }


def selftest() -> int:
    """乾淨路徑通過不算數：三種竄改都必須被指名抓到。"""
    import tempfile
    fails: list[str] = []

    def ck(label, cond, extra=""):
        if not cond:
            fails.append(f"{label}{(' — ' + extra) if extra else ''}")

    ident = Identity.generate()
    book = Logbook()
    for i in range(3):
        book.append("harness_attempt", {"task_id": f"t{i}", "turn": 1}, ident,
                    ts_ms=1_700_000_000_000 + i)
    for i in range(3):
        book.append("harness_verdict", {"task_id": f"t{i}", "accepted": True}, ident,
                    ts_ms=1_700_000_000_100 + i)
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        book.save(d / "receipts_HMIX.ndjson")
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
            encoding="utf-8")
        rows = [{"arm": "HMIX", "task_id": f"t{i}"} for i in range(3)]
        rec = verify_arm(d, "HMIX", rows)
        ck("A_clean_chain_is_OK", rec["verdict"] == "OK" and rec["failures"] == []
           and rec["entries_n"] == 6 and rec["verified_n"] == 6
           and rec["verdict_n"] == 3 and rec["rows_n"] == 3,
           json.dumps(rec, ensure_ascii=False)[:400])
        ck("A2_stream_id_is_genesis_hash", rec["genesis_hash_is_stream_id"] is True)

        # 竄改 1：改 payload ⇒ 那一筆簽章必須紅（而且指得出 seq）
        lines = (d / "receipts_HMIX.ndjson").read_text(encoding="utf-8").splitlines()
        e = json.loads(lines[1])
        e["payload"]["task_id"] = "tX"
        bad = list(lines)
        bad[1] = json.dumps(e, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        (d / "receipts_HMIX.ndjson").write_text("\n".join(bad) + "\n", encoding="utf-8")
        r2 = verify_arm(d, "HMIX", rows)
        ck("B_tampered_payload_is_caught",
           r2["verdict"] == "BROKEN"
           and any(f["reason"] == "bad_signature" and f["seq"] == 2
                   for f in r2["failures"]),
           json.dumps(r2["failures"], ensure_ascii=False)[:300])

        # 竄改 2：整條鏈重存、但換一把公鑰 ⇒ 每一筆都要紅
        book.save(d / "receipts_HMIX.ndjson")
        other = Identity.generate()
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": other.vacant_id, "pub_hex": pub_to_hex(other.pub)}),
            encoding="utf-8")
        r3 = verify_arm(d, "HMIX", rows)
        ck("C_wrong_pubkey_fails_every_entry",
           r3["verdict"] == "BROKEN" and r3["failed_n"] == 6
           and r3["verified_n"] == 0,
           str(r3["failed_n"]))

        # 竄改 3：刪掉中間一筆 ⇒ seq／prev_hash 都要紅（不是只有一個）
        (d / "receipts_HMIX.pub.json").write_text(json.dumps(
            {"vacant_id": ident.vacant_id, "pub_hex": pub_to_hex(ident.pub)}),
            encoding="utf-8")
        lines = (d / "receipts_HMIX.ndjson").read_text(encoding="utf-8").splitlines()
        (d / "receipts_HMIX.ndjson").write_text(
            "\n".join(lines[:2] + lines[3:]) + "\n", encoding="utf-8")
        r4 = verify_arm(d, "HMIX", rows)
        ck("D_deleted_entry_is_caught",
           r4["verdict"] == "BROKEN"
           and any(f["reason"] == "seq_not_contiguous" for f in r4["failures"])
           and any(f["reason"] == "prev_hash_broken" for f in r4["failures"]),
           json.dumps([f["reason"] for f in r4["failures"]], ensure_ascii=False))

        # 對帳牙齒：rows 多一題但收據沒有 ⇒ 條數與 task_id 兩條都要紅
        book.save(d / "receipts_HMIX.ndjson")
        r5 = verify_arm(d, "HMIX", rows + [{"arm": "HMIX", "task_id": "t9"}])
        ck("E_missing_verdict_for_a_row_is_caught",
           r5["verdict"] == "BROKEN"
           and any(f["reason"] == "verdict_count_ne_rows" for f in r5["failures"])
           and any(f["reason"] == "verdict_task_ids_ne_rows" for f in r5["failures"]),
           json.dumps([f["reason"] for f in r5["failures"]], ensure_ascii=False))
    for f in fails:
        print(f"  FAIL {f}")
    print("selftest: " + ("PASS" if not fails else f"{len(fails)} FAILED"))
    return 1 if fails else 0


def render(out: dict) -> str:
    L = [f"═══ 收據鏈驗證 {out['glob']} ═══",
         f"run {out['runs_n']}　鏈 {out['chains_n']}　"
         f"entries {out['entries_total']}　驗過 {out['verified_total']}　"
         f"失敗 {out['failed_total']}　壞鏈 {out['broken_chains_n']}",
         "",
         f"{'run':30}{'arm':9}{'條數':>6}{'驗過':>6}{'失敗':>6}"
         f"{'verdict':>8}{'rows':>6}  chain_head"]
    for r in out["chains"]:
        L.append(f"{r['run']:30}{r['arm']:9}{r['entries_n']:>6}{r['verified_n']:>6}"
                 f"{r['failed_n']:>6}{r.get('verdict_n', 0):>8}"
                 f"{r.get('rows_n', 0):>6}  {(r['head'] or '')[:16]}…  {r['verdict']}")
        for f in r["failures"]:
            L.append(f"    ! {json.dumps(f, ensure_ascii=False)}")
    L += ["", f"總判：{out['verdict']}", out["note"]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", help="run 目錄的 glob（相對 repo 根），例如 'runs/g_r529_*'")
    ap.add_argument("--json", help="把報表寫成 JSON")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.glob:
        ap.error("要給 --glob 或 --selftest")
    out = run_glob(args.glob)
    print(render(out))
    if args.json:
        p = pathlib.Path(args.json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 0 if out["verdict"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
