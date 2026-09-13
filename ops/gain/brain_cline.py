#!/usr/bin/env python3
"""Cline／Kimi 後端——實作 `run_x1` 那個 Brain protocol：`generate(prompt) -> str`。

為什麼是這支：SPEC_GAIN §6 要宣稱「任何 agent platform」，而 Vacant 這一層包的
就是一個 callable。這支是第一個真實後端；宣稱平台無關需要**第二個後端同號**，
只有一個就只能說「在這個後端上成立」。

**全 I/O 落盤（鐵律 3）**：每一次呼叫——含失敗與重試——逐字寫進 JSONL：
prompt 全文、回應全文、耗時、成本、重試次數、錯誤訊息。不做截斷、不做去識別。
理由是這個專案的紀律是「只數產物不看返回值」，而回應全文就是產物本身；
存摘要等於把後來能重新判讀的機會丟掉。

retry×4 指數 backoff；四次都失敗記 `infra_void`（09 §3.5）——
**infra_void 不算成功也不算失敗**，它是「這一格沒有量到」，
與「量到 0」必須分得開。

退避表（2026-09-13 改；`DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md` §十一）
────────────────────────────────────────────────────────────────────────
1004 於 2026-09-13 01:44Z 模型崩潰後被 LM Studio **JIT 重載並帶上 TTL 1 小時**，
之後每小時卸載一次；重載本身要 8–10 秒，期間端點回 HTTP 400
`Model unloaded`／`Failed to load model`。舊的 `backoff_s=2.0` 退避是
2／4／8 秒（四次嘗試之間只睡 14 秒，而且三次請求本身在幾百毫秒內就被拒絕）
⇒ **整格在重載窗內打完四次，記成 infra_void**（r5 的 a3／b1／b2／b3 各 1–3 列）。
⇒ `DEFAULT_BACKOFF_S = 5.0`，退避表 5／10／20／40 秒。
⚠ 誠實邊界：`retries=4`（鐵律 3 的 ×4，本次**不動**）只會用到前三格，
  總退避 35 秒；第四格 40 秒要 `retries=5` 才輪得到。35 秒已經涵蓋實測的
  8–10 秒重載窗，但它不是「保證撐得過任何重載」——只是把上界從 14 秒抬到 35 秒。

⚠ `generate()` 的原始碼被 `tests/test_gain_harness_arms.py::GENERATE_SHA` 釘死
  （T12：H 臂不准動既有五臂）。所以退避改的是**建構子的預設值**
  （`backoff_s`）而不是 `generate()` 裡那一行——那一行的公式
  `backoff_s * 2**(attempt-1)` 本來就是指數退避，換底數就等於換表，
  `generate()` 與 `chat()` 因此拿到**同一張表**而原始碼逐位元不變。
  這是刻意的取捨，不是繞過：既有五臂的**等待時間確實變了**（實驗條件），
  它落盤在 `summary.json.request_policy.backoff_s`，可被稽核看見。
  ⇒ 這一項已於 2026-09-13 由 Fable **事後明文授權**（DECISION_20260912
  §十二-4 補記 4）：行為改變＝重試等待 14 秒 → 35 秒。

推論模式（`reasoning_effort`）：**兩條路都送**
────────────────────────────────────────────
2026-09-13 Fable 實測：1003（0.4.24）與 1004（0.4.17）**都**吃 OpenAI 相容的
頂層 `reasoning_effort`；1003 加 `"none"` 之後與 1004 完全一致（prompt 18 token、
completion 2、reasoning 0）。其他寫法（`reasoning.effort`、
`chat_template_kwargs.enable_thinking`、`thinking.type`）在 1003 都無效。

⚠ `generate()` 送這個欄位是 **Fable 於 2026-09-13 明文授權的 T12 例外**
  （`GENERATE_SHA` 同日更新，舊值 b523c15f…、新值見 tests 的註解）。
  為什麼非改不可：OFF／OFF5／CONFORM／EQ5／ON **五臂全部走 `generate()`**，
  只在 `chat()` 送等於只對齊 H 臂，反而在臂之間造出一個 OFF 沒有的推論條件差
  ——那比原本「兩台後端不同」更糟。
  行為差異只有兩處：請求 body 多一個欄位（`None`／`"default"` ⇒ **不送**
  ⇒ 對非 thinking 後端逐位元無變化）、`calls.jsonl` 多一個 `reasoning_effort` 欄。
"""
from __future__ import annotations

import contextlib
import json
import os
import pathlib
import signal
import threading
import time
import urllib.error
import urllib.request

API = "https://api.cline.bot/api/v1/chat/completions"
DEFAULT_MODEL = "cline-pass/kimi-k3"

#: 退避底數（秒）。`generate()`／`chat()` 都算 `DEFAULT_BACKOFF_S * 2**(attempt-1)`
#: ⇒ 5／10／20／40。改自 2.0（2／4／8），理由見模組 docstring 的「退避表」。
DEFAULT_BACKOFF_S = 5.0
#: 上面那張表的字面值，給測試與報告引用（**不是**另一條實作路徑）。
BACKOFF_SCHEDULE_S = (5.0, 10.0, 20.0, 40.0)

