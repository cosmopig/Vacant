"""引用備份：凡是用過、引用過的文獻，證據必須落盤可驗（2026-08-06）。

## 為什麼要有這支

專案對實驗資料的紀律是「不 pack ＝ 沒跑過」。文獻應該套同一條：**引用過的東西，
證據要在手上，而且要能被別人驗**。否則我們一邊要求自己的每個數字都指得出原始檔案，
一邊拿沒有存檔的二手引述去寫論文。

實際狀況是三種，這支把三種都存下來並標清楚差別：

  A 有全文 PDF        —— 記路徑與 sha256。最強。
  B 只有摘要          —— 付費牆／典藏點擋直連。抓 Crossref／Semantic Scholar 的
                          摘要落盤，記來源 URL 與抓取時間。**摘要不等於全文**，
                          任何據此下的論斷都要標。
  C 經二手來源轉引    —— 我們手上有 X 的全文，X 逐字引了 Y 並附頁碼。存的是
                          「我們讀到那句話的地方」，不是 Y 的原件。

還有第四種，掃描檔沒有文字層（Gambetta、Marsh）：機器擷取得到亂碼，必須渲染成
影像判讀。既然是用眼睛讀的，就把**當時讀的那一頁影像**存下來，否則沒有任何紀錄
證明我們真的看過。

## 輸出

  參考文獻/_引用備份/
    MANIFEST.json      每一筆引用 → 證據型別、路徑、sha256、抓取時間
    abstracts/{id}.json  B 類的摘要原始回應（含來源 URL）
    rendered/{f}_p{n}.png  掃描檔實際讀過的頁面
    verification.jsonl   我親自逐字核對過的引文：出處檔、sha256、核對方式

MANIFEST 的用途跟 _index/files.jsonl 一樣：後續 agent 用它判斷某條引用可不可信，
不必重新去猜我們到底看過什麼。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REF = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/專題/參考文獻"
OUT = REF / "_引用備份"
MAILTO = "cosmo20050801@gmail.com"

# 索引檔 → 它所在的目錄（pdf_path 是相對於該目錄）
INDEXES = [
    ("2026-08-06_agent信任", "index.json"),
    ("2026-08-06_信任定義", "index.json"),
    ("2026-08-06_信任定義", "index_add.json"),
    ("2026-08-06_人類運作邏輯", "index.json"),
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_json(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={
        "User-Agent": f"vacant-citation-archive/1.0 (mailto:{MAILTO})",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _openalex_abstract(work: dict) -> str | None:
    """OpenAlex 存的是倒排索引（詞 → 位置），還原成連續文字。"""
    inv = work.get("abstract_inverted_index")
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


def has_abstract(attempt: dict) -> bool:
    r = attempt.get("response") or {}
    if not isinstance(r, dict):
        return False
    return bool(r.get("abstract") or (r.get("tldr") or {}).get("text")
                or r.get("_abstract_reconstructed"))


def fetch_abstract(item: dict) -> dict | None:
    """抓摘要。Semantic Scholar → Crossref → OpenAlex，全部落盤。

    存的是**原始回應**不是我們整理過的版本——整理過的東西沒辦法讓別人重驗。

    三個都拿不到也要記下來：「查過但拿不到」跟「沒查過」是兩件事，而只有前者
    可以支撐「這條只能靠二手」的說法。Semantic Scholar 有時會明講
    `elided by the publisher`，那個訊息本身就是證據，要留著。
    """
    doi = (item.get("doi") or "").strip().removeprefix("https://doi.org/")
    tried: list[dict] = []

    if doi:
        s2 = (f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
              "?fields=title,abstract,year,venue,authors,externalIds,openAccessPdf,tldr")
        try:
            d = get_json(s2)
            tried.append({"source": "semanticscholar", "url": s2, "response": d})
            if d.get("abstract") or (d.get("tldr") or {}).get("text"):
                return {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "摘要取得": "semanticscholar", "attempts": tried}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            tried.append({"source": "semanticscholar", "url": s2, "error": str(e)})
        time.sleep(1.2)

        cr = f"https://api.crossref.org/works/{doi}?mailto={MAILTO}"
        try:
            d = get_json(cr)
            msg = d.get("message", d)
            tried.append({"source": "crossref", "url": cr, "response": msg})
            if msg.get("abstract"):
                return {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "摘要取得": "crossref", "attempts": tried}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            tried.append({"source": "crossref", "url": cr, "error": str(e)})
        time.sleep(1.2)

        oa = f"https://api.openalex.org/works/https://doi.org/{doi}?mailto={MAILTO}"
        try:
            d = get_json(oa)
            ab = _openalex_abstract(d)
            d.pop("abstract_inverted_index", None)   # 倒排索引很長，只留還原後的
            if ab:
                d["_abstract_reconstructed"] = ab
            tried.append({"source": "openalex", "url": oa, "response": d})
            if ab:
                return {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "摘要取得": "openalex", "attempts": tried}
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            tried.append({"source": "openalex", "url": oa, "error": str(e)})
        time.sleep(1.2)

    if not doi:
        # 沒有 DOI 就用標題查，命中要人工核對，所以標記出來
        q = urllib.parse.quote(item.get("title", "")[:180])
        s2t = (f"https://api.semanticscholar.org/graph/v1/paper/search?query={q}&limit=3"
               "&fields=title,abstract,year,venue,authors,externalIds,tldr")
        try:
            d = get_json(s2t)
            tried.append({"source": "semanticscholar_title_search", "url": s2t,
                          "response": d, "警告": "以標題查得，需人工核對是否同一篇"})
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            tried.append({"source": "semanticscholar_title_search", "url": s2t, "error": str(e)})
        time.sleep(1.2)

    if not tried:
        return None
    got = next((a["source"] for a in tried if has_abstract(a)), None)
    note = None
    if not got:
        blob = json.dumps(tried, ensure_ascii=False)
        note = ("出版社遮蔽摘要（Semantic Scholar 明示 elided by the publisher）"
                if "elided by the publisher" in blob
                else "三個開放索引都查過，均無摘要可取")
    return {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "摘要取得": got or "無", "取不到的原因": note, "attempts": tried}


def render_page(pdf: Path, page: int, dest_stem: Path) -> Path | None:
    """把掃描檔的某一頁渲染成 PNG——沒有文字層的東西是用眼睛讀的，
    就要留下當時讀的那張影像，否則沒有紀錄證明我們看過。"""
    try:
        subprocess.run(["pdftoppm", "-r", "130", "-png", "-f", str(page), "-l", str(page),
                        str(pdf), str(dest_stem)], check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    hits = sorted(dest_stem.parent.glob(f"{dest_stem.name}-*.png"))
    return hits[0] if hits else None


# 實際讀過、但只存在於網頁上的來源。沒有 PDF 不代表可以不存檔——
# 網頁會改會消失，而我們引用的是「當時讀到的那個版本」。
WEB_READS = [
    {
        "id": "mcleod_sep",
        "url": "https://plato.stanford.edu/entries/trust/",
        "title": "Trust (Stanford Encyclopedia of Philosophy)",
        "為什麼讀它": "Baier 1986《Trust and Antitrust》原文在 JSTOR 付費牆後，"
                      "其信任定義與『背叛測試』是經由這一條 OA 條目逐字取得的。"
                      "引用 Baier 時必須標明轉引自此。",
    },
]

# 沒有文字層、實際靠渲染影像讀過的頁面：(目錄, 檔名, PDF 頁碼, 讀它是為了什麼)
RENDERED_READS = [
    ("2026-08-06_信任定義", "1988_Gambetta_can-we-trust-trust.pdf", 5,
     "書頁 p.217 的信任定義。before／and 兩處斜體在原文紙面上，二手引用通常略掉。"),
]

# 我親自逐字核對過的引文。存下來是因為「agent 說它讀到」與「我自己開檔看到」
# 是兩種不同強度的證據，而下游只看得到結論。
VERIFIED_QUOTES = [
    {
        "id": "srivatsa2005",
        "dir": "2026-08-06_agent信任",
        "pdf": "pdf/2005_Srivatsa_trustguard-strategic-oscillation.pdf",
        "quote": "Or it could oscillate between building and milking reputation.",
        "method": "pdftotext 全文擷取後 grep -i oscillat，命中原文 §2 第 139 行",
        "用在哪": "脈衝攻擊不是本專題提出的——這句話是主要依據",
    },
    {
        "id": "kim2025",
        "dir": "2026-08-06_agent信任",
        "pdf": "pdf/2025_Kim_correlated-errors-in-llms.pdf",
        "quote": "models agree 60% of the time when both models err",
        "method": "pdftotext 擷取摘要段；另核對內文 0.602 與 HuggingFace 0.423 / 隨機 0.127",
        "用在哪": "推翻「盲區沒有外生錨定」",
    },
    {
        "id": "krumdick2025",
        "dir": "2026-08-06_agent信任",
        "pdf": "pdf/2025_Krumdick_no-free-labels-llm-judge.pdf",
        "quote": "the Cohen's κ decreases from 0.86 to 0.16 in the pairwise case "
                 "on questions GPT-4o could not answer",
        "method": "pdftotext 擷取後 grep 0.86/0.16，命中內文第 473 行與表格 0.86±0.02 / 0.16±0.08",
        "用在哪": "盲區不是常數，集中在評審自己也不會做的題目上",
    },
    {
        "id": "begin2026",
        "dir": "2026-08-06_agent信任",
        "pdf": "pdf/2026_Begin_preference-optimization-monoculture-prediction-markets.pdf",
        "quote": "of ρ = 0.70 and reducing ten agents to the effective forecasting power "
                 "of ≈1.4 independent",
        "method": "pdftotext 擷取後 grep，另核對內文 Neff = 1.38 與表格 1.38 [1.36, 1.40]",
        "用在哪": "同源評審的有效獨立數",
    },
    {
        "id": "gambetta1988",
        "dir": "2026-08-06_信任定義",
        "pdf": "pdf/1988_Gambetta_can-we-trust-trust.pdf",
        "quote": "both before he can monitor such action (or independently of his capacity "
                 "ever to be able to monitor it) and in a context in which it affects his own action",
        "method": "PDF 無文字層（pdftotext 得 0 字元），以 pdftoppm 渲染 p.5（書頁 217）"
                  "為影像後判讀；影像存於 rendered/",
        "用在哪": "信任的經典定義把「不依賴監督」寫進必要條件，而監督正是 Vacant 的全部價值",
    },
    {
        "id": "mayer1995_via_koerber2018",
        "dir": "2026-08-06_信任定義",
        "pdf": "pdf/2018_Koerber_questionnaire-trust-in-automation.pdf",
        "quote": "irrespective of the ability to monitor or control that other party. "
                 "(Mayer et al., 1995, p. 712)",
        "method": "**二手轉引**。Mayer 1995 原件在 AMR 付費牆後，未取得。"
                  "此處核對的是 Körber 2018 全文第 110 行的逐字引述（附原文頁碼 p.712）。",
        "用在哪": "同上。引用時必須標明轉引，不可寫成直接引自 AMR",
    },
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "abstracts").mkdir(exist_ok=True)
    (OUT / "rendered").mkdir(exist_ok=True)

    entries: list[dict] = []
    seen: set[str] = set()

    for folder, fname in INDEXES:
        idx = REF / folder / fname
        if not idx.exists():
            print(f"  跳過（不存在）：{folder}/{fname}")
            continue
        items = json.load(idx.open()).get("items", [])
        for it in items:
            key = f"{folder}::{it.get('id')}"
            if key in seen:
                continue
            seen.add(key)
            rec: dict[str, Any] = {
                "id": it.get("id"), "folder": folder, "title": it.get("title"),
                "year": it.get("year"), "doi": it.get("doi") or None,
            }
            pdf_rel = it.get("pdf_path")
            pdf = (REF / folder / pdf_rel).resolve() if pdf_rel else None
            if it.get("fulltext") and pdf and pdf.exists():
                rec |= {"證據": "A_全文", "path": str(pdf.relative_to(REF)),
                        "bytes": pdf.stat().st_size, "sha256": sha256(pdf)}
            else:
                rec |= {"證據": "B_僅摘要",
                        "原因": it.get("fulltext_reason") or "索引未標 fulltext"}
            entries.append(rec)

    # B 類：把摘要抓下來落盤
    todo = [e for e in entries if e["證據"] == "B_僅摘要"]
    print(f"需要補摘要備份：{len(todo)} 筆")
    for i, e in enumerate(todo, 1):
        dest = OUT / "abstracts" / f"{e['folder']}__{e['id']}.json"
        if dest.exists():
            e["abstract_path"] = str(dest.relative_to(REF))
            e["sha256"] = sha256(dest)
            continue
        src = {k: e.get(k) for k in ("id", "title", "year", "doi")}
        got = fetch_abstract(src)
        if got:
            got["索引項"] = src
            dest.write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
            e["abstract_path"] = str(dest.relative_to(REF))
            e["sha256"] = sha256(dest)
            print(f"  [{i}/{len(todo)}] {e['id']}")
        else:
            e["abstract_path"] = None
            print(f"  [{i}/{len(todo)}] {e['id']} —— 抓不到，留白")

    # 網頁來源：存當時讀到的那個版本
    webs = []
    for w in WEB_READS:
        dest = OUT / "web" / f"{w['id']}.html"
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            try:
                req = urllib.request.Request(w["url"], headers={
                    "User-Agent": f"vacant-citation-archive/1.0 (mailto:{MAILTO})"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    dest.write_bytes(r.read())
                print(f"  網頁存檔：{w['id']}")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                print(f"  網頁存檔失敗：{w['id']} —— {e}")
        if dest.exists():
            webs.append({**w, "path": str(dest.relative_to(REF)),
                         "bytes": dest.stat().st_size, "sha256": sha256(dest),
                         "retrieved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})

    # 掃描檔：把實際讀過的頁面渲染存檔
    rendered = []
    for folder, name, page, why in RENDERED_READS:
        pdf = REF / folder / "pdf" / name
        if not pdf.exists():
            continue
        stem = OUT / "rendered" / f"{Path(name).stem}_p{page}"
        png = render_page(pdf, page, stem)
        if png:
            rendered.append({"pdf": f"{folder}/pdf/{name}", "page": page, "為什麼讀它": why,
                             "png": str(png.relative_to(REF)), "sha256": sha256(png)})
            print(f"  渲染存檔：{name} p{page}")

    # 我親自核對過的引文
    ver = []
    for q in VERIFIED_QUOTES:
        pdf = REF / q["dir"] / q["pdf"]
        ver.append({**{k: v for k, v in q.items() if k != "dir"},
                    "pdf": f"{q['dir']}/{q['pdf']}",
                    "存在": pdf.exists(),
                    "sha256": sha256(pdf) if pdf.exists() else None})
    (OUT / "verification.jsonl").write_text(
        "\n".join(json.dumps(v, ensure_ascii=False) for v in ver) + "\n", encoding="utf-8")

    # 回填 fulltext_reason：「沒有全文」與「還沒去拿」是兩件事，只有前者能支撐
    # 「這條只能靠二手」。理由不是編的——它來自上面真的打過的那幾支 API，
    # 原始回應留在 abstracts/ 裡可以重驗。
    by_key = {(e["folder"], str(e["id"])): e for e in entries}
    for folder, fname in INDEXES:
        idx = REF / folder / fname
        if not idx.exists():
            continue
        doc = json.load(idx.open())
        changed = 0
        for it in doc.get("items", []):
            if it.get("fulltext") or (it.get("fulltext_reason") or "").strip():
                continue
            if "【檔案內容錯誤】" in (it.get("title") or ""):
                continue
            e = by_key.get((folder, str(it.get("id"))))
            ap = e.get("abstract_path") if e else None
            if not ap:
                continue
            got = json.loads((REF / ap).read_text())
            src, why = got.get("摘要取得"), got.get("取不到的原因")
            it["fulltext_reason"] = (
                f"本輪未取得全文。{why}（查詢紀錄：{ap}）" if src in (None, "無")
                else f"本輪未取得全文；摘要已備份，來源 {src}（查詢紀錄：{ap}）。"
                     "摘要不等於全文，據此下的論斷須標明。")
            changed += 1
        if changed:
            idx.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  回填 {folder}/{fname}：{changed} 筆 fulltext_reason")

    n_a = sum(1 for e in entries if e["證據"] == "A_全文")
    n_b = len(entries) - n_a
    manifest = {
        "note": "凡是用過、引用過的文獻，證據要在手上且可驗。證據分三級："
                "A_全文（PDF 在手，最強）、B_僅摘要（付費牆，摘要落盤，**不等於全文**，"
                "據此下的論斷必須標明）、以及 verification.jsonl 裡經人工逐字核對的引文。"
                "二手轉引另外標明——存的是我們讀到那句話的地方，不是原件。",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "counts": {"總計": len(entries), "A_全文": n_a, "B_僅摘要": n_b,
                   "人工核對引文": len(ver), "渲染存檔頁": len(rendered),
                   "網頁存檔": len(webs)},
        "渲染讀取": rendered,
        "網頁來源": webs,
        "entries": sorted(entries, key=lambda e: (e["folder"], str(e["id"]))),
    }
    (OUT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n→ {OUT}")
    print(f"  總計 {len(entries)} 筆：全文 {n_a}、僅摘要 {n_b}")
    print(f"  人工核對引文 {len(ver)} 條、渲染存檔 {len(rendered)} 頁")


if __name__ == "__main__":
    main()
