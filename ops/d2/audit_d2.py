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
        for a, b in zip(self.events, self.events[1:]):
            if b["seq"] != a["seq"] + 1:
                self.problems.append(f"seq gap {a['seq']}→{b['seq']}")
            if not b.get("prev_hash"):
                self.problems.append(f"no prev_hash at {b['seq']}")

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


def audit(root: pathlib.Path, manifest: dict) -> dict:
    sets = {s["set"]: s for s in manifest["sets"]}
    access = []
    if (root / "access.jsonl").exists():
        access = [json.loads(x) for x in (root / "access.jsonl").read_text().splitlines() if x.strip()]
    reports: dict = {}
    prov_rows, attr_rows, cov_rows, problems = [], [], [], []
    for sdir in sorted((root / "cells").iterdir()):
        sid = sdir.name
        s = sets[sid]
        c0 = sdir / "c0"
        if not (c0 / "done.json").exists():
            continue
        b0 = json.loads((c0 / "done.json").read_text())["chain_len"]
        snap = Record(c0 / "snapshot" / "vh")
        reports[sid] = {"c0": snap.file_at(b0) or ""}
        for adir in sorted(p for p in sdir.iterdir() if p.name != "c0" and (p / "done.json").exists()):
            arm = adir.name
            rec = Record(adir / "final" / "vh")
            problems += [f"{sid}/{arm}: {p}" for p in rec.problems]
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
            # ---- 出處覆蓋率（c 臂第一次來源檢查）
            if arm == "c":
                scs = rec.source_checks(bounds[0], bounds[1])
                if scs:
                    c0_lines = reports[sid]["c0"].splitlines()
                    for cl in s["claims"]:
                        ln = next((i + 1 for i, x in enumerate(c0_lines) if x.strip().startswith(cl["template_line"].strip())), None)
                        ents = [e for e in scs[0]["payload"]["claims"] if e["line"] == ln]
                        url = next(((e.get("source") or {}).get("url") for e in ents if e.get("source")), None)
                        cov_rows.append({"set": sid, "claim": cl["id"], "line": ln, "url": url,
                                         "correct_page": bool(url and url.endswith("/" + cl["source_page"])),
                                         "status_cycle1": ents[0]["status"] if ents else None})
            # ---- 每條最終宣稱的來歷
            final = parse_report(reports[sid][f"{arm}/{ncyc}"], s["claims"])
            for cl in s["claims"]:
                v = final[cl["id"]]
                w = last_writer_of_line(rec, bounds[ncyc], cl["template_line"].strip().rstrip(":"), v)
                row = {"set": sid, "arm": arm, "claim": cl["id"], "value": v, "write_step": None, "write_cycle": None,
                       "read_step": None, "url": None, "read_sha256": None, "server_saw_read": None}
                if w:
                    row["write_step"] = w["payload"]["step"]
                    row["write_cycle"] = next((k for k in range(ncyc + 1) if w["seq"] <= bounds[k]), None)
                    r = reader_before(rec, w["seq"], v or "")
                    if r:
                        out = rec.blob(r["payload"].get("output_blob")) or b""
                        urls = URL_RE.findall(step_cmd(rec, r))
                        sha = hashlib.sha256(out).hexdigest()
                        if not urls and r["payload"].get("tool") == "read":
                            # 讀的是 agent 自己用 curl 存下來的檔：找寫出這個檔的那一步、同一段裡導進它的網址
                            fu = file_url(rec, r, step_cmd(rec, r))
                            if fu:
                                urls, sha = [fu[0]], fu[1]
                        row.update(read_step=r["payload"]["step"], url=urls[0] if urls else None,
                                   read_sha256=sha)
                        if urls:
                            host = urls[0].split("/")[2]
                            path = "/" + urls[0].split("/", 3)[3] if urls[0].count("/") >= 3 else "/"
                            row["server_saw_read"] = any(a["host"] == host and a["path"] == path and a["sha256"] == row["read_sha256"] for a in access)
                prov_rows.append(row)
            # ---- 錯誤歸因
            for k in range(1, ncyc + 1):
                pre = parse_report(reports[sid][f"{arm}/{k - 1}"] if k > 1 else reports[sid]["c0"], s["claims"])
                post = parse_report(reports[sid][f"{arm}/{k}"], s["claims"])
                sc = rec.source_checks(bounds[k - 1], bounds[k])
                handed: set[int] = set(sc[0]["payload"]["affected_lines"]) if sc else set()
                sc_by_line = {e["line"]: e for e in (sc[0]["payload"]["claims"] if sc else [])}
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
                    page_url = next((u for u in fetched if u.endswith("/" + cl["source_page"])), None)
                    if pre[cid] is None:
                        seg = "claim line missing from the report (draft changed or dropped it)"
                    elif arm == "a":
                        seg = "not maintained (arm a)"
                    elif arm == "c":
                        e = sc_by_line.get(ln) or {}
                        src = (e.get("source") or {}).get("url")
                        if kind == "miss" and ln not in handed:
                            if src and not src.endswith("/" + cl["source_page"]):
                                seg = "provenance points to the wrong page (not handed to agent)"
                            elif not src:
                                seg = "provenance not recorded (and not handed — should not happen)"
                            else:
                                seg = "change not detected (source re-read said unchanged)"
                        elif kind == "miss":
                            seg = ("handed to agent, page not re-read" if not page_url else
                                   "handed to agent, page re-read, not corrected")
                        else:
                            seg = ("agent changed a line it was not handed" if ln not in handed else
                                   "agent changed a handed line wrongly")
                    else:
                        if kind == "miss":
                            seg = "page not re-read" if not page_url else "page re-read, not corrected"
                        else:
                            seg = "agent changed a correct value wrongly"
                    attr_rows.append({"set": sid, "arm": arm, "cycle": k, "claim": cid, "kind": kind, "segment": seg,
                                      "pre": pre[cid], "post": post[cid], "truth": t_new})
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
        d = prov_sum.setdefault(r["arm"], {"claims": 0, "write_step": 0, "read_step": 0, "server_saw_read": 0})
        d["claims"] += 1
        d["write_step"] += r["write_step"] is not None
        d["read_step"] += r["read_step"] is not None
        d["server_saw_read"] += bool(r["server_saw_read"])
    cov = {"claims": len(cov_rows), "with_source": sum(1 for r in cov_rows if r["url"]),
           "correct_page": sum(1 for r in cov_rows if r["correct_page"])}
    return {"scores": res, "attribution": attr_rows, "attribution_table": seg_table,
            "provenance": prov_rows, "provenance_summary": prov_sum, "coverage": cov, "coverage_rows": cov_rows,
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
    out = {k: res[k] for k in ("harness_match", "coverage", "provenance_summary", "attribution_table", "record_problems")}
    out["summary"] = res["scores"]["summary"]
    print(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True, default=str))
    return 0 if not mism else 3


if __name__ == "__main__":
    raise SystemExit(main())