#: HTTP 400 的 body 裡出現這些字樣 ⇒ 那是**後端正在換模型**，不是壞請求。
#: 2026-09-13 實測：LM Studio 的 JIT 重載窗（TTL 到期後第一通請求）會回
#: `{"error":{"message":"Model unloaded. ..."}}` 或 `Failed to load model`；
#: 模型崩潰時回 `The model has crashed without additional information`。
#: ⚠ 400 在 round356 之後**本來就走重試**（只有 401/402/403 不重試），
#:   所以這張表不是「讓 400 變可重試」——它讓「可重試」這件事**說得出理由**，
#:   並且讓 401/402/403 在帶著重載字樣時也重試（認證錯誤不會這樣講話）。
RELOAD_ERROR_MARKERS = (
    "model unloaded",
    "failed to load model",
    "crashed",
    "model is not loaded",
    "loading model",
)
#: 5xx 一律可重試（伺服器自己說它壞了）。
RETRYABLE_STATUS_MIN = 500
#: 認證／額度：不重試（語意上不是暫時性路由問題）。
AUTH_STATUS_NON_RETRYABLE = frozenset({401, 402, 403})
#: OpenAI 相容的關思考旗標。2026-09-13 Fable 實測：1003（LM Studio 0.4.24）
#: 與 1004（0.4.17）**都**接受頂層 `reasoning_effort`；1003 加了
#: `"reasoning_effort": "none"` 之後與 1004 行為完全一致（prompt 18 token、
#: completion 2、reasoning 0）。其他寫法（`reasoning.effort`、
#: `chat_template_kwargs.enable_thinking`、`thinking.type`）在 1003 都無效。
REASONING_EFFORT_VALUES = ("none", "default", "low", "medium", "high")
#: `"default"` ＝ **不送這個欄位**（讓後端自己決定），不是送字串 "default"。
REASONING_EFFORT_OMIT = "default"


def has_reload_marker(text: str) -> bool:
    """錯誤字串裡有沒有「後端正在換模型」的字樣（大小寫不敏感）。"""
    low = (text or "").lower()
    return any(m in low for m in RELOAD_ERROR_MARKERS)


def is_retryable(exc: BaseException, err_text: str = "") -> bool:
    """這個例外該不該重試。**純函式**，判準寫在這裡而不是散在兩個迴圈裡。

    · 非 HTTP 錯誤（連不上、逾時、RelayError、EmptyResponse）⇒ 重試（既有語意）。
    · HTTP 5xx ⇒ 重試。
    · HTTP 401/402/403 ⇒ 不重試——**除非** body 帶重載字樣
      （那就是後端在換模型，代理層回什麼碼都不改變它是暫時的這件事）。
    · 其餘（400/404/…）⇒ 重試（round356 的裁決，見 `generate()` 裡的長註解）。
    """
    if not isinstance(exc, urllib.error.HTTPError):
        return True
    if exc.code >= RETRYABLE_STATUS_MIN:
        return True
    if exc.code in AUTH_STATUS_NON_RETRYABLE:
        return has_reload_marker(err_text)
    return True

# SPEC_GAIN §6 要宣稱「任何 agent platform」，而那需要**兩個後端同號**——
# 只跑一個後端就宣稱平台無關，是把「沒試過別的」講成「別的也一樣」。
# 所以端點必須可換。換掉之後**端點身分要跟結果一起落盤**：它是實驗條件，
# 不是實作細節；兩個後端的數字混在一起看不出來，就等於沒有第二個後端。
#
# 用法：VACANT_GAIN_API=http://127.0.0.1:1234/v1/chat/completions
# 本地端點通常不驗證；金鑰為空字串時不送 Authorization 標頭。
def endpoint() -> str:
    return os.environ.get("VACANT_GAIN_API", "").strip() or API


class RelayError(RuntimeError):
    """端點回 HTTP 200 但 body 是錯誤物件。可重試，不是錯答案。"""


class EmptyResponse(RuntimeError):
    """端點回 200 但 content 是空的。當成可重試的端點狀況，不是錯答案。"""


class InfraVoid(RuntimeError):
    """端點連不上／重試用盡。呼叫端必須把這一格記成 infra_void，不可當成錯誤答案。"""


class WallClockTimeout(TimeoutError):
    """整個 HTTP 請求超過牆鐘上限仍沒回來。與 socket timeout 同語意，可重試。"""


