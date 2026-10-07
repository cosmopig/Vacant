#!/usr/bin/env python3
"""twin/twin_letter — 段 1「寫信」：不開 pi，直接打一次模型（無工具），把信寫進 `信.md`。

這支在架構裡承重什麼：P13（2026-10-07，`decisions/DECISION_20261007_TWIN_DIVINE.md` §四）把段 1 從「一個 pi 工作階段
（讀 TRAITS.md、ws_write 信.md）」換成「一通模型呼叫」。理由：信是一段純文字轉換（特質 → 抽象化的性情＋命盤＋想試的事），
不需要工具、不需要多回合；省掉一個 pi 工作階段（啟動、工具協商、模型一次只做一件事的來回）。

* 呼叫的是 `$VACANT_RUN_PROXY/v1/chat/completions`——也就是 `vacant run` 的中介，所以這一通照樣被收據算到
  （`requests_seen`）、照樣進 wire log；**不是**旁路。
* **沒有牆鐘逾時**：用串流（`stream: true`），逾時只是「連續 `stall_s` 秒沒有收到任何一個位元組」（卡死偵測，
  與段 2 的卡死偵測同一個精神）。串流不通或回空 ⇒ 重打（最多 `attempts` 次）。
* 輸出只有 `信.md`；stdout 什麼都不印（pi 的 `agent_stdout.log` 被電視旁註當 JSON 事件 tail，不准汙染）。
* 之後仍由 `twin_letter_guard.py` 做確定性關卡（移走 TRAITS.md、LEAK 8 字、時段詞、300 字、命盤段重寫）——
  模型寫什麼都要過它，所以這裡不做內容判斷。

⚠ 誠實邊界：段 1 不再有 `ws_*` 工具的步驟紀錄與 `thought`——電視在段 1 看不到「它在想」，只看得到 run_started。
只用標準函式庫（可以單獨複製進沙箱）。
"""
from __future__ import annotations

import json
import os
import re
import pathlib
import sys
import urllib.error
import urllib.request

LETTER = "信.md"
TRAITS = "TRAITS.md"
DEFAULT_STALL_S = 150.0
DEFAULT_ATTEMPTS = 3
MAX_TOKENS = 4096


class Stalled(Exception):
    """連續 stall_s 秒沒有收到任何一行 `data:`（P13 實測：舊 VM 第一次真跑，兩組的寫信那一通在中介後面掛了 2500–3600 秒，
    socket 層的讀取逾時沒有觸發——中介可能先吐了標頭或保活的註解行）。"""


def _post_stream(url: str, key: str, body: dict, stall_s: float) -> str:
    """串流打一通；回 assistant 的 content（不含思考）。卡死偵測：連續 `stall_s` 秒沒有新的 `data:` 行 ⇒ 關連線、丟 Stalled。
    不是牆鐘：一直有 token 進來的慢模型不受影響。"""
    import threading
    import time
    req = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}",
                 "Accept": "text/event-stream"})
    parts: list[str] = []
    state = {"last": time.time(), "stalled": False, "done": False}
    holder: dict = {}

    def watchdog() -> None:
        while not state["done"]:
            time.sleep(1.0)
            if time.time() - state["last"] >= stall_s:
                state["stalled"] = True
                r = holder.get("resp")
                try:
                    if r is not None:
                        r.close()
                except Exception:                                 # noqa: BLE001
                    pass
                return

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        # 連線＋等標頭階段也受同一個守衛（urlopen 本身卡住時 resp 還沒有；watchdog 關不到它，所以 urlopen 再加 socket 逾時當第二道）
        with urllib.request.urlopen(req, timeout=stall_s) as resp:
            holder["resp"] = resp
            state["last"] = time.time()
            if "json" in (resp.headers.get("Content-Type") or "").lower():
                try:
                    obj = json.loads(resp.read().decode("utf-8", "replace"))
                except ValueError:
                    return ""
                ch = (obj.get("choices") or [{}])[0] if isinstance(obj, dict) else {}
                c = (ch.get("message") or {}).get("content")
                return c if isinstance(c, str) else ""
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                state["last"] = time.time()
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except ValueError:
                    continue
                for ch in obj.get("choices") or []:
                    c = (ch.get("delta") or {}).get("content")
                    if isinstance(c, str):
                        parts.append(c)
    except (OSError, ValueError, AttributeError) as exc:
        if state["stalled"]:
            raise Stalled() from exc
        raise
    finally:
        state["done"] = True
    if state["stalled"]:
        raise Stalled()
    return "".join(parts)


