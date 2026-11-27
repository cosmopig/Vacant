#!/usr/bin/env python3
"""控制器實驗的稽核包匯出：逐格結果表（CSV＋JSON）、C 臂決策事件（JSONL）＋鏈頭錨點、token／逾時分主機分解。
不輸出家目錄路徑、主機位址、帳號：主機只用 provider 名（lms1003*／lms1004*／colab-*），路徑一律相對 root。
用法：export_ctl_audit.py <root> <out_dir> <batch_name>"""
import csv, hashlib, json, pathlib, shutil, sys, collections
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
from vacant_network.logbook import LogEntry, Logbook  # noqa: E402
from vacant_network.identity import PublicIdentity  # noqa: E402

def load(p):
    try: return json.loads(pathlib.Path(p).read_text())
    except Exception: return None

def main(root, out, name):
    root, out = pathlib.Path(root), pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    rows, events, anchors = [], [], []
    for cj in sorted(root.glob("cells/*/*/*/cell.json")):
        c = load(cj); cdir = cj.parent
        atts = []
        for i, a in enumerate(c.get("attempts", []), 1):
            aj = load(cdir / f"attempt_{i}" / "attempt.json") or {}
            g = (aj.get("grade") or {}).get("detail") or {}
            u = a.get("usage") or aj.get("usage") or {}
            atts.append({"k": i, "started": aj.get("started"), "acc_passed": a.get("acc_passed"), "acc_total": a.get("acc_run"), "acc_status": a.get("acc_status"),
                         "timed_out": a.get("timed_out"), "wall_s": a.get("wall_s"), "rule": a.get("rule"), "action": a.get("action"),
                         "hidden_passed": g.get("tests_passed"), "hidden_total": g.get("tests_total"), "hidden_pass": a.get("grade_pass"),
                         "tokens_in": u.get("input"), "tokens_out": u.get("output"), "calls": u.get("calls")})
        d = c.get("delivered_attempt")
        dl = atts[d - 1] if d and d <= len(atts) else {}
        tok = sum((x["tokens_in"] or 0) + (x["tokens_out"] or 0) for x in atts)
        rows.append({"batch": name, "task": c.get("task"), "rep": c.get("rep"), "arm": c.get("arm"), "host": c.get("provider"),
                     "started": c.get("started"), "ended": c.get("ended"), "n_attempts": len(atts), "delivered_attempt": d, "accepted": c.get("accepted"),
                     "hidden_pass": c.get("pass"), "hidden_passed": dl.get("hidden_passed"), "hidden_total": dl.get("hidden_total"),
                     "timeouts": sum(1 for x in atts if x["timed_out"]), "tokens_total": tok, "wall_s": c.get("wall_s"),
                     "infra_void": c.get("infra_void"), "harness_sha256": c.get("harness_sha256"), "plan_sha256": c.get("plan_sha256"),
                     "attempts": atts})
        ch = cdir / "controller_chain.ndjson"
        if ch.exists():
            raw = ch.read_bytes(); lines = [l for l in raw.decode().splitlines() if l.strip()]
            ents = [LogEntry.from_json(json.loads(l)) for l in lines]
            for e in ents:
                p = e.payload if isinstance(e.payload, dict) else {}
                events.append({"batch": name, "cell": c.get("cell"), "seq": e.seq, "ts_ms": e.ts_ms, "type": e.type, "attempt": p.get("attempt"),
                               "rule": p.get("rule"), "action": p.get("action"), "reason": p.get("reason"), "evidence": p.get("evidence")})
            pubf = cdir / "controller_chain.pub.json"; pub = load(pubf) or {}
            ok = None
            if pub.get("pub_hex"):
                ok = Logbook(ents).verify_chain(PublicIdentity.from_hex(pub["vacant_id"], pub["pub_hex"]))
            dst = out / f"{name}_chains" / c.get("cell").replace("/", "__")
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ch, dst / "controller_chain.ndjson")
            if pubf.exists(): shutil.copyfile(pubf, dst / "controller_chain.pub.json")
            anchors.append({"batch": name, "cell": c.get("cell"), "events": len(ents), "chain_sha256": hashlib.sha256(raw).hexdigest(),
                            "stream_id": Logbook(ents).stream_id(), "head": Logbook(ents).head(), "pub_hex": pub.get("pub_hex"),
                            "vacant_id": pub.get("vacant_id"), "verify_chain": ok,
                            "chain_file": f"{name}_chains/" + c.get("cell").replace("/", "__") + "/controller_chain.ndjson"})
    (out / f"{name}_cells.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    flat = [{k: v for k, v in r.items() if k != "attempts"} for r in rows]
    with open(out / f"{name}_cells.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0].keys())); w.writeheader(); w.writerows(flat)
    with open(out / f"{name}_controller_events.jsonl", "w") as f:
        for e in events: f.write(json.dumps(e, ensure_ascii=False) + "\n")
    (out / f"{name}_chain_anchors.json").write_text(json.dumps(anchors, ensure_ascii=False, indent=1))
    # token / timeout decomposition by arm × host
    agg = collections.defaultdict(lambda: {"cells": 0, "tokens": 0, "timeouts": 0, "attempts": 0, "early_stop_pass_at_1": 0})
    for r in rows:
        if r["infra_void"]: continue
        a = agg[(r["arm"], r["host"])]; a["cells"] += 1; a["tokens"] += r["tokens_total"]; a["timeouts"] += r["timeouts"]; a["attempts"] += r["n_attempts"]
        if r["n_attempts"] == 1 and r["accepted"]: a["early_stop_pass_at_1"] += 1
    dec = [{"arm": k[0], "host": k[1], **v, "tokens_per_cell": round(v["tokens"] / v["cells"]) if v["cells"] else None} for k, v in sorted(agg.items())]
    (out / f"{name}_token_timeout_by_arm_host.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1))
    txt = (out / f"{name}_cells.json").read_text() + (out / f"{name}_controller_events.jsonl").read_text()
    assert "/home/" not in txt and "100.119." not in txt and "100.86." not in txt, "private path/IP leaked"
    for d in sorted((out / f"{name}_chains").glob("*/controller_chain.ndjson")):
        t = d.read_text(); assert "/home/" not in t, "private path in chain"
    print(name, "cells", len(rows), "events", len(events), "anchors", len(anchors), "verify_ok", sum(1 for a in anchors if a["verify_chain"]), "heads_null", sum(1 for a in anchors if not a["head"]))
    for d in dec: print(" ", d)

if __name__ == "__main__":
    main(*sys.argv[1:4])
