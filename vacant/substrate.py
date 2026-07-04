"""L0 substrate — 可換的「腦」。架構總規格 §3 L0 / §4 substrate 層。

設計原則（共識定案 §4）：
  vacant 平常睡硬碟（零算力），被喚醒才租用一顆共享 base model。
  多樣性活在「身體狀態」（HERMES_HOME 的 skills/memory），不在算力。

本檔提供兩種 substrate：

  1. EchoSubstrate（本機 CPU、零 GPU、零 API）——
     這正是規格說的「A 層機制模擬（免費，CPU）」。它真的讀寫 vacant 的
     HERMES_HOME：解出一題可檢查任務後，把該 niche 當成「習得的 skill」
     寫回 HOME。於是：
       - 復活（G3）可被驗收：第二次喚醒同一身體 → 帶回已習得 skills。
       - 學習曲線（§11）真的會上升：累積越多 skill → 正確率越高。
     這是 AutoHarness「自合成、被環境驗證的 code harness」在 CPU 上的
     最小忠實模型（skill = 對某 niche 已驗證可解）。

  2. HermesACPSubstrate（B 層，需 3090 + vLLM + Hermes）——
     真正接 Hermes Agent 的位置，附 file:line 整合說明（架構總規格 §7）。
     本機跑不動 GPU，故僅為文件化 stub，待上機（G1）接通。
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SubstrateResult:
    output: str
    substrate_id: str          # 哪顆腦（用於 reputation 的 per-substrate keying）
    learned_skill: str | None  # 這次是否習得新 skill（accumulation 訊號）
    error: str | None = None   # infra 層失敗訊號（如 "infra_void"）；非 None 者呼叫端不得計為一票


class Substrate(ABC):
    """喚醒後，host 把一個 substrate「綁」到某 vacant 的 HERMES_HOME 上跑。"""

    substrate_id: str

    @abstractmethod
    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        """在 home 的累積狀態上跑一個 prompt/task，並把新習得寫回 home。"""
        raise NotImplementedError


# --- HOME 的最小檔案模型（對應 HERMES_HOME 的 skills/memories）---------------
def _skills_path(home: Path) -> Path:
    return home / "skills.json"


def _memory_path(home: Path) -> Path:
    return home / "memory.ndjson"


def load_skills(home: Path) -> set[str]:
    p = _skills_path(home)
    if p.exists():
        return set(json.loads(p.read_text(encoding="utf-8")))
    return set()


def save_skills(home: Path, skills: set[str]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    _skills_path(home).write_text(
        json.dumps(sorted(skills), ensure_ascii=False), encoding="utf-8"
    )


def append_memory(home: Path, item: dict[str, Any]) -> None:
    home.mkdir(parents=True, exist_ok=True)
    with _memory_path(home).open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


class EchoSubstrate(Substrate):
    """CPU-only 確定性 substrate。可解一族可檢查任務（見 tasks.py）。

    行為模型：
      - 若該任務 niche 已是 home 的 skill → 確定解對（已習得專家）。
      - 否則以 base 機率 p_base 解對（裸 base model 偶爾會）；解對且尚未習得
        → 把該 niche 寫回 home 當新 skill（accumulation / 進化）。
    用 (vacant_id, task_id) 作種子 → 完全可重現（固定 seed，§11 可重現性）。
    """

    def __init__(self, substrate_id: str = "echo-cpu", p_base: float = 0.34) -> None:
        self.substrate_id = substrate_id
        self.p_base = p_base

    def _seeded_unit(self, *parts: str) -> float:
        h = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
        return int.from_bytes(h[:8], "big") / 2**64

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        if task is None:
            # 無結構任務：純回聲（保留 demo 可用性）。
            return SubstrateResult(output=f"[echo] {prompt}", substrate_id=self.substrate_id, learned_skill=None)

        from .tasks import NICHE_SOLVERS

        niche = task["niche"]
        inp = task["input"]
        solver = NICHE_SOLVERS[niche]  # 專家「真的算」（信封裡沒有答案）
        skills = load_skills(home)
        learned: str | None = None

        if niche in skills:
            answer = solver(inp)  # 已是專家 → 確定解對
        else:
            # 用完整 home 路徑當種子（唯一識別此 vacant），確保 roll 真的逐 vacant 不同。
            roll = self._seeded_unit(str(home), task["task_id"], self.substrate_id)
            if roll < self.p_base:
                answer = solver(inp)
                # 環境驗證通過 → 習得 skill（寫回 HOME），這就是「累積」。
                skills.add(niche)
                save_skills(home, skills)
                learned = niche
                append_memory(home, {"event": "skill_acquired", "niche": niche, "task_id": task["task_id"]})
            else:
                answer = f"[guess:{niche}]"  # 解錯 → verifier 會抓

        return SubstrateResult(output=str(answer), substrate_id=self.substrate_id, learned_skill=learned)


class HermesACPSubstrate(Substrate):
    """B 層真實接法（需 3090 + vLLM + Hermes）。本機為 stub，上機（G1）接通。

    整合點（架構總規格 §7，皆 file:line 已查）：
      - 指 base model 到 3090：config.yaml `model.provider: vllm` +
        `model.base_url: http://localhost:8000/v1`（runtime_provider.py:748）。
      - Ingress 用 ACP：`hermes-acp`（stdio JSON-RPC：initialize → new_session →
        prompt → PromptResponse，觸發 run_conversation）。**不用** mcp serve。
      - 綁身體：spawn 時設 env `HERMES_HOME=<this vacant's home>`
        （hermes_constants.py:44）→ agent init 自動載回該 HOME 的
        skills/memories/SOUL/session lineage（state.db, hermes_state.py:514）。
      - resume：帶 last_session_id 續對話；或同 HOME 開新 session 接新任務。

    上機待驗（§10）：ACP 精確 session resume、反代 base_url 是否被
    is_local_endpoint 干擾、egress allowlist 是否擋住 5 類繞過工具。
    """

    substrate_id = "hermes-acp-vllm"

    def __init__(self, base_url: str = "http://localhost:8000/v1", model: str = "hermes-3-8b") -> None:
        self.base_url = base_url
        self.model = model

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:  # pragma: no cover
        raise NotImplementedError(
            "HermesACPSubstrate 需在測試機（RTX 3090 + vLLM + Hermes）上接通；"
            "本機（Intel Mac 無 GPU）請用 EchoSubstrate 跑 A 層機制模擬。"
        )


# --- NW-1 · LMStudioSubstrate（真模型腦，接 qwen3.6 @ LM Studio）--------------
#
# 為何存在：X1/X3/demo 全要真模型自己算，EchoSubstrate 只是假腦。這是所有實驗的
# 地基。真跑在 VM（http://192.168.56.1:8765）上；本檔用 monkeypatch mock HTTP 做
# 單元測試，無 VM 亦可 import 與測通。

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_think(text: str) -> str:
    """移除 reasoning 模型的 <think>…</think> 區塊，只留最終答案。"""
    return _THINK_RE.sub("", text).strip()


def _extract_message(d: dict[str, Any]) -> str:
    """從 /api/v1/chat 回應取「最後一則 message」的內容。

    容忍兩種回應形狀：
      - responses 風格：{"output": [{"type":"reasoning",...}, {"type":"message","content":...}]}
      - chat-completions 風格：{"choices": [{"message": {"content": ...}}]}
    reasoning 模型把思考放進 reasoning 物件、最終答案放進 message；取最後 message 即答案。
    抽不到任何 message 內容 → 拋 ValueError（由 call() 視為一次失敗、進 retry）。
    """
    out = d.get("output")
    if isinstance(out, list):
        msgs = [
            _content_to_text(o.get("content", ""))
            for o in out
            if isinstance(o, dict) and o.get("type") == "message"
        ]
        if msgs and msgs[-1]:
            return msgs[-1]
    choices = d.get("choices")
    if isinstance(choices, list) and choices:
        content = _content_to_text(((choices[-1] or {}).get("message") or {}).get("content"))
        if content:
            return content
    raise ValueError("回應中找不到 message 內容")


def _content_to_text(content: Any) -> str:
    """content 可能是純字串，也可能是結構化 content-block list（[{type:'text',text:…}]）。
    一律壓平成字串——否則 list 流出 call() 後，run() 的 _strip_think regex 會
    TypeError 崩掉整個 run（而非被當成一次可 retry 的失敗）。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                parts.append(str(b.get("text") or b.get("content") or ""))
            elif isinstance(b, str):
                parts.append(b)
        return "".join(parts)
    return "" if content is None else str(content)