# ── 牆鐘護欄（round460d）────────────────────────────────────────────────
#
# ⚠ **為什麼 `urlopen(timeout=…)` 不夠**——這是 2026-09-07 R460 冒煙掛掉四小時
#   換來的：`timeout=` 設的是 **socket 逾時，不是請求逾時**。它的作用範圍是
#   *每一次* socket 操作；`http.client` 讀狀態列走的是
#   `BufferedReader.readline()`，那是一個**迴圈**，每繞一圈就重新開始計時
#   （CPython `sock_call_ex` 的 deadline 是每次 `recv_into` 各自初始化的）。
#   ⇒ 一個「timeout=600」的請求在原理上沒有牆鐘上限。
#
#   實測（`smoke_r460/HANG_EVIDENCE_sample_pid58764.txt`）：HMIX 第一通呼叫
#   `timeout_s=600`、`retries=4`，卡在 `_read_status` 的 `poll()` 裡
#   **4 小時 08 分**（600 s 的 24.8 倍），calls.jsonl 一列都沒新增
#   （失敗才落盤，而它還沒失敗）。最後**確實**丟了 `TimeoutError: timed out`
#   ——所以逾時不是沒設，是沒有束縛住牆鐘。期間機器沒有睡
#   （`pmset -g log` 自 09-07 04:17 之後無 Sleep，且有 caffeinate assertion）。
#
# 護欄用 SIGALRM：訊號會打斷 `poll()`，例外從 urlopen 裡面往外拋，
# 被既有的 `except Exception` 接住 ⇒ 落盤 ⇒ 重試 ⇒ 用盡才 `InfraVoid`。
# **語意完全沿用既有那條路，不新增 void 種類。**
#
# ⚠ 邊界（誠實話）：只有主執行緒能裝 SIGALRM，非主執行緒時本護欄是 no-op。
#
# ⚠ **round460e（2026-09-08，Fable A3）：護欄從「只掛 `chat()`」改成「兩條都掛」。**
#   原本只掛 `chat()` 的理由是 `generate()` 的原始碼被
#   `tests/test_gain_harness_arms.py::test_t12…` 逐位元釘死（§4.5 不動清單）。
#   但 D9 之後六個行程各自長跑，`generate()` 是 OFF／OFF5／CONFORM 三條臂**唯一**
#   的呼叫路徑；讓那三條臂繼續暴露在「4 小時不返回、calls.jsonl 一列都不寫」
#   的死法上，換到的只是一個 sha 沒變。所以解凍那一格：
#   **T12 的 `GENERATE_SHA` 隨之更新，並在測試裡逐字註明改動是純基建**
#   （bounds a hang；正常路徑行為逐字不變），既有五臂的**行為**仍然一個字沒動。
#   兩條路徑現在的語意完全相同：護欄比 socket 逾時晚 `WALL_CLOCK_SLACK_S` 才動作，
#   只有在 OS 沒有兌現 socket 逾時的時候才會咬到，咬到之後走既有的
#   `except Exception` → 落盤 → 重試 → 用盡才 `InfraVoid`（**不新增 void 種類**）。
WALL_CLOCK_SLACK_S = 60


@contextlib.contextmanager
def _wall_clock_guard(seconds: float):
    """`seconds` 秒之後強制打斷區塊內的阻塞，丟 `WallClockTimeout`。"""
    if (seconds <= 0 or not hasattr(signal, "SIGALRM")
            or threading.current_thread() is not threading.main_thread()):
        yield                       # 裝不了就明說裝不了，不假裝有護欄
        return

    def _fire(signum, frame):       # noqa: ARG001
        raise WallClockTimeout(
            f"整個請求超過 {seconds:.0f}s 牆鐘上限仍未返回"
            "（socket 逾時只綁單次 recv，不綁請求）")

    prev_handler = signal.signal(signal.SIGALRM, _fire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prev_handler)


