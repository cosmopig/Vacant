#!/usr/bin/env python3
"""重算 c0 的紀錄標記（量具修正，2026-11-28；附錄 B 補充）。不叫任何模型；不改任何既有檔（新寫 flags_v2.json）。

對 root 底下每一份 c0：開 c0/snapshot/vh 的紀錄，用和 c0 當時相同的邊界（done.json 的 chain_len）重算：
  1. literal 模式（舊行為）—— 檢查和原本的 flags.json 逐行相同（重現性）；
  2. 修正模式（預設 b24：凍結頁按 sha256 補回被 gc 刪的內容＋B24 封閉三項正規化；--mode n2db 只用來重現已棄用的寬規則）
     → 寫 c0/flags_v2.json，並記補回了幾頁、補不回的頁（sha256 不在凍結頁、或凍結頁 sha256 不符）。
--regress：另外用答案鍵算回歸數字（只看 c0 初稿本身的被標行，不算任何臂的分數）：修正前後被標的有值行數、
  其中評為錯的比例（標記精確度），分組別；以及修正後仍被標、但寬鬆口徑（數字序列）判斷值在頁面裡的行數（要另查）。
用法：expT_reflag.py <root> [--write] [--regress] [--json OUT]
"""
from __future__ import annotations
import argparse, collections, json, pathlib, re, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def flags_for(c0: pathlib.Path, claims, mode: str):
    FB.set_flag_matching(mode)
    rec = FB.open_recorder(c0 / "snapshot" / "vh")
    done = json.loads((c0 / "done.json").read_text())
    text = (c0 / "report.md").read_text(encoding="utf-8", errors="replace")
    return FB.compute_flags_from_recorder(rec, text, claims, round_idx=0, prev_values=None, prev_bound_seq=0,
                                          cur_bound_seq=int(done.get("chain_len") or 0) or None, ingest_egress=False), rec


def restore_stats(rec, c0: pathlib.Path):
    pinned = set(json.loads((c0 / "site_snapshot_sha256.json").read_text()).values())
    restored, unrestorable = [], []
    for e in rec.events():
        if e.get("type") == "source_fetch" and e.get("status") == 200 and e.get("sha256") and not e.get("tls"):
            if S._blob_text(rec, e["sha256"]) is None:
                (restored if e["sha256"] in FB.FROZEN_FALLBACK and e["sha256"] in pinned else unrestorable).append(e["url"])
    return sorted(set(restored)), sorted(set(unrestorable))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("root"); ap.add_argument("--write", action="store_true")
    ap.add_argument("--regress", action="store_true"); ap.add_argument("--json"); ap.add_argument("--mode", default="b24", choices=["b24", "n2db"])
    a = ap.parse_args(); root = pathlib.Path(a.root)
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]
    truth = M.load_manifests_with_truth(plan)
    out = {"cells": [], "literal_reproduces_original": 0, "literal_mismatch": [], "regress": None}
    reg = collections.defaultdict(lambda: collections.Counter())
    for c0 in sorted((root / "cells").glob("*/r*/c0")):
        if not (c0 / "done.json").is_file() or not (c0 / "flags.json").is_file():
            continue
        sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
        claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
        FB.add_frozen_fallback(c0 / "site_frozen", c0 / "site_snapshot_sha256.json")
        orig = json.loads((c0 / "flags.json").read_text())
        lit, _ = flags_for(c0, claims, "literal")
        same = {k: v.get("flagged") for k, v in lit["flags_by_claim"].items()} == {k: v.get("flagged") for k, v in orig["flags_by_claim"].items()}
        if same:
            out["literal_reproduces_original"] += 1
        else:
            out["literal_mismatch"].append(f"{sid}/r{rep}")
        v2, rec = flags_for(c0, claims, a.mode)
        restored, unrestorable = restore_stats(rec, c0)
        v2["flag_matching"] = a.mode; v2["restored_pages"] = restored; v2["unrestorable_pages"] = unrestorable
        if a.write:
            (c0 / "flags_v2.json").write_text(json.dumps(v2, ensure_ascii=False, indent=1))
        out["cells"].append({"set": sid, "rep": rep, "flagged_before": orig["flagged_count"], "flagged_after": v2["flagged_count"],
                             "restored_pages": len(restored), "unrestorable_pages": len(unrestorable)})
        if a.regress:
            dom = "football" if sid.startswith(("fb", "ff")) else "software_company"
            # 寬鬆口徑用的頁面純文字：這一格出口 200 的頁（補回後）
            pages = []
            for e in rec.events():
                if e.get("type") == "source_fetch" and e.get("status") == 200 and not e.get("tls"):
                    t = FB._blob(rec, e.get("sha256"))
                    if t is not None:
                        pages.append(S._plain(t))
            seqs = ["|".join(x.replace(",", "") for x in NUM.findall(t)) for t in pages]
            for cid in orig["flags_by_claim"]:
                o, n = orig["flags_by_claim"][cid], v2["flags_by_claim"][cid]
                if o.get("is_blank"):
                    continue
                wrong = M.strict_status(o.get("value"), cid, tr, 0) != "correct"
                if o.get("flagged"):
                    reg[dom]["flagged_before"] += 1; reg[dom]["flagged_before_wrong"] += wrong
                if n.get("flagged"):
                    reg[dom]["flagged_after"] += 1; reg[dom]["flagged_after_wrong"] += wrong
                    toks = [x.replace(",", "") for x in NUM.findall(str(n.get("value") or ""))]
                    if len(toks) >= 2 and any(("|" + "|".join(toks) + "|") in ("|" + s_ + "|") for s_ in seqs):
                        reg[dom]["still_flagged_but_loose_match"] += 1
                if o.get("flagged") and not n.get("flagged"):
                    reg[dom]["unflagged_by_fix"] += 1; reg[dom]["unflagged_by_fix_wrong"] += wrong
    if a.regress:
        out["regress"] = {}
        for dom, c in reg.items():
            out["regress"][dom] = dict(c)
            out["regress"][dom]["precision_before"] = round(c["flagged_before_wrong"] / c["flagged_before"], 4) if c["flagged_before"] else None
            out["regress"][dom]["precision_after"] = round(c["flagged_after_wrong"] / c["flagged_after"], 4) if c["flagged_after"] else None
    s = json.dumps(out, ensure_ascii=False, indent=1)
    if a.json:
        pathlib.Path(a.json).write_text(s)
    print(json.dumps({k: v for k, v in out.items() if k != "cells"}, ensure_ascii=False))
    for c in out["cells"]:
        if c["set"] in ("fb-s14", "fb-s07") and c["rep"] == 1:
            print(c)


if __name__ == "__main__":
    main()
