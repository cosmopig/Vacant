"""零設定的交件前檢視：把證據檢查的發現寫成送回 agent 的那幾行（英文）。

這支在架構裡承重什麼：`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md` §三。字句是規格的一部分——
改一個字就要重新確認 KS-1（`memory.assert_ks1_clean`：沒有責任／懲罰字眼）與「沒有行動者識別」
（`feedback.feedback_ks1_clean`）。常數在載入這支時就驗一次。

只說**紀錄顯示了什麼、要重做哪一段**；不說答案對不對、不說誰錯、不要求 agent 在最後的訊息加標題
（第 1 版有，拿掉：它會改變輸出格式，也讓模型用「承認沒驗證」代替修正）。

誠實邊界：
1. 引號裡的片段（值、指令、錯誤訊息、最後訊息裡的說法）來自工作區與 agent 自己的話，最多 80 字元並跳脫；
   過不了檢查的那一行換成固定的替代行並計數（`withheld`），不會安靜丟掉。
2. 這些字句只在 L-fake（假模型照劇本回應）量過「送得到、會照做」；真模型會不會照做，是評測要量的。
"""
from __future__ import annotations

import json
from typing import Any

from ..memory import KS1Violation, assert_ks1_clean
from .feedback import MAX_LINES, REVIEW_HEADER, KS1FeedbackError, feedback_ks1_clean

PERSONA = ("Take the role of a careful reviewer who checks the draft against the materials given "
           "for the task. Redo only the parts listed below; leave everything else as it is.")
FOOTER = "This review lists what the record shows; it does not say whether the answer is right."
WITHHELD = "- a point was withheld (wording check)"
INSPECT = "inspect them with head, or load them in code"

for _t in (REVIEW_HEADER, PERSONA, FOOTER, WITHHELD):
    assert_ks1_clean(_t)

#: 退回的先後：要求的檔不存在、失敗的步驟、測試說法最先（最確定），值其次，點名沒讀最後
ORDER = {"missing_output": 0, "failed_step": 1, "test_claim": 2, "unsourced": 3, "unread": 4}


def q(s: Any, n: int = 80) -> str:
    """引號裡的片段：最多 n 字元、JSON 跳脫（換行、引號不會把一行拆開或提早結束）。"""
    t = str(s)
    if len(t) > n:
        t = t[: n - 1] + "…"
    return json.dumps(t, ensure_ascii=False)[1:-1]


def line_for(f: dict[str, Any]) -> str:
    k = f["kind"]
    if k == "unsourced":
        tail = ""
        if f.get("unread_attach"):
            tail = " Given files not opened so far: " + ", ".join(f["unread_attach"][:6]) + "."
        if f.get("single_answer"):
            return (f"- {f['path']}: \"{q(f['value'])}\" was not found in anything this task read "
                    f"or computed. Recompute it from the given files in a command ({INSPECT}) and "
                    f"write only the recomputed value to {f['path']}.{tail}")
        return (f"- {f['path']} line {f['line']}: \"{q(f['value'])}\" was not found in anything "
                f"this task read or computed. Recompute it from the given files ({INSPECT}), or "
                f"mark it as an assumption on that line.{tail}")
    if k == "missing_output":
        return (f"- The request asks for {q(f.get('asked') or f['path'])}, but it does not exist. "
                f"Finish the task and write it.")
    if k == "unread":
        return (f"- {f['path']} was named in the task but was not opened in the recorded steps. "
                f"Inspect it (for example with head, or load it in code) and redo the parts that "
                f"depend on it.")
    if k == "test_claim":
        sub = f.get("sub")
        if sub == "failed":
            return (f"- The final message says \"{q(f['quote'])}\", but the last test run (step "
                    f"{f['step']}: {q(f['cmd'], 60)}) failed. Fix it and re-run, or report that it "
                    f"fails.")
        if sub == "stale":
            return (f"- The final message says \"{q(f['quote'])}\", but {f['path']} changed at step "
                    f"{f['step']} after the last passing run (step {f['last_pass']}). Re-run the "
                    f"tests and report the result.")
        return (f"- The final message says \"{q(f['quote'])}\", but no test or build command ran in "
                f"the recorded steps. Run it and report the actual result.")
    if k == "failed_step":
        return (f"- Step {f['step']} ({q(f['cmd'], 60)}) failed: \"{q(f['error'])}\". The "
                f"deliverable was written after it without that output. Fix and re-run it, or say "
                f"in the final message that it failed.")
    raise ValueError(f"unknown finding kind {k!r}")


def render(findings: list[dict[str, Any]], *, actor_tokens: set[str] | None = None,
           previous_open: set[str] | None = None) -> tuple[str, int]:
    """發現 → 送回 agent 的整段文字；回 `(文字, 被換成替代行的行數)`。
    `previous_open`：上一回合還開著的 finding_id——這一次仍在的標 `(still open)`。"""
    toks = actor_tokens or set()
    prev = previous_open or set()
    fs = sorted(findings, key=lambda f: (ORDER.get(f["kind"], 9), f.get("path") or "",
                                         f.get("line") or 0))
    room = MAX_LINES - 3
    body, withheld = [], 0
    for f in fs[:room] if len(fs) <= room else fs[:room - 1]:
        ln = line_for(f)
        if f.get("finding_id") in prev:
            ln += "  (still open)"
        try:
            feedback_ks1_clean(ln, toks)
        except (KS1FeedbackError, ValueError, KS1Violation):
            ln, withheld = WITHHELD, withheld + 1
        body.append(ln)
    if len(fs) > room:
        body.append(f"- … and {len(fs) - (room - 1)} more points of the same kinds.")
    return "\n".join([REVIEW_HEADER, PERSONA, *body, FOOTER]), withheld
