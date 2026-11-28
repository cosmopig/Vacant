#!/usr/bin/env python3
"""實驗 T 確認批次：升級臂 EB／ER／EN 與參考臂 HP（附錄 C、附錄 C 補充 C1–C11）。第二版（2026-11-28）。
離線、單次 Haiku Messages API 呼叫；請求只帶 model／max_tokens（4096）／system／messages，不帶 tools、tool_choice、temperature、MCP（C9）。

E 臂（每一份初稿；第一部分 root 的 r1..rk；用修正後標記 flags_v2.json）：
  EB 只交空白行；ER 交修正後標記的 flagged（含空白）；EN 交全部空白行＋從「有填、ER 沒標」的行隨機抽出和 ER 有填行同樣多的行
  （不夠就全拿、記差額；種子＝sha256("<組>|<次>|EN") 前 8 字）。EN 與 ER 的**有填行重疊必須為 0**，否則不呼叫（C7）。
  給 Haiku 的頁面（C3）：B25 驗收後的「補回後紀錄頁面集合」＝這份 c0 出口紀錄裡 200 的頁（去重），內容是 revision 0 凍結文字；
  每份每臂記頁數與總字元數。寫回（C5）：Haiku 沒給值（空、not found、unknown／N/A、解析失敗、被截斷而缺）就保留初稿原值；
  給的值和原值相同時不算替換。
HP（C10）：每組固定 2 次、不依初稿；輸入＝該組 revision 0 凍結站全部頁面文字＋空白 template（全部行都是目標）；提示通過 assert_ks1_clean；
  超過上下文（輸入估計 >190k token）的組不做、列名、不截頁。
門檻（C1）：--gate 先檢查 30 組 × r1..rk 都有 done.json、沒有 infra_void；越界／網路掃描為 0 且掃到的 c0 執行數＝30×k；
  B25（頁面集合＝伺服器 200 集合、無法補回 0、sha 對凍結站）與 B33(1)（一致性 0）全量通過；flags_v2.json 存在。不過 ⇒ 結束碼 1。
花費（C2）：--dry-run 算每筆提示字元數，上界＝輸入 token ≤ 字元數÷2.5、輸出 ≤ 4096，單價 $1／$5 每百萬；上界合計 ≤ --max-usd 才可正式跑
  （超過就先縮 HP，E 臂不縮）。正式跑以初稿為單位、三臂交錯；實際花費到上限立即停，被擋下的格寫 report.md＝初稿原文、meta 標 budget_cap。
API 錯誤＝基礎設施：重試最多 2 次，仍失敗 ⇒ 該份該臂作廢。每筆記帳；每份每臂一條新簽章鏈，事件含請求 body 的 sha256（C9）。
用法：
  expTc_escalate.py --drafts D1 D2 --k K --gate                     # 只做 C1 檢查
  expTc_escalate.py --drafts D1 D2 --k K --dry-run [--hp N]         # 算上界、寫提示 sha 清單
  expTc_escalate.py --drafts D1 D2 --k K --run [--hp N] [--max-usd 20] [--exclude-sets s1,s2]
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, hashlib, json, pathlib, random, sys, threading, time
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_feedback as FB  # noqa: E402
from ops.d2 import expT_metrics as M  # noqa: E402
from vacant_network import crypto  # noqa: E402
from vacant_network.identity import Identity  # noqa: E402
from vacant_network.logbook import Logbook  # noqa: E402
from vacant_network.memory import assert_ks1_clean  # noqa: E402

MODEL = "claude-haiku-5-5"; MAX_TOKENS = 4096; PRICE_IN, PRICE_OUT = 1.0, 5.0
LOCK = threading.Lock(); ARMS = ("EB", "ER", "EN")


def body_sha(system_prompt: str, user_prompt: str) -> str:
    """和 expT_feedback.call_haiku_messages_api 逐位元相同的請求 body 的 sha256（C9）。"""
    body = {"model": MODEL, "max_tokens": MAX_TOKENS, "system": system_prompt, "messages": [{"role": "user", "content": user_prompt}]}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False).encode("utf-8")).hexdigest()


def recorded_pages(c0: pathlib.Path) -> list[str]:
    """B25 的「補回後紀錄頁面集合」：出口紀錄裡 200、非 TLS 的網址（去重、依首次出現順序）。"""
    rec = FB.open_recorder(c0 / "snapshot" / "vh"); seen = []
    for e in rec.events():
        if e.get("type") == "source_fetch" and e.get("status") == 200 and not e.get("tls") and e.get("url") not in seen:
            seen.append(e["url"])
    return seen


def targets(flags: dict, claims, sid: str, rep: int):
    fb = flags["flags_by_claim"]; order = [c["id"] for c in claims]
    blank = [c for c in order if fb.get(c, {}).get("is_blank")]
    er = [c for c in order if fb.get(c, {}).get("flagged")]
    er_filled = [c for c in er if c not in blank]
    pool = [c for c in order if c not in blank and c not in er]
    seed = int(hashlib.sha256(f"{sid}|{rep}|EN".encode()).hexdigest()[:8], 16)
    pick = random.Random(seed).sample(pool, min(len(er_filled), len(pool)))
    en = blank + sorted(pick, key=order.index)
    en_filled = [c for c in en if c not in blank]
    info = {"n_blank": len(blank), "er_filled": len(er_filled), "en_filled": len(en_filled), "en_pool": len(pool),
            "en_shortfall": max(0, len(er_filled) - len(pool)), "en_seed": seed,
            "overlap_all_lines": len(set(er) & set(en)), "overlap_filled": len(set(er_filled) & set(en_filled)),
            "er_has_filled": bool(er_filled)}
    return {"EB": blank, "ER": er, "EN": en}, info


def prompt_for(c0: pathlib.Path, ids, claims, flags, pages_urls):
    rec = FB.open_recorder(c0 / "snapshot" / "vh")
    pages = FB.load_frozen_fetched_pages(pages_urls, c0 / "site_frozen", rec=rec)
    tclaims = [c for c in claims if c["id"] in ids]
    sp, up, withheld = FB.build_haiku_escalation_prompt(tclaims, flags["values"], pages, actor_tokens=set())
    return sp, up, withheld, pages


def call(sp, up):
    errs = []
    for attempt in range(3):
        try:
            return FB.call_haiku_messages_api(system_prompt=sp, user_prompt=up, model=MODEL, max_tokens=MAX_TOKENS, timeout_s=180), errs
        except Exception as e:  # noqa: BLE001
            errs.append(f"{type(e).__name__}: {str(e)[:160]}"); time.sleep(5 * (attempt + 1))
    return None, errs


def write_result(outdir, base_text, claims, ids, res, sp, up, meta, arm, cell_label):
    extracted = FB.parse_haiku_escalation_response(res["text"], ids)
    values_before = FB.parse_report_values(base_text, claims)
    give = [cid for cid in ids if extracted.get(cid) not in (None, "")]
    final = FB.apply_haiku_replacements(base_text, claims, give, extracted)
    same = [cid for cid in give if FB.parse_report_values(final, claims).get(cid) == values_before.get(cid)]
    (outdir / "prompt.txt").write_text(res["prompt_text"]); (outdir / "response.txt").write_text(res["text"] + "\n"); (outdir / "report.md").write_text(final)
    meta.update({"called": True, "stop_reason": res.get("stop_reason"), "truncated": res.get("stop_reason") == "max_tokens",
                 "extracted": extracted, "replaced_ids": [c for c in give if c not in same], "same_as_original_ids": same,
                 "no_value_ids": [c for c in ids if c not in give], "input_tokens": int(res["input_tokens"]), "output_tokens": int(res["output_tokens"]),
                 "cost_usd": float(res["cost_usd"]), "wall_s": float(res.get("wall_s") or 0), "prompt_sha256": res["prompt_sha256"],
                 "response_sha256": res["response_sha256"], "request_body_sha256": body_sha(sp, up)})
    FB.append_credit_ledger(None, purpose=f"expTc escalation {arm}", model=res["model"], input_tokens=int(res["input_tokens"]),
                            output_tokens=int(res["output_tokens"]), cost_usd=float(res["cost_usd"]), cell=cell_label)
    ident = Identity.generate(); book = Logbook()
    FB.escalation_event(book, ident, arm=arm, decision="escalate_haiku", model=res["model"], escalated_claim_ids=ids,
                        fetched_urls=meta.get("pages_given", []), prompt_sha256=res["prompt_sha256"], response_sha256=res["response_sha256"],
                        input_tokens=int(res["input_tokens"]), output_tokens=int(res["output_tokens"]), cost_usd=float(res["cost_usd"]),
                        withheld=int(meta.get("withheld") or 0),
                        extra={"request_body_sha256": meta["request_body_sha256"], "write_back": "keep_draft_value_when_no_value",
                               "replaced": len(meta["replaced_ids"])})
    book.save(outdir / "chain.ndjson")
    (outdir / "chain.pub.json").write_text(json.dumps({"vacant_id": ident.vacant_id, "pub_hex": crypto.pub_to_hex(ident.pub), "head": book.head()}))


def gate(droots, k):
    from ops.d2 import expTc_confirm_analysis as A
    from ops.d2 import expT_b25 as B25
    plan = json.loads((REPO / "ops/d2/plans/expTc_drafts_qwen9b.json").read_text())
    sets = [f"{m['prefix']}-{x}" for m in plan["materials"] for x in m["sets"]]
    rep = {"k": k, "expected": 30 * k if len(sets) == 30 else len(sets) * k, "missing": [], "infra_void": [], "no_flags_v2": [],
           "escape": [], "infra_scan": [], "scanned": 0, "b25_fail": [], "b33_inconsistent": []}
    where = {}
    for sid in sets:
        for rp in range(1, k + 1):
            c0 = next((d / "cells" / sid / f"r{rp}" / "c0" for d in droots if (d / "cells" / sid / f"r{rp}" / "c0" / "done.json").is_file()), None)
            if c0 is None:
                rep["missing"].append(f"{sid}/r{rp}"); continue
            where[(sid, rp)] = c0
            if json.loads((c0 / "done.json").read_text()).get("infra_void"):
                rep["infra_void"].append(f"{sid}/r{rp}")
            if not (c0 / "run" / "run.json").is_file():          # B48(2)
                rep["missing"].append(f"{sid}/r{rp}:no_run.json")
            if not (c0 / "flags_v2.json").is_file():
                rep["no_flags_v2"].append(f"{sid}/r{rp}")
            b = B25.check_cell(c0, False)
            if not (b["recorded_eq_server"] and b["unrestorable_pages"] == 0 and not b["sha_not_exactly_one_frozen"]):
                rep["b25_fail"].append(f"{sid}/r{rp}")
    d2 = str(droots[0].parent)
    for d in droots:
        for kk, v in A.scan_runs(d, d2).items():
            if kk[2] == "c0" and kk[1] <= k and not v.get("in_progress"):   # B48(2)：只計有 run.json 的執行
                rep["scanned"] += 1
                if v["escape"]:
                    rep["escape"].append(list(kk))
                if v["infra"]:
                    rep["infra_scan"].append(list(kk))
    import subprocess
    tmp = droots[0] / "escalation_gate_flagcheck.json"
    subprocess.run([sys.executable, str(REPO / "ops/d2/expT_flagcheck.py"), *map(str, droots), "--json", str(tmp)], check=True, capture_output=True)
    fc = json.loads(tmp.read_text())
    rep["b33_inconsistent"] = [x for x in fc["b33_inconsistent"] if int(x.split("/r")[1].split("/")[0]) <= k]
    rep["pass"] = not (rep["missing"] or rep["infra_void"] or rep["no_flags_v2"] or rep["escape"] or rep["infra_scan"] or rep["b25_fail"]
                       or rep["b33_inconsistent"] or rep["scanned"] != rep["expected"])
    return rep, where, sets


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--gate", action="store_true"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--run", action="store_true")
    ap.add_argument("--hp", type=int, default=2); ap.add_argument("--max-usd", type=float, default=20.0); ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--exclude-sets", default="")
    a = ap.parse_args(); droots = [pathlib.Path(x) for x in a.drafts]; excl = {x for x in a.exclude_sets.split(",") if x}
    g, where, sets = gate(droots, a.k)
    (droots[0] / "escalation_gate.json").write_text(json.dumps(g, ensure_ascii=False, indent=1))
    print("gate", json.dumps({k_: (v if not isinstance(v, list) else len(v)) for k_, v in g.items()}, ensure_ascii=False), flush=True)
    if a.gate:
        return 0 if g["pass"] else 1
    if not g["pass"]:
        print("GATE FAILED — no calls (C1)"); return 1
    plan = json.loads((droots[0] / "RUN.json").read_text())["plan_body"]; truth = M.load_manifests_with_truth(plan)
    # 建工作清單（以初稿為單位；三臂交錯）
    drafts, prompts = [], []
    for sid in sets:
        if sid in excl:
            continue
        for rp in range(1, a.k + 1):
            c0 = where[(sid, rp)]; flags = json.loads((c0 / "flags_v2.json").read_text()); claims = truth[sid]["claims"]
            tg, info = targets(flags, claims, sid, rp)
            if info["overlap_filled"] != 0:
                print(f"EN/ER filled overlap != 0 at {sid}/r{rp} — implementation error, no calls (C7)"); return 1
            pages_urls = recorded_pages(c0)
            item = {"c0": c0, "sid": sid, "rep": rp, "claims": claims, "flags": flags, "tg": tg, "info": info, "pages": pages_urls, "arms": {}}
            for arm in ARMS:
                if tg[arm]:
                    sp, up, wh, pages = prompt_for(c0, tg[arm], claims, flags, pages_urls)
                    item["arms"][arm] = {"sp": sp, "up": up, "withheld": wh, "n_pages": len(pages), "chars": sum(len(p.get("text", "")) for p in pages),
                                         "page_shas": {p["url"]: p.get("sha256") for p in pages}}
                    prompts.append(len(sp) + len(up))
            drafts.append(item)
    hp_jobs = []
    if a.hp > 0:
        for sid in sets:
            if sid in excl:
                continue
            c0 = where[(sid, 1)]; claims = truth[sid]["claims"]
            site = c0 / "site_frozen"; pinned = json.loads((c0 / "site_snapshot_sha256.json").read_text())
            host = f"http://{sid}-r1.d2-sources.example/"
            urls = [host + name for name in sorted(pinned)]
            pages = FB.load_frozen_fetched_pages(urls, site, rec=None)
            sp, up, wh = FB.build_haiku_escalation_prompt(claims, {c["id"]: None for c in claims}, pages, actor_tokens=set())
            assert_ks1_clean(sp); assert_ks1_clean(up)
            est_in = (len(sp) + len(up)) / 2.5
            for i in range(1, a.hp + 1):
                hp_jobs.append({"sid": sid, "i": i, "claims": claims, "sp": sp, "up": up, "pages": urls, "skip": est_in > 190000,
                                "template": (pathlib.Path(__import__('os').path.expandvars(next(m["dir"] for m in plan["materials"] if sid.startswith(m["prefix"])))) / "sets" / sid.split("-", 1)[1] / "template.md")})
    ub = lambda chars: chars / 2.5 * PRICE_IN / 1e6 + MAX_TOKENS * PRICE_OUT / 1e6
    e_ub = sum(ub(c) for c in prompts); hp_ub = sum(ub(len(j["sp"]) + len(j["up"])) for j in hp_jobs if not j["skip"])
    dry = {"drafts": len(drafts), "e_calls": len(prompts), "e_upper_usd": round(e_ub, 2), "hp_calls": sum(1 for j in hp_jobs if not j["skip"]),
           "hp_upper_usd": round(hp_ub, 2), "hp_skipped_sets": sorted({j["sid"] for j in hp_jobs if j["skip"]}),
           "hp_prompt_sha256": {f"{j['sid']}#{j['i']}": hashlib.sha256((j["sp"] + "\n" + j["up"]).encode()).hexdigest() for j in hp_jobs},
           "e_prompt_sha256": {f"{d['sid']}/r{d['rep']}/{arm}": hashlib.sha256((v["sp"] + "\n" + v["up"]).encode()).hexdigest() for d in drafts for arm, v in d["arms"].items()},
           "ER_EN_overlap_all_lines_mean": round(sum(d["info"]["overlap_all_lines"] for d in drafts) / max(1, len(drafts)), 3),
           "en_shortfall_drafts": sum(1 for d in drafts if d["info"]["en_shortfall"]), "er_without_filled": sum(1 for d in drafts if not d["info"]["er_has_filled"])}
    (droots[0] / "escalation_dryrun.json").write_text(json.dumps(dry, ensure_ascii=False, indent=1))
    print("dry", json.dumps({k_: v for k_, v in dry.items() if not k_.endswith("sha256")}, ensure_ascii=False), flush=True)
    if a.dry_run or not a.run:
        return 0
    if e_ub > a.max_usd:
        print("E-arm upper bound alone exceeds cap — not starting (C2)"); return 2
    if e_ub + hp_ub > a.max_usd:
        print("E + HP upper bound exceeds cap — rerun with smaller --hp (C2)"); return 2
    spent = [0.0]

    def do_draft(d):
        base = (d["c0"] / "report.md").read_text(encoding="utf-8", errors="replace")
        for arm in ARMS:
            od = d["c0"].parents[2].parent / "escalation" / d["sid"] / f"r{d['rep']}" / arm
            od.mkdir(parents=True, exist_ok=True)
            if (od / "meta.json").is_file():
                continue
            meta = {"arm": arm, "target_ids": d["tg"][arm], "selection": d["info"], "model": MODEL, "max_tokens": MAX_TOKENS,
                    "write_back": "keep_draft_value_when_no_value", "pages_given": d["pages"]}
            if not d["tg"][arm]:
                meta.update({"called": False, "reason": "no_target_lines"}); (od / "report.md").write_text(base)
                (od / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); continue
            v = d["arms"][arm]; meta.update({"n_pages": v["n_pages"], "page_chars": v["chars"], "withheld": v["withheld"], "page_shas": v["page_shas"]})
            with LOCK:
                capped = spent[0] >= a.max_usd
            if capped:
                meta.update({"called": False, "budget_cap": True}); (od / "report.md").write_text(base)
                (od / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); continue
            res, errs = call(v["sp"], v["up"])
            if res is None:
                meta.update({"called": True, "infra_void": True, "errors": errs}); (od / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1)); continue
            meta["retries"] = len(errs)
            with LOCK:
                spent[0] += float(res["cost_usd"])
            write_result(od, base, d["claims"], d["tg"][arm], res, v["sp"], v["up"], meta, arm, f"{d['sid']}/r{d['rep']}/{arm}")
            (od / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))

    with cf.ThreadPoolExecutor(a.workers) as ex:
        for i, f in enumerate(cf.as_completed([ex.submit(do_draft, d) for d in drafts]), 1):
            f.result()
            if i % 20 == 0:
                print(f"drafts {i}/{len(drafts)} spent ${spent[0]:.2f}", flush=True)
    for j in hp_jobs:
        od = droots[0] / "escalation_hp" / j["sid"] / f"hp{j['i']}"; od.mkdir(parents=True, exist_ok=True)
        if (od / "meta.json").is_file():
            continue
        tpl = j["template"].read_text(encoding="utf-8", errors="replace")
        meta = {"arm": "HP", "model": MODEL, "max_tokens": MAX_TOKENS, "pages_given": j["pages"]}
        if j["skip"]:
            meta.update({"called": False, "reason": "over_context"}); (od / "meta.json").write_text(json.dumps(meta, indent=1)); continue
        with LOCK:
            capped = spent[0] >= a.max_usd
        if capped:
            meta.update({"called": False, "budget_cap": True}); (od / "meta.json").write_text(json.dumps(meta, indent=1)); continue
        res, errs = call(j["sp"], j["up"])
        if res is None:
            meta.update({"called": True, "infra_void": True, "errors": errs}); (od / "meta.json").write_text(json.dumps(meta, indent=1)); continue
        spent[0] += float(res["cost_usd"])
        write_result(od, tpl, j["claims"], [c["id"] for c in j["claims"]], res, j["sp"], j["up"], meta, "HP", f"{j['sid']}/hp{j['i']}")
        (od / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"done spent ${spent[0]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
