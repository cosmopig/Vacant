"""suitegauge — 「套件要上鏈，必須先證明它擋得住一組已知壞草稿」的純量具。

這支在架構裡承重什麼
====================
R449（`DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md`）§三-3 量到的破口：
去中心化執行對**驗收套件本身被腐化**零保護。`visible_check := "pass"` 時，執行器
全誠實、每條鏈都驗得過、爭議率 0.0%，而交付準確率掉 6.47pp（MBPP+）／18.68pp（LCB），
假交付 31%／49%。§四-3 的裁決是把 repo 已有的量具驗證（`gain_run.probe_instrument`
的「參考解通過 12/12、壞解被擋 12/12」）**綁進套件的 commit**。

本模組就是那個量具的**純函式核心**，被兩邊共用：

  - `ops/gain/gain_run.py::probe_instrument`（SPEC_GAIN §5.2 的量具驗證，行為不變）
  - `vacant/peerexec.py::commit_suite`（套件上鏈前的合格閘）

**為什麼要抽出來而不是各寫一份**：兩份實作＝兩條會漂移的判準。`probe_instrument`
的 docstring 已經寫過「只驗正向會漏掉『什麼都判通過』，只驗反向會漏掉『什麼都判
失敗』」——這條規則只准有一個真相來源。（`gain_run` 那邊的 `stub = ...` 字面留在
原處不動：`ops/gain/r474_stub_sweep.py` 用 AST 逐字取那一行，抽走會讓那把尺安靜失準。）

紅線與誠實邊界（改碼不得刪）
----------------------------
1. **V/GT 分離沒有破。** 量具吃的是參考解與壞樁，兩者都是**驗證者側**的物件：
   不是任何 worker 的產出、不進任何 prompt、不進 `hidden_check` 的路徑。這與
   `gain_run._canonical_solutions` 的 docstring 是同一套論證（「量具驗證是驗證者側
   的動作，跟 agent 無關」）。餵進來的 `check_code` 是**可見**驗收套件；
   `hidden_check` 一處都沒有出現在本模組。
2. **雙向才算數。** `ok` 同時要求 `ref_passed` 與 `all_rejected`，而且
   `n_broken >= 1`——空的壞解集合會讓 `all_rejected` 空洞地成立，那是 fail-open。
3. **單邊保證。** 壞樁擋得住只證明「這套驗收不是對什麼都放行」，**不證明**它涵蓋
   真需求。一套「通過量具、但把三條 assert 刪到只剩一條」的套件照樣通過本量具——
   殘留攻擊的量測見 `ops/gain/replay/peer_exec_sim.py --gauge-gate`（weak 變體）。這條是
   R449 §七的推翻條件二，寫在這裡以免日後被讀成「套件固定點已解」。
4. **沙箱是被信任的輸入。** `runner` 注入進來，本模組不決定怎麼跑；跑法錯了
   （白名單漏洞、逾時）量具會一致地錯，這是 peerexec 誠實邊界 §3 的同一條。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Sequence

GAUGE_VERSION = 1

#: `runner(code, check_code, entry_point, timeout_s) -> (通過?, 訊息)`。
#: 簽章刻意與 `gain_run.meets_demand` 對齊，讓「量具用的判準」與「出貨閘門用的判準」
#: 是同一個函式，不是兩個長得像的函式。
CheckRunner = Callable[[str, str, "str | None", int], "tuple[bool, str]"]

DEFAULT_TIMEOUT_S = 10


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def broken_stub(entry_point: str | None) -> str:
    """預設壞樁：能載入、什麼都不算。

    ⚠ 這一行與 `gain_run.probe_instrument` 裡的 `stub = ...` **必須逐字相同**。
      那邊留著字面而不是呼叫這裡，是因為 `ops/gain/r474_stub_sweep.py` 用
      `ast.get_source_segment` 逐字取那個運算式當作它自己的樁（`H_stub_wiring`／
      `I_stub_tracks_source` 兩條自檢釘住這件事）。漂移的防呆寫在
      `tests/test_peerexec.py::test_default_broken_stub_matches_probe_instrument`：
      它用同一支 AST 抽取器把那邊的字面取出來 eval，跟這裡比對。
    """
    return f"def {entry_point or '_f'}(*a, **k):\n    return None\n"


def default_runner(
    code: str, check_code: str, entry_point: str | None, timeout_s: int,
) -> tuple[bool, str]:
    """預設跑法＝`gain_run.meets_demand`，lazy import。

    lazy 的理由與 `peerexec.sandbox_probe` 同一條：`ops.gain` 是實驗 runner，不是
    `vacant` 的相依。本模組在沒有 ops 的環境（展件）仍然 import 得起來。
    """
    from ops.gain.gain_run import meets_demand  # noqa: PLC0415

    return meets_demand(code, check_code, timeout_s, entry_point=entry_point)


@dataclass(frozen=True)
class GaugeOutcome:
    """一次量具驗證的完整產物。`ok` 是唯一的合格判準，其餘欄位是它的憑據。"""

    suite_sha256: str
    ref_sha256: str
    ref_passed: bool
    ref_detail: str
    n_broken: int
    n_rejected: int
    accepted_stubs: tuple[int, ...]      # 溜過去的壞樁 index（要指名，不只是計數）

    @property
    def all_rejected(self) -> bool:
        return self.n_broken > 0 and self.n_rejected == self.n_broken

    @property
    def ok(self) -> bool:
        """雙向都要過，而且壞解集合不准是空的（空集合＝fail-open）。"""
        return bool(self.ref_passed and self.all_rejected)

    def as_dict(self) -> dict:
        return {
            "v": GAUGE_VERSION,
            "suite_sha256": self.suite_sha256,
            "ref_sha256": self.ref_sha256,
            "ref_passed": self.ref_passed,
            "n_broken": self.n_broken,
            "n_rejected": self.n_rejected,
            "all_rejected": self.all_rejected,
            "accepted_stubs": list(self.accepted_stubs),
            "ok": self.ok,
        }


def gauge_suite(
    check_code: str,
    reference: str,
    broken_stubs: Sequence[str] = (),
    *,
    entry_point: str | None = None,
    runner: CheckRunner | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> GaugeOutcome:
    """SPEC_GAIN §5.2 的兩個方向，對**一套**驗收跑一次。

    先跑參考解（必須通過），再依序跑每一個壞樁（每一個都必須被擋）。呼叫順序固定，
    因為 `probe_instrument` 的落盤順序就是這個順序——換順序等於換一份產物。

    例外**不吞**：`runner` 丟出來的（例如 `InfraVoid`）照原樣往上拋。
    「量具跑不起來」與「量具量到 0」必須分得開，這是 06-30 稽核紀律的原句。
    """
    run = runner or default_runner
    ref_ok, ref_msg = run(reference, check_code, entry_point, timeout_s)
    accepted: list[int] = []
    n_rej = 0
    for i, stub in enumerate(broken_stubs):
        stub_ok, _ = run(stub, check_code, entry_point, timeout_s)
        if stub_ok:
            accepted.append(i)
        else:
            n_rej += 1
    return GaugeOutcome(
        suite_sha256=sha256_hex(check_code),
        ref_sha256=sha256_hex(reference),
        ref_passed=bool(ref_ok),
        ref_detail=ref_msg or "",
        n_broken=len(broken_stubs),
        n_rejected=n_rej,
        accepted_stubs=tuple(accepted),
    )
