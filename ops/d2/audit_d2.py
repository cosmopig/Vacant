#!/usr/bin/env python3
"""D2′ 稽核：**只讀紀錄**（病歷的鏈＋內容定址庫、來源伺服器的存取紀錄、封存的改動清單），不看 agent 對話、
不讀執行器存的 report.md，重算每一臂的分數、追每條最終宣稱的來歷、把每個錯誤歸因到一段。

只用標準函式庫，自己讀病歷的檔案格式（不 import vacant_network），讓沒參與的人可以照著重寫：
  病歷：<vh>/trace/projects/<key>/chain.ndjson（＋分卷 chain-NNNNNN.ndjson[.gz]），一行一筆事件，`seq` 連續、
        `prev_hash` 串起來；內容：<vh>/trace/objects/<sha 前兩碼>/<sha>。
  step 事件：payload.tool、input_blob（工具輸入 JSON）、output_blob（工具輸出）、post_index（這一步之後的
        工作區索引 JSON：{路徑: [內容 sha, 大小, mtime, …]}）、writes。
  unrecorded_change：payload.after_index。
  source_check（產品 `vacant trace sources --check` 寫的）：每條宣稱的來源、狀態、受影響的行。
週期的切點：執行器在每個週期結束時記下的鏈的最後 seq（cycle.json 的 chain_len、c0 的 done.json）——這是唯一
從執行器拿的東西；內容一律從病歷重建。

輸出：
  scores       用重建的 report.md 算的分數（與 score_d2.py 同一個 `score()`），以及和執行器分數逐列比對的結果
  provenance   每一臂最後一版的每條宣稱：寫下它的那一步、那一步所在的週期、它之前讀到這個值的那一步、
               網址、讀到的內容 sha256；伺服器存取紀錄裡有沒有對得上的那一次讀取
  attribution  每一個錯誤（漏抓、誤改、初稿錯）歸到哪一段
  coverage     c 臂第一次來源檢查時，出處指到正確頁面的比例
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score_d2 import canon, load_harness, parse_report, score  # noqa: E402

URL_RE = re.compile(r"https?://[^\s'\"<>|;]+")


class Record:
    def __init__(self, vh: pathlib.Path):
        self.vh = vh
        projs = list((vh / "trace" / "projects").iterdir())
        if len(projs) != 1:
            raise SystemExit(f"{vh}: expected one project, got {len(projs)}")
        self.pdir = projs[0]
        self.events = self._load()
        self.problems: list[str] = []
        self._check_seq()

    def _load(self) -> list[dict]:
        vols = sorted(self.pdir.glob("chain-*.ndjson*"))
        out = []
        for v in vols + [self.pdir / "chain.ndjson"]:
            if not v.exists():
                continue
            data = gzip.decompress(v.read_bytes()) if v.suffix == ".gz" else v.read_bytes()
            for line in data.decode().splitlines():
                if line.strip():
                    out.append(json.loads(line))
        return out

    def _check_seq(self) -> None:
        """真的驗鏈（獨立稽核 11-25 第 3 點）：每一筆的雜湊＝sha256(canonical(stream_id, branch_id, seq, prev_hash,
        ts_ms, type, payload))，canonical＝sort_keys、緊湊分隔、UTF-8 不轉義；prev_hash 串接；stream_id＝創世那一筆的雜湊；
        Ed25519 簽章用創世記的 signer 驗；signer 必須是這個 VACANT_HOME 的 trust.json 裡 verifier 角色的一把鑰匙；
        步驟引用的內容（input／output／post_index）在內容定址庫裡、雜湊對得上。結果寫進 `self.verify`。"""
        v = {"entries": len(self.events), "hash_chain_ok": True, "signatures_ok": None, "signer_trusted": None,
             "blobs_checked": 0, "blobs_bad": 0, "problems": []}
        def canon(o):
            return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except ImportError:                        # 沒有 cryptography：只驗雜湊鏈，照實寫
            Ed25519PublicKey = None
        if not self.events or self.events[0].get("type") != "trace_genesis":
            v["problems"].append("first entry is not trace_genesis")
        signer = (self.events[0].get("payload") or {}).get("signer") if self.events else None
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(signer)) if (Ed25519PublicKey and signer) else None
        if pub is not None:
            v["signatures_ok"] = True
        try:
            trust = json.loads((self.vh / "intake" / "trust.json").read_text())
            v["signer_trusted"] = bool(signer) and signer in (trust.get("verifier") or {}).values()
        except (OSError, ValueError):
            v["signer_trusted"] = None
        prev, sid = "0" * 64, None
        for i, e in enumerate(self.events):
            core = {k: e.get(k) for k in ("stream_id", "branch_id", "seq", "prev_hash", "ts_ms", "type", "payload")}
            if e.get("seq") != (self.events[0]["seq"] + i):
                v["problems"].append(f"seq {e.get('seq')} at position {i}")
            if e.get("prev_hash") != prev:
                v["hash_chain_ok"] = False
                v["problems"].append(f"prev_hash mismatch at seq {e.get('seq')}")
            h = hashlib.sha256(canon(core)).hexdigest()
            if i == 0:
                sid = h
            elif e.get("stream_id") != sid:
                v["hash_chain_ok"] = False
                v["problems"].append(f"stream_id mismatch at seq {e.get('seq')}")
            if pub is not None:
                try:
                    pub.verify(bytes.fromhex(e.get("sig") or ""), canon(core))
                except Exception:              # noqa: BLE001
                    v["signatures_ok"] = False
                    v["problems"].append(f"bad signature at seq {e.get('seq')}")
            prev = h
            p = e.get("payload") or {}
            if e.get("type") == "step":
                for key in ("input_blob", "output_blob", "post_index"):
                    sha = p.get(key)
                    if sha:
                        v["blobs_checked"] += 1
                        b = self.blob(sha)
                        if b is None or hashlib.sha256(b).hexdigest() != sha:
                            v["blobs_bad"] += 1
        self.verify = v
        self.problems += v["problems"][:20]
        if v["blobs_bad"]:
            self.problems.append(f"{v['blobs_bad']} referenced blobs missing or hash mismatch")
        if v["signer_trusted"] is False:
            self.problems.append("genesis signer is not a verifier key in trust.json")

    def blob(self, sha: str | None) -> bytes | None:
        if not sha:
            return None
        p = self.vh / "trace" / "objects" / sha[:2] / sha
        return p.read_bytes() if p.exists() else None

    def text(self, sha: str | None) -> str | None:
        b = self.blob(sha)
        return None if b is None else b.decode("utf-8", "replace")

    def index_at(self, seq: int) -> str | None:
        idx = None
        for e in self.events:
            if e["seq"] > seq:
                break
            p = e.get("payload") or {}
            if e["type"] == "step" and p.get("post_index"):
                idx = p["post_index"]
            elif e["type"] == "unrecorded_change" and p.get("after_index"):
                idx = p["after_index"]
        return idx

    def file_at(self, seq: int, path: str = "report.md") -> str | None:
        idx = self.index_at(seq)
        if idx is None:
            return None
        ix = json.loads(self.text(idx) or "{}")
        ent = ix.get(path)
        return self.text(ent[0]) if ent else None

    def steps(self, lo: int, hi: int) -> list[dict]:
        return [e for e in self.events if e["type"] == "step" and lo < e["seq"] <= hi]

    def source_checks(self, lo: int, hi: int) -> list[dict]:
        return [e for e in self.events if e["type"] == "source_check" and lo < e["seq"] <= hi]

    def handed_lines(self, lo: int, hi: int) -> set[int] | None:
        """這個週期 c 臂真的交給 agent 的行：從鏈上記下的提示文字讀（`- line N:`）。沒有提示＝這週期沒叫 agent ⇒ 空集合。"""
        out: set[int] = set()
        for e in self.events:
            if e["type"] == "prompt" and lo < e["seq"] <= hi:
                t = self.text((e.get("payload") or {}).get("text_blob")) or ""
                out |= {int(m) for m in re.findall(r"(?m)^- line (\d+):", t)}
        return out


def step_cmd(rec: Record, e: dict) -> str:
    try:
        inp = json.loads(rec.text(e["payload"].get("input_blob")) or "{}")
    except ValueError:
        return ""
    return str(inp.get("command") or inp.get("path") or "")


def last_writer_of_line(rec: Record, hi: int, line_prefix: str, value: str | None) -> dict | None:
    """在 seq ≤ hi 的步驟裡，最後一個讓這一行變成現在這個值的步驟。"""
    best = None
    prev_line = None
    for e in rec.events:
        if e["seq"] > hi:
            break
        if e["type"] != "step" or not e["payload"].get("post_index"):
            continue
        ix = json.loads(rec.text(e["payload"]["post_index"]) or "{}")
        ent = ix.get("report.md")
        txt = rec.text(ent[0]) if ent else ""
        ln = next((x for x in (txt or "").splitlines() if x.strip().startswith(line_prefix)), None)
        if ln != prev_line:
            best = e if (value is not None and ln is not None and canon(ln.split(":", 1)[-1]) == canon(value)) else best
            prev_line = ln
    return best


def reader_before(rec: Record, write_seq: int, value: str) -> dict | None:
    """寫入之前、同一個工作階段裡，輸出含有這個值的最近一步（抓網頁的那一步）。"""
    cv = canon(value)
    w = next(e for e in rec.events if e["seq"] == write_seq)
    sess = (w["payload"].get("actor") or {}).get("session")
    for e in reversed([x for x in rec.events if x["type"] == "step" and x["seq"] < write_seq]):
        if (e["payload"].get("actor") or {}).get("session") != sess:
            continue
        if e["payload"].get("tool") in ("edit", "write") or "report.md" in step_cmd(rec, e):
            continue        # 讀交件自己（之前寫進去的值）不是來源
        out = rec.text(e["payload"].get("output_blob")) or ""
        if cv and any(canon(m) == cv for m in re.findall(r"v?\d+\.\d+\.\d+|\$?\d[\d,]*", out)):
            return e
    return None


def _pages(cl: dict) -> list[str]:
    """宣稱的正確來源頁：舊教材一頁（`source_page`）；留出教材可能好幾頁（`source_pages`）。"""
    return list(cl.get("source_pages") or [cl["source_page"]])


def file_url(rec: Record, read_step: dict, path: str) -> tuple[str, str] | None:
    """`read <檔>` 讀到的檔是哪一個網址抓來的：最近一個寫了這個檔的步驟，它的指令裡 `curl … URL … > 檔`。
    回（網址、那一步寫出的內容 sha256）。"""
    name = pathlib.PurePosixPath(path).name
    for e in reversed([x for x in rec.events if x["type"] == "step" and x["seq"] < read_step["seq"]]):
        hit = [wr for wr in e["payload"].get("writes") or [] if pathlib.PurePosixPath(wr.get("path", "")).name == name]
        if not hit:
            continue
        cmd = step_cmd(rec, e)
        for seg in re.split(r"&&|\|\||;|\n", cmd):
            if re.search(r">\s*\S*" + re.escape(name) + r"\b", seg):
                u = URL_RE.findall(seg)
                if len(u) == 1:
                    return u[0], hit[0].get("after") or ""
        return None
    return None


def candidate_urls(rec: Record, write_seq: int, value: str) -> list[str]:
    """沒有產品出處的行：寫入之前、同一個工作階段裡，抓過、而且輸出裡有這個數值的網址（全部列出，不挑）。"""
    cv = canon(value)
    w = next(e for e in rec.events if e["seq"] == write_seq)
    sess = (w["payload"].get("actor") or {}).get("session")
    out: list[str] = []
    for e in rec.events:
        if e["seq"] >= write_seq or e["type"] != "step" or (e["payload"].get("actor") or {}).get("session") != sess:
            continue
        urls = URL_RE.findall(step_cmd(rec, e))
        if not urls:
            continue
        txt = rec.text(e["payload"].get("output_blob")) or ""
        if cv and any(canon(m) == cv for m in re.findall(r"v?\d+\.\d+\.\d+|\$?\d[\d,]*", txt)):
            out += [u for u in urls if u not in out]
    return out


def served(access: list[dict], url: str, before_ts: float, arm: str) -> bool:
    """來源伺服器在這之前把這個網址給過 agent（不是 Vacant 的重讀）；存取紀錄帶臂時要對得上臂。"""
    try:
        host, path = url.split("/")[2], "/" + url.split("/", 3)[3]
    except IndexError:
        return False
    return any(a["host"] == host and a["path"] == path and a.get("ua") != "vacant-source-check"
               and a["ts"] <= before_ts + 1 and (a.get("arm") in (None, arm, "c0")) for a in access)


def fetch_idiom(snap: Record, upto: int) -> str:
    """初稿怎麼抓頁面（覆蓋率按這個分層）：看初稿裡第一個含 curl／wget 的殼層指令。"""
    for e in snap.events:
        if e["seq"] > upto or e["type"] != "step":
            continue
        cmd = step_cmd(snap, e)
        if not re.search(r"\b(curl|wget)\b", cmd):
            continue
        n = len(URL_RE.findall(cmd))
        if re.search(r"\bfor\b|\bwhile\b", cmd):
            return "loop"
        if re.search(r">\s*/tmp/", cmd):
            return "redirect outside workspace"
        if re.search(r">\s*\S", cmd):
            return "redirect into workspace file"
        if re.search(r"\b(ls|sed|awk|python3?|node)\b", cmd):
            return "mixed with other commands"
        return "one url, stdout" if n == 1 else "several urls, stdout"
    return "no fetch command"


def audit(root: pathlib.Path, manifest: dict) -> dict:
    sets = {s["set"]: s for s in manifest["sets"]}
    access = []
    if (root / "access.jsonl").exists():
        access = [json.loads(x) for x in (root / "access.jsonl").read_text().splitlines() if x.strip()]
    reports: dict = {}
    prov_rows, attr_rows, cov_rows, problems = [], [], [], []
    chain_ver: dict = {}
    for sdir in sorted((root / "cells").iterdir()):
        sid = sdir.name
        s = sets[sid]
        c0 = sdir / "c0"
        if not (c0 / "done.json").exists():
            continue
        b0 = json.loads((c0 / "done.json").read_text())["chain_len"]
        snap = Record(c0 / "snapshot" / "vh")
        chain_ver[f"{sid}/c0"] = snap.verify
        reports[sid] = {"c0": snap.file_at(b0) or ""}
        for adir in sorted(p for p in sdir.iterdir() if p.name != "c0" and (p / "done.json").exists()):
            arm = adir.name
            rec = Record(adir / "final" / "vh")
            problems += [f"{sid}/{arm}: {p}" for p in rec.problems]
            chain_ver[f"{sid}/{arm}"] = rec.verify
            # 四臂接的是同一個初稿病歷：快照的鏈必須是這一臂的鏈的前綴
            if [json.dumps(e, sort_keys=True) for e in rec.events[:len(snap.events)]] != \
                    [json.dumps(e, sort_keys=True) for e in snap.events]:
                problems.append(f"{sid}/{arm}: chain does not start with the c0 record")
            bounds = [b0]
            ncyc = len(s.get("cycles") or []) or (len(s["truth"]) - 1)
            for k in range(1, ncyc + 1):
                info = json.loads((adir / f"cycle_{k}" / "cycle.json").read_text())
                bounds.append(info["chain_len"])
                reports[sid][f"{arm}/{k}"] = rec.file_at(info["chain_len"]) or ""
            # ---- 出處覆蓋率（c 臂第一次來源檢查）＋初稿的抓取寫法（覆蓋率按寫法分層報；獨立稽核第 4 點）
            if arm == "c":
                scs = rec.source_checks(bounds[0], bounds[1])
                if scs:
                    c0_lines = reports[sid]["c0"].splitlines()
                    idiom = fetch_idiom(snap, b0)
                    for cl in s["claims"]:
                        ln = next((i + 1 for i, x in enumerate(c0_lines) if x.strip().startswith(cl["template_line"].strip())), None)
                        ents = [e for e in scs[0]["payload"]["claims"] if e["line"] == ln]
                        url = next(((e.get("source") or {}).get("url") for e in ents if e.get("source")), None)
                        cov_rows.append({"set": sid, "claim": cl["id"], "line": ln, "url": url, "fetch_idiom": idiom,
                                         "correct_page": bool(url and any(url.endswith("/" + pg) for pg in _pages(cl))),
                                         "picked_by": next(((e.get("source") or {}).get("picked_by") for e in ents if e.get("source")), None),
                                         "status_cycle1": ents[0]["status"] if ents else None})
            # ---- 每條最終宣稱的來歷（獨立稽核第 2 點）：網址只取產品在鏈上簽下的 source_check；
            #      沒有 source_check 的臂（a、b、d）產品沒有算出處，這裡不猜，只列候選
            final = parse_report(reports[sid][f"{arm}/{ncyc}"], s["claims"])
            fin_lines = reports[sid][f"{arm}/{ncyc}"].splitlines()
            all_sc = rec.source_checks(0, bounds[ncyc])
            for cl in s["claims"]:
                v = final[cl["id"]]
                ln = next((i + 1 for i, x in enumerate(fin_lines) if x.strip().startswith(cl["template_line"].strip())), None)
                w = last_writer_of_line(rec, bounds[ncyc], cl["template_line"].strip().rstrip(":"), v)
                row = {"set": sid, "arm": arm, "claim": cl["id"], "value": v, "write_step": None, "write_cycle": None,
                       "provenance_by": None, "url": None, "url_correct_page": None, "seen_sha256": None,
                       "candidates": None, "server_saw_fetch": None}
                if w:
                    row["write_step"] = w["payload"]["step"]
                    row["write_cycle"] = next((k for k in range(ncyc + 1) if w["seq"] <= bounds[k]), None)
                    ent = None
                    for e in reversed(all_sc):
                        if e["seq"] < w["seq"]:
                            break
                        ent = next((x for x in e["payload"]["claims"] if x["line"] == ln and canon(x.get("value")) == canon(v)
                                    and x.get("source")), None)
                        if ent:
                            break
                    if ent:
                        src = ent["source"]
                        row.update(provenance_by="product source_check", url=src.get("url"),
                                   url_correct_page=any(src.get("url", "").endswith("/" + pg) for pg in _pages(cl)),
                                   seen_sha256=src.get("baseline_sha256") or src.get("seen_sha256"))
                    else:
                        cands = candidate_urls(rec, w["seq"], v or "")
                        row.update(provenance_by="candidates (no product provenance for this line)", candidates=cands or None)
                    urls = [row["url"]] if row["url"] else (row["candidates"] or [])
                    wts = w.get("ts_ms", 0) / 1000.0
                    row["server_saw_fetch"] = any(served(access, u, wts, arm) for u in urls) if urls else None
                prov_rows.append(row)
            # ---- 錯誤歸因（獨立稽核第 1 點：交辦清單＝鏈上記下的提示裡真的列出的行，不是 affected_lines）
            for k in range(1, ncyc + 1):
                pre = parse_report(reports[sid][f"{arm}/{k - 1}"] if k > 1 else reports[sid]["c0"], s["claims"])
                post = parse_report(reports[sid][f"{arm}/{k}"], s["claims"])
                sc = rec.source_checks(bounds[k - 1], bounds[k])
                handed = rec.handed_lines(bounds[k - 1], bounds[k]) if arm in ("c", "c_every") else set()
                sc_by_line = {e["line"]: e for e in (sc[0]["payload"]["claims"] if sc else [])}
                sc_next = rec.source_checks(bounds[k], bounds[k + 1]) if k < ncyc else []
                next_by_line = {e["line"]: e for e in (sc_next[0]["payload"]["claims"] if sc_next else [])}
                fetched = {u for st in rec.steps(bounds[k - 1], bounds[k]) for u in URL_RE.findall(step_cmd(rec, st))}
                lines_now = reports[sid][f"{arm}/{k - 1}"].splitlines() if k > 1 else reports[sid]["c0"].splitlines()
                for cl in s["claims"]:
                    cid = cl["id"]
                    t_new, t_old = s["truth"][k][cid], s["truth"][k - 1][cid]
                    ok_post = canon(post[cid]) == canon(t_new)
                    ok_pre = canon(pre[cid]) == canon(t_old)
                    changed = t_new != t_old
                    if ok_post or not (changed or ok_pre):
                        continue
                    kind = "miss" if changed else "false_mod"
                    ln = next((i + 1 for i, x in enumerate(lines_now) if x.strip().startswith(cl["template_line"].strip())), None)
                    page_url = next((u for u in fetched if any(u.endswith("/" + pg) for pg in _pages(cl))), None)
                    extra = {}
                    if pre[cid] is None:
                        seg = "claim line missing from the report (draft changed or dropped it)"
                    elif arm == "a":
                        seg = "not maintained (arm a)"
                    elif arm in ("c", "c_every"):
                        e = sc_by_line.get(ln) or {}
                        src = (e.get("source") or {}).get("url")
                        st = e.get("status")
                        if kind == "miss" and ln not in handed:
                            if st == "no_source" or not e:
                                seg = "provenance not recorded (no_source); not handed this cycle"
                            elif src and not any(src.endswith("/" + pg) for pg in _pages(cl)):
                                seg = "provenance points to the wrong page; not handed"
                            else:
                                seg = "change not detected (source re-read said unchanged); not handed"
                        elif kind == "miss":
                            seg = ("handed to agent, page not re-read" if not page_url else
                                   "handed to agent, page re-read, not corrected")
                        else:
                            seg = ("agent changed a line it was not handed" if ln not in handed else
                                   "agent changed a handed line wrongly")
                        # 基準更新的漏洞（獨立稽核第 7 點）：交辦了沒改對，下一次檢查卻說 unchanged
                        nx = next_by_line.get(ln) or {}
                        if kind == "miss" and ln in handed and nx.get("status") == "unchanged" \
                                and canon(nx.get("value")) == canon(post[cid]):
                            extra["baseline_refreshed_while_stale"] = True
                    else:
                        if kind == "miss":
                            seg = "page not re-read" if not page_url else "page re-read, not corrected"
                        else:
                            seg = "agent changed a correct value wrongly"
                    attr_rows.append({"set": sid, "arm": arm, "cycle": k, "claim": cid, "kind": kind, "segment": seg,
                                      "pre": pre[cid], "post": post[cid], "truth": t_new, **extra})
    res = score(manifest, reports)
    # c0 初稿錯
    for r in res["rows"]:
        if r["arm"] == "c0" and r["status"] != "correct":
            attr_rows.append({"set": r["set"], "arm": "c0", "cycle": 0, "claim": r["claim"], "kind": "draft_wrong",
                              "segment": "first draft already wrong", "pre": None, "post": r["value"],
                              "truth": sets[r["set"]]["truth"][0][r["claim"]]})
    seg_table: dict = {}
    for a in attr_rows:
        seg_table.setdefault(a["arm"], {}).setdefault(a["kind"], {}).setdefault(a["segment"], 0)
        seg_table[a["arm"]][a["kind"]][a["segment"]] += 1
    prov_sum: dict = {}
    for r in prov_rows:
        d = prov_sum.setdefault(r["arm"], {"claims": 0, "write_step": 0, "product_provenance": 0,
                                           "product_provenance_correct_page": 0, "candidates_only": 0,
                                           "server_saw_fetch": 0})
        d["claims"] += 1
        d["write_step"] += r["write_step"] is not None
        d["product_provenance"] += r["provenance_by"] == "product source_check"
        d["product_provenance_correct_page"] += bool(r["url_correct_page"])
        d["candidates_only"] += bool(r["candidates"])
        d["server_saw_fetch"] += bool(r["server_saw_fetch"])
    cov = {"claims": len(cov_rows), "with_source": sum(1 for r in cov_rows if r["url"]),
           "correct_page": sum(1 for r in cov_rows if r["correct_page"])}
    by_idiom: dict = {}
    for r in cov_rows:
        d = by_idiom.setdefault(r["fetch_idiom"], {"sets": set(), "claims": 0, "correct_page": 0})
        d["sets"].add(r["set"])
        d["claims"] += 1
        d["correct_page"] += r["correct_page"]
    cov["by_fetch_idiom"] = {k: {"sets": len(v["sets"]), "claims": v["claims"], "correct_page": v["correct_page"]}
                             for k, v in sorted(by_idiom.items())}
    loophole = sum(1 for a in attr_rows if a.get("baseline_refreshed_while_stale"))
    return {"scores": res, "attribution": attr_rows, "attribution_table": seg_table,
            "provenance": prov_rows, "provenance_summary": prov_sum, "coverage": cov, "coverage_rows": cov_rows,
            "baseline_refreshed_while_stale": loophole, "chain_verification": chain_ver,
            "record_problems": problems}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    manifest = json.loads(pathlib.Path(a.manifest).read_text())
    res = audit(root, manifest)
    hr, hc = load_harness(root)
    hs = score(manifest, hr)
    key = lambda r: (r["set"], r["arm"], r["cycle"], r["claim"])        # noqa: E731
    A = {key(r): r["status"] for r in res["scores"]["rows"]}
    H = {key(r): r["status"] for r in hs["rows"]}
    mism = [{"row": k, "audit": A.get(k), "harness": H.get(k)} for k in sorted(set(A) | set(H)) if A.get(k) != H.get(k)]
    res["harness_match"] = {"rows": len(H), "mismatches": len(mism), "examples": mism[:20]}
    body = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    if a.out:
        pathlib.Path(a.out).write_text(body)
    cv = res["chain_verification"]
    res["chain_verification_summary"] = {
        "chains": len(cv), "hash_chain_ok": sum(1 for v in cv.values() if v["hash_chain_ok"]),
        "signatures_ok": sum(1 for v in cv.values() if v["signatures_ok"]),
        "signer_trusted": sum(1 for v in cv.values() if v["signer_trusted"]),
        "blobs_checked": sum(v["blobs_checked"] for v in cv.values()), "blobs_bad": sum(v["blobs_bad"] for v in cv.values())}
    out = {k: res[k] for k in ("harness_match", "coverage", "provenance_summary", "attribution_table", "record_problems",
                               "chain_verification_summary", "baseline_refreshed_while_stale")}
    out["summary"] = res["scores"]["summary"]
    print(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=str))
    return 0 if not mism else 3


if __name__ == "__main__":
    raise SystemExit(main())
