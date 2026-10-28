"""`vacant trace show`（round 27 dogfood：在本機大專案上實跑找到兩處摩擦）。

1. 檔案改動觀察被永久關掉之後（一次增量掃描超過 8s 掛鉤時限 ⇒ recorder 關掃描，
   這是誠實邊界：寧可照實記「沒觀察到」也不擋 agent），`trace blame` 每一筆都回
   unattributable，但 `trace show` 的步驟視圖完全正常、看不出來——coverage 事件被
   靜默丟掉。病歷的主視圖必須把「觀察已停用」這個狀態寫出來（只在 blame 頁的
   小字裡有，等于沒有）。
2. 本機病歷 1900+ 步；看最近幾步只能 `vacant trace show | tail`。加 `--tail N`
   （只影響人的視圖；`--json` 仍是全量記錄）。
3. 本專案病歷 4062 個 bash 步、4055 個沒有歸屬寫入，`trace show` 印出的行是空的
   ——行沒有內容、看不出那步做了什麼（第 92 輪 dogfood）。工具輸入（實際做了什麼）
   存在物件庫裡；沒有歸屬寫入的步，show 印它的一行預覽。blob 被 gc 掉就退回空白行，
   `show` 永遠不因這個失敗（本專案 5094 個輸入 blob 已有 4930 個被 gc）。
4. 步的視圖行沒有「什麼時候」也沒有「花了多久」——兩者在記錄裡都有（`ts_ms`／`wall_ms`），
   要看只能轉 `--json` 自己換算（round 122 dogfood）。人看的視圖直接印本地時間與耗時；
   舊條目缺欄位（本專案 41/6816 步沒有 `wall_ms`）就省掉該段，不崩潰。
5. 本專案病歷 7000+ 步：看某一個工作階段／只看失敗步只能整卷翻（round 127 dogfood）。
   加 `--session PREFIX`（前綴比對；專案層事件沒有工作階段、不進這個視圖、照實報告
   濾掉了幾筆）與 `--errors`（只看失敗步）；`--json` 仍是全量記錄。
"""
from __future__ import annotations

import argparse
import json
import re

import pytest

from vacant_network.intake import contract as C
from vacant_network.intake import keys
from vacant_network.trace import cli
from vacant_network.trace import recorder as R

SALES = "id,amount\n1,10\n2,20\n3,30\n"


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    p = tmp_path / "proj"
    (p / "data").mkdir(parents=True)
    (p / "data" / "sales.csv").write_text(SALES)
    return p, R.Recorder(p)


def _step(rec: R.Recorder, sid: str, tool: str = "bash", actor: R.Actor | None = None):
    actor = actor or R.Actor("pi", "s1")
    rec.pre(sid, actor, tool, {})
    return rec.post(sid, actor, tool, {}, "")


