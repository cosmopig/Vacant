#!/usr/bin/env python3
"""實驗 T 確認批次的固定分析，第二版（預註冊 `decisions/prereg/PREREG_20261128_EXPT_CONFIRM.md` 主文＋附錄 A＋附錄 B）。
在任何確認批次的初稿或回饋格被評分之前提交；sha256 記在預註冊附錄 B 之後。

輸入：兩台的初稿 root（第一部分）與兩台的回饋 root（第二部分）。計畫 sha 必須各自相同。
  1. 基礎設施分類（B4）與越界（B2：讀工作區外的檔＋網路繞過＋存取紀錄對 egress 紀錄對帳），逐次 agent 執行判定，只用紀錄、不看分數。
  2. 起點檢查（B4 iv）：A 的報告與起點 c0 的 sha256 對 `reused_c0_sha256.json`。
  3. 回饋四臂：`expT_metrics.score_cell` 逐格評分；**組加權**（先組內平均、再組間平均）；以組為群集的 bootstrap（2,000 次、種子 20261127；
     95% 與 90% 用同一份重抽）；組層級符號翻轉置換 p（10,000 次、種子 20261130、雙尾）。
     主要：T−TB（門檻／等價界限 5pp）、T−G（10pp；另要求 B7 傷害條件）。描述：TB−G、G−A、T−A、TB−A。
  4. 選擇器（B8）：兩台初稿合併成單一逐組表；k 對所有組相同（缺份 ⇒ 全部降到 rep1–4；仍缺的組排除；排除 >5 組 ⇒ 未定）。
     record（同探索的紀錄分數）、nonblank、random（k 份平均）、oracle。主要：record−random（5pp）、record−nonblank（3pp）。
  5. Holm 只作用於四個主要比較的置換 p；區間不調整；等價（TOST：90% 區間完全在 (−Δ,+Δ) 內）不進 Holm（B1、B12）。
  6. 非空白初稿分層，三段判讀（B5）；拿掉前 2 組（判讀）與前 2 對（並報）（B6）；B7 傷害條件與整份清空的對；B9 對齊與條件化比較。
  7. 未來版本相符的行數只描述（B3）。
用法：
  expTc_confirm_analysis.py --drafts D1 D2 --fb F1 F2 --out OUT.json [--md OUT.md]
  （只有初稿時：--fb 可省略，只算選擇器與初稿的基礎設施／越界。）
"""
from __future__ import annotations
import argparse, collections, json, pathlib, random, re, statistics, sys
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "ops" / "d2"))
from ops.d2 import expT_metrics as M  # noqa: E402
import scan_leak as S  # noqa: E402

SD = M.SD
DELTA = {"T_vs_TB": 0.05, "T_vs_G": 0.10, "record_vs_random": 0.05, "record_vs_nonblank": 0.03}
FB_PRIMARY = [("T", "TB"), ("T", "G")]
FB_DESCRIPTIVE = [("TB", "G"), ("G", "A"), ("T", "A"), ("TB", "A")]
NET_FLAG = re.compile(r"--noproxy|(?:^|[\s\"'])-x\s|--proxy\b|--no-proxy\b|\bunset\s+[\w ]*proxy|\benv\s+-u\s+\w*proxy|\benv\s+-i\b|no_proxy\s*=|"
                      r"\bhttps?_proxy\s*=\s*(?:[\"']{2}|\s)|proxies\s*=\s*\{\s*\}|trust_env\s*=\s*False|\bnode\b[^|;&]*(?:fetch|https?://|\.m?js\b)", re.I)
# LM Studio 的模型端點（agent 透過 pi 連，不經工具呼叫；工具呼叫裡出現時也不算繞過）
LMS_HOSTS = {"w1003", "w1004"}
# 相對路徑、家目錄、萬用字元、程式拼接的路徑（vacant-cloud 補核：絕對路徑比對抓不到這些）。沙箱裡多半只看到空目錄，
# 所以只有「工具回傳裡出現教材或別格的內容特徵」時才算越界；命中次數一律照報。
PATH_SUSPECT = re.compile(r"\.\./|(?:^|[\s\"'=(])~/|\$\{?HOME\}?|(?:^|[\s\"'])/\*|\*\*/|os\.path\.join|glob\.glob|\bglob\(|pathlib\.Path\(|\bfind\s+[/~.]|\bls\s+(?:-\w+\s+)*[/~]", re.I)
MATERIAL = re.compile(r"site_frozen|flags\.json|manifest\.json|SOURCES\.md|cycle_\d|realrev\w*|d2_private|/cells/|reused_c0|routes\.json|access\.jsonl|\.live_secret")
URL = re.compile(r"https?://([A-Za-z0-9.\-]+)(?::(\d+))?(/[^\s\"'\\]*)?")


# ---------------------------------------------------------------- statistics
def boot(vals: list[float], n: int = 2000, seed: int = 20261127) -> dict:
    if not vals:
        return {"ci95": None, "ci90": None}
    rng = random.Random(seed); k = len(vals); ms = []
    for _ in range(n):
        ms.append(sum(vals[rng.randrange(k)] for _ in range(k)) / k)
    ms.sort()
    q = lambda p: round(ms[min(n - 1, max(0, int(p * n) - (1 if p > 0.5 else 0)))], 4)
    return {"ci95": [q(0.025), q(0.975)], "ci90": [q(0.05), q(0.95)]}


def perm_p(vals: list[float], n: int = 10000, seed: int = 20261130) -> float | None:
    if not vals:
        return None
    rng = random.Random(seed); obs = abs(sum(vals) / len(vals)); hit = 0
    for _ in range(n):
        s = sum(v if rng.random() < 0.5 else -v for v in vals) / len(vals)
        if abs(s) >= obs - 1e-12:
            hit += 1
    return round((hit + 1) / (n + 1), 5)


