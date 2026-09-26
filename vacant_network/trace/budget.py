"""零設定 v3：回合預算快用完時，提醒 agent 先把要求的檔寫出來。

這支在架構裡承重什麼：`decisions/DECISION_20260926_ZERO_CONFIG_V3.md` §二（v3-2）。付費批次（2026-09-25）
82 個失敗裡 55 個是「沒交」——agent 被回合上限切斷時還沒寫答案檔，Vacant 的交件前檢查只在 agent 自己說
做完時跑，永遠輪不到（`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md` §七 問題一）。這裡把同一條「要求寫出的檔
不存在」搬到回合結束時：

- pi 擴充自己數回合（和回合上限的計數同一種數法），**只在 agent 的系統提示裡寫了回合上限**、只剩最後 2 或
  1 回合、這一回合有執行工具時才問這裡；這裡再確認：沒有契約、模式是 `evidence`、要求的檔（人打的話裡要求
  寫出的、不是給的資料）現在不在工作區裡、這個要求之內還沒提醒過 2 次、這一回合還沒提醒過。
- 提醒搭在**下一通本來就要送出的請求**上（pi `turn_end` 的草稿），不多一通模型呼叫、不超過人設的上限。
- 沒有寫明上限（一般互動使用）⇒ 這裡根本不會被問，模型收到的請求和沒裝時逐位元組相同。

誠實邊界：
1. 只看檔在不在，不看內容、不引用任何值——Vacant 不替 agent 選答案。
2. 上限是從 agent 看得到的系統提示讀出來的（`agents.BUDGET_RE_SRC`）；沒寫明的上限（例如花費上限、時間上限）
   看不到，這一條就不作用。一般互動使用裡幾乎不會觸發：它幫的是有預算上限的情境（評測、CI、headless 批次）。
3. 模型收到提醒之後會不會寫、寫的對不對，是評測要量的；付費批次的模擬顯示太早提醒會讓模型提早停下來
   （寫完就停），所以只在最後 2 回合。
"""
from __future__ import annotations

import os
from typing import Any

from . import capture
from .recorder import Recorder

MAX_NUDGES = 2          # 一個要求之內最多提醒幾次（最後 2 回合各一次）
NUDGE_TURNS_LEFT = (1, 2)


def missing_outputs(rec: Recorder, platform: str, session: str) -> tuple[int, list[tuple[str, str]]]:
    """(這一回合的起點, [(相對路徑, 人寫的樣子)])：人要求寫出、現在不在工作區裡的檔（給的資料不算）。"""
    from .evidence import Evidence
    ev = Evidence(rec, platform=platform, session=session)
    start, texts, steps = ev.window()
    outs = ev.requested_outputs(texts)
    if not outs:
        return start, []
    start_idx = steps[0].pre_index if steps and steps[0].pre_index else ev.tr.initial
    named, in_dirs = ev.materials(texts, start_idx)
    given = set(named) | set(in_dirs)
    missing = [(rel, raw) for rel, raw in outs
               if rel not in given and not os.path.exists(rec.workspace / rel)]
    return start, missing


def turn_check(agent: str, session_id: str | None, cwd: str | None, turn: Any, budget: Any, *,
               mode: str) -> tuple[str, str, dict[str, Any]]:
    """回 `(action, reason, record)`；`action` 是 `continue`（附上提醒）或 `allow`（什麼都不送）。"""
    try:
        turn_i, budget_i = int(turn), int(budget)
    except (TypeError, ValueError):
        return "allow", "", {"nudge": {"why": "no stated budget"}}
    left = budget_i - turn_i
    if mode != "evidence" or left not in NUDGE_TURNS_LEFT:
        return "allow", "", {"nudge": {"why": f"mode={mode}, turns left={left}"}}
    ws = capture.workspace_for(cwd, None)
    if ws is None:
        return "allow", "", {}
    rec = Recorder(ws)
    if not rec.chain_path.is_file():
        return "allow", "", {"nudge": {"why": "nothing recorded"}}
    session = str(session_id or "unknown")
    key = f"{agent}:{session}"
    start, missing = missing_outputs(rec, agent, session)
    if not missing:
        return "allow", "", {"nudge": {"why": "requested outputs exist or none asked"}}
    sent = [e for e in rec.events() if e.get("type") == "nudge"      # events(): payload 攤平在最上層
            and e.get("session") == key and e.get("window_start") == start]
    if len(sent) >= MAX_NUDGES or any(e.get("turn") == turn_i for e in sent):
        return "allow", "", {"nudge": {"why": "already reminded"}}
    from . import review
    from .stopcheck import _actor_tokens
    text, withheld = review.render_nudge([raw for _, raw in missing], turns_left=left,
                                         budget=budget_i, actor_tokens=_actor_tokens(rec))
    rec.append("nudge", {"session": key, "window_start": start, "turn": turn_i, "budget": budget_i,
                         "paths": [rel for rel, _ in missing], "withheld": withheld})
    return "continue", text, {"nudge": {"sent": len(missing), "turn": turn_i, "budget": budget_i}}
