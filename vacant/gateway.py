"""L2 閘道（boundary trust）— ingress + egress。架構總規格 §3 L2 / §6。

信任只在「之間那條線」上建立，不碰 agent 腦內（§2.2）：
  - Ingress（被呼叫方）：外來請求先到閘道 → 驗章 → 防 replay → 信譽把關 → 才喚醒 agent。
  - Egress（呼叫方）：agent 對外唯一出口 → 查信譽選對象 → 簽章信封 → 送對端閘道。
  - 閘道只簽 / 驗 / 把關 / 記帳，**不解讀 body 語意**。

閘道是 host 常駐的一部分；vacant 身體睡在硬碟，閘道按需 load → 記 → persist
（callee 身體的 load/persist 委由 waker 在單一週期內完成）。
in-process `peers` 模擬「POST 對端閘道」；上機換真 HTTP 不影響其餘邏輯。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomic import atomic_write_text
from .body import VacantBody, now_ms
from .envelope import ChannelGuard, Envelope, ReviewEnvelope
from .identity import PublicIdentity
from .registry import Registry, ReviewRejected
from .verifier import is_correct, verify_checkable
from .waker import Waker


class BadSignature(Exception):
    """驗章失敗 → 冒名 / 竄改。prevents 級（key custody 假設下）。"""


class ReputationRejected(Exception):
    """信譽把關拒收（known-bad caller）。raises-cost 級。"""


@dataclass
class CallOutcome:
    correct: bool
    answer: str
    callee_id: str
    substrate: str
    result_env: Envelope


class Gateway:
    """一個 vacant 的薄閘道（sidecar）。同時能當呼叫方與被呼叫方。"""

    REP_FLOOR = 0.15       # 信譽地板：低於此且有足夠觀測 → 拒收
    MIN_OBS_TO_GATE = 3.0  # 觀測不足不把關（保護冷啟動）

    def __init__(
        self,
        name: str,
        vacant_id: str,
        root: Path,
        waker: Waker,
        registry: Registry,
    ) -> None:
        self.name = name
        self.vacant_id = vacant_id
        self.root = root
        self.waker = waker
        self.registry = registry
        # production 硬化：ingress 防重放狀態**持久化**到信任庫 → host 重啟後仍防 replay
        # （不再退化為 detects）。啟動時載回上次的 per-sender (seq, hash)。
        self._guard_path = self.root / self.name / "trust" / "ingress_guard.json"
        if self._guard_path.exists():
            self.ingress_guard = ChannelGuard.from_json(json.loads(self._guard_path.read_text()))
        else:
            self.ingress_guard = ChannelGuard()  # per-sender 防重放（收）
        self.egress_guard = ChannelGuard()       # per-target seq（送；本地計數即可）
        self.peers: dict[str, "Gateway"] = {}

    def _persist_ingress_guard(self) -> None:
        atomic_write_text(self._guard_path, json.dumps(self.ingress_guard.to_json()))

    def connect(self, other: "Gateway") -> None:
        """in-process 建立點對點連線（模 peer gateway 握手）。"""
        self.peers[other.vacant_id] = other
        other.peers[self.vacant_id] = self

    # === Egress：呼叫方 =====================================================
    def call(self, niche: str, task: dict[str, Any], *, mode: str = "reputation") -> CallOutcome:
        """a2a_call 的閘道底層：路由 → 簽信封 → 送 → 驗回 → 自動評審。

        mode: "reputation"（C3：UCB 信譽路由）| "random"（C1：隨機路由）。
        """
        substrate_id = self.waker.substrate.substrate_id
        if mode == "random":
            card = self.registry.route_random(niche, seed=task["task_id"])
        else:
            card = self.registry.route(niche, substrate_id)
        if card is None:
            raise LookupError(f"無人宣告能解 niche={niche}")
        callee_id = card.vacant_id

        # 禁止經網路路徑自呼：caller 與 callee 是同一份磁碟身體時，waker.wake 會
        # 載入/寫回它，而本方法尾端又會用「載入時的舊副本」persist → 覆蓋掉 waker
        # 的 WAKE/INFERENCE，造成 logbook 遺失。自我委派應走 in-process，不繞閘道。
        if callee_id == self.vacant_id:
            raise ValueError("不支援經閘道自呼（self-call）；自我子任務請在 in-process 處理")

        callee_gw = self.peers.get(callee_id)
        if callee_gw is None:
            raise LookupError(f"未連線到 callee 閘道：{callee_id[:16]}…")

        body = VacantBody.load(self.name, self.root)  # 呼叫方醒來、簽發、記帳

        seq, prev = self.egress_guard.next_seq(callee_id)
        call_env = Envelope.create(
            body.identity,
            to=callee_id,
            seq=seq,
            prev_hash=prev,
            ts_ms=now_ms(),
            kind="call",
            body={"prompt": task["prompt"], "task_id": task["task_id"], "niche": niche, "input": task["input"]},
        )
        self.egress_guard.record_sent(call_env)
        body.log("A2A_OUT", {"to": callee_id[:16], "task_id": task["task_id"], "seq": seq})

        # try/finally：不論對端 ingress 是否丟例外（驗章/replay/信譽拒收），呼叫方的
        # A2A_OUT（已送出的事實）都要落地 → 與已前進的 egress_guard seq 保持一致。
        try:
            result_env = callee_gw.ingress(call_env)  # 對端只信任已簽章的 envelope

            callee_pub = PublicIdentity.from_hex(callee_id, card.pub_hex)
            if not result_env.verify_sig(callee_pub):
                raise BadSignature("result 信封驗章失敗")
            self.ingress_guard.accept(result_env)

            answer = result_env.body["answer"]
            substrate = result_env.body["substrate"]

            # 自動 verify（可檢查任務）→ 簽 ReviewEnvelope → 餵信譽索引（非循環真值）。
            # credit-memory v1 改動3：review 是綁 (stream, branch, head) 的簽章物件，
            # registry 只收驗簽＋head 新鮮＋去重；weight 由 registry 內生。
            stream_id = result_env.body.get("stream_id") or callee_id
            chain_head = result_env.body.get("chain_head", "")
            branch_id = result_env.body.get("branch_id", "main")
            self.registry.note_head(callee_id, stream_id, chain_head)
            scores = verify_checkable(task, answer)
            review = ReviewEnvelope.create(
                body.identity,
                target_id=callee_id,
                target_stream_id=stream_id,
                branch_id=branch_id,
                target_head=chain_head,
                task_id=task["task_id"],
                substrate=substrate,
                scores=scores,
                ts_ms=now_ms(),
            )
            body.log("REVIEW", {
                "target": callee_id[:16], "task_id": task["task_id"], "scores": scores,
                "target_head": chain_head[:16], "review_sig": review.sig[:16],
            })
            # review 被拒（去重/head 競態）不可毀掉一次已成功、已驗章的交付——
            # 交付與評審是兩件事：前者已完成，後者失敗只記帳不擲回呼叫方。
            try:
                self.registry.record_review(review)
            except ReviewRejected as e:
                body.log("REVIEW_REJECTED", {
                    "target": callee_id[:16], "task_id": task["task_id"], "reason": str(e)[:200],
                })
        finally:
            body.persist()  # 呼叫方一次 load/persist 週期：A2A_OUT（恆）+ REVIEW（成功時）

        return CallOutcome(
            correct=is_correct(task, answer),
            answer=answer,
            callee_id=callee_id,
            substrate=substrate,
            result_env=result_env,
        )

    # === Ingress：被呼叫方 ==================================================
    def ingress(self, env: Envelope) -> Envelope:
        """驗章 → 驗收件人 → 防 replay → 信譽把關 → 喚醒自己 → 簽 result 回。

        被執行的任務輸入「只」來自已簽章的 env.body，沒有任何旁路（side-channel）。
        （Codex 獨立審查抓到的 Bug 2/3：補上收件人檢查、移除未簽 task 旁路，已修。）
        """
        # 1. 驗章（防冒名）。寄件者公鑰來自 registry 的 halo 公告（announce 已驗綁定）。
        sender_card = self.registry.card(env.frm)
        if sender_card is None:
            raise BadSignature(f"未知寄件者（未在 halo 公告）：{env.frm[:16]}…")
        sender = PublicIdentity.from_hex(env.frm, sender_card.pub_hex)
        if not env.verify_sig(sender):
            raise BadSignature(f"call 信封驗章失敗：宣稱來自 {env.frm[:16]}…")

        # 2. 驗收件人：簽章雖覆蓋了 to，但仍須拒絕「不是寄給我」的信封，
        #    否則簽給 Bob 的信封可被投遞到 Carol 處理。
        if env.to != self.vacant_id:
            raise BadSignature(f"收件人不符：信封寄給 {env.to[:16]}…，但我是 {self.vacant_id[:16]}…")

        # 3. 防 replay / 亂序（seq 單調 + prev_hash 串接）。接受後立即持久化 →
        #    host 重啟仍防 replay（production 硬化）。
        self.ingress_guard.accept(env)  # 失敗 → ReplayError
        self._persist_ingress_guard()

        # 4. 信譽把關（known-bad 擋掉；新人靠探索通過）。用「本顆腦上」的口徑，
        #    與 egress 路由一致，避免在這顆腦上爛卻靠別顆腦的好成績矇混。
        score, obs = self.registry.standing(env.frm, self.waker.substrate.substrate_id)
        if obs >= self.MIN_OBS_TO_GATE and score < self.REP_FLOOR:
            raise ReputationRejected(f"caller 信譽 {score:.2f} < 地板 {self.REP_FLOOR}")

        # 5. 被執行的任務「只」由已簽章的 env.body 建構（無未簽旁路）。
        callee_task = {
            "task_id": env.body.get("task_id"),
            "niche": env.body.get("niche"),
            "input": env.body.get("input"),
            "prompt": env.body.get("prompt"),
        }

        # 6. 預留 result 的 seq，連同 A2A_IN/A2A_OUT 一起讓 waker 寫進同一週期
        rseq, rprev = self.egress_guard.next_seq(env.frm)
        wake = self.waker.wake(
            self.vacant_id,
            env.body["prompt"],
            callee_task,
            pre_events=[("A2A_IN", {"from": env.frm[:16], "task_id": env.body.get("task_id"), "seq": env.seq})],
            post_events=[("A2A_OUT", {"to": env.frm[:16], "task_id": env.body.get("task_id"), "seq": rseq, "kind": "result"})],
        )

        # 5. 用喚醒後（已寫回）的 body 身份簽 result（identity 穩定不變）
        lb = wake.body.logbook
        result_env = Envelope.create(
            wake.body.identity,
            to=env.frm,
            seq=rseq,
            prev_hash=rprev,
            ts_ms=now_ms(),
            kind="result",
            body={
                "task_id": env.body.get("task_id"),
                "answer": wake.result.output,
                "substrate": wake.result.substrate_id,
                # 改動3 的 head 新鮮性錨點：交付時附上自己的 stream 身份與鏈頭，
                # caller 的 ReviewEnvelope 就綁著「這個 head 為止的歷史」。
                "stream_id": lb.stream_id() or self.vacant_id,
                "branch_id": lb.branch_id(),
                "chain_head": lb.head(),
            },
        )
        self.egress_guard.record_sent(result_env)
        return result_env