def holm(ps: dict) -> dict:
    items = sorted((p, k) for k, p in ps.items() if p is not None)
    m = len(items); out = {k: None for k in ps}; run = 0.0
    for i, (p, k) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p)); out[k] = round(run, 5)
    return out


def summarize(by_set: dict, delta: float | None) -> dict:
    """by_set: {set: [unit diffs]} → 組加權點估計、區間、p、等價。"""
    sets = sorted(by_set); vals = [sum(by_set[s]) / len(by_set[s]) for s in sets]
    if not vals:
        return {"sets": 0, "units": 0, "diff": None, "ci95": None, "ci90": None, "perm_p": None, "unit_weighted_diff": None, "equivalent_within_delta": None}
    b = boot(vals); d = round(sum(vals) / len(vals), 4)
    units = [v for s in sets for v in by_set[s]]
    out = {"sets": len(vals), "units": len(units), "diff": d, **b, "perm_p": perm_p(vals),
           "unit_weighted_diff": round(sum(units) / len(units), 4)}
    if delta is not None and b["ci90"]:
        out["equivalent_within_delta"] = (b["ci90"][0] > -delta and b["ci90"][1] < delta)
    return out


def drop_top(by_set: dict, delta: float | None, unit: str) -> dict:
    """拿掉貢獻最大的 2 個單位（unit='set'：組；'pair'：對），和效果同方向。"""
    sets = sorted(by_set)
    direction = 1 if sum(sum(v) / len(v) for v in by_set.values()) >= 0 else -1
    if unit == "set":
        top = sorted(sets, key=lambda s: direction * sum(by_set[s]) / len(by_set[s]), reverse=True)[:2]
        rest = {s: v for s, v in by_set.items() if s not in top}
        dropped = top
    else:
        pairs = [(s, i, v) for s in sets for i, v in enumerate(by_set[s])]
        top = sorted(pairs, key=lambda x: direction * x[2], reverse=True)[:2]
        rest = {s: [v for i, v in enumerate(by_set[s]) if (s, i) not in {(t[0], t[1]) for t in top}] for s in sets}
        rest = {s: v for s, v in rest.items() if v}
        dropped = [f"{t[0]}#{t[1]}" for t in top]
    r = summarize(rest, delta)
    return {"unit": unit, "dropped": dropped, "diff": r.get("diff"), "ci95": r.get("ci95")}