#: 被用爛的抽象詞（與 `twinagent.ABSTRACT_WORDS` 同值，測試釘住；這支要能單獨複製進沙箱所以不 import）。
ABSTRACT_WORDS = ("渴望", "靜默", "虛無", "細碎", "共振", "壓抑", "沉默", "溫潤", "圓潤")
MAX_EACH = 1
_SENT = re.compile(r"[^。！？!?\n]*[。！？!?]?|\n")


def overused(text: str) -> dict[str, int]:
    """每個抽象詞在整封信（含命盤段）出現的次數，只列超過 `MAX_EACH` 的。"""
    return {w: text.count(w) for w in ABSTRACT_WORDS if text.count(w) > MAX_EACH}


def strip_overused(text: str) -> tuple[str, int]:
    """確定性：依序掃每個句子，某個抽象詞已經出現過 `MAX_EACH` 次，之後含它的整句拿掉。回（新文字, 拿掉幾句）。
    換行原樣保留；命盤段的標頭行（`MBTI：`…）若整行被拿掉，由 `fortune.render_section` 重寫標頭，所以不會壞。"""
    seen = {w: 0 for w in ABSTRACT_WORDS}
    out, dropped = [], 0
    for m in _SENT.finditer(text):
        s = m.group(0)
        if not s:
            continue
        hit = [w for w in ABSTRACT_WORDS if w in s]
        if hit and any(seen[w] >= MAX_EACH for w in hit):
            dropped += 1
            continue
        for w in hit:
            seen[w] += s.count(w)
        out.append(s)
    return re.sub(r"\n{3,}", "\n\n", "".join(out)).strip(), dropped


def write_letter(cwd: str | os.PathLike, system: str, first: str, base: str, model: str, key: str,
                 *, stall_s: float = DEFAULT_STALL_S, attempts: int = DEFAULT_ATTEMPTS) -> int:
    """讀 `cwd/TRAITS.md`，打模型，寫 `cwd/信.md`。成功 0；沒寫出來 3。"""
    cwd = pathlib.Path(cwd)
    try:
        traits = (cwd / TRAITS).read_text(encoding="utf-8", errors="replace")
    except OSError:
        print("工作區裡沒有 TRAITS.md。停。", file=sys.stderr)
        return 3
    url = base.rstrip("/") + "/v1/chat/completions"
    body = {"model": model, "stream": True, "temperature": 0.8, "max_tokens": MAX_TOKENS,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": f"{first}\n\n<TRAITS.md>\n{traits}\n</TRAITS.md>"}]}
    for n in range(1, max(1, attempts) + 1):
        try:
            text = _post_stream(url, key, body, stall_s).strip()
        except (urllib.error.URLError, OSError, ValueError, Stalled) as exc:
            print(f"寫信第 {n} 次失敗：{type(exc).__name__}", file=sys.stderr)
            continue
        if text:
            bad = overused(text)
            if bad and n < max(1, attempts):          # 超用了 ⇒ 重寫一次（把超用的詞講給它聽，不給例句）
                note = "、".join(f"「{w}」用了 {c} 次" for w, c in bad.items())
                body2 = dict(body)
                body2["messages"] = body["messages"] + [
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"上一版{note}，每個詞整封信最多只能出現一次。把超用的詞全部換成"
                                                "具體的動作、東西、聲音或手感，整封信重寫一次，格式不變。"}]
                try:
                    t2 = _post_stream(url, key, body2, stall_s).strip()
                except (urllib.error.URLError, OSError, ValueError, Stalled):
                    t2 = ""
                if t2:
                    text = t2
            text, dropped = strip_overused(text)
            if dropped:
                print(f"抽象詞超用，拿掉 {dropped} 句。", file=sys.stderr)
            if not text:
                continue
            (cwd / LETTER).write_text(text + "\n", encoding="utf-8")
            return 0
        print(f"寫信第 {n} 次回空。", file=sys.stderr)
    return 3


def main(argv: list[str]) -> int:
    if len(argv) != 7 or argv[1] != "write":
        print("用法：twin_letter.py write <工作區> <段1指令> <段1第一句> <proxy base> <model>", file=sys.stderr)
        return 2
    stall = float(os.environ.get("VACANT_TWIN_STALL_S") or DEFAULT_STALL_S)
    key = os.environ.get("OPENAI_API_KEY") or "sk-vacant-run"
    return write_letter(argv[2], argv[3], argv[4], argv[5], argv[6], key, stall_s=stall)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
