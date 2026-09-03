#!/usr/bin/env python3
"""r444 的收據鏈稽核（CRITERION_20260903_R666）：P-C4 到底驗不驗得起來。

判準在 `CRITERION_20260903_R666_RECEIPT_CHAIN_UNVERIFIABLE.md`，本檔只執行它。

三個 verdict 刻意分開，**不准壓成兩個**：
  OK            —— 該項判準通過
  BROKEN        —— 該項判準被違反（有東西壞了）
  UNVERIFIABLE  —— 這一項在結構上量不到（鏈的 entries／公鑰不在磁碟上）。
                   它不是 BROKEN：SPEC_GAIN 對 infra_void 的同一種區分，
                   「沒量到」≠「量到 0」。把它塗成 BROKEN 會讓收官那一輪誤觸
                   R440R §四 的中止準則（那條說的是「verify_chain 為假」）。

用法：
  python3 ops/gain/replay/receipt_chain_audit.py --run runs/g_r444_conform_mbpp \\
      --rows /dev/shm/r666/rows.snapshot.jsonl --json out.json
  python3 ops/gain/replay/receipt_chain_audit.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

HEX64 = re.compile(r"^[0-9a-f]{64}$")
# run 目錄裡本來就有的三個 jsonl；鏈檔若存在會是別的名字。
KNOWN_JSONL = {"rows.jsonl", "calls.jsonl", "notes.jsonl"}


def audit_dir(run_dir: str) -> dict:
    """P-R666-1：run 目錄裡有沒有鏈檔／公鑰檔。"""
    if not os.path.isdir(run_dir):
        return {"verdict": "BROKEN", "reason": "run_dir_missing", "run_dir": run_dir}
    names = sorted(os.listdir(run_dir))
    chain_like = [n for n in names
                  if (n.endswith(".ndjson")
                      or (n.endswith(".jsonl") and n not in KNOWN_JSONL))]
    pub_like = [n for n in names if "pub" in n.lower() or n.endswith(".pem")]
    return {
        # 「沒有鏈檔」＝ P-R666-1 成立 ⇒ 這一項的 verdict 是 OK（預測命中），
        # 而鏈本身的可驗性另外用 chain_verifiable 表達，不要混在一起。
        "verdict": "OK",
        "files": names,
        "chain_like_files": chain_like,
        "pubkey_like_files": pub_like,
        "chain_verifiable": "YES" if (chain_like and pub_like) else "UNVERIFIABLE",
        "why": ("鏈的 entries 與公鑰都在磁碟上" if (chain_like and pub_like)
                else "run 目錄沒有鏈 entries／公鑰 ⇒ verify_chain 跑不起來"),
    }


def audit_rows(rows: list[dict]) -> dict:
    """P-R666-2/-3/-4：從 rows 能查到的結構性證據。"""
    if not rows:
        return {"verdict": "BROKEN", "reason": "no_rows"}

    missing_head, cross_arm_leak = [], []
    heads, attempt_hashes = [], []
    head_eq_last, n_conform = 0, 0

    for r in rows:
        arm = r.get("arm")
        head = r.get("receipt_head")
        if arm == "CONFORM":
            n_conform += 1
            if not (isinstance(head, str) and HEX64.match(head)):
                missing_head.append(r.get("task_id"))
            else:
                heads.append(head)
            ats = r.get("conform_attempts") or []
            hs = [a.get("entry_hash") for a in ats if a.get("entry_hash")]
            attempt_hashes.extend(hs)
            # verdict 事件在 attempts 之後追加 ⇒ 鏈頭必然已經前進。
            if hs and head == hs[-1]:
                head_eq_last += 1
        elif head is not None:
            cross_arm_leak.append((arm, r.get("task_id")))

    dup_attempt = [h for h, c in Counter(attempt_hashes).items() if c > 1]
    dup_head = [h for h, c in Counter(heads).items() if c > 1]

    p2 = "OK" if (not missing_head and not cross_arm_leak and n_conform > 0) else "BROKEN"
    p3 = "OK" if not dup_attempt else "BROKEN"
    p4 = "OK" if (not dup_head and head_eq_last == 0) else "BROKEN"

    return {
        "verdict": "OK" if p2 == p3 == p4 == "OK" else "BROKEN",
        "n_rows": len(rows), "n_conform_rows": n_conform,
        "P-R666-2": {"verdict": p2, "missing_receipt_head": len(missing_head),
                     "missing_task_ids": missing_head[:10],
                     "cross_arm_leak": len(cross_arm_leak)},
        "P-R666-3": {"verdict": p3, "n_attempt_hashes": len(attempt_hashes),
                     "n_unique": len(set(attempt_hashes)),
                     "n_duplicated_values": len(dup_attempt)},
        "P-R666-4": {"verdict": p4, "n_heads": len(heads),
                     "n_unique_heads": len(set(heads)),
                     "head_equals_last_attempt": head_eq_last},
    }


def verify_persisted_chains(run_dir: str) -> dict:
    """P-C4 後半：run 目錄裡若有落盤的鏈＋公鑰，就真的重算並驗簽。

    round666 之後 `gain_run.save_receipts` 會寫 `receipts_<ARM>.ndjson` 與
    `receipts_<ARM>.pub.json`。沒有那兩個檔就是 UNVERIFIABLE（r444 的狀態），
    **不是** BROKEN——別讓收官那一輪誤觸 R440R §四 的中止準則。
    """
    sys.path.insert(0, os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    from vacant.identity import PublicIdentity
    from vacant.logbook import Logbook

    out = {}
    if not os.path.isdir(run_dir):
        return {"verdict": "BROKEN", "reason": "run_dir_missing"}
    for name in sorted(os.listdir(run_dir)):
        if not name.startswith("receipts_") or not name.endswith(".ndjson"):
            continue
        arm = name[len("receipts_"):-len(".ndjson")]
        pub_path = os.path.join(run_dir, f"receipts_{arm}.pub.json")
        if not os.path.exists(pub_path):
            out[arm] = {"verdict": "BROKEN", "reason": "chain_without_pubkey"}
            continue
        meta = json.load(open(pub_path, encoding="utf-8"))
        book = Logbook.load(__import__("pathlib").Path(run_dir) / name)
        who = PublicIdentity.from_hex(meta["vacant_id"], meta["pub_hex"])
        ok = book.verify_chain(who)
        out[arm] = {"verdict": "OK" if ok else "BROKEN",
                    "verify_chain": bool(ok), "n_entries": len(book),
                    "vacant_id": meta["vacant_id"]}
    if not out:
        return {"verdict": "UNVERIFIABLE",
                "reason": "no receipts_<ARM>.ndjson in run dir",
                "arms": {}}
    return {"verdict": "OK" if all(v["verdict"] == "OK" for v in out.values())
            else "BROKEN", "arms": out}


def load_rows(path: str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# ---------------------------------------------------------------- self-test
def _fixture() -> list[dict]:
    rows = []
    for i in range(3):
        rows.append({"arm": "OFF", "task_id": f"t{i}", "receipt_head": None})
        rows.append({
            "arm": "CONFORM", "task_id": f"t{i}",
            "receipt_head": "%064x" % (1000 + i),
            "conform_attempts": [{"attempt": 1, "entry_hash": "%064x" % (2000 + i)},
                                 {"attempt": 2, "entry_hash": "%064x" % (3000 + i)}],
        })
    return rows


def selftest() -> int:
    """乾淨 fixture 要全 OK；四個突變體各自要把對應判準翻成 BROKEN。

    「乾淨 PASS」單獨不算數——會 PASS 的瞎尺真的存在（GAIN_STATE 歷輪）。
    """
    import copy
    fails = []
    clean = audit_rows(_fixture())
    if clean["verdict"] != "OK":
        fails.append(f"clean fixture 應為 OK，實得 {clean['verdict']} / {clean}")

    m1 = copy.deepcopy(_fixture()); m1[1]["receipt_head"] = None
    if audit_rows(m1)["P-R666-2"]["verdict"] != "BROKEN":
        fails.append("M1（抹掉一列 receipt_head）沒被抓到")

    m2 = copy.deepcopy(_fixture())
    m2[3]["conform_attempts"][0]["entry_hash"] = m2[1]["conform_attempts"][0]["entry_hash"]
    if audit_rows(m2)["P-R666-3"]["verdict"] != "BROKEN":
        fails.append("M2（兩列 entry_hash 相同）沒被抓到")

    m3 = copy.deepcopy(_fixture())
    m3[1]["receipt_head"] = m3[1]["conform_attempts"][-1]["entry_hash"]
    if audit_rows(m3)["P-R666-4"]["verdict"] != "BROKEN":
        fails.append("M3（鏈頭＝最後一個 attempt hash）沒被抓到")

    if audit_rows([])["verdict"] != "BROKEN":
        fails.append("M4（空輸入）應為 BROKEN 不是 OK")

    # 「安靜量不到」型：CONFORM 一列都沒有時不准回 OK
    m5 = [r for r in _fixture() if r["arm"] != "CONFORM"]
    if audit_rows(m5)["P-R666-2"]["verdict"] != "BROKEN":
        fails.append("M5（沒有任何 CONFORM 列）應為 BROKEN")

    for f in fails:
        print("SELFTEST FAIL:", f)
    print(f"SELFTEST {'PASS' if not fails else 'FAIL'} — 1 clean + 5 mutants")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--rows")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.run and a.rows):
        ap.error("--run 與 --rows 都要給（rows 用快照，不要讀 live 檔）")
    chains = verify_persisted_chains(a.run)
    res = {"run_dir": a.run, "rows_path": a.rows,
           "dir": audit_dir(a.run), "rows": audit_rows(load_rows(a.rows)),
           "persisted_chains": chains}
    res["P-R666-1"] = {
        "verdict": "OK" if not res["dir"]["chain_like_files"] else "OVERTURNED",
        "chain_verifiable": res["dir"]["chain_verifiable"]}
    res["P-C4_second_half_settleable"] = (chains["verdict"] != "UNVERIFIABLE")
    res["P-C4_second_half"] = chains["verdict"]
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
