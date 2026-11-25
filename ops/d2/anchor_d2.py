#!/usr/bin/env python3
"""D2′ 外部錨點（external anchor）：在跑完當下把每條病歷鏈的尾巴、鏈檔雜湊、trust.json 雜湊、RUN.json 雜湊
寫進外部檔案；日後重算比對，可偵測任何截斷（刪尾幾筆）、改寫或換鑰重簽（連同 trust.json 一起換）。

只用標準函式庫，與 `audit_d2.py` 使用同一套 canonical 條目雜湊。

用法：
  anchor_d2.py write --root <run_root> --out <anchor.json>
  anchor_d2.py check --root <run_root> --anchor <anchor.json>
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import json
import pathlib
import sys
from typing import Any

ANCHOR_SCHEMA = "vacant.d2.anchor/1"


def canon_entry_bytes(entry: dict[str, Any]) -> bytes:
    """與 `audit_d2.Record._check_seq` 完全相同的條目正規化位元組。"""
    core = {k: entry.get(k) for k in ("stream_id", "branch_id", "seq", "prev_hash", "ts_ms", "type", "payload")}
    return json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def entry_hash(entry: dict[str, Any]) -> str:
    """單筆病歷條目的 sha256 雜湊（同 `audit_d2.py`）。"""
    return hashlib.sha256(canon_entry_bytes(entry)).hexdigest()


def _sha256_file(path: pathlib.Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _chain_files(pdir: pathlib.Path) -> list[pathlib.Path]:
    vols = sorted(pdir.glob("chain-*.ndjson*"))
    out = [v for v in vols if v.is_file()]
    cur = pdir / "chain.ndjson"
    if cur.is_file():
        out.append(cur)
    return out


def _load_events_and_sha(pdir: pathlib.Path) -> tuple[list[dict[str, Any]], str | None]:
    files = _chain_files(pdir)
    if not files:
        return [], None
    h = hashlib.sha256()
    events: list[dict[str, Any]] = []
    for f in files:
        raw = f.read_bytes()
        h.update(raw)
        data = gzip.decompress(raw) if f.suffix == ".gz" else raw
        for line in data.decode("utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events, h.hexdigest()


def discover_chains(root: pathlib.Path) -> dict[str, pathlib.Path]:
    """找出 `<root>/cells` 底下的每一條鏈：`cells/<set>/c0/snapshot/vh` 與 `cells/<set>/<arm>/final/vh`。"""
    out: dict[str, pathlib.Path] = {}
    cells = root / "cells"
    if not cells.is_dir():
        return out
    for sdir in sorted(p for p in cells.iterdir() if p.is_dir()):
        sid = sdir.name
        c0_vh = sdir / "c0" / "snapshot" / "vh"
        if c0_vh.is_dir():
            out[f"{sid}/c0"] = c0_vh
        for adir in sorted(p for p in sdir.iterdir() if p.is_dir() and p.name != "c0"):
            fin_vh = adir / "final" / "vh"
            if fin_vh.is_dir():
                out[f"{sid}/{adir.name}"] = fin_vh
    return out


def measure_chain(vh: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """量測單一 `vh` 的錨點資訊（回傳摘要 dict 與解析出的事件清單）。"""
    proj_root = vh / "trace" / "projects"
    projs = sorted(p for p in proj_root.iterdir() if p.is_dir()) if proj_root.is_dir() else []
    if len(projs) != 1:
        raise ValueError(f"{vh}: expected 1 project dir, got {len(projs)}")
    pdir = projs[0]
    events, chain_sha = _load_events_and_sha(pdir)
    last_seq = events[-1].get("seq") if events else None
    last_hash = entry_hash(events[-1]) if events else None
    trust_sha = _sha256_file(vh / "intake" / "trust.json")
    rec = {
        "entries": len(events),
        "last_seq": last_seq,
        "last_hash": last_hash,
        "chain_sha256": chain_sha,
        "trust_sha256": trust_sha,
    }
    return rec, events


def build_anchor(root: pathlib.Path) -> dict[str, Any]:
    """建立整個 run root 的外部錨點物件。"""
    root_p = pathlib.Path(root)
    chains: dict[str, dict[str, Any]] = {}
    for cid, vh in discover_chains(root_p).items():
        rec, _ = measure_chain(vh)
        chains[cid] = rec
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema": ANCHOR_SCHEMA,
        "timestamp": ts,
        "root": root_p.resolve().name,       # 只記 root 的名稱，不記含帳號名的絕對路徑（repo 公開；11-25 最終稽核）
        "run_json_sha256": _sha256_file(root_p / "RUN.json"),
        "chains": chains,
        # 第三次獨立稽核 11-25：執行器自己的紀錄（切週期用的 cycle.json、來源伺服器存取紀錄）也錨住
        "harness_files": harness_files(root_p),
    }


def harness_files(root_p: pathlib.Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {"access.jsonl": _sha256_file(root_p / "access.jsonl")}
    for f in sorted((root_p / "cells").glob("*/*/cycle_*/cycle.json")) + sorted((root_p / "cells").glob("*/c0/done.json")):
        out[str(f.relative_to(root_p))] = _sha256_file(f)
    return out


def check_anchor(root: pathlib.Path, anchor: dict[str, Any]) -> dict[str, Any]:
    """比對 `<root>` 現況與外部錨點；回報任何截斷、改寫、換鑰重簽、遺失或多出來的鏈與 RUN.json 變動。"""
    root_p = pathlib.Path(root)
    exp_run_sha = anchor.get("run_json_sha256")
    cur_run_sha = _sha256_file(root_p / "RUN.json")
    run_json_ok = cur_run_sha == exp_run_sha

    exp_chains: dict[str, dict[str, Any]] = anchor.get("chains") or {}
    found = discover_chains(root_p)

    missing_chains: list[str] = []
    extra_chains: list[str] = sorted(cid for cid in found if cid not in exp_chains)
    mismatches: list[dict[str, Any]] = []
    problems: list[str] = []

    if not run_json_ok:
        mismatches.append({
            "chain": "RUN.json",
            "reasons": ["run_json_sha256_mismatch"],
            "expected": {"run_json_sha256": exp_run_sha},
            "actual": {"run_json_sha256": cur_run_sha},
        })
        problems.append(f"RUN.json sha256 mismatch (expected {exp_run_sha}, got {cur_run_sha})")

    exp_hf = anchor.get("harness_files") or {}
    if exp_hf:
        cur_hf = harness_files(root_p)
        bad_hf = sorted(k for k in set(exp_hf) | set(cur_hf) if exp_hf.get(k) != cur_hf.get(k))
        if bad_hf:
            mismatches.append({"chain": "harness_files", "reasons": ["harness_file_changed"], "files": bad_hf[:50]})
            problems.append(f"{len(bad_hf)} harness files (cycle.json/done.json/access.jsonl) changed since the anchor")

    chains_ok = 0
    chains_bad = 0

    for cid in sorted(exp_chains):
        exp = exp_chains[cid]
        vh = found.get(cid)
        if vh is None:
            missing_chains.append(cid)
            chains_bad += 1
            mismatches.append({
                "chain": cid,
                "reasons": ["chain_missing"],
                "expected": exp,
                "actual": None,
            })
            problems.append(f"{cid}: chain missing")
            continue
        try:
            cur, events = measure_chain(vh)
        except Exception as exc:  # noqa: BLE001
            chains_bad += 1
            mismatches.append({
                "chain": cid,
                "reasons": [f"read_error: {exc}"],
                "expected": exp,
                "actual": None,
            })
            problems.append(f"{cid}: unreadable chain ({exc})")
            continue

        reasons: list[str] = []
        exp_seq = exp.get("last_seq")
        cur_seq = cur.get("last_seq")
        if cur_seq != exp_seq:
            if cur_seq is None or (exp_seq is not None and cur_seq < exp_seq):
                reasons.append(f"head_moved_backwards (seq {cur_seq} < {exp_seq})")
            else:
                # 檢查原本錨定的那一筆是否還在原處且雜湊相同
                at_exp = next((e for e in events if e.get("seq") == exp_seq), None)
                if at_exp is None or entry_hash(at_exp) != exp.get("last_hash"):
                    reasons.append(f"head_rewritten (seq {cur_seq} > {exp_seq}, anchored seq {exp_seq} hash mismatch)")
                else:
                    reasons.append(f"head_advanced (seq {cur_seq} > {exp_seq})")
        if cur.get("last_hash") != exp.get("last_hash"):
            reasons.append("last_hash_mismatch")
        if cur.get("chain_sha256") != exp.get("chain_sha256"):
            reasons.append("chain_sha256_mismatch")
        if cur.get("trust_sha256") != exp.get("trust_sha256"):
            reasons.append("trust_sha256_mismatch")

        if reasons:
            chains_bad += 1
            mismatches.append({
                "chain": cid,
                "reasons": reasons,
                "expected": exp,
                "actual": cur,
            })
            problems.append(f"{cid}: {', '.join(reasons)}")
        else:
            chains_ok += 1

    for cid in extra_chains:
        mismatches.append({
            "chain": cid,
            "reasons": ["unexpected_chain"],
            "expected": None,
            "actual": None,
        })
        problems.append(f"{cid}: unexpected chain not present in anchor")

    ok = run_json_ok and chains_bad == 0 and not missing_chains and not extra_chains
    return {
        "ok": ok,
        "anchor_timestamp": anchor.get("timestamp"),
        "run_json_ok": run_json_ok,
        "chains_checked": len(exp_chains),
        "chains_ok": chains_ok,
        "chains_bad": chains_bad,
        "missing_chains": missing_chains,
        "extra_chains": extra_chains,
        "mismatches": mismatches,
        "problems": problems,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D2 external anchor writer/checker")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_w = sub.add_parser("write", help="Write anchor JSON for all chains under --root")
    p_w.add_argument("--root", required=True)
    p_w.add_argument("--out", required=True)

    p_c = sub.add_parser("check", help="Check --root against an anchor JSON")
    p_c.add_argument("--root", required=True)
    p_c.add_argument("--anchor", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "write":
        doc = build_anchor(pathlib.Path(args.root))
        out_p = pathlib.Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "ok": True,
            "out": str(out_p),
            "chains": len(doc["chains"]),
            "run_json_sha256": doc["run_json_sha256"],
            "timestamp": doc["timestamp"],
        }, ensure_ascii=False, indent=1, sort_keys=True))
        return 0

    anchor = json.loads(pathlib.Path(args.anchor).read_text(encoding="utf-8"))
    res = check_anchor(pathlib.Path(args.root), anchor)
    print(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True))
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
