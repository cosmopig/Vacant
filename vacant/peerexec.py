"""peerexec — 去中心化的「互跑不互審」執行證言層（2026-09-04 人類指令的回應）。

這支在架構裡承重什麼
====================
R440P／R446 把 ON 從「委員會」改成「驗收閘門」（CONFORM）：跑客戶自己的可見驗收
測資、交第一份通過的、全不通過就拒交。等預算下它比多數決多交付 +4.04pp
（`g_r446_eq5_mbpp`，371 題，p=0.0135）。但人類 2026-09-04 指出這件事**把信任重新
集中了**：一個執行器 ＋ 一套驗收測資 ＝ 單點腐化。原始構想是去中心化互審，當初因為
燒預算被丟掉。

本模組是那個構想的**改寫版本**：去中心化的是**執行與證言**，不是**判斷**。

    互跑，不互審。

理由是機制性的、不是修辭：驗收測資是**確定性**的程式。同一份草稿、同一套測資，
誠實的執行器**必須**得到同一個結果。所以

    **意見分歧沒有資訊，執行分歧有資訊。**

LLM 評審之間的分歧永遠只能解讀成「他們看法不同」——那不指認任何人。執行器之間的
分歧只有兩種可能：有人沒有真的跑，或有人簽了跟自己跑出來不一樣的東西。兩者都是
**可歸屬的過錯**，而且簽章直接指出是哪一把金鑰。這是委員會式評審在結構上給不出的
東西。成本也不同：一次驗收執行是本機沙箱，**零模型呼叫**。

機制（三件事，沒有第四件）
--------------------------
1. `Executor.attest`：每個執行器在**自己的**沙箱跑 `visible_check`，把
   {task_id, draft_sha256, suite_sha256, visible_ok, first_failing_test, …}
   簽進**自己的** `vacant.logbook` hash-chain。因為證言是鏈上的一筆，執行器
   事後不能悄悄抽掉它——要抽就得重簽整條鏈。
2. `form_verdict`：對可采信的證言取多數。回傳判決**以及少數方是誰**
   （`dissenters`，具名、附 entry hash 與簽章）。
3. `select_by_quorum`：CONFORM 的選擇語意不變——依序看草稿，第一份被判為通過的
   出貨，全不通過就拒交——只是「通過」現在由法定人數決定，不是由單一執行器決定。

誠實邊界（改碼不得刪，這幾條是規格的一部分）
--------------------------------------------
1. **需求必須可以編譯成可執行的驗收測資。** 跑不起來的需求沒有免費裁判，這個機制會
   退化成「問一堆模型」，而那正是 R438／R516／R440X 量出來沒有價值的東西。
   這條是 R440P §五-1 的原句，搬到這裡一樣有效。
2. **驗收套件本身仍然是被信任的輸入。** 去中心化執行**不會**讓一套錯的驗收變對；
   全體誠實的執行器會一致地、可驗證地交出一個錯的答案。`commit_suite` /
   `open_suite` 只把套件**在時間上釘死**（草稿存在之前就承諾其雜湊），
   `challenge_rerun` 只給落敗方一個重跑的權利——兩者都是 raises-cost，不是 prevents。
   **這是本模組剩下的固定點，不准講成已經解決。**
3. **沙箱缺陷是相關失效，不是腐化。** k 個執行器如果跑同一份 `vacant/checks.py`、
   同一個 Python、同一台機器，它們會**一致地**錯，法定人數會全票通過一個錯的判決，
   而且分歧率為 0（看起來最健康）。要打斷這個相關性需要**實作多樣性**的沙箱，
   本模組沒有提供，也不宣稱提供。（gain_run 的 `_GAIN_ALLOWED_IMPORTS` 白名單
   漏掉 `typing` 曾經結構性地打歪一整條臂——那正是這種失效的實例。）
4. **多數決有數學上界。** 腐化者過半時機制**反轉**：他們成為多數，誠實的執行器被
   `dissenters` 指名。本模組不會假裝偵測得到這件事；`Verdict.unanimous` 與
   `contested` 只描述觀察到的分佈，不描述真相。上界就是 ⌊(k-1)/2⌋，寫在
   `MAJORITY_BOUND_NOTE`。
5. **簽章指認的是金鑰，不是人。** 與 `gain_run.save_receipts` 同一條邊界：私鑰不落盤、
   身份是一次性的，所以收據能證明「這筆證言事後沒被改過、且與同一把金鑰的其他證言
   同源」，**不能**證明背後是哪一個主體。要接到主體需要 `vacant/registry.py` 的
   擁有權表，那不在本模組。

紅線
----
- V/GT 分離（SPEC §5.3）：執行器**只准**跑 `visible_check`。`hidden_check` 一處都
  沒有出現在本模組——計分是稽核端的事，不是機制的一部分。
- KS-1／A4：本模組不產生任何 prompt 文字，零模型呼叫。
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import logbook as _lb
from .canonical import canonical_bytes
from .identity import Identity, PublicIdentity
from .logbook import Logbook, review_commitment

ATTEST_VERSION = 1
ATTEST_TYPE = "peer_exec_attestation"
SUITE_COMMIT_TYPE = "peer_exec_suite_commit"
VERDICT_TYPE = "peer_exec_verdict"

#: 多數決的上界，寫成常數是為了讓它出現在收據裡而不是只出現在論述裡。
MAJORITY_BOUND_NOTE = (
    "majority over k executors tolerates at most floor((k-1)/2) corrupt executors; "
    "beyond that the verdict inverts and honest executors are the named dissenters"
)


def sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def suite_hash(task: Mapping[str, Any]) -> str:
    """驗收套件的雜湊 ＝ sha256(visible_check.code)。

    只雜湊 `visible_check`：`hidden_check` 不是驗收套件的一部分，也不准進入任何
    執行器看得到的東西（V/GT 分離）。
    """
    return sha256_hex(((task.get("visible_check") or {}).get("code")) or "")


# ── 執行探針 ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ProbeResult:
    """一次本機驗收執行的結果。這是執行器**宣稱**看到的東西，不是真相。"""

    visible_ok: bool
    first_failing_test: int | None = None
    n_visible_tests: int | None = None
    loads_ok: bool | None = None
    detail_reason: str | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "visible_ok": bool(self.visible_ok),
            "first_failing_test": self.first_failing_test,
            "n_visible_tests": self.n_visible_tests,
            "loads_ok": self.loads_ok,
            "detail_reason": self.detail_reason,
        }


Probe = Callable[[str, Mapping[str, Any]], ProbeResult]


def sandbox_probe(draft_code: str, task: Mapping[str, Any], *, timeout_s: int = 10) -> ProbeResult:
    """預設探針：跑 runtime **自己的** `meets_demand`／`conform_failure_detail`。

    為什麼是 lazy import：`ops.gain.gain_run` 是實驗 runner，不是 `vacant` 的相依；
    把 import 留在函式內，本模組在沒有 ops 的環境（例如展件）仍然 import 得起來，
    而測試可以注入自己的 probe。**判定邏輯不重寫**——重寫等於多出第二套判準，
    和出貨閘門漂移，那正是 `conform_failure_detail` 的 docstring 已經寫過的坑。
    """
    from ops.gain.gain_run import conform_failure_detail, meets_demand  # noqa: PLC0415

    check_code = ((task.get("visible_check") or {}).get("code")) or ""
    ep = task.get("entry_point")
    ok, _ = meets_demand(draft_code, check_code, timeout_s, entry_point=ep)
    if ok:
        sl = None
        try:
            from ops.gain.gain_run import _visible_test_slicer  # noqa: PLC0415

            sl = _visible_test_slicer(check_code)
        except Exception:  # noqa: BLE001
            sl = None
        return ProbeResult(True, None, sl[0] if sl else None, True, None)
    d = conform_failure_detail(draft_code, dict(task), timeout_s=timeout_s)
    return ProbeResult(
        False,
        d.get("first_failing_test"),
        d.get("n_visible_tests"),
        d.get("loads_ok"),
        d.get("detail_reason"),
    )


# ── 證言 ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Attestation:
    """一筆簽章證言 ＝ 執行器自己 hash-chain 上的一筆 entry。

    `entry` 帶著 seq／prev_hash，所以一筆證言不只是「簽過」，它還**釘在鏈的某個
    位置**上：執行器要抽掉一筆已發出的證言，就得重簽它之後的整條鏈。
    """

    executor_id: str
    entry: _lb.LogEntry

    @property
    def payload(self) -> dict[str, Any]:
        p = self.entry.payload
        return p if isinstance(p, dict) else {}

    @property
    def visible_ok(self) -> bool:
        return bool(self.payload.get("visible_ok"))

    @property
    def entry_hash(self) -> str:
        return self.entry.hash()

    def to_json(self) -> dict[str, Any]:
        return {"executor_id": self.executor_id, "entry": self.entry.to_json()}

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> "Attestation":
        return cls(str(d["executor_id"]), _lb.LogEntry.from_json(dict(d["entry"])))


@dataclass
class Executor:
    """一個具名執行器：一把金鑰、一條 logbook、一個沙箱探針。

    執行器**不評審**。它唯一能說的話是「我跑了這份草稿對這套驗收，結果是這個」。
    它沒有意見的空間，所以也沒有「意見不同」這個藉口。
    """

    executor_id: str
    identity: Identity
    book: Logbook = field(default_factory=Logbook)
    probe: Probe = sandbox_probe

    @classmethod
    def new(cls, executor_id: str, *, probe: Probe = sandbox_probe) -> "Executor":
        return cls(executor_id, Identity.generate(), Logbook(), probe)

    @property
    def public(self) -> PublicIdentity:
        return PublicIdentity(vacant_id=self.identity.vacant_id, pub=self.identity.pub)

    def attest(
        self,
        task: Mapping[str, Any],
        draft_code: str,
        *,
        suite_sha256: str | None = None,
        ts_ms: int | None = None,
    ) -> Attestation:
        """跑一次驗收，把結果簽進自己的鏈，回傳可攜證言。零模型呼叫。"""
        res = self.probe(draft_code, task)
        payload = {
            "v": ATTEST_VERSION,
            "executor_id": self.executor_id,
            "task_id": task.get("task_id"),
            "draft_sha256": sha256_hex(draft_code),
            "suite_sha256": suite_sha256 or suite_hash(task),
            **res.as_payload(),
        }
        entry = self.book.append(
            ATTEST_TYPE, payload, self.identity,
            ts_ms=int(time.time() * 1000) if ts_ms is None else ts_ms,
        )
        return Attestation(self.executor_id, entry)


def roster_of(executors: Iterable[Executor]) -> dict[str, PublicIdentity]:
    """executor_id → PublicIdentity。驗章必須用名冊上的公鑰。

    **不准**用證言自己帶的公鑰驗自己——那樣任何人都能偽造任何人的證言，
    「驗過了」會變成一句空話。名冊是誰進的，是部署層的問題（同樣是固定點）。
    """
    return {e.executor_id: e.public for e in executors}


def verify_attestation(
    att: Attestation,
    roster: Mapping[str, PublicIdentity],
    *,
    task_id: Any = None,
    draft_sha256: str | None = None,
    suite_sha256: str | None = None,
) -> tuple[bool, str]:
    """驗一筆證言。回傳 (可采信?, 理由)。理由字串會原樣進收據。

    可采信的條件，缺一不可：
      - 名冊上有這個 executor_id（否則是誰都不知道的人在投票）
      - entry 的 type 是證言、版本相符
      - payload 的 executor_id 與宣稱的一致（擋「借別人的名字」）
      - 綁定的 task_id／draft_sha256／suite_sha256 與本次要判的一致
        （擋重放：把上一題的通過證言貼到這一題）
      - 簽章驗過（擋竄改：改 payload 裡任何一位元都會失效）
    """
    who = roster.get(att.executor_id)
    if who is None:
        return False, "unknown_executor"
    e = att.entry
    if e.type != ATTEST_TYPE:
        return False, "wrong_entry_type"
    p = att.payload
    if p.get("v") != ATTEST_VERSION:
        return False, "bad_version"
    if p.get("executor_id") != att.executor_id:
        return False, "executor_id_mismatch"
    if "visible_ok" not in p:
        return False, "missing_verdict_field"
    if task_id is not None and p.get("task_id") != task_id:
        return False, "task_mismatch"
    if draft_sha256 is not None and p.get("draft_sha256") != draft_sha256:
        return False, "draft_mismatch"
    if suite_sha256 is not None and p.get("suite_sha256") != suite_sha256:
        return False, "suite_mismatch"
    try:
        sig = bytes.fromhex(e.sig)
    except ValueError:
        return False, "bad_signature_encoding"
    # 用 logbook 自己的 `_signed_bytes`：wire-format 只准有一個真相來源。
    # 在這裡重寫一次序列化＝製造一份會和 logbook 漂移的影子規格。
    msg = _lb._signed_bytes(  # noqa: SLF001
        e.stream_id, e.branch_id, e.seq, e.prev_hash, e.ts_ms, e.type, e.payload
    )
    if not who.verify(msg, sig):
        return False, "bad_signature"
    return True, ""


def verify_executor_chain(ex_id: str, book: Logbook, roster: Mapping[str, PublicIdentity]) -> bool:
    """整條鏈驗一次（seq 連續、prev_hash 串對、每筆簽章過）。

    分歧發生後真正該做的動作：不是吵誰對，是把兩邊的鏈拉出來各驗一次。
    """
    who = roster.get(ex_id)
    return bool(who) and book.verify_chain(who)


# ── 判決 ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Verdict:
    """一份草稿對一套驗收的法定判決，以及**分歧的歸屬**。

    `visible_ok is None` ＝ 未決（平手，或可采信證言數不足法定人數）。出貨規則把
    未決當成「不通過」——平手不是通過的證據。這使偶數人數對說謊者較弱、對破壞者
    較強，是刻意的不對稱，寫在這裡以免日後被當成 bug 修掉。
    """

    task_id: Any
    draft_sha256: str
    suite_sha256: str
    visible_ok: bool | None
    n_pass: int
    n_fail: int
    camp_pass: tuple[str, ...]
    camp_fail: tuple[str, ...]
    dissenters: tuple[str, ...]
    detail_dissenters: tuple[str, ...]
    equivocators: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    evidence: tuple[tuple[str, str], ...]  # (executor_id, entry_hash) for admitted
    quorum: int
    n_admitted: int

    @property
    def contested(self) -> bool:
        """有任何一種可歸屬的不一致——布林票、條號、作偽證、驗不過的證言，或根本沒判出來。

        `detail_dissenters` 算在內：兩個都說「不過」但卡在不同條，同樣代表有人沒有
        真的跑這套驗收。把它排除在 contested 之外會讓運維端的警報漏掉整條通道。

        `rejected` 也算在內：一筆**驗不過**的證言（偽造、重放、名冊外的人投票）比
        「少數方」更硬——它不需要跟任何人比對就已經是過錯。它進了 `as_receipt`，
        但如果不讓它翻動 `contested`，一個看收據只看 `unanimous` 的運維端會漏掉它，
        而那正是最該被看到的那一類。⚠ 反過來的代價要講清楚：這使 `contested` 對
        「有人送了一筆過期／別題的證言」也會亮燈，噪音比只看少數方高。
        """
        return (bool(self.dissenters) or bool(self.detail_dissenters)
                or bool(self.equivocators) or bool(self.rejected)
                or self.visible_ok is None)

    @property
    def unanimous(self) -> bool:
        return self.n_admitted > 0 and not self.contested

    def as_receipt(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "draft_sha256": self.draft_sha256,
            "suite_sha256": self.suite_sha256,
            "visible_ok": self.visible_ok,
            "n_pass": self.n_pass,
            "n_fail": self.n_fail,
            "n_admitted": self.n_admitted,
            "quorum": self.quorum,
            "camp_pass": list(self.camp_pass),
            "camp_fail": list(self.camp_fail),
            "dissenters": list(self.dissenters),
            "detail_dissenters": list(self.detail_dissenters),
            "equivocators": list(self.equivocators),
            "rejected": [list(r) for r in self.rejected],
            "evidence": [list(e) for e in self.evidence],
            "contested": self.contested,
            "majority_bound": MAJORITY_BOUND_NOTE,
        }


def form_verdict(
    attestations: Sequence[Attestation],
    roster: Mapping[str, PublicIdentity],
    *,
    task_id: Any,
    draft_sha256: str,
    suite_sha256: str,
    quorum: int = 1,
) -> Verdict:
    """把一組證言變成一個判決 ＋ 一份歸屬。

    步驟（每一步的產物都進收據）：
      1. 逐筆 `verify_attestation`；不可采信的進 `rejected`，附理由。
      2. 同一個執行器交出兩筆內容不同的證言 ＝ **equivocation**。兩筆都簽過，
         所以這是**證明等級**的過錯，比「少數方」強：該執行器的兩筆全部作廢並進
         `equivocators`。（同內容重複只當去重，不算過錯。）
      3. 多數決。`n_admitted < quorum` ⇒ 未決。
      4. `dissenters` ＝ 少數方（具名）。平手時兩邊都不是少數方，回未決。
      5. `detail_dissenters` ＝ 在**判 FAIL 的那一邊**裡，`first_failing_test`
         與該camp眾數不同的人。確定性套件上，兩個都說「不過」的誠實執行器**必須**
         卡在同一條；不同就代表有人沒真的跑。這是布林票之外的第二條歸屬通道，
         成本一樣是零模型呼叫。
    """
    seen: dict[str, Attestation] = {}
    equivocators: set[str] = set()
    rejected: list[tuple[str, str]] = []

    for att in attestations:
        ok, why = verify_attestation(
            att, roster, task_id=task_id,
            draft_sha256=draft_sha256, suite_sha256=suite_sha256,
        )
        if not ok:
            rejected.append((att.executor_id, why))
            continue
        prev = seen.get(att.executor_id)
        if prev is None:
            seen[att.executor_id] = att
        elif canonical_bytes(prev.payload) != canonical_bytes(att.payload):
            equivocators.add(att.executor_id)
    for eid in equivocators:
        seen.pop(eid, None)
        rejected.append((eid, "equivocation"))

    camp_pass = tuple(sorted(e for e, a in seen.items() if a.visible_ok))
    camp_fail = tuple(sorted(e for e, a in seen.items() if not a.visible_ok))
    n_pass, n_fail = len(camp_pass), len(camp_fail)
    n_admitted = n_pass + n_fail

    if n_admitted < max(1, quorum) or n_pass == n_fail:
        visible_ok: bool | None = None
        dissenters: tuple[str, ...] = ()
    elif n_pass > n_fail:
        visible_ok, dissenters = True, camp_fail
    else:
        visible_ok, dissenters = False, camp_pass

    # 第二條通道：FAIL 陣營內部對「卡在第幾條」的分歧。
    detail: list[str] = []
    if len(camp_fail) > 1:
        idx = {e: seen[e].payload.get("first_failing_test") for e in camp_fail}
        counts: dict[Any, int] = {}
        for v in idx.values():
            counts[v] = counts.get(v, 0) + 1
        modal = max(counts.items(), key=lambda kv: (kv[1], str(kv[0])))[0]
        detail = sorted(e for e, v in idx.items() if v != modal)

    return Verdict(
        task_id=task_id,
        draft_sha256=draft_sha256,
        suite_sha256=suite_sha256,
        visible_ok=visible_ok,
        n_pass=n_pass,
        n_fail=n_fail,
        camp_pass=camp_pass,
        camp_fail=camp_fail,
        dissenters=tuple(dissenters),
        detail_dissenters=tuple(detail),
        equivocators=tuple(sorted(equivocators)),
        rejected=tuple(rejected),
        evidence=tuple(sorted((e, a.entry_hash) for e, a in seen.items())),
        quorum=max(1, quorum),
        n_admitted=n_admitted,
    )


# ── 選擇（CONFORM 的語意不變，只是「通過」改由法定人數認定）────────────────
@dataclass(frozen=True)
class Selection:
    task_id: Any
    shipped_index: int | None
    shipped_worker: str | None
    shipped_sha256: str | None
    refused: bool
    verdicts: tuple[Verdict, ...]
    n_sandbox_runs: int

    def as_receipt(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "shipped_index": self.shipped_index,
            "shipped_worker": self.shipped_worker,
            "shipped_sha256": self.shipped_sha256,
            "refused": self.refused,
            "n_sandbox_runs": self.n_sandbox_runs,
            "verdicts": [v.as_receipt() for v in self.verdicts],
        }


def select_by_quorum(
    task: Mapping[str, Any],
    drafts: Sequence[tuple[str, str]],
    executors: Sequence[Executor],
    *,
    roster: Mapping[str, PublicIdentity] | None = None,
    suite_sha256: str | None = None,
    quorum: int | None = None,
    ts_ms: int | None = None,
) -> Selection:
    """依序看草稿，第一份被法定人數判為通過的出貨；全不通過就拒交。

    與 `gain_run.arm_conform` 的差別**只有一個**：`visible_ok` 不再是單一執行器的
    回傳值，而是 `form_verdict` 的多數。早停語意、拒交語意、V/GT 分離全部相同。
    """
    ros = dict(roster) if roster is not None else roster_of(executors)
    ssha = suite_sha256 or suite_hash(task)
    q = quorum if quorum is not None else len(executors) // 2 + 1
    verdicts: list[Verdict] = []
    runs = 0
    for i, (code, _worker) in enumerate(drafts):
        dsha = sha256_hex(code)
        atts = [
            e.attest(task, code, suite_sha256=ssha, ts_ms=ts_ms) for e in executors
        ]
        runs += len(executors)
        v = form_verdict(
            atts, ros, task_id=task.get("task_id"),
            draft_sha256=dsha, suite_sha256=ssha, quorum=q,
        )
        verdicts.append(v)
        if v.visible_ok:
            return Selection(task.get("task_id"), i, drafts[i][1], dsha, False,
                             tuple(verdicts), runs)
    return Selection(task.get("task_id"), None, None, None, True, tuple(verdicts), runs)


# ── 剩下的固定點：驗收套件本身的兩道緩解 ────────────────────────────────────
def commit_suite(
    book: Logbook, identity: Identity, *, task_id: Any, check_code: str, nonce: str,
    ts_ms: int | None = None,
) -> _lb.LogEntry:
    """在**草稿存在之前**把驗收套件的雜湊承諾上鏈（commit-reveal）。

    這關掉的是一條特定的攻擊：拿到草稿之後再回頭改驗收套件（改成剛好放行、或剛好
    擋掉某個人）。承諾之後套件就不能改而不被看見。

    **不能**做到的（誠實邊界）：它不讓套件變得正確、不保證套件涵蓋真需求、也不
    阻止一開始就寫壞／寫偏的套件。套件本身仍然是固定點。
    """
    payload = {"task_id": task_id, "commitment": review_commitment(check_code, nonce)}
    return book.append(
        SUITE_COMMIT_TYPE, payload, identity,
        ts_ms=int(time.time() * 1000) if ts_ms is None else ts_ms,
    )


def open_suite(entry: _lb.LogEntry, check_code: str, nonce: str) -> bool:
    """揭露：公開的套件原文＋nonce 必須重算出承諾值。"""
    if entry.type != SUITE_COMMIT_TYPE:
        return False
    p = entry.payload if isinstance(entry.payload, dict) else {}
    try:
        return p.get("commitment") == review_commitment(check_code, nonce)
    except ValueError:
        return False


@dataclass(frozen=True)
class Challenge:
    """落敗方的重跑權：換一組**不相交**的執行器再判一次。"""

    task_id: Any
    draft_sha256: str
    original: Verdict
    rerun: Verdict
    outcome: str  # "upheld" | "overturned" | "undecided"
    accused: tuple[str, ...]  # 兩次判決中被指為少數方／作偽證的人的聯集

    def as_receipt(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "draft_sha256": self.draft_sha256,
            "outcome": self.outcome,
            "accused": list(self.accused),
            "original": self.original.as_receipt(),
            "rerun": self.rerun.as_receipt(),
        }


def challenge_rerun(
    task: Mapping[str, Any],
    draft_code: str,
    panel: Sequence[Executor],
    original: Verdict,
    *,
    roster: Mapping[str, PublicIdentity] | None = None,
    suite_sha256: str | None = None,
    quorum: int | None = None,
    ts_ms: int | None = None,
) -> Challenge:
    """重跑挑戰：草稿被判不過的工人有權要求另一組執行器再跑一次同一套驗收。

    為什麼這是**便宜**的救濟：重跑一次驗收是本機沙箱、零模型呼叫，所以「給落敗方
    一次重跑權」的成本是 k 次沙箱執行，不是一輪新的模型呼叫。委員會式評審給不起
    這個權利——重審要再燒 3 通。

    誠實邊界：重跑只在**新面板的腐化比例低於一半**時才救得回來。它不是仲裁機構，
    只是把同一個多數決再抽一次樣。如果腐化是全域的（同一個 bot net 佔滿名冊），
    重跑會一致地覆述原判——`outcome="upheld"` 不等於原判正確。
    """
    ros = dict(roster) if roster is not None else roster_of(panel)
    ssha = suite_sha256 or suite_hash(task)
    q = quorum if quorum is not None else len(panel) // 2 + 1
    dsha = sha256_hex(draft_code)
    atts = [e.attest(task, draft_code, suite_sha256=ssha, ts_ms=ts_ms) for e in panel]
    rerun = form_verdict(atts, ros, task_id=task.get("task_id"),
                         draft_sha256=dsha, suite_sha256=ssha, quorum=q)
    if rerun.visible_ok is None or original.visible_ok is None:
        outcome = "undecided"
    elif rerun.visible_ok == original.visible_ok:
        outcome = "upheld"
    else:
        outcome = "overturned"
    accused = tuple(sorted(set(original.dissenters) | set(rerun.dissenters)
                           | set(original.equivocators) | set(rerun.equivocators)))
    return Challenge(task.get("task_id"), dsha, original, rerun, outcome, accused)
