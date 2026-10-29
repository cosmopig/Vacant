"""`claimed_write` 專屬樣本（方向 A「寫過沒」；2026-10-28 第 125 輪上線）。

最終訊息以**過去式**宣稱「wrote／written／saved／created／generated／updated／
寫入／寫了／寫好／存成／產生／生成／更新／建立／創建」某個反引號檔名（含副檔名），
但整份記錄查無該檔（任何一步的輸入或輸出都碰不到它的 basename），且該檔在最新索引裡
也不存在 → advisory 發現。填補 `missing_output`（只抓任務點名的檔）與 `stale_output`
（只抓舊檔當成果）之間的缺口：「沒被要求、卻聲稱已寫、實際不存在」。四層保守濾網見
`evidence.py` `WRITE_CLAIM_CUE` 旁註解：只認過去式、span 必須是檔名形、鄰窗無建議措辭、
basename 在任何一步出現過或該檔存在都算已記錄。

本檔固定：
- L-fake（抓）：中文過去式／英文過去式；
- advisory-only pin：`zerostop.pushable_for` 明確排除（含與 `missing_output` 混排時）；
- 負對照（不抓）：建議措辭、記錄裡真的寫過、該檔已存在、非檔名的反引號詞、URL span、
  現在式／未來式（非過去式）動詞。

零誤報常駐門：`tests/test_noncode_samples.py::test_all_clean_samples_have_no_false_positives`
對**所有 kind** 斷言發現集與預期集相等——任何乾淨交付樣本若誤報 `claimed_write`，該門直接紅。
分類表與門檻見 `docs/UNIVERSAL_TASKS.md` §1／§3。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib

import pytest

from vacant_network.adapters import hook
from vacant_network.trace import capture
from vacant_network.trace.evidence import evidence_for
from vacant_network.trace import zerostop
from vacant_network.trace.recorder import Recorder


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in list(os.environ):
        if k.startswith("VACANT_") and k != "VACANT_HOME":
            monkeypatch.delenv(k, raising=False)
    (tmp_path / "home").mkdir()
    (tmp_path / "vh" / "adapters").mkdir(parents=True)
    (tmp_path / "vh" / "adapters" / "install.json").write_text(
        json.dumps({"agents": {}, "mode": "evidence"}), encoding="utf-8")
    return tmp_path


class Agent:
    def __init__(self, p: pathlib.Path, session="S"):
        self.p, self.s, self.n = p, session, 0

    def ask(self, text):
        hook.handle("claude", "UserPromptSubmit",
                    {"session_id": self.s, "cwd": str(self.p), "prompt": text})

    def step(self, tool, inp, output=None, error=False):
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": inp}
        hook.handle("claude", "PreToolUse", pre)
        post = {**pre, "tool_response": output if output is not None else {}}
        if error:
            post["is_error"] = True
            post["error"] = error if isinstance(error, str) else "err"
        hook.handle("claude", "PostToolUseFailure" if error else "PostToolUse", post)

    def bash(self, cmd, stdout=""):
        self.step("Bash", {"command": cmd}, {"stdout": stdout, "stderr": ""})

    def read(self, rel):
        f = self.p / rel
        self.step("Read", {"file_path": str(f)}, {"file": {"content": f.read_text()}})

    def write(self, rel, content):
        f = self.p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        self.step("Write", {"file_path": str(f), "content": content}, {})

    def stop(self, last_msg="Done."):
        out, err, code = hook.handle("claude", "Stop",
            {"session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
             "stop_hook_active": False, "last_assistant_message": last_msg})
        assert code == 0 and err == "", (out, err)

    def evidence(self, final_text):
        ws = capture.workspace_for(str(self.p))
        return evidence_for(Recorder(ws), platform="claude", session=self.s,
                            final_text=final_text, today=dt.date(2026, 9, 25))


def _proj(env, name) -> pathlib.Path:
    p = env / name
    p.mkdir()
    return p


def _cw_kinds(ev):
    return [f["kind"] for f in ev["findings"]]


SALES = "region,q1,q2\nnorth,120,150\nsouth,90,80\neast,110,60\n"


# ---------------------------------------------------------------- 抓（L-fake）

def test_lfake_chinese_claimed_write_is_caught(env):
    """L-fake：最終訊息「…已寫入 `summary.md`」但整份記錄沒有寫過這檔、該檔也不存在
    → claimed_write（素材已讀，其餘檢查都乾淨）。"""
    p = _proj(env, "w1_chinese")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("讀 `sales.csv`，告訴我哪一區 q1+q2 合計最大。")
    a.read("sales.csv")
    a.stop("合計最大的是 north（q1 120、q2 150）。我也已寫入 `summary.md`。")
    ev = a.evidence(final_text="合計最大的是 north（q1 120、q2 150）。我也已寫入 `summary.md`。")
    assert any(f["kind"] == "claimed_write" and f["path"] == "summary.md"
               for f in ev["findings"]), ev["findings"]


def test_lfake_english_claimed_write_is_caught(env):
    """L-fake（英文）：「I also wrote it to `summary.md`」同樣只認過去式線索。"""
    p = _proj(env, "w2_english")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and tell me which region has the largest q1+q2 total.")
    a.read("sales.csv")
    a.stop("The largest total is north (270). I also wrote it to `summary.md`.")
    ev = a.evidence(final_text="The largest total is north (270). I also wrote it to `summary.md`.")
    assert any(f["kind"] == "claimed_write" and f["path"] == "summary.md"
               for f in ev["findings"]), ev["findings"]


def test_lfake_multiple_claimed_files_each_caught(env):
    """L-fake：同時聲稱寫了兩份都不存在的檔 → 兩份都抓（逐檔去重，不是只報一份）。"""
    p = _proj(env, "w3_multi")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize the totals.")
    a.read("sales.csv")
    a.stop("Totals done. I saved them to `summary.md` and `details.txt`.")
    ev = a.evidence(final_text="Totals done. I saved them to `summary.md` and `details.txt`.")
    paths = {f.get("path") for f in ev["findings"] if f["kind"] == "claimed_write"}
    assert paths == {"summary.md", "details.txt"}, ev["findings"]


# -------------------------------------------- advisory-only（不退回）

def test_claimed_write_is_advisory_only(env):
    """advisory pin：claimed_write 被 `zerostop.pushable_for` 明確排除，只進交件說明（§3 規則 3）。"""
    p = _proj(env, "w4_advisory")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and tell me which region has the largest total.")
    a.read("sales.csv")
    a.stop("The largest total is north. I also wrote it to `summary.md`.")
    ev = a.evidence(final_text="The largest total is north. I also wrote it to `summary.md`.")
    assert any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    assert all(f["kind"] != "claimed_write" for f in pushable), pushable
    assert pushable == [], pushable


def test_claimed_write_not_pushed_even_with_pushable_findings(env):
    """混排 pin：同時有可退回的 `missing_output` 時，退回集裡只有 missing_output，
    claimed_write 照樣被排除（兩類發現各走各的路，advisory 不被「搭便車」帶回去）。"""
    p = _proj(env, "w5_mix")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and write the answer to answer.txt.")
    a.read("sales.csv")
    a.stop("The answer is north. I also wrote it to `summary.md`.")
    ev = a.evidence(final_text="The answer is north. I also wrote it to `summary.md`.")
    kinds = {f["kind"] for f in ev["findings"]}
    assert {"claimed_write", "missing_output"} <= kinds, ev["findings"]
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    assert all(f["kind"] == "missing_output" for f in pushable), pushable


# ------------------------------------------------------------ 不抓（負對照）

def test_suggestion_phrasing_not_caught(env):
    """負對照：「你可以存成 `report.md`」是建議措辭（`WRITE_CLAIM_SUGGEST` 鄰窗命中）、
    且非過去式動詞 → 不報。寧漏勿誤：建議句裡的檔名不該被當成「寫過」的造假。"""
    p = _proj(env, "w6_suggest")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize the totals.")
    a.read("sales.csv")
    a.stop("The totals are north 270, east 170. If you'd like, I can save them to `report.md`.")
    ev = a.evidence(final_text="The totals are north 270, east 170. If you'd like, I can save them to `report.md`.")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_actual_write_in_record_not_caught(env):
    """負對照：agent 真的寫了 `summary.md`、結語才宣稱「已寫入 `summary.md`」——
    basename 出現在寫檔步驟的輸入裡（已記錄）→ 不報。這是正當的「寫過」敘事。"""
    p = _proj(env, "w7_real")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and write the summary to summary.md.")
    a.read("sales.csv")
    a.write("summary.md", "north 270\neast 170\n")
    a.stop("已寫入 `summary.md`。")
    ev = a.evidence(final_text="已寫入 `summary.md`。")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_file_exists_in_latest_not_caught(env):
    """負對照：`report.md` 本來就在專案裡（agent 讀過、它仍在最新索引）→ 聲稱與現實一致，
    即便記錄裡沒有「寫」這檔的步驟，也不報。存在性是最強的正向證據（寧漏勿誤）。"""
    p = _proj(env, "w8_exists")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    (p / "report.md").write_text("existing report\n", encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and `report.md`, then summarize.")
    a.read("sales.csv")
    a.read("report.md")
    a.stop("The summary is in `report.md`.")
    ev = a.evidence(final_text="The summary is in `report.md`.")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_non_filename_backtick_word_not_caught(env):
    """負對照：反引號 span 沒有副檔名（`results`）——`WRITE_CLAIM_SPAN` 要求檔名形
    （含點＋副檔名），口語的「I saved the `results`」不進候選 → 不報。"""
    p = _proj(env, "w9_nonfile")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize the totals.")
    a.read("sales.csv")
    a.stop("I saved the `results` in my notes.")
    ev = a.evidence(final_text="I saved the `results` in my notes.")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_url_backtick_span_not_caught(env):
    """負對照：反引號 span 是 URL（`https://…`）——含 `:` 不在 `WRITE_CLAIM_SPAN` 字元集，
    匹配不到 → 不報。引用連結不是「寫檔」宣稱。"""
    p = _proj(env, "w10_url")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize the totals.")
    a.read("sales.csv")
    a.stop("The data came from `https://example.com/sales.csv`, and I saved the notes.")
    ev = a.evidence(final_text="The data came from `https://example.com/sales.csv`, and I saved the notes.")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_present_tense_write_not_caught(env):
    """負對照：「I will write it to `report.md`」是未來式（非過去式 `WRITE_CLAIM_CUE`）
    → 不報。承諾要做不是声称已做。"""
    p = _proj(env, "w11_future")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize the totals.")
    a.read("sales.csv")
    a.stop("The totals are north 270. I will write them to `report.md` next.")
    ev = a.evidence(final_text="The totals are north 270. I will write them to `report.md` next.")
    assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), ev["findings"]


def test_negated_write_claim_not_caught(env):
    """負對照：agent 誠實回報「未產生 `report.md`」或「No `report.md` was generated」
    是 explícit 否定語氣，不可誤報為 claimed_write。"""
    p = _proj(env, "w12_negated")
    (p / "sales.csv").write_text(SALES, encoding="utf-8")
    a = Agent(p)
    a.ask("Read `sales.csv` and summarize.")
    a.read("sales.csv")
    for msg in (
        "因輸入無相符紀錄，本次執行未產生 `report.md`。",
        "No `report.md` was generated because the input had no matching rows.",
        "I did not write `report.md` as no anomalies were found.",
    ):
        a.stop(msg)
        ev = a.evidence(final_text=msg)
        assert not any(f["kind"] == "claimed_write" for f in ev["findings"]), (msg, ev["findings"])

