"""引用備份不准說謊（2026-08-06）。

紀律：**用過、引用過的東西，證據要在手上且可驗。** 這是把「不 pack ＝ 沒跑過」
那條實驗紀律套到文獻上。

促成這幾支判準的實際事故：文獻索引裡有一筆標著 `fulltext: true`、檔名寫著
`2019_Tallant_you-can-trust-the-ladder.pdf`，開檔一看是 Shaw et al. 2017 的
**結核桿菌抗藥性化學論文**。索引宣稱我們有那篇的全文，實際上沒有。若照著引用，
會憑空造出一條有出處、有檔案、但完全不存在的引證。

這幾支判準檢查的是**索引與磁碟一致**，不檢查 PDF 內容對不對——後者只有開檔核對
才知道，那件事寫在 `_引用備份/verification.jsonl`（人工逐字核對過的引文）。

參考文獻放在 iCloud，CI 上不會有；抓不到目錄就跳過，不要讓它變成假綠。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REF = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/專題/參考文獻"
BACKUP = REF / "_引用備份"

INDEX_FILES = [
    ("2026-08-06_agent信任", "index.json"),
    ("2026-08-06_信任定義", "index.json"),
    ("2026-08-06_信任定義", "index_add.json"),
    ("2026-08-06_人類運作邏輯", "index.json"),
]

pytestmark = pytest.mark.skipif(
    not REF.exists(), reason="參考文獻在 iCloud，本機沒掛載就跳過")


def _indexes():
    for folder, fname in INDEX_FILES:
        p = REF / folder / fname
        if p.exists():
            yield folder, fname, json.load(p.open()).get("items", [])


def test_fulltext_true_means_the_file_is_actually_there():
    """標了 fulltext 就必須真的有檔案。

    這是那次事故的直接判準：`tallant2019` 標 fulltext=true，指向的檔案是別篇論文。
    檔案存在檢查抓不到「內容是別篇」，但抓得到「改名或刪檔之後索引沒跟著改」——
    而那正是修正之後最可能復發的形態。
    """
    missing = []
    for folder, fname, items in _indexes():
        for it in items:
            if not it.get("fulltext"):
                continue
            rel = it.get("pdf_path")
            if not rel:
                missing.append(f"{folder}/{fname}::{it.get('id')} 標 fulltext 卻沒有 pdf_path")
                continue
            if not (REF / folder / rel).exists():
                missing.append(f"{folder}/{fname}::{it.get('id')} → 找不到 {rel}")
    assert not missing, "索引宣稱有全文但檔案不在：\n  " + "\n  ".join(missing)


def test_no_fulltext_entries_explain_themselves():
    """沒有全文的條目要說明為什麼。

    「沒有全文」與「還沒去拿」是兩件事，只有前者能支撐「這條只能靠二手」的說法。
    留白會讓下游以為只是漏做。
    """
    silent = []
    for folder, fname, items in _indexes():
        for it in items:
            if it.get("fulltext"):
                continue
            if not (it.get("fulltext_reason") or "").strip():
                # 標題本身若已寫明檔案內容錯誤，算是說明過了
                if "【檔案內容錯誤】" in (it.get("title") or ""):
                    continue
                silent.append(f"{folder}/{fname}::{it.get('id')}")
    assert not silent, "沒有全文卻沒說明原因：\n  " + "\n  ".join(silent)


@pytest.mark.skipif(not (BACKUP / "MANIFEST.json").exists(),
                    reason="尚未產生引用備份")
def test_manifest_covers_every_indexed_source():
    """每一筆索引到的文獻都要在備份清單裡——不論拿不拿得到全文。

    拿不到全文的那些**更需要**進清單：它們是最容易被當成「我們讀過」引用的一群。
    """
    man = json.load((BACKUP / "MANIFEST.json").open())
    covered = {(e["folder"], str(e["id"])) for e in man["entries"]}
    indexed = {(folder, str(it.get("id")))
               for folder, _f, items in _indexes() for it in items}
    gap = sorted(indexed - covered)
    assert not gap, f"這些文獻沒有進引用備份：{gap[:10]}（共 {len(gap)} 筆）"


@pytest.mark.skipif(not (BACKUP / "MANIFEST.json").exists(),
                    reason="尚未產生引用備份")
def test_fulltext_hashes_are_recorded():
    """全文條目要有 sha256。沒有雜湊就無從偵測檔案被換掉——
    而我們剛剛才發現過一個「檔名對、內容不對」的檔案。"""
    man = json.load((BACKUP / "MANIFEST.json").open())
    bad = [e["id"] for e in man["entries"]
           if e["證據"] == "A_全文" and not e.get("sha256")]
    assert not bad, f"全文條目缺 sha256：{bad[:10]}"


@pytest.mark.skipif(not (BACKUP / "verification.jsonl").exists(),
                    reason="尚未產生引用備份")
def test_verified_quotes_point_at_files_we_hold():
    """人工核對過的引文，出處檔必須在手上。

    二手轉引也算數——存的是「我們讀到那句話的地方」，那個檔案我們確實有；
    但條目的 method 必須寫明它是轉引，否則會被當成直接引自原件。
    """
    rows = [json.loads(l) for l in (BACKUP / "verification.jsonl").open() if l.strip()]
    assert rows, "verification.jsonl 是空的"
    for r in rows:
        assert r["存在"], f"{r['id']} 的出處檔不在：{r['pdf']}"
        assert r.get("sha256"), f"{r['id']} 沒有 sha256"
        if "via" in r["id"] or "轉引" in r.get("method", ""):
            assert "轉引" in r["method"], f"{r['id']} 是二手來源卻沒標明"