def _args(**kw) -> argparse.Namespace:
    base = dict(contract=None, json=False, tail=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_show_surfaces_disabled_file_change_observation(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    # recorder 的真實停用路徑（recorder.py `_disable_scan`）就是這個事件
    rec._append("coverage", {"scan_disabled": "an incremental scan passed 8s"})
    _step(rec, "s2")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    line = next((l for l in out.splitlines() if "coverage" in l), None)
    assert line is not None, f"coverage state not surfaced in trace show:\n{out}"
    assert "disabled" in line
    assert "an incremental scan passed 8s" in line
    # 這是**目前狀態**：要印在步驟之前，而不是埋在流中間
    assert out.index(line) < out.index("pi:main")


def test_show_tail_limits_to_last_steps(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    for i in range(1, 5):
        _step(rec, f"s{i}")
    assert cli.cmd_show(_args(tail=2)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 2
    assert cli.cmd_show(_args(tail=10)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 4


def test_show_tail_keeps_gap_context_after_first_shown_step(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    rec._append("unrecorded_change", {"changes": [{"kind": "modify", "path": "data/sales.csv"}],
                                      "n": 1, "observed_at": "post_tool"})
    _step(rec, "s2")
    _step(rec, "s3")
    assert cli.cmd_show(_args(tail=2)) == 0
    out = capsys.readouterr().out
    assert "GAP" in out                      # s2 之前的缺口：在顯示窗口內，保留
    assert "pi:main" in out


def test_show_tail_rejects_zero(proj, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    with pytest.raises(SystemExit, match="--tail"):
        cli.cmd_show(_args(tail=0))


def test_show_prints_input_preview_when_step_wrote_nothing(proj, capsys, monkeypatch):
    """沒有歸屬寫入的步（bash 99.8%、read 99.7%）：行必須有內容——工具輸入的一行預覽。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("b1", actor, "bash", {"command": "echo hello"})
    rec.post("b1", actor, "bash", {"command": "echo hello"}, "hello\n")
    rec.pre("r1", actor, "read", {"path": "data/sales.csv"})
    rec.post("r1", actor, "read", {"path": "data/sales.csv"}, "")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "echo hello" in bash_line, f"bash step printed no content:\n{out}"
    read_line = next(l for l in out.splitlines() if " read " in l)
    assert "data/sales.csv" in read_line, f"read step printed no content:\n{out}"


def test_show_input_preview_truncates_long_input(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    cmd = "echo " + "x" * 300
    rec.pre("b1", actor, "bash", {"command": cmd})
    rec.post("b1", actor, "bash", {"command": cmd}, "")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "x" * 100 not in bash_line           # 不整段貼進來
    assert "…" in bash_line                     # 截斷要看得出


def test_show_survives_gc_of_the_input_blob(proj, capsys, monkeypatch):
    """gc 會把 blob 刪掉（本專案歷史步 96% 的輸入 blob 已不在）：show 退回空白預覽，
    絕不因此失敗。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("b1", actor, "bash", {"command": "echo hello"})
    rec.post("b1", actor, "bash", {"command": "echo hello"}, "hello\n")
    sha = next(e["input_blob"] for e in rec.events() if e.get("type") == "step")
    rec.blobs.path(sha).unlink()                # 模擬 gc
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert "echo hello" not in bash_line        # blob 不在 ⇒ 空白，不假裝還有


def test_show_names_the_workspace(proj, capsys, monkeypatch):
    """round 107 dogfood：步驟視圖不說自己是哪個專案的病歷——在錯的 cwd 跑會靜默看到
    別專案的步（no-trace 訊息、verify、dashboard 都帶專案名；show 主視圖沒有）。
    視圖首行必須是專案路徑，看的人才知道這是谁的病歷。"""
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    first = out.splitlines()[0]
    assert str(p) in first, f"trace show does not name its workspace:\n{out}"


def test_show_prints_the_error_preview_of_a_failed_step(proj, capsys, monkeypatch):
    """round 117 dogfood：失敗步的 `trace show` 行只有一句 `error: tool reported an error`，
    真正的原因在 blob（會 gc）。入口裡留了短預覽，show 必須印出來。"""
    p, rec = proj
    monkeypatch.chdir(p)
    rec.pre("s1", R.Actor("pi", "s1"), "bash", {})
    rec.post("s1", R.Actor("pi", "s1"), "bash", {},
             "collected 3 items\nFAILED tests/test_x.py::test_y\nValueError: boom\n",
             error="tool reported an error")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    assert "error: tool reported an error" in out
    assert "[out: ValueError: boom]" in out, f"preview not shown:\n{out}"


def test_show_prints_no_preview_for_a_clean_step(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    assert "[out:" not in out and "error:" not in out


def test_show_prints_step_time_and_duration(proj, capsys, monkeypatch):
    """round 122 dogfood：步的視圖行沒有「什麼時候」也沒有「花了多久」——兩者在記錄裡都有
    （`ts_ms`／`wall_ms`），要看只能轉 `--json` 自己換算。人看的視圖直接印出來。
    時區是本地時間（給人的視圖，不是 wire 格式）。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("b1", actor, "bash", {"command": "echo hello"})
    rec.post("b1", actor, "bash", {"command": "echo hello"}, "hello\n")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    bash_line = next(l for l in out.splitlines() if "bash" in l)
    assert re.search(r"\b\d{2}:\d{2}:\d{2}\b", bash_line), f"no time on step line:\n{out}"
    assert re.search(r"\(\d+ms\)", bash_line), f"no duration on step line:\n{out}"


def test_show_time_survives_missing_fields(proj, capsys, monkeypatch):
    """舊條目可能沒有 `wall_ms`（本專案 41/6816 步）或 `ts_ms`：行照印、缺哪個省哪個，
    不崩潰、不印 None。"""
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    assert cli.cmd_show(_args()) == 0
    out = capsys.readouterr().out
    assert "None" not in out
    step_line = next(l for l in out.splitlines() if "bash" in l)
    assert re.search(r"\b\d{2}:\d{2}:\d{2}\b", step_line)   # ts_ms 現在一定有


def test_fmt_clock_and_dur_unit():
    assert cli._fmt_clock(None) == ""
    assert cli._fmt_clock(0) == "" or re.fullmatch(r"\d{2}:\d{2}:\d{2}", cli._fmt_clock(0))
    assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", cli._fmt_clock(1793141380703))
    assert cli._fmt_dur(None) == ""                          # 舊條目沒有 wall_ms
    assert cli._fmt_dur("") == ""
    assert cli._fmt_dur(0) == "0ms"
    assert cli._fmt_dur(737) == "737ms"
    assert cli._fmt_dur(12000) == "12s"
    assert cli._fmt_dur(12400) == "12.4s"
    assert cli._fmt_dur(123000) == "2m03s"


def test_show_session_filter_keeps_only_that_session(proj, capsys, monkeypatch):
    """兩個工作階段的步混在一起：`--session` 前綴只留一個。"""
    p, rec = proj
    monkeypatch.chdir(p)
    a1, a2 = R.Actor("pi", "01a1"), R.Actor("pi", "01a2")
    rec.pre("b1", a1, "bash", {}); rec.post("b1", a1, "bash", {}, "")
    rec.pre("b2", a2, "bash", {}); rec.post("b2", a2, "bash", {}, "")
    rec.pre("b3", a1, "bash", {}); rec.post("b3", a1, "bash", {}, "")
    assert cli.cmd_show(_args(session="01a1")) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 2
    assert cli.cmd_show(_args(session="01a2")) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 1


def test_show_session_no_match_lists_recent_sessions(proj, monkeypatch):
    """前綴打錯時不給空白視圖：非零退出、列出最近的工作階段，不用 `--json` 自己猜。"""
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    with pytest.raises(SystemExit) as ex:
        cli.cmd_show(_args(session="nope"))
    msg = str(ex.value)
    assert "no session" in msg
    assert "'nope'" in msg                 # 說清楚是哪個前綴沒找到
    assert "s1" in msg                     # 指路：最近的工作階段列出來了


def test_show_session_reports_hidden_project_level_entries(proj, capsys, monkeypatch):
    """專案層事件（沒有工作階段）被濾掉時照實報告，不靜默丟掉。"""
    p, rec = proj
    monkeypatch.chdir(p)
    rec._append("coverage", {"scan_disabled": "an incremental scan passed 8s"})
    _step(rec, "s1")
    assert cli.cmd_show(_args(session="s1")) == 0
    out = capsys.readouterr().out
    # 兩筆沒有工作階段：trace_genesis 與那筆 coverage
    assert "2 project-level entries not shown" in out


def test_show_session_treats_prefixed_and_plain_as_one(proj, capsys, monkeypatch):
    """同一個工作階段的兩種歷史寫法要算同一個視圖：step 事件裸寫 session、review
    事件帶 `pi:` 前綴（本專案實際數據：128 筆 review 全是 `pi:<uuid>`）。"""
    p, rec = proj
    monkeypatch.chdir(p)
    a = R.Actor("pi", "abc123")
    rec.pre("b1", a, "bash", {}); rec.post("b1", a, "bash", {}, "")
    rec._append("review", {"action": "allow", "session": "pi:abc123", "mode": "evidence"})
    assert cli.cmd_show(_args(session="abc123")) == 0
    out = capsys.readouterr().out
    # 濾掉的只有 trace_genesis（1 筆）：`pi:abc123` 的 review 被算進同一個視圖
    assert "1 project-level entries not shown" in out


def test_show_session_degenerate_prefix_matches_nothing(proj, monkeypatch):
    """`--session pi:` 這種只有前綴沒有 id 的退化輸入：不算匹配，給「找不到」而非全量。"""
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    with pytest.raises(SystemExit) as ex:
        cli.cmd_show(_args(session="pi:"))
    assert "no session" in str(ex.value)


def test_show_errors_only_failed_steps(proj, capsys, monkeypatch):
    """`--errors` 只留失敗步；沒有失敗步是合法的空結果（rc 0），不是錯。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("ok1", actor, "bash", {}); rec.post("ok1", actor, "bash", {}, "")
    rec.pre("bad1", actor, "bash", {})
    rec.post("bad1", actor, "bash", {}, "ValueError: boom\n", error="tool reported an error")
    rec.pre("ok2", actor, "bash", {}); rec.post("ok2", actor, "bash", {}, "")
    assert cli.cmd_show(_args(errors=True)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 1
    assert "ValueError: boom" in out


def test_show_errors_none_is_an_empty_result_not_an_error(proj, capsys, monkeypatch):
    p, rec = proj
    monkeypatch.chdir(p)
    _step(rec, "s1")
    assert cli.cmd_show(_args(errors=True)) == 0
    out = capsys.readouterr().out
    assert "no failed steps in this view" in out


def test_show_session_and_tail_compose(proj, capsys, monkeypatch):
    """`--tail` 數的是過濾之後的步：該工作階段的最後 N 步。"""
    p, rec = proj
    monkeypatch.chdir(p)
    a1, a2 = R.Actor("pi", "s1"), R.Actor("pi", "s2")
    for i in range(4):
        rec.pre(f"a{i}", a1, "bash", {}); rec.post(f"a{i}", a1, "bash", {}, "")
    rec.pre("b0", a2, "bash", {}); rec.post("b0", a2, "bash", {}, "")
    assert cli.cmd_show(_args(session="s1", tail=2)) == 0
    out = capsys.readouterr().out
    step_lines = [l for l in out.splitlines() if "pi:main" in l and "bash" in l]
    assert len(step_lines) == 2


def test_show_json_ignores_session_and_errors(proj, monkeypatch, capsys):
    """`--json` 是全量記錄：視圖參數（session/errors）不影響它，和 `--tail` 同一約束。"""
    p, rec = proj
    monkeypatch.chdir(p)
    actor = R.Actor("pi", "s1")
    rec.pre("ok1", actor, "bash", {}); rec.post("ok1", actor, "bash", {}, "")
    rec.pre("bad1", actor, "bash", {})
    rec.post("bad1", actor, "bash", {}, "x", error="tool reported an error")
    assert cli.cmd_show(_args(json=True, session="s1", errors=True)) == 0
    evs = json.loads(capsys.readouterr().out)
    steps = [e for e in evs if e.get("type") == "step"]
    assert len(steps) == 2                    # 兩步都在，未被視圖參數濾掉


def test_show_json_ignores_tail(proj, monkeypatch, capsys):
    p, rec = proj
    monkeypatch.chdir(p)
    for i in range(1, 4):
        _step(rec, f"s{i}")
    assert cli.cmd_show(_args(json=True, tail=1)) == 0
    evs = json.loads(capsys.readouterr().out)
    steps = [e for e in evs if e.get("type") == "step"]
    assert len(steps) == 3                    # --json 是全量記錄，不受視圖參數影響
