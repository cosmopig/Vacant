"""量具。輸出扁平 key=value，讓 bash 拿得到而不用 jq。

三態鐵律：量不到的東西印 `null`，不印 0、不印 False。
"""
import json
import os
import pathlib
import sqlite3
import sys

# repo root 由呼叫端傳進來，不要從 sys.argv[0] 往上數——證據目錄搬到別處
# （`OUT=/tmp/...`）時往上數會數到別的地方，而且會安靜地數錯。
sys.path.insert(0, os.environ["VACANT_ROOT"])
from ops.exhibit.twin.twinstore import TwinStore  # noqa: E402


def counts(db):
    p = pathlib.Path(db)
    if not p.exists():
        print("exists=0"); return 0
    # ⚠ 這裡**不能**用 read_only=True：kill -9 之後主檔旁邊還躺著 `-wal`，
    # `mode=ro` 開檔時做不了 WAL 回復，會直接炸。而「重開時把 WAL 回復回來」
    # 正是第 4 節要量的東西。
    st = TwinStore(p)
    rows = list(st.conn.execute("SELECT seq,sub_id,kind,payload_json FROM twin_event"
                                " ORDER BY seq ASC"))
    kinds, per_sub, engines = {}, {}, {}
    with_reason = 0
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        d = per_sub.setdefault(r["sub_id"], {})
        d[r["kind"]] = d.get(r["kind"], 0) + 1
        if r["kind"] == "generated":
            try:
                pl = json.loads(r["payload_json"]) or {}
            except Exception:  # noqa: BLE001
                pl = {}
            e = pl.get("engine", "unparsable")
            engines[e] = engines.get(e, 0) + 1
            if e == "fallback_deterministic" and pl.get("degrade_reason"):
                with_reason += 1
    v = st.verify()
    print("exists=1")
    print("events=%d" % len(rows))
    for k in ("submitted", "generated", "published", "error", "ingest_gap", "note"):
        print("k_%s=%d" % (k, kinds.get(k, 0)))
    print("subs=%d" % len([s for s, d in per_sub.items() if d.get("submitted")]))
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("verify_checked=%d" % v["checked"])
    print("verify_broken_at=%s" % ("null" if v["broken_at"] is None else v["broken_at"]))
    real = sum(n for e, n in engines.items() if str(e).startswith("lmstudio:"))
    fb = engines.get("fallback_deterministic", 0)
    print("engine_real=%d" % real)
    print("engine_fallback=%d" % fb)
    print("engine_other=%d" % (sum(engines.values()) - real - fb))
    print("degraded_with_reason=%d" % with_reason)
    print("store_bytes=%d" % p.stat().st_size)
    mx = 0
    for s, d in per_sub.items():
        if d.get("submitted"):
            mx = max(mx, d.get("generated", 0))
    print("max_generated_per_sub=%d" % mx)
    mxs = max([d.get("submitted", 0) for d in per_sub.values()] or [0])
    print("max_submitted_per_sub=%d" % mxs)
    st.close()
    return 0


def viewfile(path):
    p = pathlib.Path(path)
    if not p.exists():
        print("exists=0"); return 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print("exists=1"); print("parses=0"); print("err=%s" % type(e).__name__); return 0
    print("exists=1"); print("parses=1")
    ppl = d.get("people") or []
    print("people=%d" % len(ppl))
    print("chain_ok=%d" % (1 if ((d.get("chain") or {}).get("ok")) else 0))
    print("v_real=%d" % len([p for p in ppl if str(p.get("engine") or "").startswith("lmstudio:")]))
    print("v_fallback=%d" % len([p for p in ppl if p.get("engine") == "fallback_deterministic"]))
    print("v_noengine=%d" % len([p for p in ppl if not p.get("engine")]))
    print("gaps=%s" % ((d.get("counts") or {}).get("gaps")))
    print("errors=%s" % ((d.get("counts") or {}).get("errors")))
    print("bytes=%d" % p.stat().st_size)
    return 0


def clockfold(db):
    """時鐘倒退：造一條 ts 遞減的事件流，看摺疊與驗鏈會不會出錯。

    負控制在這裡是**內建**的：同時算一次「如果照 ts 排序會摺出什麼」。
    兩者若相同，這個檢查就沒有解析度（證明不了 fold 不看 ts）。
    """
    p = pathlib.Path(db)
    st = TwinStore(p)
    st.append("submitted", "v1", {"card": {"need": "整理桌面"}}, source="probe",
              ts_unix_ms=3_000_000)
    st.append("generated", "v1", {"arrival": "第一版", "engine": "e_old"},
              source="probe", ts_unix_ms=2_000_000)
    # NTP 把時鐘往回校 40 分鐘之後才發生的那一列：ts 更小，但 seq 更大。
    st.append("generated", "v1", {"arrival": "第二版", "engine": "e_new"},
              source="probe", ts_unix_ms=1_000_000)
    cur = st.current("v1") or {}
    by_seq = (cur.get("twin") or {}).get("engine")
    rows = list(st.conn.execute("SELECT ts_unix_ms,payload_json FROM twin_event"
                                " WHERE kind='generated'"))
    by_ts = json.loads(sorted(rows, key=lambda r: r["ts_unix_ms"])[-1]["payload_json"])["engine"]
    v = st.verify()
    ts = [r["ts_unix_ms"] for r in st.conn.execute(
        "SELECT ts_unix_ms FROM twin_event ORDER BY seq ASC")]
    print("fold_by_seq=%s" % by_seq)
    print("fold_if_sorted_by_ts=%s" % by_ts)
    print("discriminates=%d" % (1 if by_seq != by_ts else 0))
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("ts_monotonic=%d" % (1 if all(b >= a for a, b in zip(ts, ts[1:])) else 0))
    print("flagged_by_anything=null")   # 沒有任何地方檢查 ts 單調——沒量到就是 null
    st.close()
    return 0


def tamper(db):
    """負控制：繞過 trigger 改一列，證明 verify 真的會紅（在**副本**上做）。"""
    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
    raw.execute("PRAGMA writable_schema=OFF"); raw.close()
    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("UPDATE twin_event SET payload_json='{\"tampered\":1}' WHERE seq=1")
    raw.close()
    st = TwinStore(db)
    v = st.verify()
    print("verify_ok=%d" % (1 if v["ok"] else 0))
    print("broken_at=%s" % ("null" if v["broken_at"] is None else v["broken_at"]))
    st.close()
    return 0


def seed(db, n):
    st = TwinStore(db)
    for i in range(int(n)):
        st.append("submitted", "seed-%02d" % i,
                  {"card": {"need": "整理第 %d 疊紙" % i, "shape": "圓潤",
                            "texture": "光滑", "color": "暖土", "vibe": "慢"},
                   "card_text": "需求：整理第 %d 疊紙" % i}, source="probe:seed")
    print("seeded=%d" % int(n))
    st.close()
    return 0


CMDS = {"counts": counts, "viewfile": viewfile, "clockfold": clockfold,
        "tamper": tamper, "seed": seed}
sys.exit(CMDS[sys.argv[1]](*sys.argv[2:]))
