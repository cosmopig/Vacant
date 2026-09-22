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


@pytest.fixture(autouse=True)
def _need_the_evidence_on_disk(request):
    """證據讀不到 ⇒ **跳過並講清楚**，不准紅成「引用壞了」。

    ⚠ 原本的 skip 只看 `REF.exists()`。iCloud 目錄在、檔案是 dataless 的時候
      它放行，然後 `json.load` 炸掉——而那個紅的意思會被讀成
      「索引與磁碟不一致」，完全是另一件事。
      2026-09-22 就這樣紅了三條。
    """
    # ⚠ 分辨器自己的單元測試**不需要**那些證據——它們用 tmp_path 造假檔。
    #    不豁免的話它們會跟著被跳過：看起來沒紅、其實沒跑。
    #    （2026-09-22 加完測試第一次跑就踩到，7 條全 skip。）
    if request.node.get_closest_marker("no_evidence_needed"):
        return
    if reasons := _dataless_reasons():
        pytest.skip("沒量到（不是不合格）：證據沒有下載到這台機器 ⇒ "
                    + "；".join(reasons)
                    + "。抓下來：`brctl download <路徑>` 或在 Finder 裡打開它。")


def _dataless(p: Path) -> str | None:
    """這個檔是不是 iCloud 的 **dataless** 檔？是的話回一句人看得懂的理由。

    🔴 **`exists()` 與 `st_size` 都會騙人。** 2026-09-22 實測四個索引檔：

        p.exists()       → True
        st_size          → 99331
        st_blocks        → 0          ← 本機沒有資料
        read_bytes()     → b""        ← **回空的而且不報錯**

    不分辨的話 `json.load` 會在第一個字元就炸，這幾支測試紅成
    「引用備份壞了」——而真相是**這台機器讀不到那份證據**。
    那是三態鐵律在檔案系統上的樣子：**沒量到 ≠ 壞掉**。

    ⚠ 判準用 `read_bytes()` 的長度不是只看 `st_blocks`：
      下載到一半也可能 `st_blocks > 0` 而內容不完整。讀到多少才算數。
    """
    st = p.stat()
    if p.read_bytes():
        return None
    return (f"{p.parent.name}/{p.name} 是 iCloud dataless 檔"
            f"（st_size={st.st_size}、st_blocks={st.st_blocks}、實際讀到 0 bytes）")


def _dataless_reasons() -> list[str]:
    """所有讀不到的索引。**有任何一個就要整組跳過**——
    只讀到一半的索引會讓「manifest 涵蓋每一筆」這種判準空洞地通過。"""
    out = []
    for folder, fname in INDEX_FILES:
        p = REF / folder / fname
        if p.exists() and (r := _dataless(p)):
            out.append(r)
    if (BACKUP / "MANIFEST.json").exists() and (r := _dataless(BACKUP / "MANIFEST.json")):
        out.append(r)
    return out


def _indexes():
    for folder, fname in INDEX_FILES:
        p = REF / folder / fname
        if p.exists():
            raw = p.read_bytes()
            # 走到這裡表示上面的 skip 沒擋住 ⇒ 有內容。空的要炸得看得懂，
            # 不要讓它變成一句 "Expecting value: line 1 column 1"。
            assert raw, f"{p} 讀到空的——應該已經被 dataless 檢查擋下來了"
            yield folder, fname, json.loads(raw).get("items", [])


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


# ---------------------------------------------------------------------------
# 分辨器自己要被釘住：它是「紅」與「跳過」的分水嶺
# ---------------------------------------------------------------------------

@pytest.mark.no_evidence_needed
def test_dataless_分得出_讀不到_與_內容壞掉(tmp_path):
    """空的 ⇒ 沒量到（跳過）；有內容但不是 JSON ⇒ **壞掉（要紅）**。

    🔴 這兩者混在一起就是這批修正要解決的問題本身。分不出來的話，
      一個真的壞掉的索引會被當成「iCloud 沒下載」靜靜跳過——
      那比原本紅錯原因更糟。
    """
    empty = tmp_path / "empty.json"
    empty.write_bytes(b"")
    assert _dataless(empty) is not None, "空檔案沒被認出來 ⇒ 會拿去 json.load 炸掉"
    assert "dataless" in _dataless(empty)

    broken = tmp_path / "broken.json"
    broken.write_text("{ 這不是 JSON", encoding="utf-8")
    assert _dataless(broken) is None, (
        "有內容卻被當成『沒下載』⇒ 真的壞掉的索引會被靜靜跳過")

    good = tmp_path / "good.json"
    good.write_text('{"items": []}', encoding="utf-8")
    assert _dataless(good) is None


@pytest.mark.no_evidence_needed
def test_dataless_的理由要指得出是哪一個檔(tmp_path):
    """只說「讀不到」不夠——展場／稽核當天要知道去 download 哪一個。"""
    p = tmp_path / "某某索引" / "index.json"
    p.parent.mkdir()
    p.write_bytes(b"")
    r = _dataless(p)
    assert "某某索引/index.json" in r, r
    assert "st_size" in r and "st_blocks" in r, "沒有帶出判斷依據：" + r
