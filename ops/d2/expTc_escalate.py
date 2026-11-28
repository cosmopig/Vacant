#!/usr/bin/env python3
"""實驗 T 確認批次：升級臂 EB／ER／EN（附錄 C）。離線、單次 Haiku API 呼叫、不開工具、不能上網（host 端 urllib 直連 API）。2026-11-28。

每一份確認初稿（第一部分 root 裡的 c0，k 份；用修正後的標記 flags_v2.json）：
  EB：只把空白行交給 Haiku。
  ER：紀錄判為沒依據的行（修正後標記的 flagged，含空白）交給 Haiku。
  EN：全部空白行＋從「有填、但 ER 沒標」的行裡隨機抽出與「ER 標到的有填行」同樣多的行（不夠就全拿，記差額）；
      種子＝sha256("<組>|<次>|EN") 前 8 個十六進位字。ER 沒標任何有填行時 ER＝EN＝EB，該份不進 ER 對 EN 的比較。
給 Haiku 的頁面：這份初稿出口紀錄裡 200 的頁（gc 刪掉的已按 sha256 從 revision 0 凍結頁補回；`flags_v2.json` 的 fetched_urls），
  只給凍結的 revision 0 文字（`expT_feedback.load_frozen_fetched_pages`）。提示、解析、簽章事件沿用探索批次 TE 的實作與 KS-1 檢查。
寫回規則（附錄 C 事前寫死）：Haiku 對某行**沒給值**（空字串、not found、unknown／N/A、解析失敗、被截斷而缺）⇒ 保留初稿原值；
  給了值才替換。max_tokens 固定 4096。
API 錯誤（限流、額度、4xx、5xx、逾時）＝基礎設施：重試最多 2 次，仍失敗 ⇒ 該份該臂作廢（記次數）。
花費：每筆記帳到 api_credit_ledger.jsonl；頭 3 次呼叫後估單價，預估總額超過 --max-usd 就停在開跑前（整臂縮，不做到一半）。
輸出：<drafts root>/escalation/<組>/r<次>/<臂>/{prompt.txt,response.txt,meta.json,report.md,chain.ndjson,chain.pub.json}
用法：expTc_escalate.py --drafts D1 D2 --k K [--arms EB ER EN] [--max-usd 20] [--workers 2] [--dry-run]
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, hashlib, json, pathlib, random, sys, threading, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from ops.d2 import expT_feedback as FB  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network import crypto  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402

MODEL = "claude-haiku-5-5"; MAX_TOKENS = 4096; LOCK = threading.Lock()


def targets(flags: dict, claims, sid: str, rep: int):
    fb = flags["flags_by_claim"]
    blank = [c["id"] for c in claims if fb.get(c["id"], {}).get("is_blank")]
    er = [c["id"] for c in claims if fb.get(c["id"], {}).get("flagged")]
    er_filled = [cid for cid in er if cid not in blank]
    pool = [c["id"] for c in claims if c["id"] not in blank and c["id"] not in er]
    seed = int(hashlib.sha256(f"{sid}|{rep}|EN".encode()).hexdigest()[:8], 16)
    pick = random.Random(seed).sample(pool, min(len(er_filled), len(pool)))
    en = blank + sorted(pick, key=lambda x: [c["id"] for c in claims].index(x))
    return {"EB": blank, "ER": er, "EN": en}, {"er_filled": len(er_filled), "en_pool": len(pool), "en_shortfall": max(0, len(er_filled) - len(pool)),
                                              "en_seed": seed, "overlap_ER_EN": len(set(er) & set(en)), "er_has_filled": bool(er_filled)}


def one(c0: pathlib.Path, outdir: pathlib.Path, arm: str, ids: list[str], claims, flags: dict, max_usd: float, spent: list, dry: bool, info: dict):
    outdir.mkdir(parents=True, exist_ok=True)
    c0_text = (c0 / "report.md").read_text(encoding="utf-8", errors="replace")
    meta = {"arm": arm, "target_ids": ids, "selection": info, "model": MODEL, "max_tokens": MAX_TOKENS, "write_back": "keep_draft_value_when_no_value"}
    if not ids:
        meta.update({"called": False, "reason": "no_target_lines"}); (outdir / "report.md").write_text(c0_text)
        (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); return meta
    rec = FB.open_recorder(c0 / "snapshot" / "vh")
    pages = FB.load_frozen_fetched_pages(flags.get("fetched_urls") or [], c0 / "site_frozen", rec=rec)
    tclaims = [c for c in claims if c["id"] in ids]
    sys_p, user_p, withheld = FB.build_haiku_escalation_prompt(tclaims, flags["values"], pages, actor_tokens=set())
    meta.update({"pages_given": [p["url"] for p in pages], "page_shas": {p["url"]: p["sha256"] for p in pages}, "withheld": withheld})
    if dry:
        meta["called"] = False; meta["dry_run_prompt_chars"] = len(sys_p) + len(user_p)
        (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); return meta
    with LOCK:
        if spent[0] >= max_usd:
            meta.update({"called": False, "reason": "budget_cap"}); (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); return meta
    res, errs = None, []
    for attempt in range(3):
        try:
            res = FB.call_haiku_messages_api(system_prompt=sys_p, user_prompt=user_p, model=MODEL, max_tokens=MAX_TOKENS, timeout_s=180)
            break
        except Exception as e:  # noqa: BLE001
            errs.append(f"{type(e).__name__}: {str(e)[:160]}"); time.sleep(5 * (attempt + 1))
    if res is None:
        meta.update({"called": True, "infra_void": True, "errors": errs}); (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); return meta
    extracted = FB.parse_haiku_escalation_response(res["text"], ids)
    give = [cid for cid in ids if extracted.get(cid) not in (None, "")]
    final = FB.apply_haiku_replacements(c0_text, claims, give, extracted)
    (outdir / "prompt.txt").write_text(res["prompt_text"]); (outdir / "response.txt").write_text(res["text"] + "\n"); (outdir / "report.md").write_text(final)
    meta.update({"called": True, "stop_reason": res.get("stop_reason"), "truncated": res.get("stop_reason") == "max_tokens",
                 "extracted": extracted, "replaced_ids": give, "no_value_ids": [c for c in ids if c not in give],
                 "input_tokens": int(res["input_tokens"]), "output_tokens": int(res["output_tokens"]), "cost_usd": float(res["cost_usd"]),
                 "wall_s": float(res.get("wall_s") or 0), "prompt_sha256": res["prompt_sha256"], "response_sha256": res["response_sha256"], "retries": len(errs)})
    with LOCK:
        spent[0] += float(res["cost_usd"])
        FB.append_credit_ledger(None, purpose=f"expTc escalation {arm}", model=res["model"], input_tokens=int(res["input_tokens"]),
                                output_tokens=int(res["output_tokens"]), cost_usd=float(res["cost_usd"]), cell=f"{c0.parts[-3]}/{c0.parts[-2]}/{arm}")
    ident = Identity.generate(); book = Logbook()
    FB.escalation_event(book, ident, arm=arm, decision="escalate_haiku", model=res["model"], escalated_claim_ids=ids,
                        fetched_urls=meta["pages_given"], prompt_sha256=res["prompt_sha256"], response_sha256=res["response_sha256"],
                        input_tokens=int(res["input_tokens"]), output_tokens=int(res["output_tokens"]), cost_usd=float(res["cost_usd"]),
                        withheld=withheld, extra={"write_back": "keep_draft_value_when_no_value", "replaced": len(give)})
    book.save(outdir / "chain.ndjson")
    (outdir / "chain.pub.json").write_text(json.dumps({"vacant_id": ident.vacant_id, "pub_hex": crypto.pub_to_hex(ident.pub), "head": book.head()}))
    (outdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--arms", nargs="+", default=["EB", "ER", "EN"]); ap.add_argument("--max-usd", type=float, default=20.0)
    ap.add_argument("--workers", type=int, default=2); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    jobs = []
    for r in a.drafts:
        root = pathlib.Path(r); plan = json.loads((root / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
        for c0 in sorted(root.glob("cells/*/r*/c0")):
            sid, rep = c0.parts[-3], int(c0.parts[-2][1:])
            if rep > a.k or not (c0 / "flags_v2.json").is_file():
                continue
            flags = json.loads((c0 / "flags_v2.json").read_text()); claims = truth[sid]["claims"]
            tg, info = targets(flags, claims, sid, rep)
            for arm in a.arms:
                od = root / "escalation" / sid / f"r{rep}" / arm
                if (od / "meta.json").is_file():
                    continue
                jobs.append((c0, od, arm, tg[arm], claims, flags, info))
    spent = [0.0]
    print(f"jobs {len(jobs)}", flush=True)
    if not a.dry_run and jobs:
        # 頭 3 次估單價
        head = [j for j in jobs if j[3]][:3]
        for j in head:
            one(*j[:6], a.max_usd, spent, False, j[6])
        n_call = sum(1 for j in jobs if j[3]); unit = spent[0] / max(1, len(head))
        est = unit * n_call
        print(f"unit ${unit:.4f} x {n_call} calls ≈ ${est:.2f} (cap ${a.max_usd})", flush=True)
        if est > a.max_usd:
            print("ESTIMATE OVER CAP — stopping before the full run (shrink arms per Appendix C)", flush=True); return 2
        jobs = [j for j in jobs if j not in head]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, *j[:6], a.max_usd, spent, a.dry_run, j[6]) for j in jobs]
        for i, f in enumerate(cf.as_completed(futs), 1):
            f.result()
            if i % 25 == 0:
                print(f"{i}/{len(futs)} spent ${spent[0]:.2f}", flush=True)
    print(f"done spent ${spent[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