class ClineBrain:
    """一個 agent。`system` 決定它的性格——異質性就是從這裡來的。"""

    def __init__(self, agent_id: str, system: str, *, key: str,
                 log_path: pathlib.Path, model: str = DEFAULT_MODEL,
                 temperature: float = 0.7, retries: int = 4,
                 backoff_s: float = DEFAULT_BACKOFF_S, timeout_s: int = 240,
                 reasoning_effort: str | None = None) -> None:
        self.agent_id = agent_id
        self.system = system
        self.key = key
        self.api = endpoint()
        self.model = model
        self.temperature = temperature
        self.retries = retries
        # 2026-09-13：預設由 2.0 改成 5.0（退避 5／10／20／40）。
        # `generate()` 被 T12 釘死，所以退避只能從這裡換底數——
        # 公式在 `generate()` 與 `chat()` 裡是同一條，換底數＝同時換兩邊的表。
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        if reasoning_effort is not None and reasoning_effort not in REASONING_EFFORT_VALUES:
            raise ValueError(
                f"reasoning_effort 只認得 {REASONING_EFFORT_VALUES}，"
                f"拿到 {reasoning_effort!r}")
        #: None ＝ 沿用舊行為（不送這個欄位）；"default" 也是不送。
        #: ⚠ 只有 `chat()` 會送它——`generate()` 的原始碼被 T12 釘死，
        #:   動它就是動既有五臂（見模組 docstring 的最後一段）。
        self.reasoning_effort = reasoning_effort
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.cost = 0.0
        self.market_cost = 0.0

    # ── 退避 ────────────────────────────────────────────────────────
    def backoff_delay(self, attempt: int) -> float:
        """第 `attempt` 次失敗之後要睡幾秒。與 `generate()` 裡那一行**同一條公式**。

        預設 5／10／20／40（`BACKOFF_SCHEDULE_S`）。
        ⚠ `retries=4` 只會睡前三次（5+10+20＝35 秒）；第四格要 `retries=5`
          才輪得到，而 retries 是鐵律 3 訂的 ×4，這裡不動它。
        """
        return self.backoff_s * (2 ** (attempt - 1))

    # ── 落盤 ────────────────────────────────────────────────────────
    def _log(self, rec: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())      # 中途被砍也要留得住

    # ── 呼叫 ────────────────────────────────────────────────────────
    def generate(self, prompt: str, *, role: str = "gen",
                 meta: dict | None = None, system: str | None = None,
                 timeout_s: int | None = None, retries: int | None = None) -> str:
        """timeout_s／retries 為 None 時用實例預設；評審等短 deadline 角色可單次覆蓋。

        覆蓋值會寫進落盤紀錄（SPEC_GAIN §7：timeout／retry 是實驗條件）。
        """
        effective_system = system or self.system
        effective_timeout = self.timeout_s if timeout_s is None else timeout_s
        effective_retries = self.retries if retries is None else retries
        if effective_timeout <= 0 or effective_retries <= 0:
            raise ValueError("timeout_s／retries 必須為正數")
        # 8765 中轉的不同節點對同一個模型用不同命名：`qwen/qwen3.6-35b-a3b`
        # 與 `qwen_qwen3.6-35b-a3b`。節點一換，舊寫法就 404。只重試沒有用——
        # 停在新節點的話四次都是 404。所以 404 時輪替兩種寫法。
        #
        # ⚠ **實際用了哪一個 ID 要逐次落盤**（`model` 欄位寫的是該次送出的值）。
        #   模型身分是實驗條件；若某些題走 slash、某些題走 underscore 而紀錄
        #   只留設定值，事後就分不出那是不是同一個後端在服務。
        variants = [self.model]
        if "/" in self.model:
            variants.append(self.model.replace("/", "_", 1))
        elif "_" in self.model:
            variants.append(self.model.replace("_", "/", 1))

        # round529-3（2026-09-13，**Fable 明文授權**改這個被 T12 釘死的函式）：
        # 推論模式要對齊就必須從**這一條路**送出去——OFF／OFF5／CONFORM／EQ5／ON
        # 五臂全部走 `generate()`，只在 `chat()` 送等於只對齊了 H 臂，
        # 反而在臂之間造出一個 OFF 沒有的推論條件差（比「兩台不同」更糟）。
        # 來源與預設與 `chat()` **同一個**（`self.reasoning_effort`）；
        # `None`／`"default"` ⇒ **不送這個欄位** ⇒ 對非 thinking 後端逐位元無變化。
        send_effort = (self.reasoning_effort
                       if self.reasoning_effort not in (None, REASONING_EFFORT_OMIT)
                       else None)

        def make_body(model_id: str) -> bytes:
            payload = {
                "model": model_id,
                "messages": [{"role": "system", "content": effective_system},
                             {"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "stream": False,
            }
            if send_effort is not None:
                payload["reasoning_effort"] = send_effort
            return json.dumps(payload).encode()

        last_err = ""
        for attempt in range(1, effective_retries + 1):
            model_id = variants[(attempt - 1) % len(variants)]
            body = make_body(model_id)
            t0 = time.time()
            headers = {"Content-Type": "application/json"}
            if self.key:                      # 本地端點沒有金鑰，不要送空的 Bearer
                headers["Authorization"] = f"Bearer {self.key}"
            req = urllib.request.Request(self.api, data=body, headers=headers)
            try:
                # socket 逾時綁單次 recv，牆鐘護欄綁整個請求（見 _wall_clock_guard）。
                # round460e：本行是本檔對 `generate()` 的**唯一**改動，純基建
                # ——它只給「OS 沒兌現 socket 逾時」那條路一個上界，
                # 正常路徑上行為逐字不變（護欄比 socket 逾時晚
                # WALL_CLOCK_SLACK_S 才動作，且咬到之後走既有的重試→InfraVoid）。
                with _wall_clock_guard(effective_timeout + WALL_CLOCK_SLACK_S):
                    with urllib.request.urlopen(req, timeout=effective_timeout) as r:
                        payload = json.load(r)
                d = payload.get("data", payload)
                # ⚠ 算力中轉（8765）會回 **HTTP 200 但 body 是 {"error": "terminated"}**。
                #   不擋的話會在下一行變成 KeyError: 'choices'——行為仍然是重試，
                #   但落盤的錯誤訊息看不出是端點掐掉的還是回應結構變了。
                #   實測 2026-08-24：8 筆連續呼叫 0 失敗，這是瞬斷不是常態；
                #   正因為罕見才更要留下看得懂的訊息，事後才查得出來。
                if isinstance(d, dict) and "choices" not in d and d.get("error"):
                    raise RelayError(f"端點回 200 但 body 是錯誤：{d['error']!r}")
                choice = d["choices"][0]["message"]
                text = choice.get("content") or ""
                # ⚠ 推理模型（實測 qwen3.6-35b-a3b）把思考放進 reasoning_content，
                #   答案放 content。token 預算被思考吃光時 content 會是**空字串**，
                #   而空字串進 extract_code 之後會被記成「答錯」——
                #   那是端點狀況冒充能力上限，正好是 infra_void 要擋的東西。
                #   空回應在這裡走重試；重試用盡才記 infra_void（不算成功也不算失敗）。
                if not text.strip():
                    raise EmptyResponse(
                        f"content 為空（finish_reason="
                        f"{d['choices'][0].get('finish_reason')}，"
                        f"reasoning {len(choice.get('reasoning_content') or '')} 字）")
                gw = choice.get("provider_metadata", {}).get("gateway", {})
                usage = d.get("usage") or {}
                cost = float(usage.get("cost") or gw.get("cost") or 0)
                # BYOK calls may bill $0 at the Cline gateway while still consuming paid
                # provider inference. market_cost preserves equal-cost comparisons.
                market_cost = float(usage.get("market_cost") or cost)
                self.calls += 1
                self.cost += cost
                self.market_cost += market_cost
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "api": self.api,
                    "model": model_id,
                    # 伺服端在回應本體裡自己報的 model 欄（OpenAI 相容格式的頂層
                    # "model" 鍵）——`model`/`model_configured` 只驗得到請求端
                    # 送出的值沒被換掉，驗不到 1004／中轉那端服務的是不是同一個
                    # 模型（R483 §5、R516 §8 的落盤缺口）。沒有就是 None，
                    # 不假裝有值。
                    "server_model": d.get("model") if isinstance(d, dict) else None,
                    "model_configured": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": True,
                    "timeout_s": effective_timeout, "retries_max": effective_retries,
                    # 送出去的推論模式（None ＝ 沒送這個欄位）。鐵律 3：送了什麼
                    # 要落盤，否則「這一列是在哪一種推論條件下量到的」查不回來。
                    "reasoning_effort": send_effort,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "cost_usd": cost,
                    "market_cost_usd": market_cost,
                    "usage": usage,
                    "system": effective_system,
                    "prompt": prompt,          # 全文
                    "response": text,          # 全文
                    "meta": meta or {},
                })
                return text
            except Exception as e:                      # noqa: BLE001
                # round662：`str(HTTPError)` 只給「HTTP Error 400: Bad Request」，
                # 伺服器解釋錯誤原因的**回應本體被丟掉**。實測後果：
                # `g_het3_r278` 的 133 筆與 `g_r356_3arm` 的 517 筆 400 訊息
                # 逐字完全相同，事後無法從 log 追根因——而 400 正是 Group B
                # 92.8% 的 infra_void 主因。`e.read()` 拿得到本體，補上它。
                # ⚠ 純儀器：不改控制流、不改重試判定、不改 void 的定義。
                body = ""
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        raw = e.read()
                        if raw:
                            body = " | body=" + raw.decode(
                                "utf-8", "replace")[:2000]
                    except Exception:               # noqa: BLE001
                        body = " | body=<讀取失敗>"
                last_err = f"{type(e).__name__}: {e}{body}"
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "api": self.api,
                    "model": model_id,
                    "model_configured": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": False,
                    "timeout_s": effective_timeout, "retries_max": effective_retries,
                    "reasoning_effort": send_effort,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": last_err,
                    "system": effective_system,
                    "prompt": prompt,
                    "meta": meta or {},
                })
                # 404 為什麼從「不重試」移出來（2026-08-24 實測）：
                # runs/g_off60_relay_20260824 有 18 格 infra_void，**17 格是 404**。
                # 原因不是模型 ID 打錯——是 8765 算力中轉在 run 跑到一半換了節點，
                # 新節點的模型 ID 命名不同（`qwen/xxx` → `qwen_xxx`），舊 ID 短暫
                # 解析不到。同一輪的延遲也從前半中位 40s 跳到後半 107s，佐證換了節點。
                #
                # 對**固定端點**而言 404 是永久錯誤，不該重試；對**負載平衡的中轉**
                # 而言它可能是暫時的。這裡的代價不對稱：誤判成永久 ⇒ 白丟 17 格；
                # 誤判成暫時 ⇒ 多花四次重試後仍記 infra_void，結果一樣只是慢一點。
                # 所以 404 走重試。
                #
                # 400 為什麼也移出「不重試」（round356，2026-08-30 實測，推翻
                # round296 的「記錄不修」）：round296 定的重啟條件是「同一
                # (agent,task) 重試後會成功」，本輪的證據是它的等價形式——
                # `g_r342/g_r345/g_r348` 三個 run 合併，29 個曾經 400-void 的
                # task_id 裡 24 個在同一個 run 的另一臂成功過（不是模型對這題
                # 內容穩定拒答）；且 56 個 400 錯誤裡 51 個在 attempt=1 就
                # `break`（`InfraVoid` 訊息裡的「重試 N 次仍失敗」是印
                # `effective_retries` 設定值，不是實際嘗試次數，從沒真的重試
                # 過）。同一時間 400 造成的 void 率把三個 post-fix run 的
                # 每一臂都推到 30-65%，遠超 SPEC 的 10% 閘門（見
                # `DECISION_20260830_R356_HTTP400_RETRY_REVERSAL.md`）。
                # round296 把範圍限定在「review 角色」，但 OFF5 臂的 400
                # 全部發生在 gen 角色（OFF5 不叫 review）——前提不成立，
                # 改成不分角色。401/402/403（認證／額度）維持不重試，
                # 語意上不像暫時性路由問題。
                non_retryable = isinstance(e, urllib.error.HTTPError) and e.code in {
                    401, 402, 403,
                }
                if non_retryable:
                    break
                if attempt < effective_retries:
                    time.sleep(self.backoff_s * (2 ** (attempt - 1)))

        raise InfraVoid(f"{self.agent_id} 重試 {effective_retries} 次仍失敗：{last_err}")

    # ── 多輪呼叫（round460b：harness 臂 HPI/HOC/HMIX 用）──────────────────
    #
    # ⚠ 為什麼是**另一個方法**而不是把 `generate` 重構成它的特例：
    #   `generate` 是 OFF／OFF5／CONFORM／EQ5／ON 五條既有臂**唯一**的呼叫路徑，
    #   它的落盤欄位（`prompt` 全文、`system`、`model`、重試語意）已經有 r444–r447
    #   等多輪 run 的歸檔在引用。重構它＝所有既有臂的碼與落盤同時變動，
    #   而本輪的承重宣稱之一就是「既有五臂逐位不變」（HARNESS_STUDY §4.5）。
    #   代價是這裡與 `generate` 有一段重複的請求／重試碼——**那是刻意付的**，
    #   `tests/test_gain_harness_arms.py` 用 `generate` 原始碼的 sha256 釘死不變。
    #
    # 與 `generate` 的差別只有三處（HARNESS_STUDY §4.0.2 逐字）：
    #   1. body 的 `messages` ＝ [system] + 呼叫端給的整串對話；
    #   2. 落盤多 `messages`（全文陣列）／`finish_reason`／`turn` 三個鍵，
    #      並**保留** `prompt` ＝ 最後一則 user 訊息全文，讓 `latency_summary`、
    #      `calls_audit.py` 這些既有工具不必改就讀得到；
    #   3. 回傳 `(text, info)`——`finish_reason` 是截斷保護（HARNESS_STUDY F6）
    #      的唯一資訊來源，而 `generate` 只回字串，拿不到它。
    #   其餘（temperature、retry／backoff、404 型號輪替、RelayError／
    #   EmptyResponse／InfraVoid 語意、非重試碼 401/402/403）逐字沿用。
    def chat(self, messages: list[dict], *, role: str = "gen",
             meta: dict | None = None, system: str | None = None,
             timeout_s: int | None = None, retries: int | None = None,
             turn: int | None = None, max_tokens: int | None = None,
             reasoning_effort: str | None = None,
             ) -> tuple[str, dict]:
        """messages ＝ [{"role": "user"|"assistant", "content": str}, ...]。

        `system` 為 None 時用 `self.system`。回傳 `(text, info)`；`info` 至少含
        `finish_reason`／`usage`／`model`／`server_model`／`latency_ms`／`attempt`。

        ⚠ `max_tokens` 預設 **None ＝ 不送**：實驗臂的 request body 除了 `messages`
          之外必須與 OFF 完全相同，只有 H 臂設輸出上限會憑空造出一個 OFF 沒有的
          劣勢（HARNESS_STUDY §4.0.6）。只有**線路模式探針**會傳這個參數。

        ⚠ `reasoning_effort` 為 None 時用 `self.reasoning_effort`；`"default"`
          與 None 都**不送這個欄位**。送出去的值逐次落盤（`reasoning_effort` 欄），
          因為「1003 是 thinking、1004 不是」這種事只有落盤看得出來
          （DECISION_20260912 §十一）。
        """
        effective_system = system or self.system
        effective_timeout = self.timeout_s if timeout_s is None else timeout_s
        effective_retries = self.retries if retries is None else retries
        if effective_timeout <= 0 or effective_retries <= 0:
            raise ValueError("timeout_s／retries 必須為正數")
        if not messages or any(
                not isinstance(m, dict) or m.get("role") not in ("user", "assistant")
                or not isinstance(m.get("content"), str) for m in messages):
            raise ValueError("messages 必須是 user／assistant 的 {role, content} 串")
        last_user = next((m["content"] for m in reversed(messages)
                          if m["role"] == "user"), "")

        variants = [self.model]
        if "/" in self.model:
            variants.append(self.model.replace("/", "_", 1))
        elif "_" in self.model:
            variants.append(self.model.replace("_", "/", 1))

        effort = (self.reasoning_effort if reasoning_effort is None
                  else reasoning_effort)
        if effort is not None and effort not in REASONING_EFFORT_VALUES:
            raise ValueError(
                f"reasoning_effort 只認得 {REASONING_EFFORT_VALUES}，拿到 {effort!r}")
        send_effort = effort if effort not in (None, REASONING_EFFORT_OMIT) else None

        def make_body(model_id: str) -> bytes:
            payload = {
                "model": model_id,
                "messages": ([{"role": "system", "content": effective_system}]
                             + [{"role": m["role"], "content": m["content"]}
                                for m in messages]),
                "temperature": self.temperature,
                "stream": False,
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            # 推論模式是**實驗條件**（DECISION_20260912 §十一：同一顆模型檔在
            # 1003／1004 上跑成 thinking／非 thinking 兩種條件）⇒ 要嘛不送、
            # 要嘛送出去而且落盤送了什麼，不准有「大概是預設值」這種狀態。
            if send_effort is not None:
                payload["reasoning_effort"] = send_effort
            return json.dumps(payload).encode()

        last_err = ""
        for attempt in range(1, effective_retries + 1):
            model_id = variants[(attempt - 1) % len(variants)]
            body = make_body(model_id)
            t0 = time.time()
            headers = {"Content-Type": "application/json"}
            if self.key:
                headers["Authorization"] = f"Bearer {self.key}"
            req = urllib.request.Request(self.api, data=body, headers=headers)
            try:
                # socket 逾時綁單次 recv，牆鐘護欄綁整個請求（見 _wall_clock_guard）
                with _wall_clock_guard(effective_timeout + WALL_CLOCK_SLACK_S):
                    with urllib.request.urlopen(req, timeout=effective_timeout) as r:
                        payload = json.load(r)
                d = payload.get("data", payload)
                if isinstance(d, dict) and "choices" not in d and d.get("error"):
                    raise RelayError(f"端點回 200 但 body 是錯誤：{d['error']!r}")
                choice = d["choices"][0]["message"]
                finish_reason = d["choices"][0].get("finish_reason")
                text = choice.get("content") or ""
                if not text.strip():
                    raise EmptyResponse(
                        f"content 為空（finish_reason={finish_reason}，"
                        f"reasoning {len(choice.get('reasoning_content') or '')} 字）")
                gw = choice.get("provider_metadata", {}).get("gateway", {})
                usage = d.get("usage") or {}
                cost = float(usage.get("cost") or gw.get("cost") or 0)
                market_cost = float(usage.get("market_cost") or cost)
                self.calls += 1
                self.cost += cost
                self.market_cost += market_cost
                latency_ms = int((time.time() - t0) * 1000)
                server_model = d.get("model") if isinstance(d, dict) else None
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "api": self.api,
                    "model": model_id,
                    "server_model": server_model,
                    "model_configured": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": True,
                    "timeout_s": effective_timeout, "retries_max": effective_retries,
                    # 送出去的推論模式（None ＝ 沒送這個欄位）。
                    "reasoning_effort": send_effort,
                    "latency_ms": latency_ms,
                    "cost_usd": cost,
                    "market_cost_usd": market_cost,
                    "usage": usage,
                    "system": effective_system,
                    # `prompt` 保留＝最後一則 user 訊息全文（既有工具的相容欄位）；
                    # `messages` 才是這一次真正送出去的全部內容。
                    "prompt": last_user,
                    "messages": [{"role": m["role"], "content": m["content"]}
                                 for m in messages],
                    "finish_reason": finish_reason,
                    "turn": turn,
                    "response": text,
                    "meta": meta or {},
                })
                return text, {
                    "finish_reason": finish_reason, "usage": usage,
                    "model": model_id, "server_model": server_model,
                    "latency_ms": latency_ms, "attempt": attempt,
                    "cost_usd": cost, "market_cost_usd": market_cost,
                }
            except Exception as e:                      # noqa: BLE001
                body_txt = ""
                if isinstance(e, urllib.error.HTTPError):
                    try:
                        raw = e.read()
                        if raw:
                            body_txt = " | body=" + raw.decode(
                                "utf-8", "replace")[:2000]
                    except Exception:               # noqa: BLE001
                        body_txt = " | body=<讀取失敗>"
                last_err = f"{type(e).__name__}: {e}{body_txt}"
                retryable = is_retryable(e, last_err)
                reload_window = has_reload_marker(last_err)
                wait_s = (self.backoff_delay(attempt)
                          if retryable and attempt < effective_retries else 0.0)
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "api": self.api,
                    "model": model_id,
                    "model_configured": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": False,
                    "timeout_s": effective_timeout, "retries_max": effective_retries,
                    "reasoning_effort": send_effort,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "error": last_err,
                    # 為什麼要落盤這三格：retry 的**判準**與**等了多久**在事後
                    # 只能靠它們重建。r5 的 infra_void 之所以查得出是「重載窗
                    # 太短」而不是「後端壞了」，靠的就是有沒有這種可讀的紀錄。
                    "retryable": retryable,
                    "reload_window": reload_window,
                    "backoff_s": wait_s,
                    "system": effective_system,
                    "prompt": last_user,
                    "messages": [{"role": m["role"], "content": m["content"]}
                                 for m in messages],
                    "turn": turn,
                    "meta": meta or {},
                })
                if not retryable:
                    break
                if wait_s:
                    time.sleep(wait_s)

        raise InfraVoid(f"{self.agent_id} 重試 {effective_retries} 次仍失敗：{last_err}")