# ---------------------------------------------------------------- run scanning (B2, B4)
def scan_runs(root: pathlib.Path, d2: str) -> dict:
    """逐次 agent 執行：越界（檔案、網路繞過）、基礎設施分類、模型行為（上下文用完、逾時、沒抓頁面）。只用紀錄，不看分數。

    判定（附錄 B 的 B2／B4，加上 11/28 看結果前的執行補充）：
      越界（整對排除；初稿則作廢重跑）＝
        (a) 參數含教材根目錄或 run root 的絕對路徑；
        (b) 參數命中相對路徑／家目錄／萬用字元／程式拼接路徑的樣式，且工具回傳（去掉 agent 自己的 live 與輸出目錄後）出現教材或別格的特徵；
        (c) 繞過代理的參數（--noproxy、-x／--proxy、unset／env -u *proxy、改 no_proxy）；
        (d) curl／wget 指令直接指向 localhost／127.0.0.1，或別組的來源主機；
        (e) 存取紀錄裡這次執行窗內、這一格主機的 200 網址，不在這一臂（含 c0）的 egress 紀錄（flags.json 的 fetched_urls）裡。
        只出現在 grep 樣式或文字裡的外部網址不算（經過代理的外部請求會被來源伺服器回 404，也會留在存取紀錄）。
      基礎設施（初稿重跑；回饋輪整對排除）＝
        這一格主機的請求拿到 5xx；或拿到 404、但那一頁確實在這一格的凍結站裡（路由壞了，例如撞埠）；
        或 agent 發了請求到自己的主機、存取紀錄在執行窗內卻沒有任何一筆（伺服器沒在聽）；
        或模型端點錯誤（stopReason=error／errorMessage）且不是上下文用完。
        對不存在的頁面拿到 404、或整次執行沒有抓任何頁面，算模型行為，照報次數。
    """
    acc = [json.loads(l) for l in (root / "access.jsonl").read_text().splitlines() if l.strip()] if (root / "access.jsonl").is_file() else []
    pm = re.compile(re.escape(d2) + r"/|" + re.escape(str(root)) + r"/")
    fetch_cmd = re.compile(r"\b(?:curl|wget|requests\.\w+\(|urlopen\(|urllib\.request|fetch\(|http\.get\()[^|;&]*?https?://([A-Za-z0-9.\-]+)", re.I)
    runs = {}
    for log in sorted((root / "cells").glob("*/r*/*/**/run/agent.log")):
        rel = log.relative_to(root / "cells").parts
        sid, rep, arm = rel[0], int(rel[1][1:]), rel[2]
        rnd = rel[3] if rel[3].startswith("round_") else "c0"
        host = f"{sid}-r{rep}.d2-sources.example"
        site = root / "cells" / sid / f"r{rep}" / "c0" / "site_frozen"
        rj = json.loads((log.parent / "run.json").read_text()) if (log.parent / "run.json").is_file() else {}
        t0, t1 = rj.get("t_start"), rj.get("t_end")
        txt = log.read_text(errors="replace")
        own = re.compile(re.escape(str(log.parent)) + r"[^\s\"']*|d2_private_live/[0-9a-f]+[^\s\"']*")
        file_esc = net_esc = own_req = 0; kinds = collections.Counter(); fetched_hosts: set = set()
        for tn, args, res in S.calls(log):
            if pm.search(own.sub("", args)):            # agent 自己的輸出目錄（掛在沙箱裡）不算
                file_esc += 1; kinds["file_outside_abs"] += 1
            elif PATH_SUSPECT.search(args):
                kinds["path_pattern"] += 1
                if MATERIAL.search(own.sub("", res)):
                    file_esc += 1; kinds["path_pattern_with_material_output"] += 1
            if NET_FLAG.search(args):
                net_esc += 1; kinds["proxy_bypass_flag"] += 1
            for m in fetch_cmd.finditer(args):
                h = m.group(1)
                fetched_hosts.add(h)
                if h in LMS_HOSTS or h.split(".")[0] in LMS_HOSTS:
                    continue
                if h == host:
                    own_req += 1
                elif h in ("127.0.0.1", "localhost"):
                    net_esc += 1; kinds["fetch_localhost_direct"] += 1
                elif h.endswith(".d2-sources.example"):
                    net_esc += 1; kinds["fetch_other_set_host"] += 1
                else:
                    kinds["fetch_external_via_proxy"] += 1
            if tn in ("fetch", "web_fetch", "webfetch") and host in args:
                own_req += 1
        # 附錄 B 補充（正向規則）：指令裡抓的每一個網址，在執行窗內都要對到一筆出口紀錄（egress.jsonl 的 GET 或 CONNECT），
        # 或一筆被白名單擋下的紀錄（net_blocked.jsonl）；對不到 ⇒ 繞過。
        cell_dir = root / "cells" / sid / f"r{rep}"
        vhs = [cell_dir / "c0" / "snapshot" / "vh"] if arm == "c0" else [cell_dir / arm / "final" / "vh"]
        eg_win = []
        for vh in vhs:
            for ej in vh.glob("trace/projects/*/egress.jsonl"):
                for line in ej.read_text(errors="replace").splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if t0 and t1 and t0 * 1000 - 1000 <= e.get("ts_ms", 0) <= t1 * 1000 + 1000:
                        eg_win.append(e)
        eg_urls = {e.get("url") for e in eg_win if e.get("method") in ("GET", "HEAD", "POST")}
        eg_hosts = {str(e.get("url", "")).split("://", 1)[-1].split("/", 1)[0].split(":")[0] for e in eg_win}
        blk = log.parent / "net_blocked.jsonl"
        blk_hosts = set()
        if blk.is_file():
            for line in blk.read_text(errors="replace").splitlines():
                try:
                    b = json.loads(line)
                except ValueError:
                    continue
                if t0 and t1 and t0 - 1 <= b.get("ts", 0) <= t1 + 1:
                    blk_hosts.add(str(b.get("host") or "").split(":")[0])
        call_urls = set()
        for tn, args, res in S.calls(log):
            for m in re.finditer(r"\b(?:curl|wget|requests\.\w+\(|urlopen\(|urllib\.request|fetch\(|http\.get\()[^|;&]*?(https?://[A-Za-z0-9.\-]+(?::\d+)?[^\s\"'\\|;&)]*)", args, re.I):
                call_urls.add(m.group(1))
        unmatched_calls = sorted(u for u in call_urls
                                 if u not in eg_urls and u.split("://", 1)[1].split("/", 1)[0].split(":")[0] not in (eg_hosts | blk_hosts)
                                 and "$" not in u and "{" not in u)
        own_page_urls = {u.rstrip("/") for u in call_urls if u.split("://", 1)[1].startswith(host)}
        win_any = [a for a in acc if t0 and t1 and t0 - 1 <= a.get("ts", 0) <= t1 + 1]
        # 附錄 B 補充 B13-3：指令裡抓網址的每一個主機，執行窗內至少要在來源伺服器的存取紀錄裡出現一次
        # （經過代理的外部請求會被記成 404）；完全沒有紀錄 ⇒ 直連、繞過。
        seen_hosts = {a.get("host") for a in win_any}
        unmatched = sorted(h for h in fetched_hosts if h not in seen_hosts and h not in LMS_HOSTS and h.split(".")[0] not in LMS_HOSTS
                           and h not in ("127.0.0.1", "localhost"))
        if unmatched:
            net_esc += len(unmatched); kinds["fetch_without_server_record"] += len(unmatched)
        if unmatched_calls:
            net_esc += len(unmatched_calls); kinds["fetch_call_without_egress_record"] += len(unmatched_calls)
        win = [a for a in win_any if a.get("host") == host]
        n200 = sum(1 for a in win if a.get("status") == 200)
        n5xx = sum(1 for a in win if int(a.get("status") or 0) >= 500)
        n404_exist = sum(1 for a in win if a.get("status") == 404 and (site / str(a.get("path", "")).lstrip("/")).is_file())
        n404_missing = sum(1 for a in win if a.get("status") == 404) - n404_exist
        model_err = ('"stopReason":"error"' in txt) or ('"errorMessage"' in txt)
        ctx = '"stopReason":"length"' in txt
        runs[(sid, rep, arm, rnd)] = {
            "file_escape_calls": file_esc, "net_escape_calls": net_esc, "escape_kinds": dict(kinds),
            "own_host_requests_in_args": own_req, "server_200": n200, "server_5xx": n5xx,
            "server_404_existing_page": n404_exist, "server_404_missing_page": n404_missing,
            "model_error": model_err, "context_exhausted": ctx,
            "timeout": (rj.get("rc") == "timeout") or (float(rj.get("wall_s") or 0) >= 599.0),
            "no_fetch": len(win) == 0 and own_req == 0,
            "net_blocked": sum(1 for _ in blk.read_text().splitlines()) if blk.is_file() else 0,
            # 量具缺口（標記可疑的主訊號；只用紀錄、不碰答案鍵）：指令裡字面出現的本格頁面網址數 − 出口紀錄到的 200 頁面數
            "requested_own_pages": len(own_page_urls),
            "egress_own_pages_200": len({e.get("url") for e in eg_win if e.get("method") == "GET" and e.get("status") == 200 and host in str(e.get("url"))}),
            "infra": bool(n5xx or n404_exist or (own_req > 0 and len(win) == 0) or (model_err and not ctx)),
            "_access_urls": sorted({f"http://{a['host']}{a['path']}" for a in win if a.get("status") == 200})}
    for key, r in runs.items():
        sid, rep, arm, rnd = key
        cell = root / "cells" / sid / f"r{rep}"
        # egress 紀錄＝Vacant 出口代理的 egress.jsonl（c0 看快照；各臂看 final，內含 c0 起點與各輪）。
        # flags.json 的 fetched_urls 不是完整清單（只列和行有關的頁），不能拿來對帳。
        eg = set()
        srcs = [cell / "c0" / "snapshot" / "vh"] if arm == "c0" else [cell / arm / "final" / "vh", cell / "c0" / "snapshot" / "vh"]
        for vh in srcs:
            for ej in vh.glob("trace/projects/*/egress.jsonl"):
                for line in ej.read_text(errors="replace").splitlines():
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("method") == "GET" and e.get("status") == 200 and e.get("url"):
                        eg.add(e["url"])
        miss = [u for u in r.pop("_access_urls") if u not in eg]
        r["unlogged_server_200"] = len(miss)
        r["escape"] = bool(r["file_escape_calls"] or r["net_escape_calls"] or miss)
    return runs


