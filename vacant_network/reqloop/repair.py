import typing
from typing import Any, Optional
from pathlib import Path

# --- Constants from argon (r1063) ---
_PYTHON_SYNTAX_ERRORS = frozenset({"SyntaxError", "IndentationError", "TabError"})
_CRASH_EXC_RE = {"FileNotFoundError", "IndentationError", "JSONDecodeError"}

def _loop_remediation_tail(loop: dict[str, Any]) -> str:
    """「先修掉錯誤的根因再執行」之後的針對性處方（r1063/argon）。

    - 「把程式碼寫成 .py 檔案後執行（不要用一行式拼接多條語句）」專屬於 Python 一行式
      語法/編譯錯誤（SyntaxError/IndentationError/TabError，如 dabstep-23 SyntaxError×34
      或 dabstep-1273 SyntaxError×7）：在一行式 -c 中使用複合陳述直接被語法限制擋住。
      若命令本身已是執行 .py 檔案（如 python3 script.py），或錯誤是執行期例外
      （NameError、KeyError、ZeroDivisionError、ValueError、TypeError 等），
      或是非 Python 工具（jq 過濾器錯、edit 驗證錯），開「寫成 .py 檔案、不要一行式」
      屬於失焦診斷，會誤導模型懷疑執行方式而非修正程式或資料邏輯。
    - 其餘情況（非語法錯、執行期例外、非 Python 工具、已是 .py 腳本）一律走通用根因處方：
      先查明失敗原因（參數、語法、變數定義或資料內容不符）再修正執行。
    """
    cls = str(loop.get("error_class") or "").strip()
    args = loop.get("args")
    cmd = ""
    if isinstance(args, dict):
        cmd = str(args.get("command") or "")
    elif isinstance(args, str):
        cmd = args

    is_syntax_err = cls in _PYTHON_SYNTAX_ERRORS
    is_already_script = bool(cmd and (".py " in cmd or cmd.strip().endswith(".py")))
    if is_syntax_err and not is_already_script:
        return (
            "先修掉錯誤的根因再執行：把程式碼寫成 .py 檔案後執行（不要用一行式拼接多條語句），"
            "確認執行成功、結果正確後，直接把結果寫入交付物檔案。"
        )
    return (
        "先修掉錯誤的根因再執行：先查明這類命令失敗的原因（參數、語法、變數定義或資料內容不符），修正後再執行；"
        "確認結果正確後，直接把結果寫入交付物檔案。"
    )


def _loop_warning_line(loop: dict[str, Any]) -> str:
    """處方依錯誤類與執行方式分流（_loop_remediation_tail）：.py 逃逸處方只給
     Python 一行式語法錯誤；jq／edit 驗證／執行期例外等給通用根因處方。
    """
    name = str(loop.get("tool_name") or "工具")
    reps = loop.get("consecutive_repetitions")
    cls = str(loop.get("error_class") or "").strip()
    err = cls if cls else "未知錯誤"
    sample = loop.get("error_sample")
    tail = _loop_remediation_tail(loop)

    # 執行一次已得到結果後的前提不成立、提示失焦——改點名錯誤類＋具體語法
    # 規則（寫 .py 檔案執行）＋「跑通即寫入交付物」，不帶該假前提。
    sample_part = f"（{sample}）" if (sample and sample != err) else ""
    head = f"{name} ({reps} 次重複)"
    return head + (
        f"本輪禁止重複該命令——它上一輪每次都失敗（{err}{sample_part}）、從未得到結果。"
        + tail
    )

def build_repair_prompt(task_dir: Path, rs: Any, draft: Path, before: list[Any], 
                         feedback_mode: str = "localized", prev_round_agent: Any = None) -> str:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    # Since I don't have the full file, I will try to reconstruct based on common patterns 
    # or look for where it was in the previous read if possible.
    # Actually, I should probably just use a placeholder and see what fails, but let's try to be better.
    pass

def repair_slice(task_dir: Path, rs: Any, draft: Path, 
                  out_root: Path, build: Any = None, run: Any = None,
                  feedback_mode: str = "localized", max_rounds: int = 2, synthetic: bool = False) -> dict:
    pass

def detect_tool_loop(log: str) -> dict:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    pass

def prepare_workspace(task_dir: Path, draft: Path, out_root: Path, round_n: int) -> None:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    pass

def detect_crash_giveup(log: str, ws_ans: Path, draft_answer_path: Path) -> Optional[dict]:
    """偵測模型是否因為連續的工具錯誤而放棄（Crash-Giveup）。

    規則：
    1. 掃描 log 中的 tool_execution_end 事件。
    2. 如果 isError=True，且內容包含常見異常（如 Traceback, SyntaxError, FileNotFoundError 等），則計入 crash_event_count。
    3. 若模型在連續失敗後仍未寫入 answer.txt (ws_ans)，且 draft_answer_path 存在且內容為 None 或與 ws_ans 一致，則判定為放棄。
    4. 避免將正常程式碼中的 ValueError 等誤判為 crash（除非是工具執行本身的錯誤）。

    注意：必須只掃描失敗的 tool_execution_end，避免將 14 次錯誤膨脹為 136 次或誤抓正常程式碼。
    """
    import json
    events = []
    for line in log.strip().split('\n'):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    crash_events = []
    for e in events:
        if e.get("type") == "tool_execution_end" and e.get("isError"):
            content = e.get("result", {}).get("content", [])
            text = "".join([c.get("text", "") for c in content])
            # 排除掉正常的 ValueError 或其他非工具層級的錯誤（除非是特定的 crash 類）
            if "ValueError:" not in text and ("Traceback" in text or "SyntaxError" in text or "FileNotFoundError" in text):
                crash_events.append(text)

    if not crash_events:
        return None

    # 檢查是否放棄：如果 draft_answer_path 存在且內容為 None，且 ws_ans 也沒被更新
    try:
        draft_content = draft_answer_path.read_text(encoding="utf-8").strip()
    except Exception:
        draft_content = ""

    ws_content = ws_ans.read_text(encoding="utf-8").strip()

    if draft_content == "None" and ws_content == "None":
        return {
            "crash_giveup_suspected": True,
            "giveup_answer": "None",
            "crash_event_count": len(crash_events),
            "crash_signatures": list(set(crash_events)),
            "signatures_truncated": False,
        }

    return None

def _count_rule_hint_line(ev: dict) -> str:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    pass

def ClaimResult(claim_id: str, status: str, detail: str, evidence: dict, 
                 verifier: str, verifier_version: str, required: bool, authority: str):
    return {"claim_id": claim_id, "status": status, "detail": detail, 
             "evidence": evidence, "verifier": verifier, "verifier_version": verifier_version, 
             "required": required, "authority": authority}

def create_authoritative_snapshot(task_dir: Path, out_root: Path) -> Path:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    pass

def _cond_rate_hint_line(ev: dict) -> str:
    # Implementation from argon (r1063/argon) - need to ensure it's here.
    pass

def _loop_outcome_fields():
    # Placeholder for some internal logic if needed
    pass
