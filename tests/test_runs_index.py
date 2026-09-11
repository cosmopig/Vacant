"""`ops/gain/build_runs_index.py` 的釘樁測試（round457）。

這支在架構裡承重什麼：索引的全部價值在於它不會說謊。產生器改壞了不會噴錯，
它會照樣吐出一份看起來很合理的 JSON——所以要用**手工核對過的事實**把它釘住。

釘四件事，每一件都對應一種具體的壞法：

  1. `50 個目錄有 summary.json`         ← 掃描範圍縮水／擴張（分類邏輯漂掉）
  2. `g_r449c_eq5_lcb3` 的 `n_rows` 189 ← 行數統計壞掉（例如把 header 算進去）
  3. `lcb_bank_v2` 120 題               ← 題庫解析壞掉／指到錯的檔
  4. 索引裡不含 MBPP+ 的任何位元組      ← **私有資料外洩**（最嚴重的一種）

第 4 條是 CLAUDE.md 的資料紀律：`.vacant-private/` 是不轉散布的官方包，
索引只准記路徑字串與 `vacant/codebench.py` 裡的 sha256 釘值。

另外釘「冪等」：同一份資料重跑兩次必須逐位元組相同，否則 `--check` 這個
迴歸機制本身就是壞的。
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("ops.gain.build_runs_index")
from ops.gain.build_runs_index import (  # noqa: E402
    _opening_of, build_index, main, render_md)


@pytest.fixture(scope="module")
def idx() -> dict:
    return build_index()


def test_dirs_with_summary_json_is_50(idx):
    """HEAD 有 50 個 run 目錄帶 summary.json（2026-09-11 重建索引時點過）。

    這個數字會隨新 run 落盤而增加——變了就更新這裡，但**要先確認是真的多了
    一個 run**，而不是分類邏輯把別的東西算進來了。

    44 → 50 的那六個是 R460 的 harness 六塊（`g_r460_harness_lcb2_{a1..b3}`）：
    它們在 2026-09-08／09 落盤，而索引一直停在 2026-09-07 的點數
    ⇒ `build_runs_index.py --check` 從那時起就是紅的（R529 v1 §九-5 記的已知未償）。
    2026-09-11 重跑產生器補上，逐塊核對過是真的多了六個 run 而不是分類漂掉。
    """
    assert idx["counts"]["dirs_with_summary_json"] == 50
    counted = sum(1 for r in idx["runs"]
                  if any(f["name"] == "summary.json" for f in r["files"]))
    assert counted == 50
    names = {r["name"] for r in idx["runs"]}
    assert {f"g_r460_harness_lcb2_{t}" for t in ("a1", "a2", "a3", "b1", "b2", "b3")} <= names


def test_r449c_n_rows_is_189(idx):
    """`g_r449c_eq5_lcb3` 是單臂（EQ5）、lcb v3 189 題，所以列數＝題數＝189。"""
    r = next(x for x in idx["runs"] if x["name"] == "g_r449c_eq5_lcb3")
    assert r["n_rows"] == 189
    assert r["n_distinct_task_ids"] == 189
    assert r["n_rows_by_arm"] == {"EQ5": 189}
    assert r["kind"] == "real_run"
    assert r["bank"]["family"] == "lcb"
    assert r["bank"]["version"] == "v3"
    assert r["bank"]["match"] == "exact"


def test_lcb_bank_v2_has_120_tasks(idx):
    """v2＝v1 的 91 題 ＋ test4 視窗新增 29 題。sha256 也要對得上釘值。"""
    v2 = idx["banks"]["lcb"]["v2"]
    assert v2["n_tasks"] == 120
    assert v2["n_tasks_pin_in_codebench"] == 120
    assert v2["sha256_matches_pin"] is True
    # v1 ⊂ v2，而 v3 與 v2 零交集——這兩條關係是「樣本外複製」宣稱的前提。
    assert idx["banks"]["lcb_relations"]["v1_subset_of_v2"] is True
    assert idx["banks"]["lcb_relations"]["v2_v3_overlap"] == 0


def test_no_private_evalplus_bytes_in_index(idx, tmp_path):
    """索引裡只准出現 MBPP+ 的路徑與釘值，不准出現題目內容。

    做法：把整份索引序列化，確認 (a) 私有包的實測 sha256 不在裡面
    （只准有 codebench.py 的釘值字串，兩者相同時這一條靠 b/c 把關）、
    (b) 沒有任何 `mbppplus_` 開頭的題目文字被夾帶進來、
    (c) 私有檔的位元組長度不等於任何被索引檔案的長度紀錄。
    """
    blob = json.dumps(idx, ensure_ascii=False)
    mp = idx["banks"]["mbpp_plus"]
    assert mp["private"] is True
    assert mp["redistributed"] is False
    assert mp["path"] == ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
    assert mp["n_tasks_pin_in_codebench"] == 378

    # 索引不得包含任何 .vacant-private/ 底下的**檔案條目**（只准有那一行路徑字串）。
    for r in idx["runs"]:
        for f in r["files"]:
            assert ".vacant-private" not in f["name"]
    assert ".vacant-private" not in json.dumps(idx["top_level_files"])

    # 題目內容的指紋：MBPP+ 的題目 prompt 一定含 "assert"；索引不該有整段題幹。
    assert "\\ndef " not in blob or blob.count("\\ndef ") < 5, \
        "索引裡出現了疑似程式碼題幹——檢查有沒有把題庫內容讀進來"

    # 就算私有包在本機存在，索引也不准去算它的內容雜湊當成資料。
    priv = ROOT / mp["path"]
    if priv.exists():
        import hashlib
        real = hashlib.sha256(priv.read_bytes()).hexdigest()
        # 釘值本來就等於實測值；要防的是「索引把整包讀進來當檔案條目」。
        assert real == mp["sha256_pin_in_codebench"]
        assert str(priv.stat().st_size) not in json.dumps(
            [f for r in idx["runs"] for f in r["files"]])


def test_idempotent_and_check_mode(tmp_path, idx):
    """同資料重跑必須逐位元組相同，且 `--check` 對剛寫好的輸出要回 0。"""
    out = tmp_path / "idx"
    assert main(["--out", str(out)]) == 0
    j1 = (out / "INDEX.json").read_text()
    m1 = (out / "INDEX.md").read_text()
    assert main(["--out", str(out)]) == 0
    assert (out / "INDEX.json").read_text() == j1
    assert (out / "INDEX.md").read_text() == m1
    assert main(["--check", "--out", str(out)]) == 0

    # 動一個位元組就要被抓到——`--check` 有沒有牙齒。
    (out / "INDEX.md").write_text(m1 + "\n篡改\n")
    assert main(["--check", "--out", str(out)]) == 1


def test_headline_must_be_about_this_run(idx):
    """headline 只能來自「宣告區點名這個 run」的裁決檔——round457 稽核抓到的錯。

    首版把 `g_r444_conform_mbpp` 配到 `DECISION_20260904_R440T_E3_WRAPUP.md`，
    但那是 r443／E3 的收官，第 84 行只寫了一句「若 CONFORM 實跑顯示…」的前瞻
    假設。**被順帶提到不等於被裁決。** 這支釘住修好後的行為：

      - r444 沒有專屬裁決 ⇒ headline 是 None、`no_settlement_decision`，
        併庫收官改列 related_settlements（不硬配）。
      - r445 的 headline 是它自己的獨立稽核，不是併庫收官。
      - 每一個有 headline 的 run，其來源檔的宣告區或標題一定點名了它。
    """
    by = {r["name"]: r for r in idx["runs"]}

    r444 = by["g_r444_conform_mbpp"]
    assert r444["headline"] is None
    assert r444["headline_from"] is None
    assert r444["headline_source"] == "no_settlement_decision"
    assert r444["related_settlements"] == [
        "CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md"]
    assert "E3_WRAPUP" not in json.dumps(
        [r444["headline_from"], r444["related_settlements"]])

    assert (by["g_r445_conform_mbpp_ext"]["headline_from"]
            == "DECISION_20260904_R440X_R445_INDEPENDENT_AUDIT.md")
    assert (by["g_r449_eq5_lcb2"]["headline_from"]
            == "DECISION_20260906_R449B_FABLE_AUDIT_REPLICATED_ON_HARD.md")
    assert (by["g_r441_gemma_only_mbpp_b"]["headline_from"]
            == "DECISION_20260902_R516_E1_FINAL_WRAPUP.md")

    # 通則：有 headline 就必須真的被那份文件點名（標題或宣告區）。
    for r in idx["runs"]:
        src = r["headline_from"]
        if not src:
            assert r["headline"] is None, r["name"]
            continue
        text = (ROOT / src).read_text()
        opening = _opening_of(text)
        assert r["name"] in opening, f"{r['name']} 的 headline 來源沒點名它：{src}"
        assert r["headline"] == next(
            ln.lstrip("#").strip() for ln in text.splitlines() if ln.strip()), \
            f"{r['name']} 的 headline 不是該檔標題的逐字複製"


def test_prereg_is_never_a_verdict(idx):
    """PREREG／CRITERION 是量測**之前**寫的判準，不准被當成裁決。

    混進來就會讓索引把「我們打算怎麼判」講成「判決是什麼」。
    """
    for r in idx["runs"]:
        for rel in r["verdict_decisions"] + [r["headline_from"] or ""]:
            assert "PREREG" not in rel.upper(), (r["name"], rel)
            assert not rel.startswith("CRITERION"), (r["name"], rel)


def test_analysis_dirs_are_not_evidence(idx):
    """`_analysis_*` 一律歸 analysis，且沒有一個被誤判成 real_run。"""
    for r in idx["runs"]:
        if r["name"].startswith(("_analysis", "analysis_")):
            assert r["kind"] == "analysis", r["name"]
    assert idx["counts"]["by_kind"]["analysis"] >= 130
    reals = {r["name"] for r in idx["runs"] if r["kind"] == "real_run"}
    assert not any(n.startswith(("_analysis", "analysis_")) for n in reals)


def test_md_is_rendered_from_the_same_index(idx):
    """人讀版必須由同一份 dict 產生，且把「不是證據」那句話寫出來。"""
    md = render_md(idx)
    assert "衍生物，不是證據" in md
    assert "不轉散布" in md
    assert "g_r449c_eq5_lcb3" in md
    # 索引不准比資料樂觀：沒被稽核的 run 要有自己的一節。
    assert "跑完但沒被獨立稽核的 run" in md


def test_generator_runs_as_a_script(tmp_path):
    """真的用子行程跑一次——import 路徑壞掉時單元測試看不出來。"""
    out = tmp_path / "cli"
    r = subprocess.run(
        [sys.executable, str(ROOT / "ops/gain/build_runs_index.py"),
         "--out", str(out)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    assert r.returncode == 0, r.stderr
    data = json.loads((out / "INDEX.json").read_text())
    assert data["counts"]["dirs_with_summary_json"] == 50
