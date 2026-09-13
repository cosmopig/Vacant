#!/usr/bin/env python3
"""把 r454 的三條鏈組進 `examples/receipt_viewer_multiparty.html`（展件：三把金鑰的收據）。

這支在架構裡承重什麼（CLAUDE.md §展件可直接複用的、
DECISION_20260906_R454_FABLE_AUDIT_NAMED_DISSENT.md §三-4）：
R454 的指名結論只有在「別人拿得到三條鏈、而且真的能自己重算一次」時才是可究責的
證據。那一頁就是重算端；這一支是它的組裝器，而且**只做搬運與可重現的推導**——
展場那一頁上的每一個數字都由頁內 JS 從內嵌資料算出來，不是這裡算好貼進去的。

內嵌什麼（全部與 `ops/gain/replay/r454/` 底下的原檔逐位元組相同）：
  att_K{1,2,3}.book.json     三條完整的簽章鏈（1840／1840／1899 筆，共 5579 筆）
  pub_K{1,2,3}.json          三把公鑰（含**沒有進簽章**的平台字串）
  r454_exhibition_receipt.json  展出那一格（Mbpp/100 第 0 份）的歸檔收據
  r454_gauge.json            量具紀錄（哪一套驗收清單過了量具）

外加兩塊**推導**出來的對照表（不是原檔，所以標示得出來）：
  cand_map                「第幾份草稿」對照表。這個編號不在簽章裡，它是執行器
                          job 表上的位置（`peer_exec_real.build_jobs`：
                          sorted(task_id) × 候選索引）。從 att_K*.ndjson 讀，
                          並逐筆用 entry 的 hash 釘回鏈上那一筆才寫出來。
                          K3 的 1899 筆比 job 數多 59（自相矛盾格簽兩份），
                          光看鏈內容有 3 格分不出是哪一格——所以這張表必須外帶。
  single_key_reference    r446 單執行器那一次真跑的出貨 sha（`gate_code_sha256`），
                          以及歸檔分析腳本算出來的出貨結果，供頁面自我對照。
                          **不含任何隱藏測資推出來的欄位**（delivered_correct／
                          false_delivery 一律不進頁面）。

另外把 `examples/receipt_viewer.html` 的 CANON 區段整段複製過去：兩頁的正規化與
hash 佈局必須是同一份位元組，否則
`ops/gain/replay/receipt_viewer_node_check.mjs` 的 N1–N5b 只覆蓋得到其中一頁。

用法：
  .venv/bin/python ops/gain/replay/build_multiparty_viewer.py
  .venv/bin/python ops/gain/replay/build_multiparty_viewer.py --check   # 只檢查、不寫
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from vacant.canonical import canonical_bytes  # noqa: E402

R454 = REPO / "ops" / "gain" / "replay" / "r454"
VIEWER = REPO / "examples" / "receipt_viewer_multiparty.html"
SOURCE_VIEWER = REPO / "examples" / "receipt_viewer.html"

KEYS = ("K1", "K2", "K3")
CANON_BEGIN = "/* === CANON-BEGIN ==="
CANON_END = "/* === CANON-END === */"
CANON_COPY_BEGIN = "/* CANON-COPY-BEGIN"
CANON_COPY_END = "/* CANON-COPY-END */"

#: 內嵌區塊 id → 來源檔（None ＝ 推導出來的，不是原檔）。
BLOCKS: dict[str, str | None] = {
    "book-K1": "att_K1.book.json",
    "book-K2": "att_K2.book.json",
    "book-K3": "att_K3.book.json",
    "pub-K1": "pub_K1.json",
    "pub-K2": "pub_K2.json",
    "pub-K3": "pub_K3.json",
    "exhibition-receipt": "r454_exhibition_receipt.json",
    "gauge": "r454_gauge.json",
    "cand-map": None,
    "single-key-ref": None,
}


# --- 推導 -------------------------------------------------------------------

def _entry_hash(e: dict) -> str:
    core = {k: e[k] for k in
            ("stream_id", "branch_id", "seq", "prev_hash", "ts_ms", "type", "payload")}
    return hashlib.sha256(canonical_bytes(core)).hexdigest()


def cand_map() -> dict[str, str]:
    """每一把金鑰：鏈上第 i 筆 ↔ 「第幾份草稿」，一位數字一筆。

    來源是執行器自己寫的 `att_K*.ndjson`（**未簽章**的執行紀錄），但每一筆都用
    entry 的 hash 釘回 `att_K*.book.json` 上的同一筆才算數——ndjson 說謊會在這裡
    被抓到。cand_index 只有 0–4，所以一格一個字元。
    """
    out: dict[str, str] = {}
    for key in KEYS:
        rows = [json.loads(ln) for ln in
                (R454 / f"att_{key}.ndjson").read_text(encoding="utf-8").split("\n") if ln.strip()]
        book = [json.loads(ln) for ln in
                (R454 / f"att_{key}.book.json").read_text(encoding="utf-8").split("\n") if ln.strip()]
        digits: list[str] = []
        seq: list[dict] = []
        for r in rows:
            if "error" in r:
                raise SystemExit(f"{key} 的執行紀錄裡有錯誤格，不能組進展件：{r}")
            c = int(r["cand_index"])
            if not 0 <= c <= 9:
                raise SystemExit(f"{key} 的 cand_index 超出一位數：{c}")
            seq.append(r["entry"])
            digits.append(str(c))
            if "entry_equivocation" in r:
                seq.append(r["entry_equivocation"])
                digits.append(str(c))
        if len(seq) != len(book):
            raise SystemExit(f"{key}：ndjson 的 entry 數 {len(seq)} ≠ 鏈長 {len(book)}")
        for i, (a, b) in enumerate(zip(seq, book)):
            if _entry_hash(a) != _entry_hash(b):
                raise SystemExit(f"{key} 第 {i + 1} 筆：ndjson 的 entry 與鏈上那一筆對不上")
        out[key] = "".join(digits)
    return out


def single_key_reference() -> dict:
    """r446 單執行器的出貨 sha ＋ 歸檔分析腳本算出來的出貨結果（頁面拿來自我對照）。

    刻意**不搬**任何隱藏測資推出來的欄位：`delivered_correct`／`false_delivery`
    留在 `r454_result.json` 裡，不進展件。展件上唯一提到隱藏測資的地方是
    那一塊圍起來的「給觀眾的答案，機制看不到」，而且是靜態文字。
    """
    res = json.loads((R454 / "r454_result.json").read_text(encoding="utf-8"))
    tasks = {}
    for row in res["task_rows"]:
        tasks[row["task_id"]] = {
            "r446_runtime_sha256": row.get("runtime_sha"),
            "r446_accepted": bool(row.get("runtime_accepted")),
            "analysis_shipped_index": row.get("shipped_index"),
            "analysis_shipped_sha256": row.get("shipped_sha256"),
        }
    return {
        "note": "r446_* ＝ 只有一把金鑰的那一次真跑（runs/g_r446_eq5_mbpp 的 gate_code_sha256）；"
                "analysis_* ＝ ops/gain/replay/r454_named_dissent.py 這次算出來的出貨結果。"
                "兩者都不在這一頁驗得到的簽章鏈上，只拿來跟頁面自己重算的結果對照。",
        "quorum": res["quorum"],
        "k": res["k"],
        "tasks": tasks,
    }


def derived_block(block_id: str) -> str:
    if block_id == "cand-map":
        return json.dumps(cand_map(), ensure_ascii=False, sort_keys=True)
    if block_id == "single-key-ref":
        return json.dumps(single_key_reference(), ensure_ascii=False, sort_keys=True, indent=0)
    raise KeyError(block_id)


def expected_block(block_id: str) -> str:
    src = BLOCKS[block_id]
    if src is None:
        return derived_block(block_id)
    return (R454 / src).read_text(encoding="utf-8").strip("\n")


def expected_canon() -> str:
    html = SOURCE_VIEWER.read_text(encoding="utf-8")
    i, j = html.find(CANON_BEGIN), html.find(CANON_END)
    if i < 0 or j < 0:
        raise SystemExit("examples/receipt_viewer.html 裡找不到 CANON-BEGIN／CANON-END")
    return html[i:j + len(CANON_END)]


# --- 抽出 / 寫入 -------------------------------------------------------------

def extract_block(html: str, block_id: str) -> str:
    m = re.search(r'<script[^>]*id="%s"[^>]*>\n(.*?)\n</script>' % re.escape(block_id),
                  html, re.S)
    if not m:
        raise ValueError(f"頁面裡找不到 id={block_id} 的內嵌區塊")
    return m.group(1)


def extract_canon(html: str) -> str:
    i = html.find(CANON_COPY_BEGIN)
    j = html.find(CANON_COPY_END)
    if i < 0 or j < 0:
        raise ValueError("頁面裡找不到 CANON-COPY-BEGIN／CANON-COPY-END")
    i = html.index("\n", i) + 1
    return html[i:j].rstrip("\n")


def build(html: str) -> str:
    for block_id in BLOCKS:
        body = expected_block(block_id)
        pat = re.compile(r'(<script[^>]*id="%s"[^>]*>\n)(.*?)(\n</script>)'
                         % re.escape(block_id), re.S)
        if not pat.search(html):
            raise ValueError(f"頁面裡找不到 id={block_id} 的內嵌區塊")
        # repl 傳函式 ⇒ 回傳值原樣使用，不做 \1 這類反向引用展開（資料裡有反斜線）。
        html = pat.sub(lambda m: m.group(1) + body + m.group(3), html, count=1)
    i = html.find(CANON_COPY_BEGIN)
    j = html.find(CANON_COPY_END)
    if i < 0 or j < 0:
        raise ValueError("頁面裡找不到 CANON-COPY-BEGIN／CANON-COPY-END")
    i = html.index("\n", i) + 1
    return html[:i] + expected_canon() + "\n" + html[j:]


def check(html: str) -> list[str]:
    bad = []
    for block_id in BLOCKS:
        try:
            got = extract_block(html, block_id)
        except ValueError as exc:
            bad.append(str(exc))
            continue
        if got != expected_block(block_id):
            bad.append(f"{block_id}：內嵌內容與來源不同")
    try:
        if extract_canon(html) != expected_canon():
            bad.append("CANON 區段與 examples/receipt_viewer.html 不同")
    except ValueError as exc:
        bad.append(str(exc))
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="組裝／檢查 receipt_viewer_multiparty.html")
    ap.add_argument("--check", action="store_true", help="只檢查內嵌資料是否與來源相同")
    a = ap.parse_args(argv)
    html = VIEWER.read_text(encoding="utf-8")
    if a.check:
        bad = check(html)
        for b in bad:
            print("[BROKEN] " + b)
        print("總判定：%s（%d 個內嵌區塊）" % ("OK" if not bad else "BROKEN", len(BLOCKS)))
        return 0 if not bad else 1
    out = build(html)
    VIEWER.write_text(out, encoding="utf-8")
    n = len(out.encode("utf-8"))
    print("寫出 %s：%.2f MB" % (VIEWER.relative_to(REPO), n / 1024 / 1024))
    for block_id in BLOCKS:
        body = extract_block(out, block_id)
        print("  %-20s %9d bytes  %s"
              % (block_id, len(body.encode("utf-8")), BLOCKS[block_id] or "（推導）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
