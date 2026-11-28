#!/usr/bin/env python3
"""B25 補回驗收（不看答案鍵；失敗就不發射回饋臂）。2026-11-28，附錄 B 補充。

  (1) 每一筆出口紀錄（source_fetch，200，非 TLS）的 sha256，必須剛好對到該格凍結站（site_frozen）裡的一個檔；對不到 ⇒「無法補回」（列入 B27）。
  (2) 正控制（--positive-root）：用 VACANT_HOOK_NO_GC=1 跑出的格，把保留的內容當作不存在、用同一支補回，結果必須和保留的內容逐位元組相同。
  (3) 補回後，每份 c0 紀錄到的頁面集合（去重、200）必須等於來源伺服器 access.jsonl 在該格 c0 執行窗內回 200 的頁面集合。
  (4) 補回的內容另簽一條新鏈：每份 c0 寫 c0/restore_chain.ndjson＋restore_chain.pub.json（事件 RESTORED_PAGE：網址、原 sha256、
      凍結檔名、補回時間），不覆寫原鏈。稱為「依出口 sha256 補回的內容」，不是原始簽章紀錄。（--write-chain 才寫）
  (5) 分台、分 gc 狀態報每份初稿的補回頁數與無法補回頁數。
用法：expT_b25.py <root> [<root> ...] [--positive-root R] [--write-chain] [--json OUT]
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402
from vacant_network import crypto  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402


def frozen_by_sha(c0: pathlib.Path) -> dict[str, list[str]]:
    m: dict[str, list[str]] = {}
    for f in (c0 / "site_frozen").glob("*"):
        if f.is_file():
            m.setdefault(hashlib.sha256(f.read_bytes()).hexdigest(), []).append(f.name)
    return m


def check_cell(c0: pathlib.Path, write_chain: bool) -> dict:
    rec = FB.open_recorder(c0 / "snapshot" / "vh")
    fz = frozen_by_sha(c0)
    pinned = set(json.loads((c0 / "site_snapshot_sha256.json").read_text()).values())
    evs = [e for e in rec.events() if e.get("type") == "source_fetch" and e.get("status") == 200 and not e.get("tls")]
    bad_map, restored, unrestorable, recorded = [], [], [], set()
    for e in evs:
        sha = e.get("sha256"); names = fz.get(sha, [])
        if len(names) != 1 or sha not in pinned:
            bad_map.append({"url": e["url"], "matches": len(names)})
        has_blob = S._blob_text(rec, sha) is not None
        if has_blob:
            recorded.add(e["url"])
        elif len(names) == 1 and sha in pinned:
            restored.append({"url": e["url"], "sha256": sha, "frozen_file": names[0]}); recorded.add(e["url"])
        else:
            unrestorable.append(e["url"])
    # (3) 對伺服器存取紀錄
    root = c0.parents[2] if c0.parts[-3] != "cells" else c0.parents[3]
    root = c0.parent.parent.parent.parent
    sid, rep = c0.parts[-3], c0.parts[-2]
    host = f"{sid}-{rep}.d2-sources.example"
    rj = json.loads((c0 / "run" / "run.json").read_text())
    acc = [json.loads(l) for l in (root / "access.jsonl").read_text().splitlines() if l.strip()]
    srv = {f"http://{a['host']}{a['path']}" for a in acc if a.get("host") == host and a.get("status") == 200
           and rj["t_start"] - 1 <= a.get("ts", 0) <= rj["t_end"] + 1}
    uniq_restored = {r["url"]: r for r in restored}
    out = {"set": sid, "rep": rep, "egress_200": len(evs), "unique_pages": len({e['url'] for e in evs}),
           "restored_pages": len(uniq_restored), "unrestorable_pages": len(set(unrestorable)), "sha_not_exactly_one_frozen": bad_map,
           "recorded_eq_server": recorded == srv, "recorded_minus_server": sorted(recorded - srv), "server_minus_recorded": sorted(srv - recorded),
           "gc_ran": (c0 / "snapshot" / "vh" / "gc_report.json").is_file()}
    if write_chain and uniq_restored and not (c0 / "restore_chain.ndjson").exists():
        ident = Identity.generate(); book = Logbook()
        for r in uniq_restored.values():
            book.append("RESTORED_PAGE", {"url": r["url"], "sha256": r["sha256"], "frozen_file": r["frozen_file"],
                                          "basis": "egress sha256 == revision-0 frozen page sha256 (Appendix B supplement B25)",
                                          "restored_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, ident, ts_ms=int(time.time() * 1000))
        book.save(c0 / "restore_chain.ndjson")
        (c0 / "restore_chain.pub.json").write_text(json.dumps({"vacant_id": ident.vacant_id, "pub_hex": crypto.pub_to_hex(ident.pub),
                                                               "head": book.head(), "note": "依出口 sha256 補回的內容（不是原始簽章紀錄）"}, indent=1))
        out["restore_chain_written"] = True
    return out


def positive_control(root: pathlib.Path) -> dict:
    """NO_GC 跑出的格：保留的內容檔 vs 凍結頁（補回會用的那份）逐位元組比對。"""
    res = {"cells": 0, "pages": 0, "byte_identical": 0, "mismatch": []}
    for c0 in sorted((root / "cells").glob("*/r*/c0")):
        rec = FB.open_recorder(c0 / "snapshot" / "vh"); fz = frozen_by_sha(c0); res["cells"] += 1
        for e in rec.events():
            if e.get("type") == "source_fetch" and e.get("status") == 200 and not e.get("tls"):
                p = rec.blobs.path(e["sha256"])
                if not p.exists():
                    res["mismatch"].append({"url": e["url"], "why": "blob missing under NO_GC"}); continue
                names = fz.get(e["sha256"], [])
                res["pages"] += 1
                if len(names) == 1 and (c0 / "site_frozen" / names[0]).read_bytes() == p.read_bytes():
                    res["byte_identical"] += 1
                else:
                    res["mismatch"].append({"url": e["url"], "why": f"frozen matches={len(names)}"})
        res["gc_ran"] = (c0 / "snapshot" / "vh" / "gc_report.json").is_file()
    return res


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs="+"); ap.add_argument("--positive-root")
    ap.add_argument("--write-chain", action="store_true"); ap.add_argument("--json")
    a = ap.parse_args()
    out = {"cells": [], "positive_control": None}
    if a.positive_root:
        out["positive_control"] = positive_control(pathlib.Path(a.positive_root))
    for r in a.roots:
        for c0 in sorted(pathlib.Path(r).glob("cells/*/r*/c0")):
            if (c0 / "done.json").is_file():
                d = check_cell(c0, a.write_chain); d["root"] = pathlib.Path(r).name; out["cells"].append(d)
    cs = out["cells"]
    pc = out["positive_control"] or {}
    out["summary"] = {"cells": len(cs), "restored_pages": sum(c["restored_pages"] for c in cs), "unrestorable_pages": sum(c["unrestorable_pages"] for c in cs),
                      "cells_with_restore": sum(1 for c in cs if c["restored_pages"]), "sha_map_failures": sum(len(c["sha_not_exactly_one_frozen"]) for c in cs),
                      "recorded_ne_server": [f"{c['root']}/{c['set']}/{c['rep']}" for c in cs if not c["recorded_eq_server"]],
                      "positive_control_pass": bool(pc) and not pc.get("mismatch") and pc.get("pages", 0) > 0 and not pc.get("gc_ran"),
                      "by_root": {r: {"cells": sum(1 for c in cs if c["root"] == r), "restored": sum(c["restored_pages"] for c in cs if c["root"] == r),
                                      "unrestorable": sum(c["unrestorable_pages"] for c in cs if c["root"] == r),
                                      "gc_ran_cells": sum(1 for c in cs if c["root"] == r and c["gc_ran"])} for r in {c["root"] for c in cs}}}
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({"summary": out["summary"], "positive_control": {k: v for k, v in pc.items() if k != "mismatch"} | {"mismatch_n": len(pc.get("mismatch", []))} if pc else None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
