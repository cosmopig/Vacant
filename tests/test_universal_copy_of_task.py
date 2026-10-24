"""方向 A（通用任務）：`copy_of_task` 檢查 — 把任務提示詞當答案交出去。

域無關、只看紀錄（提示詞 vs 要求的交付檔）、預設**只進交件說明、不退回**給 agent。
三重保守條件：`_collapse` 正規化後提示詞包含於交付檔、比例 ≥ 0.8、提示詞 ≥ 60 字。
合併門檻見 docs/UNIVERSAL_TASKS.md §3；誤報守衛：轉述（照抄引用內容、不含指令句）不觸發。
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from vacant_network.adapters import hook, install as INS
from vacant_network.trace import capture, zerostop
from vacant_network.trace.evidence import evidence_for
from vacant_network.trace.recorder import Recorder


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


class Agent:
    """最小掛鉤模擬（與 tests/test_universal_and_coding_upgrades.py 同模式）。"""

    def __init__(self, proj: pathlib.Path, session: str = "S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text: str) -> None:
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def write(self, rel: str, content: str) -> None:
        self.n += 1
        f = self.p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": "Write",
               "tool_use_id": f"t{self.n}", "tool_input": {"file_path": str(f), "content": content}}
        hook.handle("claude", "PreToolUse", pre)
        hook.handle("claude", "PostToolUse", {**pre, "tool_response": {}})

    def stop(self, last_msg: str = "Done.") -> dict:
        out, err, code = hook.handle("claude", "Stop", {
            "session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": last_msg})
        assert code == 0 and err == ""
        return json.loads(out) if out else {}

    def evidence(self, final_text: str = "", today=dt.date(2026, 9, 25)) -> dict:
        ws = capture.workspace_for(str(self.p))
        return evidence_for(Recorder(ws), platform="claude", session=self.s,
                            final_text=final_text, today=today)


def _proj(env, name: str = "proj") -> pathlib.Path:
    p = env / "work" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def _copies(ev: dict) -> list[dict]:
    return [f for f in ev["findings"] if f.get("kind") == "copy_of_task"]


# 1) 把提示詞當答案交出去 → 抓到，且只進交件說明
def test_copy_of_prompt_is_flagged_and_advisory_only(env):
    prompt = (
        "請把今天產品評審會的會議紀錄整理成正式報告。要求：包含議程項目、"
        "每個項目的結論、後續行動清單（含負責人與期限）。報告寫入 report.md，"
        "結構為背景、討論、決議、後續行動四段。語氣中立客觀，不加入個人意見，"
        "每個結論前面標注發言者姓名與時間。"
    )
    a = Agent(_proj(env, "copy"))
    a.ask(prompt)
    a.write("report.md", "# 產品評審報告\n\n" + prompt)   # 連指令句一起照抄
    a.stop("報告已寫好，放在 report.md。")
    ev = a.evidence(final_text="報告已寫好，放在 report.md。")
    c = _copies(ev)
    assert len(c) == 1, ev["findings"]
    assert c[0]["path"].endswith("report.md")
    # 只進交件說明：pushable_for 必須把它排除
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    assert all(f.get("kind") != "copy_of_task" for f in pushable)
    # 交件說明（delivery note）的短描述要能渲染，不炸
    assert zerostop._say(c[0]).endswith("report.md") or "report.md" in zerostop._say(c[0])


# 2) 乾淨的非程式交付（報告含算出來的數字）→ 不觸發
def test_legitimate_report_not_flagged(env):
    p = _proj(env, "report")
    (p / "sales.csv").write_text("region,q1,q2\nnorth,120,150\nsouth,80,95\n")
    prompt = (
        "讀 sales.csv，算出兩個區域 q1、q2 的總計與增幅百分比，寫一份三行以內"
        "的摘要到 report.md，最後一行寫明較好的區域與增幅數字。"
    )
    a = Agent(p)
    a.ask(prompt)
    a.write("sales.csv", "region,q1,q2\nnorth,120,150\nsouth,80,95\n")  # 視為已存在
    a.write("report.md", "north：q1 120、q2 150；south：q1 80、q2 95。\n"
                         "總計 north 270、south 175。\n較好的區域是 north，增幅 25.0%。")
    a.stop("摘要已寫好。")
    ev = a.evidence(final_text="摘要已寫好。")
    assert _copies(ev) == [], ev["findings"]


# 3) 誤報守衛：轉述任務（照抄引用內容、不含指令句）→ 不觸發
def test_transcription_of_quoted_content_not_flagged(env):
    para = ("本季度預算執行率為百分之八十七，剩餘預算集中在第三季度。"
            "若第四季度採購計劃不變，預計年末結餘約為四百二十萬元，"
            "財務處建議提前編列明年度採購清單，以避免年底集中支出。"
            "各部門應於本月底前回報未執行的合同項目，並說明延後原因。")
    prompt = "請把下面這段話原樣寫入 out.txt，不要增刪任何字：\n" + para
    a = Agent(_proj(env, "transcribe"))
    a.ask(prompt)
    a.write("out.txt", para)          # 只有引用內容，沒有指令句
    a.stop("已寫入 out.txt。")
    ev = a.evidence(final_text="已寫入 out.txt。")
    assert _copies(ev) == [], ev["findings"]


# 4) 誤報守衛：短提示詞（< 60 字）的巧合 → 不觸發
def test_short_prompt_coincidence_not_flagged(env):
    a = Agent(_proj(env, "short"))
    a.ask("請把會議重點寫一句話摘要到 summary.txt")
    a.write("summary.txt", "會議重點：請把會議重點寫一句話摘要到 summary.txt —— 決議延期上線一週。")
    a.stop("完成。")
    ev = a.evidence(final_text="完成。")
    assert _copies(ev) == [], ev["findings"]


# 5) 退回通道：copy_of_task 永遠不進 pushable（即使有其它可退回的發現）
def test_copy_of_task_never_pushed_even_with_others(env):
    prompt = (
        "請把今天產品評審會的會議紀錄整理成正式報告。要求：包含議程項目、"
        "每個項目的結論、後續行動清單（含負責人與期限）。報告寫入 report.md，"
        "結構為背景、討論、決議、後續行動四段。語氣中立客觀，不加入個人意見，"
        "每個結論前面標注發言者姓名與時間。"
    )
    a = Agent(_proj(env, "mix"))
    a.ask(prompt)
    a.write("report.md", prompt)
    a.stop("完成。")
    ev = a.evidence(final_text="完成。")
    assert _copies(ev)
    ev["findings"].append({"kind": "missing_output", "path": "minutes.md", "asked": "minutes.md"})
    pushable = zerostop.pushable_for(ev["findings"], 0, False)
    kinds = [f["kind"] for f in pushable]
    assert "copy_of_task" not in kinds
    assert "missing_output" in kinds      # 其它發現不受影響
