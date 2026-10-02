"""工具的必填參數 `thought`（2026-10-02）：電視上「它在想」的來源。

擴充（`pi_ext/twin_ws_tools.ts`）只把 thought 追加到 `$VACANT_TWIN_THOUGHT_LOG`；過濾（LEAK、檔名、長度）
與轉成 `twin_say` 在主機側的 `twinagent.SayForwarder`。四種：有／沒有／含檔名／含觀眾原文 ≥8 字。
⚠ 本檔零模型呼叫、不跑 node（本機沒有 pi 的型別與 typebox）；TS 那一側用靜態檢查，真跑見
`evidence_gate_20261002/thought/`。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import polaroid as polaroidlib  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from ops.exhibit.twin import twinagent  # noqa: E402
from vacant_network.memory import assert_ks1_clean  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

TS = (ROOT / "ops/exhibit/twin/pi_ext/twin_ws_tools.ts").read_text(encoding="utf-8")
TRAITS = "我很怕麻煩，但對老朋友很念舊，最近一直想寫信給國小導師，而且總是慢慢來"


def _setup(tmp_path, lines):
    ev = tmp_path / "live.jsonl"
    ev.write_text(json.dumps({"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "R1",
                              "task_id": "twin:tw-1", "arm": "RUN-ON"}) + "\n", encoding="utf-8")
    tl = tmp_path / twinagent.THOUGHT_LOG_NAME
    tl.write_text("".join((l if isinstance(l, str) else json.dumps(l, ensure_ascii=False)) + "\n" for l in lines),
                  encoding="utf-8")
    f = twinagent.SayForwarder(tmp_path / "agent_stdout.log", ev, task_id="twin:tw-1", cell_id="tw-1",
                               originals=[TRAITS], thought_log=tl)
    f._pump()
    rows = [r for r in sidecarlib.read(sidecarlib.sidecar_path(ev)) if r["type"] == "twin_say"]
    return f, rows


def test_ts_declares_a_required_thought_on_all_three_tools_and_ks1_clean_description():
    assert TS.count("thought: Type.String({ description: THOUGHT_DESC })") == 3
    assert TS.count("logThought(params);") == 3
    m = re.search(r'const THOUGHT_DESC =\s*"([^"]+)"', TS)
    assert m and "繁體中文" in m.group(1) and "檔名" in m.group(1) and "40" in m.group(1)
    assert_ks1_clean(m.group(1))


def test_ts_thought_never_goes_into_the_step_log_and_never_fails_the_tool():
    body = re.search(r"function logStep.*?\n}\n", TS, re.S).group(0)
    assert "thought" not in body                       # twin_step 不帶內容
    lt = re.search(r"function logThought.*?\n}\n", TS, re.S).group(0)
    assert "try {" in lt and "catch" in lt             # 寫不進去不丟例外
    assert 'typeof params?.thought === "string"' in lt and "if (!t) return;" in lt   # 空的／缺的：不記
    assert "THOUGHT_LOG" in lt and "if (!THOUGHT_LOG) return;" in lt


def test_wrapper_exports_the_thought_log_with_the_python_constant():
    sh = (ROOT / "ops/exhibit/twin/twin_agent.sh").read_text(encoding="utf-8")
    assert f'VACANT_TWIN_THOUGHT_LOG="$RUN_DIR/{twinagent.THOUGHT_LOG_NAME}"' in sh


def test_a_clean_thought_becomes_a_twin_say(tmp_path):
    f, rows = _setup(tmp_path, [{"ts_ms": 1, "seq": 1, "thought": "我想先看看這個世界裡有什麼可以動手的地方。"}])
    assert [r["text"] for r in rows] == ["我想先看看這個世界裡有什麼可以動手的地方。"]
    assert rows[0]["cell_id"] == "tw-1" and rows[0]["run_id"] == "R1" and rows[0]["turn"] >= 1
    assert sidecarlib.validate(rows) == []
    assert (f.thoughts_in, f.thoughts_sent, f.thoughts_dropped) == (1, 1, 0)


def test_missing_or_empty_thought_makes_no_twin_say_and_is_not_counted_as_dropped(tmp_path):
    f, rows = _setup(tmp_path, [{"ts_ms": 1, "seq": 1}, {"ts_ms": 2, "seq": 2, "thought": ""},
                                {"ts_ms": 3, "seq": 3, "thought": "   "}, {"ts_ms": 4, "seq": 4, "thought": 7},
                                "not json at all"])
    assert rows == [] and (f.thoughts_in, f.thoughts_sent, f.thoughts_dropped) == (0, 0, 0)


def test_a_thought_with_a_filename_is_dropped_but_the_next_one_still_goes(tmp_path):
    f, rows = _setup(tmp_path, [{"thought": "我要去讀 尾段_418到447片.txt 看看。"},
                                {"thought": "我想再確認一下哪個地方有空位。"},
                                {"thought": "我要把想法寫進 PLAN.md 裡。"}])
    assert [r["text"] for r in rows] == ["我想再確認一下哪個地方有空位。"]
    assert (f.thoughts_in, f.thoughts_sent, f.thoughts_dropped, f.dropped_filename) == (3, 1, 2, 2)


def test_a_thought_copying_the_viewers_text_8_chars_or_more_is_dropped(tmp_path):
    f, rows = _setup(tmp_path, [{"thought": "他說：我很怕麻煩，但對老朋友很念舊，所以我想這樣做。"},
                                {"thought": "我很怕麻煩"},             # 5 字，低於 LEAK 視窗：不算抄
                                ])
    assert [r["text"] for r in rows] == ["我很怕麻煩"]
    assert f.dropped == 1 and f.thoughts_dropped == 1 and f.thoughts_sent == 1


def test_a_long_thought_is_cut_to_80_chars_with_the_truncated_flag(tmp_path):
    f, rows = _setup(tmp_path, [{"thought": "我" * 120}])
    assert len(rows[0]["text"]) == sidecarlib.SAY_MAX and rows[0]["truncated"] is True
    assert sidecarlib.validate(rows) == []


def test_without_a_thought_log_the_forwarder_behaves_as_before(tmp_path):
    ev = tmp_path / "live.jsonl"
    ev.write_text(json.dumps({"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "R1",
                              "task_id": "twin:tw-1", "arm": "RUN-ON"}) + "\n", encoding="utf-8")
    f = twinagent.SayForwarder(tmp_path / "agent_stdout.log", ev, task_id="twin:tw-1", cell_id="tw-1")
    f._pump()
    assert f.thought_log is None and f.thoughts_in == 0 and f.forwarded == 0


def test_the_thought_log_is_erased_with_the_run_dir(tmp_path):
    ws, rd = twinagent.paths_for(tmp_path, "sub-x")
    rd.mkdir(parents=True)
    ws.mkdir(parents=True)
    (rd / twinagent.THOUGHT_LOG_NAME).write_text('{"thought":"內容"}\n', encoding="utf-8")
    out = twinagent.erase_run_artifacts(tmp_path, "sub-x")
    assert out["problems"] == [] and not twinagent.run_artifacts_present(tmp_path, "sub-x")
    assert twinagent.THOUGHT_LOG_NAME in {e["what"] for e in out["erased"]}