# ---------------------------------------------------------------- feedback scoring
def score_fb(roots):
    plan, sha = None, None
    for r in roots:
        run = json.loads((r / "RUN.json").read_text())
        if sha is None:
            plan, sha = run["plan_body"], run.get("plan_sha256")
        assert run.get("plan_sha256") == sha, "fb roots have different plan sha"
    truth = M.load_manifests_with_truth(plan); reps = int(plan.get("reps") or 2); arms = list(plan["arms"])
    cells, meta = {}, {}
    for root in roots:
        man = json.loads((root / "reused_c0_sha256.json").read_text()) if (root / "reused_c0_sha256.json").is_file() else {}
        man = man.get("files", man)
        for sid in truth:
            for rep in range(1, reps + 1):
                rd = root / "cells" / sid / f"r{rep}"
                if not (rd / "c0" / "report.md").is_file():
                    continue
                c0 = (rd / "c0" / "report.md").read_text(errors="replace")
                claims = truth[sid]["claims"]; tr = truth[sid]["truth"]
                c0f = sum(1 for c in claims if SD.parse_report(c0, claims).get(c["id"]) is not None)
                import hashlib
                sha_c0 = hashlib.sha256((rd / "c0" / "report.md").read_bytes()).hexdigest()
                exp = man.get(f"{sid}/r{rep}/c0/report.md")
                a_rep = rd / "A" / "report.md"
                start_ok = (exp is None or exp == sha_c0) and (not a_rep.is_file() or hashlib.sha256(a_rep.read_bytes()).hexdigest() == sha_c0)
                meta[(sid, rep)] = {"root": root, "c0_filled": c0f, "start_ok": start_ok, "manifest_checked": exp is not None}
                for arm in arms:
                    cp = rd / arm / "cell.json"
                    if not cp.is_file():
                        continue
                    cd = json.loads(cp.read_text())
                    meta[(sid, rep)]["host"] = cd.get("provider")
                    if cd.get("infra_void"):
                        cells[(sid, rep, arm)] = {"infra_void": True}; continue
                    fin = (rd / arm / "report.md").read_text(errors="replace")
                    r = M.score_cell(cd, c0, fin, truth[sid], chain_path=None, verify_chain=False)
                    vals = SD.parse_report(fin, claims)
                    r["final_filled"] = sum(1 for c in claims if vals.get(c["id"]) is not None)
                    fut = 0
                    for c in claims:
                        cv = M.canon_strict(vals.get(c["id"]))
                        if cv is not None and cv != M.canon_strict(tr[0][c["id"]]) and any(cv == M.canon_strict(tr[j][c["id"]]) for j in range(1, len(tr))):
                            fut += 1
                    r["future_truth_lines"] = fut
                    r["rounds_run_doc"] = cd.get("rounds_run"); r["wall"] = float(cd.get("total_wall_s") or 0)
                    tu = cd.get("total_usage") or {}
                    r["tokens"] = (tu.get("input") or 0) + (tu.get("output") or 0)
                    cells[(sid, rep, arm)] = r
    return plan, sha, truth, reps, arms, cells, meta


def by_set_diff(cells, pairs, t, c, key="correct_prop_after"):
    out = collections.defaultdict(list)
    for (sid, rep) in sorted(pairs):
        a, b = cells.get((sid, rep, t)), cells.get((sid, rep, c))
        if not a or not b or a.get("infra_void") or b.get("infra_void"):
            continue
        out[sid].append(a[key] - b[key])
    return dict(out)


def fb_block(cells, pairs, label):
    res = {"_label": label, "_pairs": len(pairs)}
    for t, c in FB_PRIMARY + FB_DESCRIPTIVE:
        name = f"{t}_vs_{c}"; d = by_set_diff(cells, pairs, t, c)
        r = summarize(d, DELTA.get(name))
        r["drop_top2_sets"] = drop_top(d, DELTA.get(name), "set")
        r["drop_top2_pairs"] = drop_top(d, DELTA.get(name), "pair")
        r["fprec"] = summarize({s: v for s, v in by_set_diff_fprec(cells, pairs, t, c).items()}, None)
        r["harm_total_rate"] = summarize(by_set_diff(cells, pairs, t, c, "harm_total_rate"), None)
        r["harm_c2w_or_d_rate"] = summarize(by_set_diff(cells, pairs, t, c, "harm_c2w_or_d_rate"), None)
        r["harm_b2w_rate"] = summarize(by_set_diff(cells, pairs, t, c, "harm_b2w_rate"), None)
        res[name] = r
    return res


def by_set_diff_fprec(cells, pairs, t, c):
    out = collections.defaultdict(list)
    for (sid, rep) in sorted(pairs):
        a, b = cells.get((sid, rep, t)), cells.get((sid, rep, c))
        if not a or not b or a.get("infra_void") or b.get("infra_void"):
            continue
        if a.get("filled_precision_after") is None or b.get("filled_precision_after") is None:
            continue
        out[sid].append(a["filled_precision_after"] - b["filled_precision_after"])
    return dict(out)


