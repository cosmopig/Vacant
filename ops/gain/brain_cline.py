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
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.error
import urllib.request

API = "https://api.cline.bot/api/v1/chat/completions"
DEFAULT_MODEL = "cline-pass/kimi-k3"

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


class ClineBrain:
    """一個 agent。`system` 決定它的性格——異質性就是從這裡來的。"""

    def __init__(self, agent_id: str, system: str, *, key: str,
                 log_path: pathlib.Path, model: str = DEFAULT_MODEL,
                 temperature: float = 0.7, retries: int = 4,
                 backoff_s: float = 2.0, timeout_s: int = 240) -> None:
        self.agent_id = agent_id
        self.system = system
        self.key = key
        self.api = endpoint()
        self.model = model
        self.temperature = temperature
        self.retries = retries
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.cost = 0.0
        self.market_cost = 0.0

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

        def make_body(model_id: str) -> bytes:
            return json.dumps({
                "model": model_id,
                "messages": [{"role": "system", "content": effective_system},
                             {"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "stream": False,
            }).encode()

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
                last_err = f"{type(e).__name__}: {e}"
                self._log({
                    "ts_ms": int(time.time() * 1000),
                    "agent_id": self.agent_id, "role": role,
                    "api": self.api,
                    "model": model_id,
                    "model_configured": self.model, "temperature": self.temperature,
                    "attempt": attempt, "ok": False,
                    "timeout_s": effective_timeout, "retries_max": effective_retries,
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