def load_keys(path: str | None = None) -> list[str]:
    p = pathlib.Path(path or os.environ.get("CLINE_KEYS", "~/.cline-keys")).expanduser()
    if endpoint() != API and not p.exists():
        # 換到本地／自架端點且沒有金鑰檔：回一把空金鑰，不送 Authorization。
        # 只在**端點確實被換掉**時才允許——否則打正式端點缺金鑰會靜默變成 401
        # 全滅，而那在 summary 裡長得跟「題目太難」一模一樣。
        return [""]
    ks = [line.strip() for line in p.read_text().splitlines() if line.strip()]
    if not ks:
        raise SystemExit(f"{p} 裡沒有金鑰")
    slots = os.environ.get("CLINE_KEY_INDICES", "").strip()
    if slots:
        try:
            indices = [int(item.strip()) for item in slots.split(",")]
            if not indices or any(index < 0 or index >= len(ks) for index in indices):
                raise ValueError
        except ValueError as exc:
            raise SystemExit(
                "CLINE_KEY_INDICES 必須是現有 key 的零起算索引，例如 0,2,4"
            ) from exc
        ks = [ks[index] for index in indices]
    return ks


# ── agent 池：異質性從 system prompt 來 ──────────────────────────────
#
# ⚠ SPEC_GAIN §5.3：池子必須**真的**異質，而且差距要先量出來當前提。
#   全部一樣強的話，信譽路由沒有東西可以路由——那時量到「沒有增益」
#   會是實驗設計的結果，不是機制的性質。
#
# ⚠ KS-1（鐵律 1）：這些 system prompt 一律不得出現「你有責任／會被懲罰」
#   類措辭。差異只能是**工作習慣**，不能是被監督的暗示——
#   否則量到的是提示詞效果不是機制效果。
POOL = [
    ("careful-1", "你是一位資深工程師。寫程式之前先想清楚邊界情況："
                  "空輸入、單一元素、重複值、負數、型別不一致。寫完自己檢查一遍。"),
    ("careful-2", "你是一位注重正確性的工程師。先把題目的條件逐項列出來，"
                  "確認每一項都被處理到，再寫程式碼。"),
    ("plain-1",   "你是一位程式設計師。"),
    ("plain-2",   "你是一位程式設計師。請完成使用者要求的函式。"),
    ("hasty-1",   "你是一位講求速度的程式設計師。直接寫出最短的可行解，不要多想。"),
    ("hasty-2",   "你是一位程式設計師。快速給出答案，以最常見的情況為主即可。"),
]