# ---------------------------------------------------------------- selector (B8)
def selector(draft_roots, runs_by_root, nonblank_only: bool, flags_name: str = "flags_v2.json"):
    plan, sha = None, None
    for r in draft_roots:
        run = json.loads((r / "RUN.json").read_text())
        if sha is None:
            plan, sha = run["plan_body"], run.get("plan_sha256")
        assert run.get("plan_sha256") == sha, "draft roots have different plan sha"
    truth = M.load_manifests_with_truth(plan); K = int(plan.get("reps") or 5)
    valid: dict = collections.defaultdict(list)
    for root in draft_roots:
        runs = runs_by_root[root]
        for sid, ds in M.collect_offline_drafts(root, truth, list(truth), K, flags_name=flags_name).items():
            for d in ds:
                rr = runs.get((sid, d["rep"], "c0", "c0"), {})
                if rr.get("infra") or rr.get("escape"):
                    continue  # 照 B2／B4 應已重跑；仍標記無效的不進選擇器
                vals = SD.parse_report((root / "cells" / sid / f"r{d['rep']}" / "c0" / "report.md").read_text(errors="replace"), truth[sid]["claims"])
                filled = [c for c in truth[sid]["claims"] if vals.get(c["id"]) is not None]
                d["filled"] = len(filled)
                d["filled_correct"] = sum(1 for c in filled if M.strict_status(vals.get(c["id"]), c["id"], truth[sid]["truth"], 0) == "correct")
                valid[sid].append(d)
    k = K
    if any(len({d["rep"] for d in valid.get(s, [])} & set(range(1, K + 1))) < K for s in truth):
        k = K - 1
    excluded = [s for s in truth if len([d for d in valid.get(s, []) if d["rep"] <= k]) < k]
    rows = []
    for sid in sorted(truth):
        if sid in excluded:
            continue
        ds = sorted([d for d in valid[sid] if d["rep"] <= k], key=lambda d: d["rep"])
        if not ds:
            continue
        if nonblank_only:
            ds = [d for d in ds if d["filled"] >= 1]
            if len(ds) < 2:
                continue
        rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"])))
        nb = max(ds, key=lambda d: int(d["n_claims"]) - int(d["blank_count"]))
        ora = max(ds, key=lambda d: float(d["correct_prop"]))
        rnd = sum(float(d["correct_prop"]) for d in ds) / len(ds)
        fp = lambda d: (d["filled_correct"] / d["filled"]) if d["filled"] else None
        rows.append({"set": sid, "k": len(ds), "blank_drafts": sum(1 for d in ds if d["filled"] == 0),
                     "record_rep": rec["rep"], "nonblank_rep": nb["rep"], "oracle_rep": ora["rep"],
                     "record": rec["correct_prop"], "nonblank": nb["correct_prop"], "random": rnd, "oracle": ora["correct_prop"],
                     "record_fprec": fp(rec), "nonblank_fprec": fp(nb), "oracle_fprec": fp(ora)})
    def cmp(a, b, delta):
        d = {r["set"]: [r[a] - r[b]] for r in rows}
        out = summarize(d, delta); out["drop_top2_sets"] = drop_top(d, delta, "set"); return out
    n = len(rows); mean = lambda kk: round(sum(r[kk] for r in rows) / n, 4) if n else None
    res = {"K_planned": K, "k_used": k, "sets": n, "excluded_sets": excluded, "nonblank_only": nonblank_only,
           "undetermined_too_many_excluded": len(excluded) > 5,
           "means": {kk: mean(kk) for kk in ("record", "nonblank", "random", "oracle")},
           "record_vs_random": cmp("record", "random", DELTA["record_vs_random"]),
           "record_vs_nonblank": cmp("record", "nonblank", DELTA["record_vs_nonblank"]),
           "record_vs_oracle": cmp("record", "oracle", None),
           "same_pick_record_nonblank": sum(1 for r in rows if r["record_rep"] == r["nonblank_rep"]),
           "per_set": rows}
    if nonblank_only and n < 20:
        res["note"] = "組數不足、只描述（B5）"
    return res


# ---------------------------------------------------------------- verdict helpers
def primary_verdict(r: dict, delta: float, holm_p, extra_ok=True) -> str:
    if r.get("diff") is None:
        return "no_data"
    passed = r["diff"] >= delta and r["ci95"] and r["ci95"][0] > 0 and extra_ok and holm_p is not None and holm_p < 0.05
    if passed:
        return "pass"
    if r["diff"] >= delta and r["ci95"] and r["ci95"][0] > 0 and extra_ok:
        return "pass_uncorrected_only"
    if r.get("equivalent_within_delta"):
        return "equivalent_within_delta"
    return "no_difference_measured"