class _InfraVoid(Exception):
    """retry 全數失敗的內部訊號；run() 會把它轉成 SubstrateResult(error='infra_void')。"""


class LMStudioSubstrate(Substrate):
    """B 層真模型腦：接 LM Studio 的 /api/v1/chat（reasoning 模型用）。

    與 EchoSubstrate 同介面（實作 Substrate ABC），但把 prompt 真的送給遠端模型算。
    設計要點（依藍圖 NW-1）：
      - 端點 /api/v1/chat（reasoning 模型在 /v1 的 message.content 常為空，答案被塞進
        reasoning_content；/api/v1/chat 回 output=[reasoning, message]，取 message 即答案）。
      - /no_think（批次）：批次路徑在輸入尾端加 /no_think 指令關掉思考鏈以省 token；
        demo 模式可關掉（no_think=False）並傳有界 max_tokens。
      - max_tokens=None → **不傳該欄**（06-30 教訓：對 reasoning 模型設上限會把它砍在
        思考途中、content 空）。demo 模式可傳有界 2–4k。
      - call() 內建 retry×N（預設 4）；N 次全失敗 → run() 回
        SubstrateResult(output="", error="infra_void")，呼叫端**永不計為一票**。
      - 解析：strip <think>…</think>、取最後 message content。
      - **不寫死答案**：真模型自己算；learned_skill 一律 None——真腦的「學習」走 NW-3
        記憶層決定，不在 substrate 內（EchoSubstrate 的內建學習是假腦特例）。
    """

    def __init__(
        self,
        base: str = "http://192.168.56.1:8765",
        model: str = "qwen/qwen3.6-35b-a3b",
        api: str = "/api/v1/chat",
        max_tokens: int | None = None,
        retry: int = 4,
        timeout: int = 180,
        *,
        no_think: bool = True,
        system: str = "Output only the final answer. No explanation.",
    ) -> None:
        self.base = base.rstrip("/")
        self.model = model
        self.api = "/" + api.lstrip("/")     # 正規化成單一前導斜線
        self.max_tokens = max_tokens
        self.retry = max(1, int(retry))      # 至少嘗試一次
        self.timeout = timeout
        self.no_think = no_think
        self.system = system
        # per-substrate 信譽 keying：同顆腦的票要能被歸併/同源降權（去掉 vendor 前綴）。
        self.substrate_id = f"lmstudio:{model.split('/')[-1]}"

    def _payload(self, user: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "system_prompt": self.system,
            "input": user,
        }
        # max_tokens=None → 不放該欄（讓 reasoning 模型跑完；設上限會被砍在思考途中）。
        if self.max_tokens is not None:
            body["max_tokens"] = self.max_tokens
        return body

    def call(self, user: str) -> str:
        """對 base+api 送一次請求，內建 retry×self.retry。

        回傳未去 <think> 的原始 message 文字；每次「網路錯 / JSON 壞 / 抽不到 message」
        都算一次失敗並重試；self.retry 次全失敗 → 拋 _InfraVoid。
        """
        url = self.base + self.api
        data = json.dumps(self._payload(user)).encode("utf-8")
        last: Exception | None = None
        for _ in range(self.retry):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    d = json.load(r)
                return _extract_message(d)  # 抽不到 message → ValueError → 進 retry
            except Exception as e:  # noqa: BLE001 — infra 層一律吞掉並重試
                last = e
                continue
        raise _InfraVoid(str(last))

    def run(self, home: Path, prompt: str, task: dict[str, Any] | None) -> SubstrateResult:
        # 組使用者輸入：prompt（＋互查回饋 feedback，若有）（＋/no_think 批次指令）。
        parts = [prompt]
        if task:
            fb = (task.get("feedback") or "").strip()
            if fb:
                parts.append(fb)
        if self.no_think:
            parts.append("/no_think")  # 批次模式關思考鏈（省 token）
        user = "\n".join(parts)

        try:
            raw = self.call(user)
        except _InfraVoid:
            # retry 全失敗 → infra_void；呼叫端絕不把它計為一票（06-30 污染教訓）。
            return SubstrateResult(
                output="", substrate_id=self.substrate_id, learned_skill=None, error="infra_void"
            )

        answer = _strip_think(raw)  # reasoning 模型回應含 <think>…</think>，去掉留答案
        # learned_skill 一律 None：真腦的學習走 NW-3 記憶層，不在 substrate 內決定。
        return SubstrateResult(output=answer, substrate_id=self.substrate_id, learned_skill=None)
