#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W2：opencode 的回合結束檢查不該在 `opencode run` 裡被跳過。

出貨狀態是 `const NONINTERACTIVE = process.argv.includes("run")` 擋住
`session.idle` 的 stop 分支，註解宣稱「`opencode run` 在第一個 idle 就結束，
回饋送不進去，所以只會多加延遲」。

遠端 A/B（opencode 1.18.33 + stub 模型，其餘逐項相同，只差那一行）：

    出貨狀態       perf {prompt:2, session_end:1}
                   chain {trace_genesis, prompt, session_closed}
                   delivery.md / delivery.json：無
    移除閘門       perf {prompt:2, stop:1, session_end:1}
                   chain {…, review:1}
                   delivery.md / delivery.json：有

所以那個註解講錯的是「檢查會不會跑」：**它不會跑**。而 `opencode run` 正是
`vacant do`、headless harness、還有評測批次驅動 agent 的方式。

⚠ **這一條不是「回饋送得到」。** 那對 A/B 的 stub 被打到 429 上限、agent 沒說完話
（交件說明寫「Final message: not available」），兩邊 prompt 數相同、stub 收到的是
同一批請求。量到的是「檢查會跑」。所以本檔只釘住「不再被跳過」與「非互動的旗標
有被記下來」，**不宣稱**非互動回合的退回能送達模型。

`tests/test_vrun_openai_stop_not_skipped.py` 驗這兩件（零模型呼叫、零 opencode）。
端到端那一次在 `ops/` 之外，跑在有 opencode 的機器上。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from vacant_network.adapters import agents as A  # noqa: E402

FAILED: list[str] = []
PASSED: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name + (" :: " + detail if detail else ""))


def t1_gate_is_gone() -> None:
    t = A.opencode_plugin_text()
    code = "\n".join(line for line in t.splitlines()
                     if not line.lstrip().startswith("//"))
    check("1 the NONINTERACTIVE gate is gone from the code",
          "NONINTERACTIVE" not in code,
          [line for line in code.splitlines() if "NONINTERACTIVE" in line][:1])
    check("1 the stop branch is unconditional on run mode",
          'event.type === "session.idle"' in code
          and 'session.idle" && !' not in code)
    check("1 the stop hook is still called",
          'ask("stop"' in code)
    check("1 the re-prompt path is still there",
          "client.session.prompt" in code)


def t2_guards_survived() -> None:
    """移除閘門不許順手移除別的保護。"""
    t = A.opencode_plugin_text()
    check("2 child sessions are still skipped",
          "__vacantChildSessions.has(id)" in t)
    check("2 one stop check per session at a time",
          "__vacantStopBusy.has(id)" in t and "__vacantStopBusy.add(id)" in t)
    check("2 the busy flag is released",
          "__vacantStopBusy.delete(id)" in t)
    check("2 session_end on dispose still runs",
          'ask("session_end"' in t)
    check("2 a failing re-prompt does not kill the agent",
          "catch (e)" in t)


def t3_run_mode_is_recorded() -> None:
    """非互動這個事實要看得見，否則人只能從缺漏的項目裡猜。"""
    t = A.opencode_plugin_text()
    check("3 run mode is detected", 'IS_RUN_MODE = process.argv.includes("run")' in t)
    check("3 run mode is sent to the hook",
          "noninteractive: IS_RUN_MODE" in t)
    from vacant_network.adapters import hook as H
    src = pathlib.Path(H.__file__).read_text(encoding="utf-8")
    check("3 the hook records it", 'payload.get("noninteractive")' in src)
    check("3 it lands in the zero record", 'z["noninteractive_run"] = True' in src)


def t4_other_agents_untouched() -> None:
    """本檔只動 opencode 的模板。別的 agent 的接線不該被順手改掉。"""
    from vacant_network.adapters.hook import EVENT_MAP
    check("4 opencode still maps stop", EVENT_MAP["opencode"].get("stop") == "stop")
    check("4 pi still maps stop", EVENT_MAP["pi"].get("stop") == "stop")
    check("4 claude still maps Stop", EVENT_MAP["claude"].get("Stop") == "stop")
    check("4 codex still maps Stop", EVENT_MAP["codex"].get("Stop") == "stop")
    t = A.opencode_plugin_text()
    check("4 the opencode template is still marked as generated",
          "remove with `vacant uninstall`" in t)


for fn in (t1_gate_is_gone, t2_guards_survived, t3_run_mode_is_recorded,
           t4_other_agents_untouched):
    try:
        fn()
    except Exception as e:
        FAILED.append(f"{fn.__name__} raised {type(e).__name__}: {e}")


def test_opencode_stop_check_not_skipped():
    assert not FAILED, "failures:\n  " + "\n  ".join(FAILED)


if __name__ == "__main__":
    print("=" * 74)
    print("W2 — the opencode stop check must not be skipped in `run` mode")
    print("=" * 74)
    for p in PASSED:
        print("  [OK ]", p)
    for f in FAILED:
        print("  [FAIL]", f)
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    sys.exit(1 if FAILED else 0)
