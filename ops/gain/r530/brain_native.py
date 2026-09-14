#!/usr/bin/env python3
r"""R530 的後端：OpenAI 相容 **原生 `tools`** 的多輪工具迴圈。

## 為什麼要另外一支（而不是用 `ops/gain/brain_cline.py`）

`ClineBrain.chat()` **不送 `tools`、也不回 `tool_calls`**——它是為「一問一答的
程式碼生成」寫的，六臂都走它。R530 的處理是多輪工具迴圈，需要那兩樣東西。
改 `chat()` ＝ 改一個正在跑的實驗的後端（R460／R529 的 H 臂與 CONFORM 都用它），
而 T12 的紀律是「不動既有臂」。⇒ 另開一支，**一個字都不碰 `brain_cline.py`**。

沿用它的是**紀律不是程式碼**：retry ×4、指數退避、用盡才 `InfraVoid`
（鐵律 3）、全 I/O JSONL 落盤且欄位形狀與 `ClineBrain._log` 逐欄相同
（`ops/gain/harness_vgt_audit.py` 唯一的輸入就是那些欄位）。
`InfraVoid` 直接 import 它的，不另造一個同名例外。

## ⚠ 2026-09-13 的實測，與預註冊 §二-4 的假設**方向相反**

預註冊寫的是：「原生 `tools` 支不支援**本檔沒有量過**，所以預設走文字協定
（模型在 ```bash 圍欄裡寫指令）」。冒煙 `runs/_smoke/g_r530_real_1` 量到的是：

| 協定 | 實測 |
|---|---|
| 文字（```bash 圍欄） | **不通**。6 格裡 4 格零工具呼叫、工作區逐位元沒動 ⇒ `nudge_exhausted`。模型要嘛回 ```python 區塊（一次 18,023 completion tokens），要嘛吐它自己的 `<|tool_call>call:bash{…}` 內部格式——**就是不寫 ```bash 圍欄**。 |
| 原生 `tools` | **通**。`finish_reason="tool_calls"`、`tool_calls` 陣列乾淨、22 completion tokens。 |

⇒ R530 預設走**原生 `tools`**，文字協定留著當備援（`--tool-protocol text`）。
**兩種模式的資料不得混算**（SPEC_GAIN §7 的同一條、預註冊 §二-4 逐字）：
模式逐格落盤在 `summary.tool_protocol` 與每一筆 `calls.jsonl` 的
`meta.tool_protocol`。

⚠ R460 實測的「圍欄遵循 925/925」**不能拿來支持文字協定在這裡可行**：
  那是「寫一個 ```python 區塊」的一問一答任務，不是多輪工具迴圈。
  同一顆模型、不同任務形狀、不同結果——這一句要跟著上面那張表一起被引用。
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.brain_cline import (AUTH_STATUS_NON_RETRYABLE,  # noqa: E402
                                  DEFAULT_BACKOFF_S, EmptyResponse, InfraVoid,
                                  RelayError, endpoint, is_retryable)

#: 唯一的工具。schema 與 `ops/localagent.py:67-87` 逐字同形（含 description），
#: 理由沿用那一支的 docstring：12B 級模型工具越多越容易選錯，而讀檔、寫檔、
#: 跑指令、跑測試全都能經過 shell。
TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_bash",
        "description": (
            "Run a bash command in the working directory and return its "
            "stdout, stderr and exit code. Use this for everything: reading "
            "files (cat/sed -n), searching (grep/find), writing files "
            "(heredoc), and running commands."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string",
                            "description": "The bash command to run."},
                "timeout_s": {"type": "integer",
                              "description": "Seconds before the command is killed "
                                             "(default 120, max 300)."},
            },
            "required": ["command"],
        },
    },
}]

TOOL_PROTOCOLS = ("native", "text")


class NativeToolBrain:
    """OpenAI 相容端點 ＋ 原生 `tools`。`propose()` 是唯一的呼叫入口。"""

    tool_protocol = "native"

    def __init__(self, agent_id: str = "r530-worker", *, key: str = "",
                 log_path: pathlib.Path, model: str,
                 temperature: float = 0.3, retries: int = 4,
                 backoff_s: float = DEFAULT_BACKOFF_S, timeout_s: int = 900,
                 reasoning_effort: str | None = "none",
                 api: str | None = None) -> None:
        self.agent_id = agent_id
        self.key = key
        self.api = api or endpoint()
        self.model = model
        self.temperature = temperature
        self.retries = retries
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self.reasoning_effort = reasoning_effort
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    # ── 落盤（欄位形狀與 `ClineBrain._log` 逐欄相同）────────────────────
    def _log(self, rec: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())        # 中途被砍也要留得住（鐵律 3）

    def backoff_delay(self, attempt: int) -> float:
        """與 `ClineBrain.backoff_delay` **同一條公式**（5／10／20／40）。"""
        return self.backoff_s * (2 ** (attempt - 1))

    # ── 呼叫 ──────────────────────────────────────────────────────────
    def propose(self, messages: list[dict], *, system: str,
                meta: dict | None = None, role: str = "r530") -> dict:
        """送一輪，回 `{"text", "tool_calls", "usage", "finish_reason", "raw"}`。

        `tool_calls` 已經正規化成 `[{"id", "command", "timeout_s"}, …]`；
        參數 JSON 壞掉的那一筆帶 `"error"` 而不是被丟掉——
        **模型試圖做什麼比模型做成了什麼更值得留著看**
        （`ops/localagent.py` 的同一條）。

        重試用盡 ⇒ `InfraVoid`（鐵律 3；作廢的格子一列都不寫）。
        """
        payload = {
            "model": self.model,
            "messages": ([{"role": "system", "content": system}]
                         + [_wire(m) for m in messages]),
            "tools": TOOLS,
            "temperature": self.temperature,
            "stream": False,
        }
        # 推論模式是**實驗條件**（DECISION_20260912 §十一）：要嘛不送、
        # 要嘛送出去而且落盤送了什麼，不准有「大概是預設值」這種狀態。
        send_effort = (self.reasoning_effort
                       if self.reasoning_effort not in (None, "default") else None)
        if send_effort is not None:
            payload["reasoning_effort"] = send_effort
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"

        last_err = ""
        for attempt in range(1, self.retries + 1):
            t0 = time.time()
            try:
                req = urllib.request.Request(self.api, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    d = json.load(resp)
                if "choices" not in d and d.get("error"):
                    raise RelayError(f"端點回 200 但 body 是錯誤：{d['error']!r}")
                choice = d["choices"][0]
                msg = choice.get("message") or {}
                text = (msg.get("content") or "").strip()
                calls = _normalise_tool_calls(msg.get("tool_calls") or [])
                if not text and not calls:
                    raise EmptyResponse("content 與 tool_calls 都是空的")
                usage = d.get("usage") or {}
                self.calls += 1
                self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
                self.completion_tokens += int(usage.get("completion_tokens") or 0)
                latency_ms = int((time.time() - t0) * 1000)
                last_user = next((m["content"] for m in reversed(messages)
                                  if m.get("role") == "user"), "")
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role, "api": self.api,
                    "model": self.model, "server_model": d.get("model"),
                    "model_configured": self.model,
                    "temperature": self.temperature,
                    "attempt": attempt, "ok": True,
                    "timeout_s": self.timeout_s, "retries_max": self.retries,
                    "reasoning_effort": send_effort,
                    "latency_ms": latency_ms, "usage": usage,
                    "system": system,
                    "prompt": last_user,
                    # `messages` ＝ 這一次真正送出去的全部內容。V/GT 稽核
                    # （`harness_vgt_audit --scope r530`）唯一的輸入就是它。
                    "messages": [_wire(m) for m in messages],
                    "finish_reason": choice.get("finish_reason"),
                    "response": text,
                    "response_tool_calls": calls,
                    "meta": meta or {},
                })
                return {"text": text, "tool_calls": calls, "usage": usage,
                        "finish_reason": choice.get("finish_reason"), "raw": msg}
            except Exception as e:                           # noqa: BLE001
                status = getattr(e, "code", None)
                err_text = ""
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        err_text = e.read().decode("utf-8", "replace")[:800]
                    except Exception:                        # noqa: BLE001
                        err_text = ""
                last_err = f"{type(e).__name__}: {e}"
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role, "api": self.api,
                    "model": self.model, "attempt": attempt, "ok": False,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": last_err, "error_body": err_text,
                    "status": status, "meta": meta or {},
                })
                if status in AUTH_STATUS_NON_RETRYABLE:
                    # 401/402/403 重試多少次都一樣，而且重試會把「缺金鑰」
                    # 拖成「跑了很久才全滅」（`brain_cline` 的同一條）。
                    break
                if attempt < self.retries and is_retryable(e, err_text):
                    time.sleep(self.backoff_delay(attempt))
                elif attempt < self.retries:
                    time.sleep(self.backoff_delay(attempt))
        raise InfraVoid(f"{self.agent_id} 重試 {self.retries} 次仍失敗：{last_err}")


def _wire(m: dict) -> dict:
    """一則訊息的線路形狀。`tool` 角色要帶 `tool_call_id`，`assistant` 要帶
    `tool_calls`——少一個欄位端點就拼不回對話。"""
    out = {"role": m.get("role"), "content": m.get("content") or ""}
    if m.get("tool_calls"):
        out["tool_calls"] = m["tool_calls"]
    if m.get("tool_call_id"):
        out["tool_call_id"] = m["tool_call_id"]
    return out


def _normalise_tool_calls(raw: list) -> list[dict]:
    out: list[dict] = []
    for c in raw:
        fn = (c or {}).get("function") or {}
        rec: dict = {"id": c.get("id") or "", "name": fn.get("name")}
        if fn.get("name") != "run_bash":
            # 叫了不存在的工具：**記下來**，由呼叫端回一則錯誤訊息給模型。
            rec["error"] = f"unknown tool {fn.get('name')!r}"
            out.append(rec)
            continue
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError as e:
            rec["error"] = f"arguments is not valid JSON: {e}"
            out.append(rec)
            continue
        if not isinstance(args, dict) or "command" not in args:
            rec["error"] = "arguments has no `command`"
            out.append(rec)
            continue
        rec["command"] = str(args["command"])
        try:
            rec["timeout_s"] = int(args.get("timeout_s") or 0) or None
        except (TypeError, ValueError):
            rec["timeout_s"] = None
        out.append(rec)
    return out


class TextProtocolBrain:
    """備援協定：包一層 `ClineBrain.chat()`，指令從 ```bash 圍欄解析。

    ⚠ **2026-09-13 實測它在 `gemma-4-12b-it-qat` 上不通**（見模組 docstring
      那張表）。留著它有兩個理由，都不是「以防萬一」：
      1. 預註冊 §二-4 把兩種模式都登記了，而**兩種模式的資料不得混算**——
         要能混算的前提是兩種都真的跑得起來；留一個跑不起來的選項比
         偷偷刪掉它誠實。
      2. 換一顆模型時它可能才是能用的那一個；那時 `--tool-protocol text`
         要是一個真的開關，不是一段註解。
    """

    tool_protocol = "text"

    def __init__(self, inner) -> None:
        self.inner = inner
        self.model = getattr(inner, "model", None)
        self.agent_id = getattr(inner, "agent_id", "r530-worker")

    def propose(self, messages: list[dict], *, system: str,
                meta: dict | None = None, role: str = "r530") -> dict:
        from ops.gain.r530.openwork_arms import parse_commands
        text, info = self.inner.chat(messages, role=role, system=system,
                                     meta=meta)
        return {"text": text,
                "tool_calls": [{"id": "", "name": "run_bash", "command": c,
                                "timeout_s": None}
                               for c in parse_commands(text)],
                "usage": info.get("usage") or {},
                "finish_reason": info.get("finish_reason"), "raw": {}}


# ══ E-11 的發射前探針：推論模式與 prefill 吞吐 ══════════════════════════
#
# 兩件事一次量完，因為兩件事都只有**在原生 tools 請求下**才問得出來：
#
# 1. **`reasoning_tokens` 必須是 0。** R529 §十一 量到同一份 gguf 在 1003／1004
#    上跑成 thinking／非 thinking **兩種實驗條件**，而那件事只有落盤看得出來。
#    `reasoning_effort=none` 在 `chat/completions` 上有沒有生效，與它在
#    **帶 `tools` 的請求**上有沒有生效，是兩個問題——這支問的是後者。
#    ⚠ 欄位**不存在**也算紅：那代表端點根本沒回報，我們量不到
#      （`FIELD_MISSING`）。量不到不是通過。
#
# 2. **prefill 吞吐**（ms／1k prompt token）。它落盤的理由是多輪工具迴圈每一通
#    都把整段對話當 prompt 重送 ⇒ prefill 慢的那台隨輪數地慢，
#    而那會讓 `budget_wall` 在兩台上咬到不同的地方（跨題的差別截斷）。
#
#    ⚠ **這個數字冷／暖快取差一個量級，量的時候要說是哪一種。**
#      2026-09-14 去快取實測（每次換 nonce ⇒ KV 一定 miss）：
#        冷 prefill   1003 ≈ 1,509 ／ 1004 ≈ 481 ms/1k  ⇒ 3.1×
#        暖 prefill   1003 ≈ 144   ／ 1004 ≈ 54–102     ⇒ 1.4–2.7×
#        生成         1003 ≈ 22.6  ／ 1004 ≈ 14.4 ms/tok ⇒ 1.6×
#      本支量的是**暖的那一種**（第二通打同一段前綴），因為多輪迴圈的前綴
#      本來就是暖的。第一通吃冷的，那一通會慢一個量級。
#
#    ⚠ **不准拿它去解釋 smoke9 兩塊差 5 倍**——那 5 倍主要是**題目**不是後端：
#        · `corr(latency, completion)` 兩塊都是 +0.98／+1.00（延遲由生成長度決定）
#        · 每通 completion 中位數：`ow_01` **1,636**、`ow_02` **30**（**55 倍**）
#      而 smoke9 把 (1003, ow_01)／(1004, ow_02) 綁死 ⇒ 後端與題目**完全共線**，
#      那份資料本身不可歸因。`schedule_r530.py` 的佇列驗證擋的正是這件事
#      （`abort_all_blocks_one_host`），手動發射繞過了它。
#      後端的那一份差是**真的但比較小**（生成 1.6×、冷 prefill 3.1×），
#      而且它是 task 層級的干擾項不是 arm 層級的混淆項——同一題的三條臂同一台。

PROBE_SYSTEM = "You are a programmer. You have exactly one tool: run_bash."
PROBE_SHORT = "List the files in the current directory using the tool."
#: 約 9k token 的填充：量 prefill 用的。內容刻意無意義——它問的是吞吐不是能力。
PROBE_PAD_LINE = "# context padding line to make the prompt long\n"
PROBE_PAD_REPEAT = 900


def probe_inference_mode(api: str, model: str, *, key: str = "",
                         timeout_s: int = 300,
                         reasoning_effort: str | None = "none") -> dict:
    """E-11 的發射前探針。回一份可落盤的 dict；**不自己停**，判給 `gates`。

    燒兩次呼叫（短的一次、長脈絡的一次），約 20–30 秒。
    """
    import urllib.error

    def one(messages: list[dict]) -> dict:
        payload = {"model": model, "messages": messages, "tools": TOOLS,
                   "temperature": 0.3, "stream": False}
        if reasoning_effort not in (None, "default"):
            payload["reasoning_effort"] = reasoning_effort
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        t0 = time.time()
        req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            d = json.load(resp)
        ms = int((time.time() - t0) * 1000)
        u = d.get("usage") or {}
        det = u.get("completion_tokens_details") or {}
        return {
            "latency_ms": ms,
            "prompt_tokens": u.get("prompt_tokens"),
            "completion_tokens": u.get("completion_tokens"),
            # 欄位不存在與 0 是兩件事，所以不 `.get(k, 0)`。
            "reasoning_tokens": det.get("reasoning_tokens", "FIELD_MISSING"),
            "finish_reason": (d.get("choices") or [{}])[0].get("finish_reason"),
            "tool_calls_n": len(((d.get("choices") or [{}])[0].get("message")
                                 or {}).get("tool_calls") or []),
            "server_model": d.get("model"),
        }

    rec: dict = {"api": api, "model": model,
                 "reasoning_effort_sent": (
                     reasoning_effort
                     if reasoning_effort not in (None, "default") else None),
                 "error": None}
    try:
        short = one([{"role": "system", "content": PROBE_SYSTEM},
                     {"role": "user", "content": PROBE_SHORT}])
        pad = PROBE_PAD_LINE * PROBE_PAD_REPEAT
        long_ctx = one([{"role": "system", "content": PROBE_SYSTEM},
                        {"role": "user", "content": pad + "\n" + PROBE_SHORT}])
    except Exception as e:                                   # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["reasoning_tokens_all_zero"] = None
        return rec

    rec["short"] = short
    rec["long_ctx"] = long_ctx
    vals = [short["reasoning_tokens"], long_ctx["reasoning_tokens"]]
    rec["reasoning_tokens"] = vals
    rec["reasoning_tokens_all_zero"] = all(v == 0 for v in vals)
    # ── prefill 吞吐 ────────────────────────────────────────────────
    # ⚠ **差分法（長脈絡延遲 − 短延遲）算出來會是負的**，2026-09-14 實測
    #   1003 −11.3、1004 −5.6 ms/1k：長脈絡那一通**比短的還快**（短的那通
    #   吃到冷啟動、長的那通吃到 KV 快取）。一個負的「吞吐」不該就這樣流出去，
    #   所以差分法留著但**非正值一律記成 None ＋ 理由**，不四捨五入成 0。
    #
    # 主要指標改成**單通的** `long_ctx` 延遲 ÷ prompt 千 token 數。它是
    # prefill 成本的**上界**（裡面含 ~15 token 的生成），而它可以跨台比，
    # 因為兩台吃的是**逐位元相同**的 prompt。
    # 2026-09-14 配對實測：1003≈807、1004≈121 ms/1k（同 9,109 token prompt、
    # 同 15 token 輸出）；而同 prompt 的長生成 ms 比只有 1.02× ⇒ 差在 prefill。
    lp = long_ctx["prompt_tokens"] or 0
    rec["long_ctx_ms_per_1k_prompt"] = (
        round(long_ctx["latency_ms"] / (lp / 1000.0), 1) if lp else None)
    rec["long_ctx_prompt_tokens"] = lp
    rec["long_ctx_completion_tokens"] = long_ctx["completion_tokens"]
    dp = lp - (short["prompt_tokens"] or 0)
    dt = long_ctx["latency_ms"] - short["latency_ms"]
    diff = (dt / (dp / 1000.0)) if dp > 0 else None
    if diff is not None and diff > 0:
        rec["prefill_ms_per_1k_prompt"] = round(diff, 1)
    else:
        rec["prefill_ms_per_1k_prompt"] = None
        rec["prefill_diff_unusable"] = (
            f"差分法不可用（dt={dt} ms, dp={dp} tok）：長脈絡那一通不比短的慢"
            "——短的吃冷啟動、長的吃 KV 快取。改讀 `long_ctx_ms_per_1k_prompt`，"
            "它是上界而且跨台可比（兩台吃逐位元相同的 prompt）。")
    rec["note"] = (
        "prefill 吞吐是**實驗條件**不是實作細節：多輪工具迴圈每通都把整段對話"
        "當 prompt 重送，而那會讓 `budget_wall` 在兩台上咬到不同的地方。"
        "⚠ 本欄量的是**暖快取**（多輪迴圈的前綴本來就是暖的）；冷的那一通會"
        "慢一個量級（2026-09-14 去快取實測：冷 1003≈1509／1004≈481、"
        "暖 1003≈144／1004≈54–102、生成 1003≈22.6／1004≈14.4 ms/tok）。"
        "⚠ **不准**拿它解釋逐通延遲的差別——逐通延遲由**生成長度**決定"
        "（smoke9 兩塊的 corr(latency, completion) 都在 +0.98 以上）。")
    return rec
