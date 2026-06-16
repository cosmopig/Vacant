"""G3 驗收：同一 vacant 再呼叫帶回 skills/記憶（復活成立）。架構總規格 §4.2。

關鍵設計：第二次喚醒用一個「絕不靠運氣解題」的 substrate（p_base=0），
於是它能解對的*唯一*原因，就是技能從硬碟被載回來——這才真的證明
「持久的是硬碟上的身體，不是記憶體」。
"""

from __future__ import annotations

from vacant.body import VacantBody
from vacant.substrate import EchoSubstrate, load_skills
from vacant.tasks import make_task
from vacant.waker import Waker


def test_revive_brings_back_learned_skill(tmp_path):
    task = make_task(0, "reverse")

    # --- 第一次喚醒：用必學的 substrate，習得 "reverse" 並寫回 HOME ---
    body = VacantBody.create("alice", tmp_path, niches=["reverse"])
    learner = Waker(tmp_path, EchoSubstrate(p_base=1.0))
    learner.register(body)
    r1 = learner.wake(body.identity.vacant_id, task["prompt"], task)
    assert r1.revived is False                       # 初生：沒有過去
    assert r1.result.learned_skill == "reverse"
    assert "reverse" in load_skills(tmp_path / "alice" / "home")

    # --- 模擬 host 重啟：全新 waker + 一顆「永遠不靠運氣」的腦 ---
    reborn = VacantBody.load("alice", tmp_path)       # 從硬碟重新載入
    never_lucky = Waker(tmp_path, EchoSubstrate(p_base=0.0))
    never_lucky.register(reborn)
    r2 = never_lucky.wake(reborn.identity.vacant_id, task["prompt"], task)

    assert r2.revived is True                          # 帶著過去醒來
    assert task["check"](r2.result.output)             # 解對 → 技能確實從硬碟回來了
    assert r2.result.learned_skill is None             # 不是重學，是復用


def test_revive_preserves_logbook_chain(tmp_path):
    """復活後 logbook 仍是同一條可驗證的鏈（seq 連續、簽章過）。"""
    body = VacantBody.create("bob", tmp_path, niches=["caesar3"])
    w = Waker(tmp_path, EchoSubstrate(p_base=1.0))
    w.register(body)
    task = make_task(1, "caesar3")
    w.wake(body.identity.vacant_id, task["prompt"], task)
    w.wake(body.identity.vacant_id, task["prompt"], task)

    reloaded = VacantBody.load("bob", tmp_path)
    assert reloaded.logbook.verify_chain(reloaded.public_identity())
    seqs = [e.seq for e in reloaded.logbook.entries]
    assert seqs == list(range(1, len(seqs) + 1))       # 1,2,3,… 連續
    # 兩次喚醒 → 至少兩筆 WAKE + 兩筆 INFERENCE
    kinds = [e.type for e in reloaded.logbook.entries]
    assert kinds.count("WAKE") == 2
    assert kinds.count("INFERENCE") == 2
