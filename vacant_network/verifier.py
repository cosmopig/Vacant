"""自動 verifier — 可檢查任務 → 用環境真值簽 review。架構總規格 §8。

「誰來評」的解（oracle 問題）：
  - 可檢查任務 → 自動 verifier 用 check() 判對錯 → 給五維分（便宜、客觀、*非循環*，優先）。
  - 不可檢查任務 → 回到 caller 簽 review（互批，仍有 oracle 風險，誠實標明）。

verifier 產出的是「給某 (target, substrate) 的五維評分」，由信任服務寫進 reputation。
評審本身也該簽（可究責）——這由 gateway 在記 logbook 時完成。
"""

from __future__ import annotations

from typing import Any

from .reputation import DIMS


def verify_checkable(task: dict[str, Any], answer: str) -> dict[str, float]:
    """用任務自帶 check() 判對錯，轉成五維評分。

    對可檢查任務：對 → 全維 1.0；錯 → factual/logical 0、其餘中性 0.5
    （relevance/adoption 不該因單次答錯而歸零）。

    誠實邊界（「內層 oracle 問題」）：honesty=0.5 代表「答錯沒有說謊的行為證據」，
    不是「中等可信」。check() 只驗答案對錯，**看不到答題者宣稱的把握度**——「我不確定但
    剛好答錯」（誠實）與「自信地胡謅」（不誠實）會拿到同樣的 0.5。要分辨需另外觀測
    宣稱信心 vs 實際正確的落差，超出單純可檢查任務的範圍（沿用 §10 對 oracle 的態度）。
    """
    correct = bool(task["check"](answer))
    if correct:
        return {d: 1.0 for d in DIMS}
    return {
        "factual": 0.0,
        "logical": 0.0,
        "relevance": 0.5,
        "honesty": 0.5,  # 答錯不等於說謊
        "adoption": 0.0,
    }


def is_correct(task: dict[str, Any], answer: str) -> bool:
    return bool(task["check"](answer))
