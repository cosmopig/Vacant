"""L3 host / waker — 讓「持久 / 復活」成立的最小執行層。架構總規格 §3 L3 / §4.2。

這是 G3（戳出來的關鍵里程碑）：同一 vacant 第二次被呼叫時，必須帶回它第一次
累積的東西。做法忠於規格：

    持久的不是 process，是每個 vacant 的信任庫 + HERMES_HOME。
    復活 alice = host 把一個（substrate）程序綁到 alice 的 HERMES_HOME 並 resume
    → 新程序啟動即從那份 HOME 自動載回 alice 的 skills/記憶/session lineage。

對應 §4.2：查表 vacant_id→HOME → spawn 綁 HOME → resume/new_session → 跑
→ 寫回 home（substrate 自己落地 skills/memory）→ 簽 logbook → 程序退出。

關鍵實作選擇：**每次喚醒都從硬碟重新載入 body**（不靠任何 in-RAM 殘留），
這才真的證明「狀態活在硬碟、不在記憶體」。本機用 EchoSubstrate（CPU）；
上機換 HermesACPSubstrate（3090）即同一條流程。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .atomic import file_lock
from .body import VacantBody
from .substrate import Substrate, SubstrateResult

LogEvent = tuple[str, Any]  # (type, payload)


@dataclass
class VacantHome:
    """host 映射表的一列。架構總規格 §5 VacantHome。"""

    vacant_id: str
    name: str
    last_session_id: int = 0
    state: str = "Dormant"   # Born | Active | Dormant
    wake_count: int = 0


@dataclass
class WakeResult:
    body: VacantBody
    result: SubstrateResult
    session_id: int
    revived: bool  # 是否帶回了先前累積（wake_count>1）


class Waker:
    """vacant_id → HERMES_HOME 映射 + spawn 綁 HOME + resume + 寫回。

    它是 callee body 在一次喚醒中的唯一擁有者：載入 → 記事 → 跑 → 記事 → 寫回，
    全在一個 load/persist 週期內完成（避免多處持有造成不一致）。
    """

    def __init__(self, root: Path, substrate: Substrate) -> None:
        self.root = root
        self.substrate = substrate
        self._table: dict[str, VacantHome] = {}

    def register(self, body: VacantBody) -> None:
        self._table[body.identity.vacant_id] = VacantHome(
            vacant_id=body.identity.vacant_id, name=body.name, state="Born"
        )

    def is_registered(self, vacant_id: str) -> bool:
        return vacant_id in self._table

    def home_of(self, vacant_id: str) -> VacantHome:
        return self._table[vacant_id]

    def wake(
        self,
        vacant_id: str,
        prompt: str,
        task: dict[str, Any] | None = None,
        *,
        pre_events: Iterable[LogEvent] = (),
        post_events: Iterable[LogEvent] = (),
    ) -> WakeResult:
        """喚醒對的身體 → 跑 → 寫回。第二次起 = 復活（帶回累積狀態）。

        pre_events / post_events：閘道想夾帶記在同一 logbook 寫入週期的事件
        （如 ingress 的 A2A_IN / 回送 result 的 A2A_OUT），免去額外 load/persist。
        """
        if vacant_id not in self._table:
            raise KeyError(f"未註冊的 vacant：{vacant_id[:16]}…（host 沒有它的 HOME 映射）")
        home = self._table[vacant_id]

        # 並發鎖：整個 load→改→persist 週期序列化，杜絕兩個程序同時喚醒同一身體造成
        # lost-update / 半截寫入（規格 §4.4 同一 vacant 序列化）。
        with file_lock(self.root / home.name / ".lock"):
            # 復活：從硬碟「綁」新程序到持久身體（不靠任何 in-RAM 殘留）。
            body = VacantBody.load(home.name, self.root)
            home.state = "Active"
            home.wake_count += 1
            # revived = 這份身體載入時「已帶有過去」（logbook 非空）。
            revived = len(body.logbook) > 0

            for etype, payload in pre_events:
                body.log(etype, payload)

            home.last_session_id += 1
            session_id = home.last_session_id
            body.log("WAKE", {"session_id": session_id, "prompt": prompt[:80], "resume": revived})

            # substrate 在這份 HOME 上跑，並自己把 skills/memory 落地回 home。
            result = self.substrate.run(body.home_dir, prompt, task)

            body.log(
                "INFERENCE",
                {
                    "session_id": session_id,
                    "task_id": (task or {}).get("task_id"),
                    "substrate": result.substrate_id,
                    "learned_skill": result.learned_skill,
                    "output_sha256": hashlib.sha256(result.output.encode("utf-8")).hexdigest()[:16],
                },
            )

            for etype, payload in post_events:
                body.log(etype, payload)

            body.persist()  # 全檔原子寫入（見 body.persist / atomic.py）
            home.state = "Dormant"

        return WakeResult(body=body, result=result, session_id=session_id, revived=revived)
