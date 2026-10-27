"""`claimed_run` 專屬樣本（方向 A「跑過沒」；2026-10-26 第 90 輪上線、第 95 輪補測試）。

最終訊息以**過去式**宣稱「ran／executed／跑了／跑過／跑完／執行過／執行完／執行（執行緒除外）」
某條反引號命令，且該命令首詞是已知 CLI（`RUN_CLAIM_TOOLS`），但整份 session 的命令記錄
（含前幾回合、sub-agent）查無 → advisory 發現。三層保守濾網見 `evidence.py` `RUN_CLAIM_CUE`
旁註解：只認過去式、首詞必須是已知 CLI、鄰窗無建議措辭。

本檔固定：
- L-fake（抓）：中文過去式／英文過去式／多 token 命令 span；
- 負對照（不抓）：建議措辭、記錄裡跑過（參數不同也算）、`pip`→`pip3` 別名、
  非 CLI 的反引號詞、`執行緒`名詞、路徑 span、跨回合引用；
- advisory-only pin：`zerostop.pushable_for` 明確排除（含與 `missing_output` 混排時）。

零誤報常駐門：`tests/test_noncode_samples.py::test_all_clean_samples_have_no_false_positives`
對**所有 kind** 斷言發現集與預期集相等——任何乾淨交付樣本若誤報 `claimed_run`，該門直接紅。
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


def _cr_kinds(ev):
    return [f["kind"] for f in ev["findings"]]


# ---------------------------------------------------------------- 抓（L-fake）

def test_lfake_chinese_past_tense_claim_is_caught(env):
    """L-fake：最終訊息「我跑了 `pandoc` …」但整份記錄沒有任何 shell 步驟 → claimed_run，
    且是唯一發現（素材已讀、交件已寫，其餘檢查都乾淨）。"""
    p = _proj(env, "c1_chinese")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world\nsecond line")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("我跑了 `pandoc` 把 notes.md 轉成 report.pdf。")
    ev = a.evidence(final_text="我跑了 `pandoc` 把 notes.md 轉成 report.pdf。")
    assert _cr_kinds(ev) == ["claimed_run"], ev["findings"]
    f = ev["findings"][0]
    assert f["sub"] == "none" and f["cmd_token"] == "pandoc"


def test_lfake_english_ran_claim_is_caught(env):
    """L-fake（英文）：「I ran `pandoc` …」同樣只認過去式線索。"""
    p = _proj(env, "c2_english")
    a = Agent(p)
    a.ask("Convert notes.md to PDF into report.pdf.")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("I ran `pandoc` on notes.md, report.pdf is ready.")
    ev = a.evidence(final_text="I ran `pandoc` on notes.md, report.pdf is ready.")
    assert _cr_kinds(ev) == ["claimed_run"], ev["findings"]


def test_lfake_multi_token_command_claim_is_caught(env):
    """L-fake：span 是多 token 命令（`pandoc --from markdown …`），首詞仍是 CLI → 抓，
    cmd_token 取首詞（記錄比對用）。"""
    p = _proj(env, "c3_multitoken")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("I ran `pandoc --from markdown notes.md -o report.pdf` and it is ready.")
    ev = a.evidence(final_text="I ran `pandoc --from markdown notes.md -o report.pdf` and it is ready.")
    assert any(f["kind"] == "claimed_run" and f["cmd_token"] == "pandoc"
               for f in ev["findings"]), ev["findings"]


# -------------------------------------------- advisory-only（不退回）

def test_claimed_run_is_advisory_only(env):
    """advisory pin：claimed_run 被 `zerostop.pushable_for` 明確排除，只進交件說明（§3 規則 3）。"""
    p = _proj(env, "c4_advisory")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("我跑了 `pandoc` 把 notes.md 轉成 report.pdf。")
    ev = a.evidence(final_text="我跑了 `pandoc` 把 notes.md 轉成 report.pdf。")
    assert any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    assert all(f["kind"] != "claimed_run" for f in pushable), pushable
    assert pushable == [], pushable


def test_claimed_run_not_pushed_even_with_pushable_findings(env):
    """混排 pin：同時有可退回的 `missing_output` 時，退回集裡只有 missing_output，
    claimed_run 照樣被排除（兩類發現各走各的路，advisory 不被「搭便車」帶回去）。"""
    p = _proj(env, "c5_mix")
    a = Agent(p)
    a.ask("把 notes.md 整理成 report.pdf，另外寫入 summary.txt，兩份交回。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("我跑了 `pandoc` 產出兩份。")
    ev = a.evidence(final_text="我跑了 `pandoc` 產出兩份。")
    kinds = {f["kind"] for f in ev["findings"]}
    assert {"claimed_run", "missing_output"} <= kinds, ev["findings"]
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    assert all(f["kind"] == "missing_output" for f in pushable), pushable


# ------------------------------------------------------------ 不抓（負對照）

def test_suggestion_phrasing_not_caught(env):
    """負對照：「你可以執行 `pandoc` …」是建議措辭（`RUN_CLAIM_SUGGEST` 鄰窗命中），
    不是執行宣稱 → 不報。寧漏勿誤：建議句裡的命令本來就不該被當成「跑過」的證明。"""
    p = _proj(env, "c6_suggest")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.pdf", "x" * 40)
    a.stop("你可以執行 `pandoc` 把 notes.md 轉成 PDF。")
    ev = a.evidence(final_text="你可以執行 `pandoc` 把 notes.md 轉成 PDF。")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]


def test_command_in_record_not_caught(env):
    """負對照：宣稱的 CLI 在記錄裡出現過（參數不同也算——記錄比對是**子串**、小寫）→ 不報。
    這是「跨參數引用」的正當情形：agent 實際跑過 `pandoc notes.md --toc -o report.pdf`，
    結語簡化成「I ran `pandoc`」。"""
    p = _proj(env, "c7_ran")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.bash("pandoc notes.md --toc -o report.pdf", "ok")
    a.write("report.pdf", "x" * 40)
    a.stop("I ran `pandoc` and the report is ready.")
    ev = a.evidence(final_text="I ran `pandoc` and the report is ready.")
    assert ev["findings"] == [], ev["findings"]


def test_pip_pip3_alias_counts_as_run(env):
    """負對照：宣稱 `pip install …`、記錄裡是 `pip3 install …`——子串比對（`pip` 在
    `pip3 …` 裡）就算跑過 → 不報。保守方向：別名／路徑前綴（/usr/bin/…）都算命中。"""
    p = _proj(env, "c8_alias")
    a = Agent(p)
    a.ask("請準備環境並產出 report.txt。")
    a.bash("pip3 install requests", "Successfully installed requests")
    a.write("report.txt", "環境已準備好。")
    a.stop("I ran `pip install requests` and then wrote report.txt.")
    ev = a.evidence(final_text="I ran `pip install requests` and then wrote report.txt.")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]


def test_non_cli_backtick_word_not_caught(env):
    """負對照：反引號 span 的首詞不在 `RUN_CLAIM_TOOLS`（`tests`）→ 不報。
    「I ran the `tests`」是口語，不是命令宣稱；白名單是第二層濾網。"""
    p = _proj(env, "c9_noncli")
    a = Agent(p)
    a.ask("把 notes.md 整理成 report.txt 交回。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.txt", "hello world 已整理。")
    a.stop("I ran the `tests` and they all passed, report.txt is ready.")
    ev = a.evidence(final_text="I ran the `tests` and they all passed, report.txt is ready.")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]


def test_thread_noun_alone_not_a_cue(env):
    """負對照：`執行緒`（thread）名詞不是「執行過」線索（`RUN_CLAIM_CUE` 的 `(?!緒)` 負向前瞻），
    且本句沒有其他過去式線索 → 不報。中文裡「執行」的高頻合法用法之一就是線程上下文。"""
    p = _proj(env, "c10_thread")
    a = Agent(p)
    a.ask("把 notes.md 整理成 report.txt 交回。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.txt", "notes 的整理結果：hello world 已整理。")
    a.stop("這個任務的執行緒模型沒有問題。`python3` 也够用。")
    ev = a.evidence(final_text="這個任務的執行緒模型沒有問題。`python3` 也够用。")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]


def test_path_span_not_caught(env):
    """負對照：反引號 span 以 `.` 開頭（路徑 `./scripts/build.sh`）——`RUN_CLAIM_SPAN`
    要求首詞是字母開頭的 CLI 形詞（2–20 字元），路徑不進候選 → 不報。
    （`build.sh` 這類的自訂腳本也不在 `RUN_CLAIM_TOOLS`，雙重不命中。）"""
    p = _proj(env, "c11_path")
    a = Agent(p)
    a.ask("把 notes.md 整理成 report.txt 交回。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.write("report.txt", "hello world 已整理。")
    a.stop("I ran `./scripts/build.sh all` to produce report.txt.")
    ev = a.evidence(final_text="I ran `./scripts/build.sh all` to produce report.txt.")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]


def test_cross_turn_reference_not_caught(env):
    """負對照（跨回合）：pandoc 在**第一回合**跑過，第二回合的總結訊息才宣稱「我跑了
    `pandoc`」→ 不報。證據面是整份 session 的命令記錄（`_claimed_runs` 掃全部 shell steps），
    不是只看最後一回合——跨回合引用同一條跑過的命令是正常敘事，不是造假。"""
    p = _proj(env, "c12_crossturn")
    a = Agent(p)
    a.ask("把 notes.md 轉成 PDF 交回，寫入 report.pdf。")
    a.write("notes.md", "hello world")
    a.read("notes.md")
    a.bash("pandoc notes.md -o report.pdf", "ok")
    a.write("report.pdf", "x" * 40)
    a.stop("report.pdf 已產出。")
    a.ask("再確認一次 report.pdf 存在。")
    a.read("report.pdf")
    ev = a.evidence(final_text="我跑了 `pandoc` 產出 report.pdf。")
    assert not any(f["kind"] == "claimed_run" for f in ev["findings"]), ev["findings"]