REVIEWER_SYSTEM = (
    "你是一位獨立程式碼審查者。你會看到題目與候選解答。"
    "找出會讓解答不符合題意的具體反例；不要因為程式看起來合理就通過。"
    "第一行必須且只能是 VERDICT: PASS 或 VERDICT: FAIL。"
    "第二行以 CONCERN: 開頭，寫最重要的一個問題或『none』。"
    "若判 FAIL，第三行必須是 TEST_ARGS: 加上一個 Python literal list，表示呼叫"
    "目標函式的 positional arguments；第四行必須是 EXPECTED: 加上預期回傳值的"
    "Python literal。list 的每個元素對應一個 positional argument；函式只有"
    "一個引數時 list 長度為 1，不要再包一層。例：函式接兩個引數 "
    "(count, label)，範例是 TEST_ARGS: [3, \"abc\"] 與 EXPECTED: 1。"
    "若判 PASS，第三、四行分別寫 TEST_ARGS: NONE 與 EXPECTED: NONE。"
    "反例會由系統實際執行；無法解析或沒有推翻候選解答的 FAIL 不會計票。"
    "不要重寫完整答案，也不要在這四行之外輸出文字。"
)

# 同一模型家族仍有共同盲區；這些 lens 只能讓「當下做的事」不同，不能假裝成
# 模型家族異質化。實驗必須繼續單報 reviewer accuracy 與錯誤相關性。
REVIEW_LENSES = {
    "careful-1": "你的審查視角：邊界值、空輸入、重複值與負數。",
    "careful-2": "你的審查視角：逐條對照題目契約，找遺漏條件。",
    "plain-1": "你的審查視角：用最小反例推翻候選解答。",
    "plain-2": "你的審查視角：函式簽名、回傳型別、例外與副作用。",
    "hasty-1": "你的審查視角：語法、名稱、匯入與能否實際執行。",
    "hasty-2": "你的審查視角：複雜度、極端輸入與隱含假設。",
}
