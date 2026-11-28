#!/usr/bin/env python3
"""量具修正的發射前檢查（附錄 B 補充 B32(4)、B33(1)、B34 抽樣），都**不用答案鍵**。2026-11-28。

對 root（可多個）底下每一份 c0（用 c0/snapshot/vh 的紀錄、done.json 的 chain_len 為邊界）：
  B32(4) 不變性：值與這一格所有頁面文字（伺服器送來的、補回後）都不含 `*`、反引號、括號旁空白的行，
         b24 模式與 literal 模式的標記必須逐行相同（另需這一格沒有補回頁）。報合格行數與不符行數。
  B33(1) 一致性：b24 模式下理由是「值沒在讀過的內容裡」的被標行，值若在伺服器送給該格的頁面裡用同一套正規化找得到 ⇒ 實作錯誤。必須是 0。
  B34 母體：b24 模式下仍被標、且寬鬆口徑（值的數字序列依序出現在該格伺服器頁面的數字序列中）找得到的有值行，
         按 (組, 次, 行 id) 排序；依組類（足球／公司）比例分配 30 行（四捨五入、合計 30），各層用 random.Random(20261131).sample 抽。
用法：expT_flagcheck.py <root> [<root> ...] [--sample-out FILE] [--json OUT]
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, random, re, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def claims_of(root: pathlib.Path):
    plan = json.loads((root / "RUN.json").read_text())["plan_body"]
    out = {}
    for mat in plan["materials"]:
        d = pathlib.Path(__import__("os").path.expandvars(mat["dir"]))
        man = json.loads((d / "manifest.json").read_text())
        for s in man["sets"]:
            out[f"{mat['prefix']}-{s['set']}"] = s["claims"]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("roots", nargs="+"); ap.add_argument("--sample-out"); ap.add_argument("--json")
    a = ap.parse_args()
    res = {"cells": 0, "b32_qualifying_lines": 0, "b32_mismatch": [], "b33_inconsistent": [], "population": []}
    for r in a.roots:
        root = pathlib.Path(r); claims_by = claims_of(root)
        for c0 in sorted((root / "cells").glob("*/r*/c0")):
            if not (c0 / "done.json").is_file():
                continue
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:]); claims = claims_by[sid]
            FB.add_frozen_fallback(c0 / "site_frozen", c0 / "site_snapshot_sha256.json")
            done = json.loads((c0 / "done.json").read_text()); text = (c0 / "report.md").read_text(encoding="utf-8", errors="replace")
            bound = int(done.get("chain_len") or 0) or None
            FB.set_flag_matching("literal"); rec = FB.open_recorder(c0 / "snapshot" / "vh")
            lit = FB.compute_flags_from_recorder(rec, text, claims, round_idx=0, cur_bound_seq=bound, ingest_egress=False)
            FB.set_flag_matching("b24"); rec = FB.open_recorder(c0 / "snapshot" / "vh")
            b24 = FB.compute_flags_from_recorder(rec, text, claims, round_idx=0, cur_bound_seq=bound, ingest_egress=False)
            res["cells"] += 1
            evs = [e for e in rec.events() if e.get("type") == "source_fetch" and e.get("status") == 200 and not e.get("tls")]
            restored = any(S._blob_text(rec, e.get("sha256")) is None for e in evs)
            raw = [FB._blob(rec, e.get("sha256")) or "" for e in evs]
            plains = [S._plain(t) for t in raw]
            univ = FB.fetch_universe(rec)
            univ_plain = [S._plain(str(u.get("text") or "")) for u in univ if bound is None or int(u["seq"]) <= bound]
            pages_invariant = all(FB.b24_norm(p) == p for p in univ_plain)
            seqs = ["|".join(x.replace(",", "") for x in NUM.findall(t)) for t in plains]
            for cid, n in b24["flags_by_claim"].items():
                v = n.get("value")
                if v is None:
                    continue
                # B32(4)
                if FB.b24_norm(v) == v and pages_invariant and not restored:
                    res["b32_qualifying_lines"] += 1
                    if bool(n.get("flagged")) != bool(lit["flags_by_claim"][cid].get("flagged")):
                        res["b32_mismatch"].append(f"{root.name}/{sid}/r{rep}/{cid}")
                if not n.get("flagged"):
                    continue
                # B33(1)
                if FB.PROBLEM_NOT_IN_FETCHED in (n.get("reasons") or []) or n.get("problem_kind", "") and FB.PROBLEM_NOT_IN_FETCHED in n.get("problem_kind", ""):
                    nv = FB.b24_norm(v)
                    if any(S.plain_contains(FB.b24_norm(p), nv) or S.plain_contains(t, v) for p, t in zip(plains, raw)):
                        res["b33_inconsistent"].append(f"{root.name}/{sid}/r{rep}/{cid}")
                # B34 母體
                toks = [x.replace(",", "") for x in NUM.findall(str(v))]
                if len(toks) >= 2 and any(("|" + "|".join(toks) + "|") in ("|" + s_ + "|") for s_ in seqs):
                    res["population"].append([root.name, sid, rep, cid])
    pop = sorted(res["population"], key=lambda x: (x[0], x[1], x[2], x[3]))
    strata = {"football": [p for p in pop if p[1].startswith(("fb", "ff"))], "company": [p for p in pop if not p[1].startswith(("fb", "ff"))]}
    n = len(pop); alloc = {}
    if n <= 30:
        sample = pop
    else:
        fb_n = round(30 * len(strata["football"]) / n); alloc = {"football": fb_n, "company": 30 - fb_n}
        sample = []
        for k, m in alloc.items():
            sample += random.Random(20261131).sample(strata[k], min(m, len(strata[k])))
    res["population_size"] = n; res["population_by_stratum"] = {k: len(v) for k, v in strata.items()}; res["allocation"] = alloc
    res["sample"] = sample
    blob = json.dumps(sample, ensure_ascii=False).encode()
    res["sample_sha256"] = hashlib.sha256(blob).hexdigest()
    if a.sample_out:
        pathlib.Path(a.sample_out).write_bytes(blob)
    del res["population"]
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "sample"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
