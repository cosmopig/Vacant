"""tools — **這個工具是哪一類**：讀、寫、殼層、搜尋、抓網頁、子 agent。

這支在架構裡承重什麼：`recorder.py`（子 agent 的父呼叫不算「同時進行」、唯讀工具不會寫檔）
與 `blame.py`（值從哪一類工具的輸出來）要用**同一份**分類；分兩處寫，一邊改了另一邊沒改，
歸因就會悄悄變（2026-09-24 對抗審查 blame#4、#7、#8）。

名字是四個平台實測到的工具名（`ops/accountability/capture/`），不分大小寫。

## 誠實邊界（改碼請保留）

MCP 工具與自訂工具的名字千變萬化；不認得的歸 `other`——`blame.py` 對 `other` 只做保守的推論
（值出現在它的輸出裡 ⇒ 外部工具輸出，不是事實層）。
"""
from __future__ import annotations

_READ = {"read", "view", "cat", "notebookread", "read_file", "readfile", "open", "bashoutput"}
_WRITE = {"write", "edit", "multiedit", "apply_patch", "notebookedit", "str_replace",
          "create", "patch", "write_file", "replace"}
_SHELL = {"bash", "shell", "exec_command", "local_shell", "powershell", "run_shell_command",
          "shell_command", "exec"}
_AGENT = {"agent", "task", "spawn_agent", "collaborationspawn_agent", "wait_agent",
          "multi_agent_v1wait_agent", "collaborationwait_agent", "subagent", "send_message"}
_SEARCH = {"grep", "glob", "find", "ls", "list", "list_files", "search_files", "codebase_search"}
#: 不會改工作區的工具（它的呼叫期間出現的寫入不可能是它寫的）
READ_ONLY = frozenset({"read", "search", "fetch"})


def tool_kind(tool: str | None) -> str:
    t = (tool or "").lower()
    if t in _READ:
        return "read"
    if t in _WRITE:
        return "write"
    if t in _SHELL:
        return "shell"
    if t in _AGENT:
        return "agent"
    if t in _SEARCH:
        return "search"
    if any(h in t for h in ("fetch", "web", "http", "browse", "url")):
        return "fetch"
    return "other"
