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
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SubstrateResult:
    output: str
    substrate_id: str          # 哪顆腦（用於 reputation 的 per-substrate keying）
    learned_skill: str | None  # 這次是否習得新 skill（accumulation 訊號）


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
