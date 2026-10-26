"""方向 A（通用任務）離線重播：非程式場景的誤報／真陽率。

`docs/UNIVERSAL_TASKS.md` §3 的合併門檻：新檢查轉成「可退回」之前，必須在
非程式樣本集上零誤報。這個檔案就是那份樣本集（離線、無模型、可重跑）：

- 乾淨的非程式交付（報告、表格、轉述）：零**可退回**的發現（agent 不被退回）。
- L-fake（照抄題目、編造數字）：該抓的照抓（copy_of_task / unsourced）。

跑法：`pytest tests/test_noncode_samples.py -v`

注意掛鉤順序：recorder 以「Pre 前快照 → Post 後快照」的 diff 認定該步寫了什麼
（vacant_network/trace/recorder.py 的 `W.diff(pre_index, post_index)`），所以
寫檔必須落在 PreToolUse 與 PostToolUse 之間，寫在 Pre 之前的檔不會被認成這一步
的交付物（會被當成環境裡本來就有的檔）。
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

import pytest

from vacant_network.adapters import hook, install as INS
from vacant_network.trace import capture, zerostop
from vacant_network.trace.evidence import (
    COPY_CUE,
    EXTRACT_CUE,
    INLINE_COPY_MIN,
    TRANSFORM_CUE,
    VERBATIM_CUE,
    _collapse,
    evidence_for,
)
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
    """最小掛鉤模擬。寫檔順序 = Pre → 落盤 → Post（與 recorder 的 diff 對齊）。"""

    def __init__(self, proj: pathlib.Path, session: str = "S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text: str) -> None:
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def read(self, rel: str) -> None:
        f = self.p / rel
        self._tool("Read", {"file_path": str(f)},
                   {"file": {"content": f.read_text()}}, mid=None)

    def write(self, rel: str, content: str) -> None:
        f = self.p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        self._tool("Write", {"file_path": str(f), "content": content}, {},
                   mid=lambda: f.write_text(content))

    def _tool(self, tool: str, tool_input: dict, output: dict, mid=None) -> None:
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": tool_input}
        hook.handle("claude", "PreToolUse", pre)
        if mid is not None:
            mid()
        hook.handle("claude", "PostToolUse", {**pre, "tool_response": output})

    def stop(self, last_msg: str = "Done.") -> None:
        out, err, code = hook.handle("claude", "Stop", {
            "session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": last_msg})
        assert code == 0 and err == ""

    def evidence(self, final_text: str = "", today=dt.date(2026, 9, 25)) -> dict:
        ws = capture.workspace_for(str(self.p))
        return evidence_for(Recorder(ws), platform="claude", session=self.s,
                            final_text=final_text, today=today)

    def pushable(self, ev: dict) -> list[dict]:
        return zerostop.pushable_for(ev["findings"], 0, False)


def _proj(env, name: str, files: dict[str, str] | None = None) -> pathlib.Path:
    p = env / "work" / name
    p.mkdir(parents=True, exist_ok=True)
    for rel, c in (files or {}).items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)
    return p


SALES = "region,q1,q2\nnorth,120,150\nsouth,80,95\n"

# ── 乾淨樣本：零可退回的發現（誤報守衛）────────────────────────────────────

def test_clean_report_with_derived_numbers(env):
    """CSV → 摘要報告（含總計與百分比）：推導得出的數值不該算沒有出處。"""
    p = _proj(env, "n1_report", {"sales.csv": SALES})
    prompt = ("讀 `sales.csv`，算出兩個區域 q1、q2 的總計與增幅百分比，"
              "摘要寫入 report.md，最後一行寫明較好的區域與增幅數字。")
    # 註：檔名前後用 ASCII 空白／反引號包起，才能被 materials 抽出（全形「，」「（）」
    # 黏在檔名後面時抽不出，unsourced 會降成 note-only、缺檔也抽不到）——這是既有
    # 抽詞行為，樣本集就照能工作的寫法來測。
    a = Agent(p)
    a.ask(prompt)
    a.read("sales.csv")
    a.write("report.md", "north：q1 120、q2 150；south：q1 80、q2 95。\n"
                         "總計 north 270、south 175。\n較好的區域是 north，增幅 25.0%。")
    a.stop("摘要已寫好。")
    ev = a.evidence(final_text="摘要已寫好。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_table_reorganization(env):
    """混亂 CSV → 排序清洗 CSV：內容是同一批資料，不該有任何發現。"""
    p = _proj(env, "n2_table",
              {"raw.csv": "item,amount\napple,30\npear,30\npear,30\nmango,90\nkiwi,10\n"})
    a = Agent(p)
    a.ask("把 raw.csv 按金額從大到小排序、去掉重複行，結果寫入 clean.csv。")
    a.read("raw.csv")
    a.write("clean.csv", "item,amount\nmango,90\napple,30\npear,30\nkiwi,10\n")
    a.stop("已排序寫入 clean.csv。")
    ev = a.evidence(final_text="已排序寫入 clean.csv。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_transcription(env):
    """照抄引用內容（不含指令句）＝轉述任務，不該被當成照抄題目。"""
    p = _proj(env, "n3_transcribe")
    para = ("本季度預算執行率為百分之八十七，剩餘預算集中在第三季度。"
            "若第四季度採購計劃不變，預計年末結餘約為四百二十萬元，"
            "財務處建議提前編列明年度採購清單，以避免年底集中支出。")
    a = Agent(p)
    a.ask("請把下面這段話原樣寫入 out.txt，不要增刪任何字：\n" + para)
    a.write("out.txt", para)
    a.stop("已寫入 out.txt。")
    ev = a.evidence(final_text="已寫入 out.txt。")
    assert a.pushable(ev) == [], ev["findings"]
    assert all(f["kind"] != "copy_of_task" for f in ev["findings"])


def test_clean_missing_file_still_reported_but_not_copied(env):
    """要求兩份檔只交一份：缺檔要報（既有檢查在非程式任務上照常工作），且不是照抄題目。"""
    p = _proj(env, "n4_missing")
    a = Agent(p)
    a.ask("請整理今天的會議，寫入 report.md，以及寫入 minutes.md，逐條紀要。")
    a.write("report.md", "背景：季度回顧。\n決議：延期上線一週。\n後續行動：下週三前更新時程。")
    a.stop("report.md 已寫好，minutes.md 還在整理。")
    ev = a.evidence(final_text="report.md 已寫好，minutes.md 還在整理。")
    pushable = a.pushable(ev)
    assert any(f["kind"] == "missing_output" and f["path"].endswith("minutes.md")
               for f in pushable), ev["findings"]
    assert all(f["kind"] != "copy_of_task" for f in ev["findings"])


# ── 對照樣本：L-fake 該抓的照抓（真陽）────────────────────────────────────

# ── 2026-10-27：誤報量測樣本（docs/UNIVERSAL_TASKS.md §3 合併門檻的 ≥20 合格交付）──
# 每個樣本都是一個「合法交付」，且針對某一兩個 advisory 檢查的觸發條件刻意貼邊，
# 但不能報。為什麼不報（哪條豁免生效）寫在各 docstring；關鍵的「不是逐字子串」
# 事實直接用 `_collapse` 斷言釘死，免得改動 `_collapse`／cue 集後靜默改判。

def test_clean_reorder_lines(env):
    """重排任務：交件是同一批行的另一種排列（加一行標題），不是 prompt 的逐字子串。
    壓 `copy_of_inline`（「排序」是改寫線索、交件 ≥120 字，但重排後不再逐字連續）
    與 `copy_of_task`（交件不含指令句）；行內日期全部出自 prompt，unsourced 豁免。"""
    p = _proj(env, "n12_reorder")
    lines = ["2026-09-10 系統上線", "2026-09-18 修補漏洞", "2026-09-12 安全複查",
             "2026-09-20 發佈公告", "2026-09-05 專案啟動", "2026-09-22 回滾一次",
             "2026-09-15 負載測試", "2026-09-08 需求評審", "2026-09-25 驗收通過",
             "2026-09-02 需求收集"]
    prompt = ("以下事件順序是亂的：" + "；".join(lines) + "。請按日期從早到晚排序，寫入 timeline.md。")
    a = Agent(p)
    a.ask(prompt)
    ordered = sorted(lines)
    out = "時間線：\n" + "\n".join(ordered)
    assert len(_collapse(out)) >= 120 and _collapse(out) not in _collapse(prompt)
    a.write("timeline.md", out)
    a.stop("已排序寫入 timeline.md。")
    ev = a.evidence(final_text="已排序寫入 timeline.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_template_fill(env):
    """填寫型任務：prompt 給模板（含佔位）與資料，交件是填好的模板。
    壓 `copy_of_task`（交件≠prompt：佔位被換成值）與 `skeleton`（交件沒有佔位行）；
    填進的數字與日期都出自 prompt，unsourced 豁免。"""
    p = _proj(env, "n13_fill")
    a = Agent(p)
    a.ask("模板：「致【單位】：關於【事由】的函。金額【金額】元，限期【日期】前回覆。」"
          "資料：單位=資采組，事由=備品採購，金額=320，日期=2026-10-20。"
          "請將模板填完整，寫入 letter.txt。")
    out = "致資采組：關於備品採購的函。金額320元，限期2026-10-20前回覆。"
    assert _collapse(out) not in _collapse("致【單位】：關於【事由】的函。金額【金額】元，限期【日期】前回覆。")
    a.write("letter.txt", out)
    a.stop("已填好寫入 letter.txt。")
    ev = a.evidence(final_text="已填好寫入 letter.txt。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_translation(env):
    """翻譯任務：交件是另一種語言的重述，不是 prompt 的逐字子串；數字與原文一致。
    壓 `copy_of_inline`（「summarize/translate」線索＋交件 ≥120 字，但字面不同）；
    unsourced 的數字全部豁免（都出自 prompt）。"""
    p = _proj(env, "n14_trans")
    a = Agent(p)
    a.ask("Please summarize and translate the following into Traditional Chinese, "
          "write to trans.md: The platform processed 12,480 orders last quarter, "
          "up 9.5 percent year over year. The refund rate held at 0.4 percent. "
          "Customer satisfaction stayed above 90 points in all three regions. "
          "Inventory turnover improved from 4.1 to 4.6. Shipping cost per order "
          "fell by 0.8 percent. The team attributes the gain to the new routing "
          "rules shipped in June.")
    out = ("摘要（繁體中文）：上季度平台共處理 12,480 筆訂單，較上年同期成長 9.5%；"
           "退貨率維持在 0.4%。三個區域的顧客滿意度皆高於 90 分。庫存周转率從 4.1 "
           "提升到 4.6。每單配送成本下降 0.8%。團隊將成長歸因於六月推出的新路由規則。")
    assert len(_collapse(out)) >= 120 and _collapse(out) not in _collapse("processed 12,480 orders")
    a.write("trans.md", out)
    a.stop("已翻譯寫入 trans.md。")
    ev = a.evidence(final_text="已翻譯寫入 trans.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_quotation_with_commentary(env):
    """摘要＋引文：交件包含一段逐字引文，但整體是「摘要＋引文」，不是 prompt 的逐字子串。
    壓 `copy_of_inline`（引用內容合法；整體非子串）與 `copy_of_task`（交件不含指令句）。"""
    p = _proj(env, "n15_quote")
    a = Agent(p)
    a.ask("以下段落：「本季度營收 4,200 萬，年增 12%。其中訂閱收入佔六成，"
          "成長主要来自企業客戶。」請摘要成兩句以內，並附上一句原文引文，寫入 brief.md。")
    out = ("摘要：本季營收 4,200 萬、年增 12%；訂閱收入為主，企業客戶是成長引擎。\n"
           "原文：「成長主要来自企業客戶。」")
    assert _collapse(out) not in _collapse("本季度營收 4,200 萬，年增 12%。其中訂閱收入佔六成，成長主要来自企業客戶。")
    a.write("brief.md", out)
    a.stop("已寫入 brief.md。")
    ev = a.evidence(final_text="已寫入 brief.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_average_and_max(env):
    """CSV → 平均與極值：derived 池（sum/mean/min/max）豁免；與 n1 的加總/百分比互補。"""
    p = _proj(env, "n16_avg", {"scores.csv": "team,score\nalpha,80\nbeta,90\ngamma,70\n"})
    a = Agent(p)
    a.ask("讀 scores.csv，算出平均與最高分，寫入 answer.txt，每行一個數值。")
    a.read("scores.csv")
    a.write("answer.txt", "80\n90")
    a.stop("已寫入 answer.txt。")
    ev = a.evidence(final_text="已寫入 answer.txt。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_email_draft(env):
    """純文字書信：要點 → 正式信件，無數字無日期，五種通用檢查都該沉默。"""
    p = _proj(env, "n17_email")
    a = Agent(p)
    a.ask("把以下要點寫成一封給客戶的正式信件，語氣誠懇，寫入 email.txt："
          "（一）下週一上午系統維護兩小時；（二）期間線上申請暫停；"
          "（三）維護完成後會寄送確認信。")
    a.write("email.txt", "敬愛的客戶：\n\n您好！為提升服務穩定性，我們將於下週一上午進行約兩小時的"
                         "系統維護，期間線上申請暫停受理，維護完成後將另行寄送確認信。"
                         "由此造成不便，敬請見諒。\n\n順祝商祺\n服務團隊")
    a.stop("信件已寫好。")
    ev = a.evidence(final_text="信件已寫好。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_format_to_markdown_table(env):
    """格式轉換：同一批「名稱,分數」行 → Markdown 表格（加管線符與表頭）。
    壓 `copy_of_inline`（「轉換」是改寫線索、交件 ≥120 字，但加了表格語法後非逐字子串）；
    數字全部出自 prompt，unsourced 豁免。"""
    p = _proj(env, "n18_mdtable")
    rows = [("北區", "88"), ("南區", "72"), ("東區", "91"), ("西區", "64"), ("中部", "77"),
            ("雲林地", "69"), ("嘉義地", "81"), ("台南地", "93"), ("高雄地", "75"),
            ("屏東地", "58"), ("宜蘭地", "86"), ("花蓮地", "62")]
    data = "\n".join(f"{n},{s}" for n, s in rows)
    a = Agent(p)
    a.ask("把下面的分數轉換成 Markdown 表格（欄位：區域、分數），寫入 table.md：\n" + data)
    out = "| 區域 | 分數 |\n|---|---|\n" + "\n".join(f"| {n} | {s} |" for n, s in rows)
    assert len(_collapse(out)) >= 120 and _collapse(out) not in _collapse(data)
    a.write("table.md", out)
    a.stop("已轉換寫入 table.md。")
    ev = a.evidence(final_text="已轉換寫入 table.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_two_files_both_delivered(env):
    """雙交件：報告（散文）＋數據檔（CSV 推導值）都交了；missing_output 不該報，數字有出處。"""
    p = _proj(env, "n19_multi", {"budget.csv": "item,cost\nhosting,200\ndomain,60\ntool,140\n"})
    a = Agent(p)
    a.ask("讀 budget.csv，寫兩份檔：summary.md 用兩句話說明這筆預算；"
          "totals.txt 第一行寫總計、第二行寫最貴項目名。")
    a.read("budget.csv")
    a.write("summary.md", "這是一組小型營運預算，涵蓋主機、域名與工具等費用。整體以主機費為主。")
    a.write("totals.txt", "400\nhosting")
    a.stop("兩份都寫好了。")
    ev = a.evidence(final_text="兩份都寫好了。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_deduplicate_and_sort(env):
    """去重＋排序：重複項散佈在原文中，去掉後交件是 prompt 的子列（subsequence）
    而非子串（substring）——`copy_of_inline` 的逐字子串判定不該觸發。
    （交件 <120 字，另由短答案豁免；兩層保護都在，docstring 照實說。）"""
    p = _proj(env, "n20_dedup")
    items = ["無線降噪藍牙耳機", "靜音機械式鍵盤", "4K 高刷行動螢幕", "無線降噪藍牙耳機",
             "USB 高速集線器", "心形藍牙麥克風", "靜音機械式鍵盤", "低延遲電競滑鼠",
             "桌面磁吸理線盒", "雙螢幕懸浮支架", "USB-C 多口轉接頭", "心形藍牙麥克風",
             "萬能行動電源", "4K 高刷行動螢幕", "雙網卡適配器", "螢幕清潔組裝"]
    a = Agent(p)
    a.ask("以下清單有重複：" + "、".join(items) + "。請去重並排序，寫入 unique.md。")
    out = "清單（去重）：" + "、".join(sorted(set(items)))
    assert _collapse(out) not in _collapse("、".join(items))   # 子列 ≠ 子串
    assert len(_collapse(out)) < 120                              # 且 < INLINE_COPY_MIN
    a.write("unique.md", out)
    a.stop("已去重排序寫入 unique.md。")
    ev = a.evidence(final_text="已去重排序寫入 unique.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_append_to_existing_report(env):
    """追加型任務：報告檔本就在專案裡，agent 真的改了它（加一節）——
    `stale_output` 只該抓「一字未改卻稱已寫好」，真的改過就不該報。"""
    p = _proj(env, "n21_append", {"report.md": "第一節：背景。\n本季目標如期推進。\n"})
    a = Agent(p)
    a.ask("把風險一節寫入 report.md（追加在末尾）：供應商交期不穩，需準備備案。")
    a.write("report.md", "第一節：背景。\n本季目標如期推進。\n\n風險：供應商交期不穩，需準備備案。\n")
    a.stop("已更新 report.md。")
    ev = a.evidence(final_text="已更新 report.md。")
    assert a.pushable(ev) == [], ev["findings"]


def test_lfake_prompt_echo_is_caught(env):
    """把任務提示詞當答案交出去：copy_of_task 要報（advisory，不退回）。"""
    p = _proj(env, "n5_echo")
    prompt = (
        "請把今天產品評審會的會議紀錄整理成正式報告。要求：包含議程項目、"
        "每個項目的結論、後續行動清單（含負責人與期限）。報告寫入 report.md，"
        "結構為背景、討論、決議、後續行動四段。語氣中立客觀，不加入個人意見，"
        "每個結論前面標注發言者姓名與時間。"
    )
    a = Agent(p)
    a.ask(prompt)
    a.write("report.md", prompt)
    a.stop("報告已寫好。")
    ev = a.evidence(final_text="報告已寫好。")
    assert any(f["kind"] == "copy_of_task" for f in ev["findings"]), ev["findings"]
    assert all(f["kind"] != "copy_of_task" for f in a.pushable(ev))   # 不退回


def test_lfake_fabricated_number_is_caught(env):
    """讀過的資料上編造一個對不上的數字：unsourced 要報（既有檢查，非程式交付上也抓）。"""
    p = _proj(env, "n6_fabricate", {"sales.csv": SALES})
    a = Agent(p)
    a.ask("讀 `sales.csv`，寫入 report.md，寫兩行以內的摘要，說明兩個區域的規模差距。")
    a.read("sales.csv")
    a.write("report.md", "north 與 south 的規模差距明顯。\nnorth 的季度增幅達 42.7%，遠高於 south。")
    a.stop("摘要已寫好。")
    ev = a.evidence(final_text="摘要已寫好。")
    assert any(f["kind"] == "unsourced" and f["value"] == "42.7%" for f in ev["findings"]), \
        ev["findings"]


# ── 方向 A 通用檢查（2026-09-25）：skeleton／stale_output／copy_of_input ──
# 三者都只進交件說明（`zerostop.pushable_for` 明確排除）；每項一個抓得著的 L-fake、
# 一個不該抓的 clean（零誤報守衛）。

DATA = ("item,amount\napple,30\npear,30\npear,30\nmango,90\nkiwi,10\n"
        "banana,25\norange,40\ngrape,15\n")


def test_lfake_skeleton_report_is_caught(env):
    """交付的是模板骨架（多數行是未填占位符）：skeleton 要報（advisory，不退回）。"""
    p = _proj(env, "n7_skeleton")
    a = Agent(p)
    a.ask("請把今天產品評審會的會議紀錄整理成正式報告，寫入 report.md，結構為背景、討論、決議、後續行動四段。")
    a.write("report.md", "## 背景\n[待填]\n## 討論\n[待填]\n## 決議\nTBD\n## 後續行動\nTBD\n")
    a.stop("報告已寫入 report.md。")
    ev = a.evidence(final_text="報告已寫入 report.md。")
    assert any(f["kind"] == "skeleton" for f in ev["findings"]), ev["findings"]
    assert all(f["kind"] != "skeleton" for f in a.pushable(ev))   # 不退回


@pytest.mark.parametrize("line,expect", [
    ("{{name}}", True),           # 雙括號模板占位符（docstring 文件化的形狀）
    ("{{待填}}", True),
    ("{{value}}", True),
    ("{name}", False),            # 單括號＝資料值形狀（JSONL/字典/集合字面量），不當占位符
    ('{"a": 1}', False),          # JSONL 行（volumes.jsonl 誤報回歸）
    ("{1, 2, 3}", False),         # Python 集合字面量
    ("[待填]", True),
    ("TBD", True),
    ("TODO", True),
    ("___", True),
    ("待補", True),
    ("上線日期：TBD（等待供應商確認）", False),   # 行內其它內容→誠實的 TBD
    ("- [待填]", True),           # 行首清單標記先剝掉
])
def test_is_placeholder_line_shapes(line, expect):
    from vacant_network.trace.evidence import _is_placeholder_line
    assert _is_placeholder_line(line) is expect


def test_clean_honest_tbd_not_flagged(env):
    """完整報告裡一個誠實的「日期：TBD（有原因）」：不算模板骨架。"""
    p = _proj(env, "n8_honest_tbd")
    a = Agent(p)
    a.ask("請把今天評審會的紀錄整理成正式報告，寫入 report.md，結構為背景、決議、風險、後續行動四段。")
    a.write("report.md",
            "## 背景\n本季度評審會議於上週五召開。\n"
            "## 決議\n上線日期：TBD（等待供應商確認）\n"
            "風險：第三方介面文件尚未補齊。\n"
            "## 後續行動\n下週三前更新時程。\n")
    a.stop("報告已寫入 report.md。")
    ev = a.evidence(final_text="報告已寫入 report.md。")
    assert all(f["kind"] != "skeleton" for f in ev["findings"]), ev["findings"]


def test_lfake_input_copy_is_caught(env):
    """要求的「加總摘要」＝輸入素材原封不動：copy_of_input 要報（advisory，不退回）。"""
    p = _proj(env, "n9_input_copy", {"data.csv": DATA})
    a = Agent(p)
    a.ask("讀 `data.csv`，把各品項的金額加總，摘要寫入 summary.md。")
    a.read("data.csv")
    a.write("summary.md", DATA)
    a.stop("summary.md 已寫好。")
    ev = a.evidence(final_text="摘要已寫好。")
    assert any(f["kind"] == "copy_of_input" for f in ev["findings"]), ev["findings"]
    assert all(f["kind"] != "copy_of_input" for f in a.pushable(ev))   # 不退回


def test_clean_copy_task_not_flagged(env):
    """任務本身就是「複製 data.csv 到 backup/」：產出與輸入相同是預期，不報 copy_of_input。"""
    p = _proj(env, "n10_copy_task", {"data.csv": DATA})
    a = Agent(p)
    a.ask("把 `data.csv` 複製到 `backup/data_copy.csv`，不要改內容。")
    a.read("data.csv")
    a.write("backup/data_copy.csv", DATA)
    a.stop("已複製。")
    ev = a.evidence(final_text="已複製。")
    assert all(f["kind"] != "copy_of_input" for f in ev["findings"]), ev["findings"]


def test_lfake_stale_output_is_caught(env):
    """report.md 本回合前就在、agent 一字未改，卻說「已寫好」：stale_output 要報（advisory，不退回）。"""
    p = _proj(env, "n11_stale", {"report.md": "## 上季度評審紀要\n結論：採用方案 A。\n"})
    a = Agent(p)
    a.ask("請整理今天評審會的紀要，寫入 report.md。")
    a.read("report.md")
    a.stop("紀要已寫入 report.md。")
    ev = a.evidence(final_text="紀要已寫入 report.md。")
    assert any(f["kind"] == "stale_output" for f in ev["findings"]), ev["findings"]
    assert all(f["kind"] != "stale_output" for f in a.pushable(ev))   # 不退回


def test_clean_verify_noop_not_flagged(env):
    """「確認 report.md 數字正確、有錯才改」——檔本來就在、真的不用改：不報 stale_output。"""
    p = _proj(env, "n12_verify", {"report.md": "總銷售 270，其中 north 175，占 64.8%。\n"})
    a = Agent(p)
    a.ask("確認 report.md 裡的數字正確，有錯再改。")
    a.read("report.md")
    a.stop("已確認，數字正確，無需修改。")
    ev = a.evidence(final_text="已確認，數字正確，無需修改。")
    assert all(f["kind"] != "stale_output" for f in ev["findings"]), ev["findings"]


# ── 2026-10-25（round 20）：把貼在題目裡的数据原樣抄回交件（copy_of_inline）─────────

def test_lfake_inline_echo_is_caught(env):
    """L-fake：題目要求「整理成正式報告」，agent 把貼在題目裡的紀錄原樣寫成 report.md。
    copy_of_task 抓不到（交件不含指示句，比例 <0.8）；unsourced 也抓不到（數字都在 prompt → 豁免）。
    copy_of_inline 要報：交件（正規化後）是 prompt 的逐字子串，且題目要求改寫。"""
    p = _proj(env, "n13_inline_echo")
    prompt = ("以下是今天產品評審會的紀錄，請整理成正式報告（含背景、討論、決議、後續行動四段），"
              "寫入 report.md。\n"
              "甲：上週的指標掉了 3.2%，主要是渠道 A 的退單，退單率 8.1%。\n"
              "乙：建議下週一前給出補救方案，另外渠道 B 的 45 萬元預算先凍結，等審計結果。\n"
              "丙：同意。上線時間維持 10 月 9 日，不變；請各位把補救方案發給全組。\n"
              "丁：補救方案要涵蓋渠道 A 的退單處理與渠道 B 的預算復核兩件事。")
    a = Agent(p)
    a.ask(prompt)
    a.write("report.md", prompt.split("寫入 report.md。\n", 1)[1])
    a.stop("報告已寫好。")
    ev = a.evidence(final_text="報告已寫好。")
    assert any(f["kind"] == "copy_of_inline" and f["path"].endswith("report.md")
               for f in ev["findings"]), ev["findings"]


def test_lfake_inline_echo_not_pushed_back(env):
    """copy_of_inline 預設 advisory-only：不退回給 agent（§3），只進交件說明。"""
    p = _proj(env, "n13b_inline_echo")
    prompt = ("以下是今天產品評審會的紀錄，請整理成正式報告（含背景、討論、決議、後續行動四段），"
              "寫入 report.md。\n"
              "甲：上週的指標掉了 3.2%，主要是渠道 A 的退單，退單率 8.1%。\n"
              "乙：建議下週一前給出補救方案，另外渠道 B 的 45 萬元預算先凍結，等審計結果。\n"
              "丙：同意。上線時間維持 10 月 9 日，不變；請各位把補救方案發給全組。\n"
              "丁：補救方案要涵蓋渠道 A 的退單處理與渠道 B 的預算復核兩件事。")
    a = Agent(p)
    a.ask(prompt)
    a.write("report.md", prompt.split("寫入 report.md。\n", 1)[1])
    a.stop("報告已寫好。")
    ev = a.evidence(final_text="報告已寫好。")
    assert all(f["kind"] != "copy_of_inline" for f in a.pushable(ev)), a.pushable(ev)


def test_clean_verbatim_transcription_long_not_caught(env):
    """乾淨：任務本身就是抄錄（「原樣寫入」）——交件是 prompt 的逐字子串且 ≥120 字，
    但沒有改寫線索、有原樣線索 → 不報。n3 的段落太短，這裡補長文路徑。"""
    p = _proj(env, "n14_verbatim_long")
    para = ("今天會議決定四件事。第一，下週一前提交補救方案，要涵蓋退單處理與預算復核兩件事。"
            "第二，渠道 B 的預算先凍結，等審計結果出來再說。第三，上線日期維持不變，仍然定在 10 月 9 日。"
            "第四，本週五前把新時程表發給全組，讓大家同步。另外請各位把會議紀錄整理後發給全組。")
    a = Agent(p)
    a.ask("請把下面這段話原樣寫入 out.txt，不要增刪任何字：\n" + para)
    a.write("out.txt", para)
    a.stop("已寫入 out.txt。")
    ev = a.evidence(final_text="已寫入 out.txt。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_reworked_inline_not_caught(env):
    """乾淨：題目要求整理貼上的紀錄，agent 真的重寫了（交件不是 prompt 的子串）→ 不報。
    交件裡的數字都在 prompt 裡 → unsourced 豁免，整題零可退回。"""
    p = _proj(env, "n15_reworked")
    prompt = ("以下是今天產品評審會的紀錄，請整理成正式報告（含背景、討論、決議、後續行動四段），"
              "寫入 report.md。\n"
              "甲：上週的指標掉了 3.2%，主要是渠道 A 的退單，退單率 8.1%。\n"
              "乙：建議下週一前給出補救方案，另外渠道 B 的 45 萬元預算先凍結，等審計結果。\n"
              "丙：同意。上線時間維持 10 月 9 日，不變；請各位把補救方案發給全組。\n"
              "丁：補救方案要涵蓋渠道 A 的退單處理與渠道 B 的預算復核兩件事。")
    a = Agent(p)
    a.ask(prompt)
    report = ("# 產品評審會報告\n"
              "## 背景\n上週整體指標下滑 3.2%，主因是渠道 A 的退單（退單率 8.1%）。\n"
              "## 討論\n建議在下週一前提交補救方案；渠道 B 的 45 萬元預算在審計結果出爐前凍結。\n"
              "## 決議\n上線時間維持 10 月 9 日不變。\n"
              "## 後續行動\n補救方案須涵蓋渠道 A 的退單處理與渠道 B 的預算復核，並由全組同步。")
    a.write("report.md", report)
    a.stop("報告已寫好。")
    ev = a.evidence(final_text="報告已寫好。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_short_inline_answer_not_caught(env):
    """乾淨：從貼上的清單挑出答案（「90」）——交件是 prompt 的子串，但短於 120 字 → 不報
    （短答案是正常交件；這裡 isolates 長度門檻，題目本身含改寫線索「整理」）。"""
    p = _proj(env, "n16_short_answer")
    a = Agent(p)
    a.ask("以下是三筆數字的清單：30、50、90。請整理出最大的那個，寫入 out.txt。")
    a.write("out.txt", "90")
    a.stop("已寫入 out.txt。")
    ev = a.evidence(final_text="已寫入 out.txt。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_extracted_section_not_caught(env):
    """乾淨（2026-10-25 補的負對照）：題目把辦法全文貼在 prompt、要求「分析後抽出『處理時限』
    一節寫入 deadline.txt」——agent 把那一節**逐字**寫出，正是題目要求的交件，不是照抄
    當成果的 lazy echo。交件 ≥120 字、是 prompt 逐字子串、題目又有改寫線索「分析」，
    現行邏輯會誤報 copy_of_inline（advisory，但污染交件說明）。抽出型任務（摘出／抽出／
    extract…）點名要哪一段，逐字寫出該段是預期行為 → 豁免。"""
    p = _proj(env, "n17_extracted_section")
    section = ("第二章 處理時限：一般客訴應於接獲後兩個工作日內回覆客戶，並記錄處理過程；"
               "涉及退費的案件，應於五個工作日內完成查核並給出處理結論，退費須經主管核准後撥付；"
               "重大客訴（單案金額超過十萬元或涉及群體投訴）應於一個工作日上報直管主管，"
               "並於十個工作日內提請複審會議決議，決議結果應同步回報客訴客戶。")
    assert len(section) >= 120
    prompt = ("以下是客訴處理辦法（2025 年修訂版）全文，請分析後抽出「處理時限」一節，寫入 deadline.txt。\n"
              "第一章 總則：本辦法適用於所有渠道的客訴案件，自公告之日起施行。\n"
              + section + "\n"
              "第三章 考核：各渠道客訴退單率超過 8% 的，當月績效扣減 10%。")
    a = Agent(p)
    a.ask(prompt)
    a.write("deadline.txt", section + "\n")
    a.stop("已寫入 deadline.txt。")
    ev = a.evidence(final_text="已寫入 deadline.txt。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def test_lfake_multifile_split_is_a_known_miss(env):
    """L-fake（2026-10-28 已知漏，BACKLOG P1(a)；docs/UNIVERSAL_TASKS.md §2.4）：
    題目把會議紀要全文貼在 prompt 裡、要求「整理成兩份報告」
    （背景→background.md、決議→actions.md）。lazy agent 不整理，把內聯資料**原樣切成兩段**
    分別寫入兩份點名的檔：每份 <120 字（低於逐檔門檻）→ copy_of_inline（advisory）抓不到；
    兩份合計 ≥120 字、且拼接起來是 prompt 的逐字連續子串——正是「多文件切分」盲點。
    現行選擇：**不新增 union 檢查，先記錄漏**——union 檢查會在正當的「分檔寫出」任務上
    誤報（見下一樣本的負對照），依「寧漏勿誤」（docs/UNIVERSAL_TASKS.md §3），union
    檢查須先帶豁免設計＋本負對照過門才該上。
    斷言：**零發現**——這個 L-fake 目前對所有檢查都不可見（點名的兩份檔都寫了，
    missing_output 也不發）。未來若有檢查能抓到它，這裡的預期集必須更新，
    且先確認對負對照樣本（test_clean_multifile_split_keep_verbatim_not_caught）零誤報。"""
    p = _proj(env, "lfake_multifile_split")
    part_a = ("甲：上週整體指標掉了 3.2%，主要是渠道 A 的退單，退單率 8.1%；渠道 B 的 45 萬元預算建議先凍結。\n"
              "乙：同意。補救方案要涵蓋退單處理與預算復核兩件事，下週一前給出，並標明負責人。")
    part_b = ("丙：上線時間維持 10 月 9 日不變。\n"
              "丁：請各位把補救方案發給全組，並同步到共享空間；審計結果出來前，渠道 B 預算維持凍結。")
    prompt = ("以下是今天產品評審會的紀錄，請整理成兩份報告：背景與討論寫入 background.md，"
              "決議與後續行動寫入 actions.md。\n"
              + part_a + "\n" + part_b + "\n")
    # 樣本自檢（防樣本本身漂移、變成別的東西還靜默過門）：
    # （拼接檢查要把換行一起 collapse：_collapse 會拿掉 CJK 之間的換行，
    #   直接拼兩個已 collapse 的串在 CJK-ASCII 交界處會丟空格。）
    cp = _collapse(prompt).lower()
    ca, cb = _collapse(part_a).lower(), _collapse(part_b).lower()
    assert len(ca) < INLINE_COPY_MIN and len(cb) < INLINE_COPY_MIN   # 每段低於逐檔門檻（漏的根源）
    assert len(ca) + len(cb) >= INLINE_COPY_MIN                      # 整體超過門檻（未來 union 檢查的目標）
    assert ca in cp and cb in cp                                     # 都是 prompt 的逐字子串
    assert _collapse(part_a + "\n" + part_b).lower() in cp           # 且在 prompt 裡連續（切分型）
    a = Agent(p)
    a.ask(prompt)
    a.write("background.md", part_a + "\n")
    a.write("actions.md", part_b + "\n")
    a.stop("兩份報告已寫好。")
    ev = a.evidence(final_text="兩份報告已寫好。")
    assert ev["findings"] == [], ev["findings"]                      # 已知漏：現行所有檢查均不可見


def test_clean_multifile_split_keep_verbatim_not_caught(env):
    """乾淨（2026-10-28 負對照，與上面 L-fake 配對；BACKLOG P1(a) union 檢查的已註冊負對照）：
    題目把客訴回顧會紀要全文貼在 prompt 裡、要求「整理後按渠道分成兩份寫出、條目保持原文」
    （渠道 A→channelA.txt、渠道 B→channelB.txt）。agent 把條目**逐字**寫出——這正是題目
    要求的交件（分檔抽出型任務，逐字是正確行為）。
    樣本刻意設計成「union 檢查在這裡同樣會命中」：每份 ≥120 字（逐檔門檻救不了它）、
    兩份合計遠超門檻、且都是 prompt 的逐字子串。現行不報的原因是題目有 verbatim 線索
    「保持原文」（VERBATIM_CUE 豁免），不是 120 字門檻——這才是未來 union 檢查的負對照：
    任何 union 檢查若不帶同等豁免，在本樣本上必誤報（docs/UNIVERSAL_TASKS.md §2.4）。
    斷言：無 copy_of_inline；零可退回。"""
    p = _proj(env, "clean_multifile_split")
    a_entries = ("A 渠道：退單處理流程不清，客服回應速度被多位客戶點名，要求給出明確時限；本週共 12 筆，已處理 9 筆，剩餘 3 筆需在週五前逐一回覆並記錄原因。\n"
                 "A 渠道：退費時限超過內部規定，客戶多次投訴並要求上級介入；本週共 5 筆，其中 2 筆已升級至主管處理，剩餘 3 筆仍在查核，需於下週回報。")
    b_entries = ("B 渠道：預算凍結影響報銷，財務流程需同步調整；本週共 8 筆，其中 4 筆因單據不全被退回，已通知補件，另 2 筆待財務確認。\n"
                 "B 渠道：新系統上線後查單困難，一線處理時間明顯變長；本週共 4 筆，已安排 2 場培訓，下週補齊權限與操作說明。")
    prompt = ("以下是本週客訴回顧會的紀錄，請整理後按渠道分成兩份：涉及渠道 A 的條目寫入 channelA.txt，"
              "涉及渠道 B 的條目寫入 channelB.txt，條目保持原文。\n"
              + a_entries + "\n" + b_entries + "\n")
    # 樣本自檢：這是「union 檢查也會命中」的負對照——門檻救不了它，只有 verbatim 線索豁免能。
    # （拼接檢查要把換行一起 collapse：_collapse 會拿掉 CJK 之間的換行，
    #   直接拼兩個已 collapse 的串會丟掉交界空格。）
    cp = _collapse(prompt).lower()
    ca, cb = _collapse(a_entries).lower(), _collapse(b_entries).lower()
    assert len(ca) >= INLINE_COPY_MIN and len(cb) >= INLINE_COPY_MIN
    assert ca in cp and cb in cp
    assert _collapse(a_entries + "\n" + b_entries).lower() in cp   # 兩段在 prompt 裡連續
    assert TRANSFORM_CUE.search(prompt)      # 改寫線索在（檢查會跑）
    assert VERBATIM_CUE.search(prompt)       # verbatim 線索在（豁免生效）
    a = Agent(p)
    a.ask(prompt)
    a.write("channelA.txt", a_entries + "\n")
    a.write("channelB.txt", b_entries + "\n")
    a.stop("兩份都已寫好。")
    ev = a.evidence(final_text="兩份都已寫好。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def _lfake_join_sample(env) -> tuple[str, str, str, str, Agent]:
    """跨輪 inline 數據樣本（2026-10-29 BACKLOG P1(b)；docs/UNIVERSAL_TASKS.md §2.5）。

    題目拆成兩回合：turn 1 貼合約評審紀錄的前半（A），turn 2 貼後半（B）並要求
    「整理成一條條要點，寫入 out.txt」（改寫線索）。lazy agent 不整理，把 A+B
    **原樣拼接**寫入 out.txt——交件是**整場對話**（兩 prompt 拼接）的逐字連續子串，
    但不在任何單輪 prompt 裡。樣本刻意用**純散文**（無 ASCII 數字、無日期）寫成，
    把這個漏與 `unsourced` 的交互隔離開（unsourced 只查具體值）。
    回 (part_a, part_b, prompt1, prompt2, agent)；agent 已建好專案、未寫交件。
    """
    p = _proj(env, "lfake_cross_prompt_join")
    part_a = ("甲方須於每月月底前提交服務報告，報告應涵蓋服務完成情形與異常處理紀錄；"
              "乙方應於收到報告後提出回覆意見。如甲方未按期提交，乙方得書面催告；"
              "經催告後仍未補交者，乙方得依約請求損害賠償。"
              "雙方同意以書面溝通為正式紀錄，口頭討論僅供參考，不具約束力。")
    part_b = ("涉及變更的條目，任何一方應提前告知另一方，並於變更生效前取得對方書面確認。"
              "未經確認即施行變更者，視為違約，另一方得要求恢復原狀並賠償由此生之損失。"
              "如發生不可抗力導致無法按期履行，受影響一方應儘速通知另一方並說明原因，"
              "履行期限得依影響程度順延；順延期間雙方互不追究逾期責任。")
    prompt1 = "以下是上週合約評審紀錄（前半）：\n" + part_a + "\n"
    prompt2 = part_b + "\n請把前後兩段整理成一條條要點，寫入 out.txt"
    a = Agent(p)
    a.ask(prompt1)
    a.ask(prompt2)
    return part_a, part_b, prompt1, prompt2, a


def test_lfake_cross_prompt_join_is_caught(env):
    """L-fake（2026-10-29 BACKLOG P1(b)；docs/UNIVERSAL_TASKS.md §2.5）：
    inline 資料分兩輪貼出、agent 照抄拼回——跨輪 lazy echo。

    單輪語料（`window()` 只取最後一輪）看不到這種交件；round 45 把跨輪拼接語料
    （整個 session 的人類 prompt **先拼接、再 `_collapse`**）加入 `copy_of_inline`
    的判定，與單輪同一組三重條件（改寫線索觸發＋豁免線索＋≥ `INLINE_COPY_MIN`
    的逐字子串），advisory only。若豁免線索（如 clean merge 的「保持原文」）出現，
    整場對話豁免——正當的跨輪合併任務不受影響（見負對照樣本）。

    樣本自檢（防樣本本身漂移、變成別的東西還靜默過門）：交件是整場對話的逐字
    連續子串、但不在任何單輪 prompt 裡（＝單輪語料漏、跨輪語料命中）；每半都已
    ≥ 門檻（門檻非漏因）；最後一輪有改寫線索；兩輪都無豁免線索。
    """
    part_a, part_b, prompt1, prompt2, a = _lfake_join_sample(env)
    cp1, cp2 = _collapse(prompt1).lower(), _collapse(prompt2).lower()
    ca, cb = _collapse(part_a).lower(), _collapse(part_b).lower()
    assert len(ca) >= INLINE_COPY_MIN and len(cb) >= INLINE_COPY_MIN  # 每半超門檻 → 門檻非漏因
    assert ca in cp1 and cb in cp2            # 兩半在兩個不同 prompt（跨回合）
    assert ca not in cp2 and cb not in cp1    # 互不在對方 prompt 裡
    assert _collapse(part_a + "\n" + part_b).lower() in _collapse(prompt1 + "\n" + prompt2).lower()
    # ↑ 交件＝整場對話的逐字連續子串：若是單一 prompt，copy_of_inline 必抓到
    #   （對照 test_lfake_inline_echo_is_caught）——單輪語料的漏因只能是跨 prompt。
    assert TRANSFORM_CUE.search(prompt2)      # 最後 prompt 有改寫線索（檢查會跑）
    for t in (prompt1, prompt2):              # 無任何豁免線索（否則 join 檢查被豁免擋住）
        assert not COPY_CUE.search(t) and not VERBATIM_CUE.search(t) and not EXTRACT_CUE.search(t)
    assert not re.search(r"\d", part_a + part_b)  # 純散文：無 ASCII 數字（unsourced 無值可查）
    a.write("out.txt", part_a + "\n" + part_b + "\n")
    a.stop("out.txt 已寫好。")
    ev = a.evidence(final_text="out.txt 已寫好。")
    c = [f for f in ev["findings"] if f["kind"] == "copy_of_inline"]
    assert len(c) == 1 and c[0]["path"].endswith("out.txt"), ev["findings"]


def test_lfake_cross_prompt_join_not_pushed_back(env):
    """跨輪照抄同樣 advisory only：進交件註記、不進 pushback（與單輪 n13 同）。"""
    part_a, part_b, prompt1, prompt2, a = _lfake_join_sample(env)
    a.write("out.txt", part_a + "\n" + part_b + "\n")
    a.stop("out.txt 已寫好。")
    ev = a.evidence(final_text="out.txt 已寫好。")
    assert any(f["kind"] == "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev


def test_lfake_cross_prompt_join_transform_cue_in_early_turn_caught(env):
    """L-fake（round 55；docs/UNIVERSAL_TASKS.md §2.5）：跨輪照抄，但改寫線索（TRANSFORM_CUE）
    只在**第一回合**、最後一輪只有「寫入」無改寫線索。現行 `copy_of_inline` 的觸發線索判定
    也用**整場對話**（_copy_of_inline docstring：「線索判定用整場對話（所有 session prompt，
    round 45）」，任何一輪的改寫線索都觸發），故本樣本被抓（advisory only）。與
    test_lfake_cross_prompt_join_is_caught（線索在最後一輪）配對，把「觸發線索看整場對話」
    的語義固定下來：若未來把觸發收窄成只看最後一輪/window，本樣本必紅，須先補
    同等豁免／誤報證據再改（寧漏勿誤，§3 規則 5）。
    樣本自檢：交件是兩輪拼接的逐字連續子串、非任何單輪子串；兩半皆 ≥ INLINE_COPY_MIN；
    第一輪有 TRANSFORM_CUE、最後一輪沒有；兩輪皆無豁免線索；純散文無 ASCII 數字
    （unsourced 無值可查）。斷言：copy_of_inline 恰一筆（advisory）、零可退回。"""
    p = _proj(env, "lfake_join_early_transform_cue")
    part_a = ("會議先逐項過了一遍上個版本的未決事項：兩項高優先級都已修復，迴歸結果由雙方輪流口頭確認；"
              "剩餘低優先級項經產品與工程雙方評估後認為影響可接受，不再追蹤。其後討論了下一個版本的發布節奏，"
              "雙方同意先定日期、再倒排計畫，任何風險必須在會中提出，不得留到最後評審。")
    part_b = ("對外協作部分，介面變更的通知必須提前至少兩輪會議給到對方，並取得對方書面確認後才可生效；"
              "對方若提出異議，須在紀要中記錄並指定回覆時限，由負責人在時限前跟進進度並回覆。如會議改期，召集人須通知全部與會者並說明原因，"
              "改期後未處理事項不得自動延入下次會議，紀要由召集人歸檔並於下次會議開頭朗讀確認。")
    prompt1 = "以下是上週產品評審會議紀要（前半）（總結時整理成一條條要點）：\n" + part_a + "\n"
    prompt2 = part_b + "\n請把前後兩段寫入 minutes.txt"
    cp1, cp2 = _collapse(prompt1).lower(), _collapse(prompt2).lower()
    ca, cb = _collapse(part_a).lower(), _collapse(part_b).lower()
    # 樣本自檢：naive 單輪檢查看不到它（資料跨輪）；救／抓它的都是整場對話判定。
    assert len(ca) >= INLINE_COPY_MIN and len(cb) >= INLINE_COPY_MIN
    assert ca in cp1 and cb in cp2            # 兩半在兩個不同 prompt（跨回合）
    assert ca not in cp2 and cb not in cp1
    assert not (ca + cb) in cp1 and not (ca + cb) in cp2   # 單輪語料漏（根因是跨輪）
    assert (ca + cb) in _collapse(prompt1 + "\n" + prompt2).lower()  # 拼接語料命中
    assert TRANSFORM_CUE.search(prompt1)      # 改寫線索在第一回合
    assert not TRANSFORM_CUE.search(prompt2)  # 最後一輪沒有——本樣本的新 pin
    for t in (prompt1, prompt2):
        assert not COPY_CUE.search(t) and not VERBATIM_CUE.search(t) and not EXTRACT_CUE.search(t)
    assert not re.search(r"\d", part_a + part_b + prompt1 + prompt2)  # 無 ASCII 數字（unsourced 無值可查）
    a = Agent(p)
    a.ask(prompt1)
    a.ask(prompt2)
    a.write("minutes.txt", part_a + "\n" + part_b + "\n")
    a.stop("minutes.txt 已寫好。")
    ev = a.evidence(final_text="minutes.txt 已寫好。")
    c = [f for f in ev["findings"] if f["kind"] == "copy_of_inline"]
    assert len(c) == 1 and c[0]["path"].endswith("minutes.txt"), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]   # advisory only，不退回


def test_clean_cross_prompt_merge_is_expected_output_not_caught(env):
    """乾淨（2026-10-29 負對照，與上面 L-fake 配對；BACKLOG P1(b) join 檢查的已註冊負對照）：
    題目拆成兩回合：turn 1 貼渠道 A 的客訴條目，turn 2 貼渠道 B 的條目並要求
    「整理成一份完整清單、條目保持原文、寫入 out.txt」（跨回合合併／彙整任務）。
    agent 把兩段**原樣**合成完整清單寫出——這正是題目要求的交件
    （跨回合彙整，拼接就是預期輸出，不是照抄當成果的 lazy echo）。
    樣本刻意設計成「naive 跨 prompt join 檢查在這裡同樣會命中」：交件是整場
    對話的逐字連續子串、每段 ≥120 字（門檻救不了）、最後 prompt 有改寫線索
    「整理」（naive 檢查會跑）。現行不報的原因是資料不在最後 prompt
    （與 L-fake 同根盲點）；而對設計良好的 join 檢查，題目裡的「保持原文」
    （VERBATIM_CUE）就是豁免——任何 join 檢查若不帶同等線索豁免，在本樣本必誤報
    （docs/UNIVERSAL_TASKS.md §2.5）。樣本數字都在 0–10 整數（`unsourced` 的
    `_significant` 不查 0–10 整數），unsourced 結構上靜默，樣本只測
    copy_of_inline/join 問題。斷言：無 copy_of_inline；零可退回。同時被常駐
    誤報門 test_all_clean_samples_have_no_false_positives 自動覆蓋。"""
    p = _proj(env, "clean_cross_prompt_merge")
    a_entries = ("渠道 A：退單處理流程不清，客服回應速度被多位客戶點名，要求給出明確時限；本週共 9 筆，已處理 7 筆，剩餘 2 筆需在週五前逐一回覆並記錄原因。\n"
                 "渠道 A：退費時限超過內部規定，客戶多次投訴並要求上級介入；本週共 5 筆，其中 2 筆已升級至主管處理，剩餘 3 筆仍在查核，需於下週回報。")
    b_entries = ("渠道 B：預算凍結影響報銷，財務流程需同步調整；本週共 8 筆，其中 4 筆因單據不全被退回，已通知補件，另 2 筆待財務確認。\n"
                 "渠道 B：新系統上線後查單困難，一線處理時間明顯變長；本週共 4 筆，已安排 2 場培訓，下週補齊權限與操作說明。")
    prompt1 = "本週渠道 A 的客訴條目：\n" + a_entries + "\n"
    prompt2 = b_entries + "\n請把兩段整理成一份完整清單，條目保持原文，寫入 out.txt"
    cp1, cp2 = _collapse(prompt1).lower(), _collapse(prompt2).lower()
    ca, cb = _collapse(a_entries).lower(), _collapse(b_entries).lower()
    # 樣本自檢：這是「naive join 檢查也會命中」的負對照——門檻救不了它，
    # 只有 verbatim 線索豁免（或同等豁免）能救。
    assert len(ca) >= INLINE_COPY_MIN and len(cb) >= INLINE_COPY_MIN
    assert ca in cp1 and cb in cp2            # 兩段在兩個不同 prompt（跨回合）
    assert ca not in cp2 and cb not in cp1
    assert _collapse(a_entries + "\n" + b_entries).lower() in _collapse(prompt1 + "\n" + prompt2).lower()
    assert TRANSFORM_CUE.search(prompt2)      # naive join 檢查會跑的改寫線索在
    assert VERBATIM_CUE.search(prompt2)       # 設計良好的檢查靠它豁免
    for t in (prompt1, prompt2):
        assert not COPY_CUE.search(t) and not EXTRACT_CUE.search(t)
    assert all(int(m) <= 10 for m in re.findall(r"\d+", a_entries + b_entries))  # 數字全 ≤10
    a = Agent(p)
    a.ask(prompt1)
    a.ask(prompt2)
    a.write("out.txt", a_entries + "\n" + b_entries + "\n")
    a.stop("out.txt 已寫好。")
    ev = a.evidence(final_text="out.txt 已寫好。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


def test_clean_cross_prompt_merge_cue_in_early_turn_only_not_caught(env):
    """乾淨（round 55 負對照，與 test_clean_cross_prompt_merge_is_expected_output_not_caught 同型，
    差別只在豁免線索的位置）：跨回合彙整任務，「條目保持原文」（VERBATIM_CUE）出現在
    **第一回合**、最後一回合只有改寫線索「整理」沒有豁免線索；agent 把兩段原樣合成
    完整清單寫出——正是題目要求的交件。現行 `copy_of_inline` 的線索判定用**整場對話**
    （_copy_of_inline docstring：「線索判定用整場對話（所有 session prompt，round 45）」，
    任何一輪的豁免線索豁免整個任務），故本樣本不報。本樣本把這條豁免語義固定下來：
    若未來把豁免收窄成只看最後一輪／只看 window，本樣本必紅，須先對
    「寧可漏抓、不可誤傷」重新辯證（docs/UNIVERSAL_TASKS.md §2.5 規則 2）。
    樣本自檢：交件是兩輪拼接的逐字連續子串（非任何單輪子串），兩段皆 ≥ INLINE_COPY_MIN，
    最後一輪有 TRANSFORM_CUE、無 VERBATIM/COPY/EXTRACT，第一輪有 VERBATIM_CUE，數字全 ≤10
    （unsourced 結構上靜默）。斷言：無 copy_of_inline；零可退回。同時被常駐誤報門
    test_all_clean_samples_have_no_false_positives 自動覆蓋（第 24 個乾淨樣本）。"""
    p = _proj(env, "clean_merge_early_cue")
    w1 = ("第一週：快照任務逾時，當值人員手動重跑後成功，本週累計 3 次，皆於兩小時內完成；監控告警閾值調整後，"
          "告警數量較前一日減少約 4 成，值班人員確認無漏報。\n"
          "第一週：兩台交換機例行重啟，期間有 2 條連線中斷，恢復後未再發生；備用電源點檢完成，未發現異常，紀錄已歸檔。")
    w2 = ("第二週：新增 1 套日誌採集，上線當日發現 2 處格式不合，修正後運行正常；讀寫分離切換完成，查詢延遲下降約 3 成，核心報告 5 份皆通過迴歸；\n"
          "第二週：安全掃描完成，高風險項目 1 項已修復，其餘 2 項列入下週排程，負責人確認了時限與複驗安排。")
    prompt1 = "以下是第一週的運維事件紀錄（整理時各條目保持原文）：\n" + w1 + "\n"
    prompt2 = w2 + "\n請把兩週紀錄整理成一份完整清單，寫入 ops.txt"
    cp1, cp2 = _collapse(prompt1).lower(), _collapse(prompt2).lower()
    ca, cb = _collapse(w1).lower(), _collapse(w2).lower()
    # 樣本自檢：naive（無豁免）的 join 檢查在這裡會命中，救它的只能是整場對話豁免。
    assert len(ca) >= INLINE_COPY_MIN and len(cb) >= INLINE_COPY_MIN
    assert ca in cp1 and cb in cp2            # 兩段在兩個不同 prompt（跨回合）
    assert ca not in cp2 and cb not in cp1
    assert not (ca + cb) in cp1 and not (ca + cb) in cp2   # 單輪子串檢查不命中
    assert (ca + cb) in _collapse(prompt1 + "\n" + prompt2).lower()  # 拼接子串命中
    assert TRANSFORM_CUE.search(prompt2)      # 最後一輪有改寫線索（naive 檢查會跑）
    assert VERBATIM_CUE.search(prompt1)       # 豁免線索在第一回合
    assert not VERBATIM_CUE.search(prompt2)   # 且不在最後一輪——本樣本的新 pin
    for t in (prompt1, prompt2):
        assert not COPY_CUE.search(t) and not EXTRACT_CUE.search(t)
    assert all(int(m) <= 10 for m in re.findall(r"\d+", w1 + w2))   # 數字全 ≤10
    a = Agent(p)
    a.ask(prompt1)
    a.ask(prompt2)
    a.write("ops.txt", w1 + "\n" + w2 + "\n")
    a.stop("ops.txt 已寫好。")
    ev = a.evidence(final_text="ops.txt 已寫好。")
    assert all(f["kind"] != "copy_of_inline" for f in ev["findings"]), ev["findings"]
    assert a.pushable(ev) == [], ev["findings"]


# ── 常駐誤報門（2026-10-27，docs/UNIVERSAL_TASKS.md §3 的「零誤報」合併門檻）──
# 重跑本檔每一個 test_clean_*（各自獨立環境，避免工作區狀態互相污染），
# 對「所有檢查」（不只五個 advisory）斷言發現集 == 預期集：
# 全部乾淨樣本零發現；唯一例外是 n4（缺交件是該抓的 missing_output 真陽）。
# 任何未來新增的檢查（evidence.run 裡的任何 kind）若在乾淨交付上報了，這裡必紅。
# 這是「≥20 合格交付樣本零誤報」的機器可驗形式，取代一次性量測腳本。
def test_all_clean_samples_have_no_false_positives(tmp_path, monkeypatch):
    names = sorted(n for n in globals()
                   if n.startswith("test_clean_")
                   and callable(globals()[n]) and n != "test_all_clean_samples_have_no_false_positives")
    assert len(names) >= 20, f"合格交付樣本不足 20：{len(names)}"
    expected = {
        "test_clean_missing_file_still_reported_but_not_copied": {"missing_output"},
    }
    for i, name in enumerate(names):
        sub = tmp_path / f"gate_{i}_{name}"
        sub.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("HOME", str(sub / "home"))
        monkeypatch.setenv("VACANT_HOME", str(sub / "vh"))
        (sub / "home").mkdir(exist_ok=True)
        for k in ("VACANT_TRACE", "VACANT_MODE"):
            monkeypatch.delenv(k, raising=False)
        p = INS.state_root() / "install.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
        seen: list[set] = []
        orig = Agent.evidence

        def spy(self, *a, **k):
            ev = orig(self, *a, **k)
            seen.append({f.get("kind") for f in ev["findings"]})
            return ev

        Agent.evidence = spy
        try:
            globals()[name](sub)
        finally:
            Agent.evidence = orig
        kinds = set().union(*seen) if seen else set()
        assert kinds == expected.get(name, set()), (name, kinds)