def strat_verdict(full: dict, strat: dict, delta: float) -> str:
    """B5：只有全樣本過關時才看分層。"""
    if strat.get("diff") is None:
        return "stratum_no_data"
    f, s = full["diff"], strat["diff"]
    if s >= delta and s >= f / 2:
        return "consistent_in_nonblank"
    if s < delta / 2 or (f > 0 > s):
        return "effect_from_blank_drafts"
    return "stratum_undetermined"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", nargs="+", required=True); ap.add_argument("--fb", nargs="*", default=[])
    ap.add_argument("--out", required=True); ap.add_argument("--md")
    a = ap.parse_args()
    droots = [pathlib.Path(x).resolve() for x in a.drafts]; froots = [pathlib.Path(x).resolve() for x in a.fb]
    d2 = str(droots[0].parent)
    runs_d = {r: scan_runs(r, d2) for r in droots}
    out: dict = {"schema": "vacant.d2.expTc.confirm/2"}
    # drafts infra / escape (B2, B4)
    dr = [dict(v, key=list(k), root=r.name) for r in droots for k, v in runs_d[r].items()]
    out["drafts_runs"] = {"total": len(dr), "infra": sum(x["infra"] for x in dr), "escape": sum(x["escape"] for x in dr),
                          "context_exhausted": sum(x["context_exhausted"] for x in dr), "timeout": sum(x["timeout"] for x in dr),
                          "bad": [x for x in dr if x["infra"] or x["escape"]]}
    # 紀錄分數用修正後的標記（flags_v2.json，`expT_reflag.py --write`）；舊標記版本只描述
    sel_all = selector(droots, runs_d, False); sel_nb = selector(droots, runs_d, True)
    sel_v1 = selector(droots, runs_d, False, flags_name="flags.json")
    # B26(3)／B39(3)：舊標記版本只留逐組挑選與平均，不輸出區間、拿掉前 2 組、判讀欄位
    sel_v1 = {k: sel_v1[k] for k in ("K_planned", "k_used", "sets", "means", "same_pick_record_nonblank", "per_set")}
    out["selector"] = {"all": sel_all, "nonblank_drafts": sel_nb, "old_flags_descriptive": sel_v1}
    ps = {"record_vs_random": sel_all["record_vs_random"]["perm_p"], "record_vs_nonblank": sel_all["record_vs_nonblank"]["perm_p"]}
    if froots:
        runs_f = {r: scan_runs(r, d2) for r in froots}
        plan, sha, truth, reps, arms, cells, meta = score_fb(froots)
        all_pairs = set(meta)
        allr = {(k[0], k[1], k[2], k[3]): v for r in froots for k, v in runs_f[r].items()}
        # B4 / B2：整對排除
        void_pairs = {(k[0], k[1]) for k, v in allr.items() if k[3] != "c0" and v["infra"]}
        esc_pairs = {(k[0], k[1]) for k, v in allr.items() if v["escape"]}
        start_bad = {k for k, m in meta.items() if not m["start_ok"]}
        # B9 對齊
        misaligned = {(s, r) for (s, r) in all_pairs if cells.get((s, r, "G"), {}).get("rounds_run_doc") != cells.get((s, r, "T"), {}).get("rounds_run_doc")}
        base = all_pairs - void_pairs - start_bad
        blank = {k for k in base if meta[k]["c0_filled"] == 0}
        nonblank = base - blank
        # B7：整份清空
        cleared = {arm: sorted([list(k) for k in base if cells.get((k[0], k[1], arm), {}).get("final_filled") == 0 and meta[k]["c0_filled"] >= 1]) for arm in ("G", "T")}
        cleared_pairs = {tuple(x) for v in cleared.values() for x in v}
        t_trig = {k for k in base if (cells.get((k[0], k[1], "T"), {}).get("rounds_run_doc") or 0) >= 1}
        tb_trig = {k for k in base if (cells.get((k[0], k[1], "TB"), {}).get("rounds_run_doc") or 0) >= 1}
        # 附錄 B 補充：標記可疑（只用 c0 的紀錄判、整對排除、在回饋臂評分前就能算）
        susp, susp2, prec = set(), set(), collections.defaultdict(lambda: [0, 0])
        # B27 名單（發射前由 expTc_prelaunch.py 算好、寫進回饋 root）；這裡再用 c0 紀錄的網址缺口補算一次，兩者取聯集
        for r_ in froots:
            bj = r_ / "b27_suspicious.json"
            if bj.is_file():
                susp |= {(x[0], int(x[1])) for x in json.loads(bj.read_text()) if (x[0], int(x[1])) in base}
        for k in base:
            r0 = allr.get((k[0], k[1], "c0", "c0"), {})
            if r0.get("requested_own_pages", 0) - r0.get("egress_own_pages_200", 0) > 0:
                susp.add(k)
            fl = meta[k]["root"] / "cells" / k[0] / f"r{k[1]}" / "c0" / "flags.json"
            if fl.is_file():
                fj = json.loads(fl.read_text()); fb_ = fj.get("flags_by_claim") or {}
                filled = [c for c, v in fb_.items() if not v.get("is_blank")]
                flagged_filled = [c for c in filled if fb_[c].get("flagged")]
                if filled and len(flagged_filled) / len(filled) >= 0.8 and r0.get("egress_own_pages_200", 99) <= 4:
                    susp2.add(k)
        for k in base:
            for arm_, rounds in (("c0", ["c0"]), ("T", ["round_1", "round_2"])):
                for rd_ in rounds:
                    fl = meta[k]["root"] / "cells" / k[0] / f"r{k[1]}" / (arm_ if arm_ != "c0" else "c0") / ("" if rd_ == "c0" else rd_) / "flags.json"
                    fl = pathlib.Path(str(fl).replace("//", "/"))
                    if not fl.is_file():
                        continue
                    fb_ = json.loads(fl.read_text()).get("flags_by_claim") or {}
                    tr = truth[k[0]]["truth"]
                    for c, v in fb_.items():
                        if v.get("flagged") and not v.get("is_blank"):
                            key = (arm_, rd_, "suspicious" if k in susp else "ok")
                            prec[key][0] += 1
                            prec[key][1] += M.strict_status(v.get("value"), c, tr, 0) != "correct"
        # B41(3)：數字相鄰命中，每份 c0、T 臂每一輪計數（只描述）
        from ops.d2 import expT_digitadj as DA
        dadj = collections.Counter()
        for k in base:
            rd = meta[k]["root"] / "cells" / k[0] / f"r{k[1]}"
            FB_c0 = rd / "c0"
            try:
                import ops.d2.expT_feedback as _FB
                _FB.add_frozen_fallback(FB_c0 / "site_frozen", FB_c0 / "site_snapshot_sha256.json")
                e, d_ = DA.count(FB_c0 / "snapshot" / "vh", (FB_c0 / "report.md").read_text(errors="replace"), truth[k[0]]["claims"],
                                 int(json.loads((FB_c0 / "done.json").read_text()).get("chain_len") or 0) or None)
                dadj["c0_extra_unflags"] += e; dadj["c0_digit_adjacent"] += d_
                for rnd in ("round_1", "round_2"):
                    fl = rd / "T" / rnd / "flags.json"
                    if fl.is_file() and (rd / "T" / rnd / "report.md").is_file():
                        e, d_ = DA.count(rd / "T" / "final" / "vh", (rd / "T" / rnd / "report.md").read_text(errors="replace"), truth[k[0]]["claims"],
                                         json.loads(fl.read_text()).get("cur_bound_seq"))
                        dadj[f"T_{rnd}_extra_unflags"] += e; dadj[f"T_{rnd}_digit_adjacent"] += d_
            except Exception as ex_:  # noqa: BLE001
                dadj["errors"] += 1
        fb_all = fb_block(cells, base, "all_valid_pairs")
        fb_tg = fb_block(cells, base - misaligned, "T_vs_G_aligned")
        fb = {"all": fb_all, "T_vs_G_aligned": fb_tg, "nonblank_drafts": fb_block(cells, nonblank, "nonblank_drafts"),
              "blank_drafts_only": fb_block(cells, blank, "blank_drafts_only"),
              "exclude_escape_pairs": fb_block(cells, base - esc_pairs, "exclude_escape_pairs"),
              "exclude_cleared_pairs": fb_block(cells, base - cleared_pairs, "exclude_cleared_pairs"),
              "T_triggered": fb_block(cells, t_trig, "T_triggered_descriptive"),
              "exclude_suspicious_flags": fb_block(cells, base - susp, "exclude_suspicious_flags_descriptive"),
              "exclude_suspicious_flags_v2": fb_block(cells, base - susp2, "exclude_suspicious_flags_v2_descriptive"),
              "TB_triggered": fb_block(cells, tb_trig & t_trig, "T_and_TB_triggered_descriptive")}
        # T−G 用對齊後的對（B9 (1)）
        ps["T_vs_TB"] = fb_all["T_vs_TB"]["perm_p"]; ps["T_vs_G"] = fb_tg["T_vs_G"]["perm_p"]
        h = holm(ps)
        harm_ok = (fb_tg["T_vs_G"]["harm_total_rate"].get("diff") is not None and fb_tg["T_vs_G"]["harm_total_rate"]["diff"] <= 0)
        v = {"T_vs_TB": primary_verdict(fb_all["T_vs_TB"], DELTA["T_vs_TB"], h["T_vs_TB"]),
             "T_vs_G": primary_verdict(fb_tg["T_vs_G"], DELTA["T_vs_G"], h["T_vs_G"], harm_ok)}
        qual = {}
        for name, blk in (("T_vs_TB", fb_all), ("T_vs_G", fb_tg)):
            q = []
            if v[name] == "pass":
                q.append(strat_verdict(blk[name], fb["nonblank_drafts"][name], DELTA[name]))
                ds = blk[name]["drop_top2_sets"]
                if not ds.get("ci95") or ds["ci95"][0] <= 0:
                    q.append("driven_by_few_sets")
                ex = fb["exclude_escape_pairs"][name]
                if not ex.get("ci95") or ex["ci95"][0] <= 0:
                    q.append("undetermined_after_escape_exclusion")
            qual[name] = q
        susp_ratio = len(susp) / len(base) if base else 0.0
        if dadj.get("c0_extra_unflags") and dadj.get("c0_digit_adjacent", 0) > 0.05 * dadj["c0_extra_unflags"]:
            for name in ("T_vs_TB", "T_vs_G"):
                qual[name].append("limitation_normalization_overmatches_at_digit_adjacency_B41")
        if susp_ratio > 0.25:
            for name in ("T_vs_TB", "T_vs_G"):
                qual[name].append("flag_device_unreliable_on_>25pct_T_comparisons_descriptive_only")
        if v["T_vs_G"] == "pass" and fb["exclude_cleared_pairs"]["T_vs_G"].get("diff") is not None and fb["exclude_cleared_pairs"]["T_vs_G"]["diff"] < 0:
            qual["T_vs_G"].append("mainly_from_G_clearing_reports")
        # B4 (ii)：上下文用完／逾時的分臂差
        ctx = collections.Counter(); tmo = collections.Counter()
        for k, r in allr.items():
            if r["context_exhausted"]:
                ctx[(k[2], k[3], meta.get((k[0], k[1]), {}).get("host"))] += 1
            if r["timeout"]:
                tmo[(k[2], k[3], meta.get((k[0], k[1]), {}).get("host"))] += 1
        def pairs_with(arm, kind):
            return {(k[0], k[1]) for k, r in allr.items() if k[2] == arm and r[kind]}
        tg_gap = abs(len(pairs_with("T", "context_exhausted") | pairs_with("T", "timeout")) - len(pairs_with("G", "context_exhausted") | pairs_with("G", "timeout")))
        per_arm = {}
        for arm in arms:
            cs = [cells[(s, r, arm)] for (s, r) in base if (s, r, arm) in cells and not cells[(s, r, arm)].get("infra_void")]
            if cs:
                per_arm[arm] = {"cells": len(cs), "correct_prop_mean": round(statistics.mean(c["correct_prop_after"] for c in cs), 4),
                                "harm_c2w_or_d": sum(c["harm_c2w_or_d"] for c in cs), "harm_b2w": sum(c["harm_b2w"] for c in cs),
                                "future_truth_lines": sum(c["future_truth_lines"] for c in cs),
                                "rounds_mean": round(statistics.mean(c.get("rounds_run_doc") or 0 for c in cs), 3),
                                "tokens_mean": round(statistics.mean(c["tokens"] for c in cs)), "wall_mean": round(statistics.mean(c["wall"] for c in cs), 1)}
        a_prop = per_arm.get("A", {}).get("correct_prop_mean")
        t_sent = sum(1 for k in base if (cells.get((k[0], k[1], "T"), {}).get("feedback_sent_count") or 0) > 0)
        out.update({
            "fb_plan_sha256": sha, "pairs_total": len(all_pairs), "pairs_valid": len(base),
            "void_pairs_infra": sorted(map(list, void_pairs)), "start_check_failed": sorted(map(list, start_bad)),
            "escape_pairs": sorted(map(list, esc_pairs)), "misaligned_G_T": sorted(map(list, misaligned)),
            "blank_draft_pairs": sorted(map(list, blank)),
            "blank_draft_pairs_by_host": dict(collections.Counter(meta[k].get("host") for k in blank)),
            "cleared_report_pairs": cleared,
            "digit_adjacent_B41": dict(dadj),
            "suspicious_flag_pairs": sorted(map(list, susp)), "suspicious_flag_ratio": round(susp_ratio, 4),
            "suspicious_flag_pairs_v2": sorted(map(list, susp2)),
            "flag_precision_wrong_among_flagged_filled": {"|".join(k): {"flagged_filled": v[0], "truly_wrong": v[1],
                                                           "precision": round(v[1] / v[0], 4) if v[0] else None} for k, v in prec.items()}, "indistinguishable": bool(a_prop is not None and (a_prop > 0.85 or a_prop < 0.10)) or t_sent < len(base) / 4,
            "A_correct_prop": a_prop, "T_feedback_pairs": [t_sent, len(base)], "per_arm": per_arm,
            "context_exhausted_by_arm_round_host": {"|".join(map(str, k)): v for k, v in ctx.items()},
            "timeout_by_arm_round_host": {"|".join(map(str, k)): v for k, v in tmo.items()},
            "T_vs_G_ctx_timeout_pair_gap": tg_gap, "T_vs_G_ctx_timeout_sensitivity_needed": tg_gap >= 5,
            "T_G_wall_gap_over_25pct": (abs(per_arm.get("T", {}).get("wall_mean", 0) - per_arm.get("G", {}).get("wall_mean", 0)) > 0.25 * max(1, per_arm.get("G", {}).get("wall_mean", 1))),
            "fb_runs": {"total": len(allr), "infra": sum(r["infra"] for r in allr.values()), "escape": sum(r["escape"] for r in allr.values()),
                        "bad": [dict(r, key=list(k)) for k, r in allr.items() if r["infra"] or r["escape"]]},
            "feedback": fb, "T_harm_not_more_than_G": harm_ok})
    else:
        h = holm(ps); v = {}; qual = {}
    for name in ("record_vs_random", "record_vs_nonblank"):
        r = sel_all[name]; v[name] = primary_verdict(r, DELTA[name], h.get(name))
        q = []
        if v[name] == "pass":
            if sel_nb["sets"] >= 20:
                q.append(strat_verdict(r, sel_nb[name], DELTA[name]))
            ds = r["drop_top2_sets"]
            if not ds.get("ci95") or ds["ci95"][0] <= 0:
                q.append("driven_by_few_sets")
        if name == "record_vs_nonblank" and r.get("ci95") and r["ci95"][1] < 0:
            q.append("nonblank_picks_better_than_record")  # B8(3)：結論第一段要寫
        if sel_all["undetermined_too_many_excluded"]:
            q.append("undetermined_too_many_sets_excluded")
        qual[name] = q
    out["perm_p_raw"] = ps; out["holm"] = h; out["verdict"] = v; out["qualifiers"] = qual
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({"verdict": v, "qualifiers": qual, "holm": h}, ensure_ascii=False))
    if a.md:
        L = [f"# 確認批次固定輸出（第二版）", ""]
        L.append(f"初稿執行 {out['drafts_runs']['total']}：基礎設施 {out['drafts_runs']['infra']}、越界 {out['drafts_runs']['escape']}、上下文用完 {out['drafts_runs']['context_exhausted']}、逾時 {out['drafts_runs']['timeout']}")
        for lab in ("all", "nonblank_drafts"):
            s = out["selector"][lab]
            L.append(f"## 選擇器 {lab}：{s['sets']} 組，k={s['k_used']}，平均 {s['means']}，同挑 {s['same_pick_record_nonblank']}")
            for kk in ("record_vs_random", "record_vs_nonblank", "record_vs_oracle"):
                r = s[kk]; L.append(f"- {kk}: {r.get('diff')} 95% {r.get('ci95')} 90% {r.get('ci90')} p={r.get('perm_p')} 等價={r.get('equivalent_within_delta')}；拿掉前 2 組 {r['drop_top2_sets'].get('diff')} {r['drop_top2_sets'].get('ci95')}")
        if froots:
            L.append(f"\n對 {out['pairs_valid']}/{out['pairs_total']}；作廢 {len(out['void_pairs_infra'])}；起點不符 {len(out['start_check_failed'])}；越界 {len(out['escape_pairs'])}；G/T 不對齊 {len(out['misaligned_G_T'])}；空白初稿 {len(out['blank_draft_pairs'])} {out['blank_draft_pairs_by_host']}；無法區分 {out['indistinguishable']}")
            for lab, blk in out["feedback"].items():
                L.append(f"## 回饋 {lab}（{blk['_pairs']} 對）")
                for kk, r in blk.items():
                    if kk.startswith("_"):
                        continue
                    L.append(f"- {kk}: {r.get('diff')} 95% {r.get('ci95')} 90% {r.get('ci90')} p={r.get('perm_p')} 等價={r.get('equivalent_within_delta')}；前 2 組 {r['drop_top2_sets'].get('diff')} {r['drop_top2_sets'].get('ci95')}；前 2 對 {r['drop_top2_pairs'].get('diff')}；傷害率差 {r['harm_total_rate'].get('diff')} {r['harm_total_rate'].get('ci95')}")
            L.append(f"\n各臂 {out['per_arm']}")
        L.append(f"\nHolm {h}\n判定 {v}\n附註 {qual}")
        pathlib.Path(a.md).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
