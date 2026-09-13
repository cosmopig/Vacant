#!/usr/bin/env python3
"""佇列排程器：讀一份**佇列 JSON**（塊清單＋每塊的 gain_run 參數），排到 1004 的空槽。

規格：`DECISION_20260911_R529_CROSS_BANK_PREREG.md` §八（Fable 2026-09-11 裁決第 6 點）。

這支與 `ops/gain/schedule_harness_reps.py` 的關係，一句話：
**狀態機、作廢規則、idempotency 全部沿用那一支的純函式**
（`plan_tick`／`occupancy`／`block_state`／`classify_summary`／`aborted_counts`／
`_abort_to`），這裡只換三樣東西：

  1. **塊從哪裡來**——那一支的塊是寫死的 `REPS × BLOCK_TAGS`（R460R 註冊的東西），
     這一支的塊來自一份佇列 JSON，每塊自帶 `bank`／`bank_filter`／`n`／`offset`／`seed`。
     R529 一個佇列跨四個題目集，塊的形狀本來就不一樣，塞不進那張表。
  2. **槽數會變**——`--slots-now` / `--slots-after` / `--expand-when`。
     2026-09-11 的量測（Opus 探針）：1004 的 LM Studio `parallel=4`，現在 R460R
     佔三格，**第四格是真的空著**；開第四串總吞吐 +15–25%、每串慢 1.21×、
     H 臂 `budget_wall` 截斷數不變。第五、六串沒有收益。⇒ R460R 還在跑的時候
     這個佇列**只准開 1 槽**；R460R **真的收完**才擴到 4 槽。
     「真的收完」＝ 行程不在（排程器與 runner 都是）**且** 18 塊在磁碟上都
     terminal——兩個條件，理由見 `r460r_blocks_all_terminal` 的 docstring
     （2026-09-11 那次排程器猝死的事故：排程器死了 ≠ R460R 跑完了）。
  3. **獨立的鎖、獨立的 log、獨立的槽名**——與 R460R 那一支完全不共用：
       · lock  `~/vacant/logs/.schedule_queue_<queue>.lock`
                （R460R 是 `~/vacant/logs/.schedule_harness_reps.lock`）
       · log   `~/vacant/logs/schedule_queue_<queue>.log`
                （R460R 是 `~/vacant/logs/schedule_harness_reps.log`）
       · 槽名  `q1004#1`…`q1004#4`（R460R 是 `1004#1`…`1004#4`）
       · 發射器的 flock `~/vacant/.launch_r529_<TAG>.lock`
                （R460R 是 `~/vacant/.launch_rep_<TAG>.lock`）
     共用任何一樣都會變成「兩個排程器互相以為對方的塊是自己的」。
     ⚠ 本支與它的測試**從不送訊號給任何行程**：只讀 `ps`，沒有 `kill`／`pkill`。
       擴槽條件那支 `r460r_presence()` 是**純函式**，`ps` 的輸出從外面餵進來，
       所以測試餵的是字串，碰不到真的行程。

⚠ **這支不改 `schedule_harness_reps.py` 一個字**。R460R 的 18 塊正在那支底下排隊，
  改它＝改一個正在跑的實驗的排程器。要共用的東西一律用 import 的。

⚠ **完成判定只讀 `summary.json`，不數 `rows.jsonl` 的行數**
  （2026-09-13，`DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md` §十一）：
  **作廢列不寫進 `rows.jsonl`**——`gain_run` 在 `infra_void` 的格子走 `continue`，
  那一格一列都不寫 ⇒ `len(rows) ＝ processed − infra_void`。用行數當進度，
  「後端掛掉沒量到」就會被讀成「還沒跑到」，有 void 的塊永遠到不了「跑完」。
  本支的判定一律經過 `classify_summary()`（從 `schedule_harness_reps` import
  來的同一支），它讀的是 `run_terminal` 與 `arms.<arm>.{processed,infra_void}`。
  `r460r_blocks_all_terminal()` 與 `observe()` 也都走同一條路。

⚠ **擴槽沒有閂（latch）**：每一輪都重新問一次「R460R 還在不在」。在的時候縮回
  `--slots-now`。縮回**不會**去停已經發出去的塊（停不了），但會讓 `occupancy`
  發現「跑著的塊比槽多」⇒ 封鎖端點 ⇒ 這一輪一塊都不發。那正是想要的退化方向：
  萬一有人把 R460R 的排程器再啟動一次，這邊會自己停下來等，而不是把 1004 開到七串。

用法（vacant-dev）：
    setsid nohup python3 ops/gain/schedule_queue.py \\
      --queue ops/gain/queues/r529_cross_bank.json \\
      --slots-now 1 --slots-after 4 --expand-when r460r_done \\
      > ~/vacant/logs/schedule_queue_r529.out 2>&1 < /dev/null &
乾跑（只印計畫、不發射、不碰後端、不寫 runs/）：
    python3 ops/gain/schedule_queue.py --queue ops/gain/queues/r529_cross_bank.json --dry-run
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import os
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.schedule_harness_reps import (  # noqa: E402
    ABORT_KINDS, MAX_ATTEMPTS, POLL_S, VOID_RATE_ABORT, Slot, _plan_lines,
    _read_json, abort_block, abort_preflight, aborted_counts, build_queue,
    classify_summary, observe, occupancy,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

ENDPOINT_1004 = "http://100.86.226.21:1234/v1/chat/completions"
ENDPOINT_1003 = "http://100.119.113.56:1234/v1/chat/completions"

#: 這個佇列可以用的槽，**順序＝ first-fit 的優先序**。
#:
#: 2026-09-11 08:52Z 人類指示、Fable 執行：1003 卸掉 qwen3.8-27b 改載
#: `gemma-4-12b-it-qat`（context 262144、parallel 4、`--gpu max`、無 TTL，
#: gguf 與 1004 **逐位元相同**）⇒ 1003 不再是禁區。
#: ⇒ 現在就可以開的是 **1003×4 ＋ 1004 的第 4 格 ＝ 5 串**（前五個）；
#:   R460R 的排程器退出、它的 18 塊全 terminal 之後再加 **1004×3**，合計 8 串。
#: 1003 給滿 4 槽（2026-09-11 人類指示「開到最多」、Fable 依量測裁決）：
#:   它的 `parallel=4`，而 2026-09-08 那兩次崩（`decode() failed: bad alloc`／
#:   `Context size has been exceeded`）的崩因已經查明——qwen 同時佔 VRAM、
#:   context 被降到 49k——現在條件與 1004 逐位元相同（同一份 gguf、262144 context）。
#: ⚠ **每張卡不得超過 4 串**（`parallel=4`；實測 6 串沒有收益）。
#:   這條上限由 `_assert_per_host_cap` 在 import 時就檢查，不是紀律。
#:
#: ⚠ **槽名故意與 `schedule_harness_reps.SLOTS`（`1004#1`…`1004#4`、`1003#1`）不同**：
#:   前綴 `q` ＝ 這是佇列排程器的槽。兩支排程器各自只把自己佇列裡的塊擺進
#:   自己的槽表，功能上本來就不會互吃；名字分開是為了**兩份 log 不會互相冒充**
#:   ——兩邊都印「槽 1004#1」的話，事後對帳分不出是誰在講話。
#:   `#` 後面的數字仍然是它代表的那一格 LM Studio parallel slot。
QUEUE_SLOTS: tuple[Slot, ...] = (
    Slot("q1003#1", ENDPOINT_1003, "1003"),
    Slot("q1003#2", ENDPOINT_1003, "1003"),
    Slot("q1003#3", ENDPOINT_1003, "1003"),
    Slot("q1003#4", ENDPOINT_1003, "1003"),
    Slot("q1004#4", ENDPOINT_1004, "1004"),
    Slot("q1004#1", ENDPOINT_1004, "1004"),
    Slot("q1004#2", ENDPOINT_1004, "1004"),
    Slot("q1004#3", ENDPOINT_1004, "1004"),
)

#: 每張卡的併發上限（LM Studio `parallel=4`；量測 6 串無收益）。
PER_HOST_CAP = 4

#: 預設的「現在」與「R460R 收完之後」槽數。寫成常數是為了讓
#: 「5 → 8」這個數字只有一個真相，CLI 預設與預註冊引用的是同一個。
DEFAULT_SLOTS_NOW = 5
DEFAULT_SLOTS_AFTER = len(QUEUE_SLOTS)


def _assert_per_host_cap(slots: tuple[Slot, ...] = QUEUE_SLOTS,
                         cap: int = PER_HOST_CAP) -> None:
    """槽表本身不准違反每張卡 4 串的上限——**import 時就檢查**。

    ⚠ 為什麼是機制不是紀律：多開一格在 log 上長得跟正常一模一樣，
      而它會把「這批資料是在什麼併發條件下量的」變成事後查 `calls.jsonl`
      才知道的事（R460 §一〇 的同一條）。
    ⚠ 另外要注意：1004 的 #1–#3 在 R460R 還在跑的時候是**它的**，
      所以 `--slots-now` 只取前 5 格（1003×4 ＋ 1004#4）；
      上限檢查管的是「表上每張卡幾格」，`--slots-now` 管的是「這一輪用幾格」。
    """
    per: dict[str, int] = {}
    for s in slots:
        per[s.host] = per.get(s.host, 0) + 1
    bad = {h: n for h, n in per.items() if n > cap}
    if bad:
        raise SystemExit(f"槽表違反每張卡 {cap} 串的上限：{bad}。停。")


_assert_per_host_cap()

#: `--expand-when` 認得的條件。`never`＝永遠停在 `--slots-now`（保守跑法）。
EXPAND_CONDITIONS = ("r460r_done", "never", "now")

#: 佇列 JSON 每一塊的必要欄位（型別一起釘）。多餘的鍵一律拒收——
#: 打錯字的鍵被默默忽略，等於「我以為我設定了 bank_filter」。
_BLOCK_SCHEMA: dict[str, type | tuple[type, ...]] = {
    "name": str, "bank": str, "n": int, "offset": int, "seed": str, "tag": str,
}
_BLOCK_OPTIONAL: dict[str, type | tuple[type, ...]] = {
    "bank_filter": str, "note": str,
}


@dataclasses.dataclass(frozen=True)
class QBlock:
    """佇列裡的一塊。欄位就是發射器要的那幾個參數，沒有第二份真相。"""

    name: str
    bank: str
    n: int
    offset: int
    seed: str
    tag: str
    bank_filter: str | None = None
    note: str = ""

    @property
    def out(self) -> str:
        return f"runs/{self.name}"

    @property
    def launch_tag(self) -> str:
        return self.tag


@dataclasses.dataclass(frozen=True)
class Queue:
    name: str
    decision: str
    launcher: str
    arms: str
    request_timeout_s: int
    review_timeout_s: int
    gauge_scope: str
    models: str
    #: endpoint → {"host", "lmstudio_version", "version_source"}。
    #: ⚠ `lmstudio_version` 是**人回報的**（`lms version`），runner 查證不到
    #:   （`/v1/models` 與 HTTP header 都不帶版本，實測 2026-09-11）⇒
    #:   它連同 `version_source` 一起落盤，**不准**被引用成「我們量到的」。
    backends: dict
    blocks: tuple[QBlock, ...]

    @property
    def all_outs(self) -> tuple[str, ...]:
        return tuple(b.out for b in self.blocks)


def load_queue(path: str | pathlib.Path) -> Queue:
    """讀＋驗佇列 JSON。**每一條不成立都 `SystemExit`**——量不到不是通過。

    驗的東西（每一條都對應一種會安靜跑錯的壞法）：
      · 塊名唯一        ← 兩塊同名 ⇒ 第二塊撞 `abort_dir_exists`，看起來像發射器壞了
      · tag 唯一        ← tag 決定 flock 檔名，撞了會讓兩塊互相擋
      · offset／n 非負、n > 0
      · 同一個 (bank, bank_filter, seed) 之下的塊**兩兩不重疊**
                        ← 重疊＝同一題被算兩次，而那長得跟「跑完了」一模一樣
      · 認不得的鍵一律拒收 ← 打錯字的鍵被忽略＝「我以為我設了」
    """
    p = pathlib.Path(path)
    if not p.exists():
        raise SystemExit(f"佇列檔不存在：{p}。停。")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"佇列檔不是合法 JSON：{p}（{e}）。停。") from e
    if not isinstance(raw, dict):
        raise SystemExit(f"佇列檔的最外層要是 object：{p}。停。")
    need = ("name", "decision", "launcher", "arms", "request_timeout_s",
            "review_timeout_s", "gauge_scope", "models", "backends", "blocks")
    missing = [k for k in need if k not in raw]
    if missing:
        raise SystemExit(f"佇列檔缺欄位 {missing}：{p}。停。")
    extra = [k for k in raw if k not in need]
    if extra:
        raise SystemExit(f"佇列檔有認不得的欄位 {extra}：{p}。停。")
    if not isinstance(raw["blocks"], list) or not raw["blocks"]:
        raise SystemExit(f"佇列檔的 blocks 是空的：{p}。停。")
    blocks: list[QBlock] = []
    for i, b in enumerate(raw["blocks"]):
        if not isinstance(b, dict):
            raise SystemExit(f"blocks[{i}] 不是 object。停。")
        for key, typ in _BLOCK_SCHEMA.items():
            if key not in b:
                raise SystemExit(f"blocks[{i}] 缺欄位 {key}。停。")
            if not isinstance(b[key], typ) or isinstance(b[key], bool):
                raise SystemExit(f"blocks[{i}] 的 {key} 型別錯（want {typ}）。停。")
        bad = [k for k in b if k not in _BLOCK_SCHEMA and k not in _BLOCK_OPTIONAL]
        if bad:
            raise SystemExit(f"blocks[{i}] 有認不得的欄位 {bad}。停。")
        if b["n"] <= 0 or b["offset"] < 0:
            raise SystemExit(f"blocks[{i}] 的 n 要 > 0、offset 不能是負的。停。")
        blocks.append(QBlock(
            name=b["name"], bank=b["bank"], n=b["n"], offset=b["offset"],
            seed=b["seed"], tag=b["tag"],
            bank_filter=b.get("bank_filter"), note=b.get("note", "")))
    names = [b.name for b in blocks]
    if len(set(names)) != len(names):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise SystemExit(f"佇列裡有重複的塊名 {dup}。停。")
    tags = [b.tag for b in blocks]
    if len(set(tags)) != len(tags):
        dup = sorted({t for t in tags if tags.count(t) > 1})
        raise SystemExit(f"佇列裡有重複的 tag {dup}（tag 決定 flock 檔名）。停。")
    for a in blocks:
        for c in blocks:
            if a is c or (a.bank, a.bank_filter, a.seed) != (c.bank, c.bank_filter, c.seed):
                continue
            if a.offset < c.offset + c.n and c.offset < a.offset + a.n:
                raise SystemExit(
                    f"{a.name} 與 {c.name} 的題序區間重疊"
                    f"（[{a.offset},{a.offset + a.n}) vs [{c.offset},{c.offset + c.n})，"
                    "同 bank／同層／同 seed）——重疊＝同一題被算兩次。停。")
    if not isinstance(raw["request_timeout_s"], int) or raw["request_timeout_s"] <= 0:
        raise SystemExit("request_timeout_s 要是正整數。停。")
    if not isinstance(raw["review_timeout_s"], int) or raw["review_timeout_s"] <= 0:
        raise SystemExit("review_timeout_s 要是正整數。停。")
    backends = raw["backends"]
    if not isinstance(backends, dict) or not backends:
        raise SystemExit("佇列檔的 backends 要是非空 object。停。")
    known = {s.endpoint for s in QUEUE_SLOTS}
    if set(backends) != known:
        raise SystemExit(
            f"backends 的端點集合與槽表對不上：{sorted(set(backends) ^ known)}。停。")
    for ep, meta in backends.items():
        miss = [k for k in ("host", "lmstudio_version", "version_source")
                if k not in meta]
        if miss:
            raise SystemExit(f"backends[{ep}] 缺 {miss}。停。")
    return Queue(name=raw["name"], decision=raw["decision"], launcher=raw["launcher"],
                 arms=raw["arms"], request_timeout_s=raw["request_timeout_s"],
                 review_timeout_s=raw["review_timeout_s"],
                 gauge_scope=raw["gauge_scope"], models=raw["models"],
                 backends=backends, blocks=tuple(blocks))


def registration_line(block: QBlock) -> str:
    """這一塊在 DECISION 裡必須逐字出現的那一行（**整組**，不是逐項）。

    為什麼不逐項比對：四個題目集裡到處都是 `--offset 0`、`--n 20`，逐項比對會讓
    「lcb3-hard 的 offset 0」通過「evalplus 的 offset 0」那一行 ⇒ 打錯一個欄位
    照樣發得出去。整組比對之下，錯一個數字這一行就對不上。
    發射器 `launch_r529_block.sh` 用**同一個格式**再檢一次（兩邊必須一字不差）。
    """
    return (f"R529_BLOCK: {block.name} bank={block.bank} "
            f"filter={block.bank_filter or '-'} n={block.n} "
            f"offset={block.offset} seed={block.seed}")


def check_prereg(queue: Queue, repo: pathlib.Path = REPO) -> list[str]:
    """回「DECISION 裡找不到的註冊行」清單。空清單＝全部對得上。"""
    dec = repo / queue.decision
    if not dec.exists():
        return [f"(DECISION 不存在：{queue.decision})"]
    text = dec.read_text(encoding="utf-8")
    return [registration_line(b) for b in queue.blocks
            if registration_line(b) not in text]


# ── 擴槽條件 ─────────────────────────────────────────────────────────────
def _ps_lines() -> list[str] | None:
    """`ps -eo pid,cmd` 的每一行；拿不到回 `None`（＝**不知道**，不是「沒有」）。"""
    try:
        out = subprocess.run(["ps", "-eo", "pid,cmd"], capture_output=True,
                             text=True, timeout=30)
    except Exception:                                          # noqa: BLE001
        return None
    if out.returncode != 0:
        return None
    return out.stdout.splitlines()


def r460r_presence(lines: list[str] | None) -> tuple[bool, str]:
    """R460R 還在不在？回 `(還在, 理由)`。

    兩個都要沒有才算收完：
      · `schedule_harness_reps.py` 的排程器行程
      · 任何 `gain_run.py --out runs/g_r460r…` 的 runner
    只看排程器會漏掉「排程器被 kill 了但塊還在跑」，只看 runner 會漏掉
    「這一刻剛好沒塊在跑，但排程器下一輪就要發」。

    ⚠ `ps` 讀不到（`lines is None`）⇒ 回「還在」。**不知道不是「沒有」**：
      量不到就不准加負載，這是排程器版的 fail-closed。
    """
    if lines is None:
        return True, "ps_unavailable"
    sched = [ln for ln in lines
             if "schedule_harness_reps.py" in ln and " grep " not in ln]
    runners = [ln for ln in lines
               if "gain_run.py --out runs/g_r460r" in ln and " grep " not in ln]
    if sched:
        return True, f"scheduler_alive({len(sched)})"
    if runners:
        return True, f"r460r_runner_alive({len(runners)})"
    return False, "no_scheduler_no_runner"


def r460r_blocks_all_terminal(root: pathlib.Path,
                              reps: tuple[int, ...] = (1, 2, 3)) -> tuple[bool, str]:
    """R460R 這一輪排的塊是不是**全部**收完了（磁碟上的證據，不看行程）。

    ⚠ 這一格是 2026-09-11 那次事故補的：R460R 的排程器在 07:23Z 發完 b2 之後
      死掉了（原 pid 3089647，Fable 於 08:19Z 重啟），而三個 runner 還活著。
      如果只問「行程還在不在」，那段空窗一旦 runner 也跑完，這支就會判
      「R460R 收完了」而擴到 4 槽——**但 R460R 其實只跑了 5/18 塊**，
      人一重啟它就會再開三串，1004 上就變成 7 串。
      ⇒ 擴槽要**兩個條件都成立**：行程不在 **且** 18 塊都 terminal。
      「排程器死了」與「R460R 跑完了」不是同一件事。

    要真的越過這一格而人類另有判斷時，用 `--expand-when now`（顯式決定，留在 log 裡）。
    """
    missing: list[str] = []
    for b in build_queue(reps):
        summary = _read_json(root / b.out / "summary.json")
        state, _why = classify_summary(summary)
        if state != "DONE":
            missing.append(b.name)
    if missing:
        return False, f"r460r_blocks_not_done({len(missing)}/{len(build_queue(reps))})"
    return True, "r460r_all_blocks_terminal"


def effective_slots(expand_when: str, slots_now: int, slots_after: int,
                    lines: list[str] | None,
                    slots: tuple[Slot, ...] = QUEUE_SLOTS,
                    blocks_done: tuple[bool, str] | None = None
                    ) -> tuple[tuple[Slot, ...], str]:
    """這一輪可以用幾個槽。純函式（`ps` 的輸出與磁碟判定都從外面餵進來）。"""
    if expand_when not in EXPAND_CONDITIONS:
        raise SystemExit(f"--expand-when 只認得 {list(EXPAND_CONDITIONS)}。停。")
    if expand_when == "now":
        return slots[:slots_after], "expanded(--expand-when now)"
    if expand_when == "never":
        return slots[:slots_now], "not_expanded(--expand-when never)"
    still, why = r460r_presence(lines)
    if still:
        return slots[:slots_now], f"not_expanded({why})"
    if blocks_done is None:
        # 沒有磁碟證據可看 ⇒ **不知道不是「沒有」**，照樣不擴。
        return slots[:slots_now], "not_expanded(block_state_unknown)"
    done, why2 = blocks_done
    if not done:
        return slots[:slots_now], f"not_expanded({why2})"
    return slots[:slots_after], f"expanded({why}+{why2})"


# ── 重排要換一台（2026-09-11 人類指示第 4 點）───────────────────────────
def aborted_endpoints(blocks, root: pathlib.Path) -> dict[str, str]:
    """每一塊**最近一次**被作廢時跑在哪個端點上。

    `_abort_to` 把 `<OUT>.endpoint` 一起搬到 `runs/_aborted/<stem>.endpoint`，
    所以這個答案是搬不走的證據，不是排程器記在記憶體裡的東西
    （記憶體裡的東西一重啟就沒了，而「上次死在哪台」剛好是最不能丟的那一格）。
    """
    out: dict[str, str] = {}
    ab = root / "runs" / "_aborted"
    if not ab.exists():
        return out
    for b in blocks:
        cands = sorted(
            (f for k in ABORT_KINDS for f in ab.glob(f"{b.name}_{k}_*.endpoint")),
            key=lambda f: f.name)
        if cands:
            try:
                ep = cands[-1].read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if ep:
                out[b.name] = ep
    return out


def plan_launches_queue(pending: list[str], busy: dict[str, str],
                        attempts: dict[str, int], prev_endpoint: dict[str, str],
                        slots: tuple[Slot, ...]) -> list[tuple[str, str]]:
    """把待跑的塊依佇列順序丟進空槽；**重排過的塊優先換一台**。

    與 `schedule_harness_reps.plan_launches` 的差別只有一條規則：那一支把重排
    釘死在 `REQUEUE_HOST = "1004"`（R460R 的情境是「1003 已知會崩」）；
    這裡兩台載的是**逐位元相同**的 gguf，所以規則變成
    **「別再回同一台」**——一塊在某台連續 void，最可能的成因就是那台的狀態。

    ⚠ 換不到別台時**不硬等**：那一塊這一輪跳過（留在佇列原位，下一輪再看），
      空槽讓給下一塊。硬等會讓一個壞塊把整條佇列卡住。
    """
    free = [s for s in slots if s.slot_id not in busy]
    out: list[tuple[str, str]] = []
    for name in pending:
        if not free:
            break
        requeued = attempts.get(name, 0) >= 1
        avoid = prev_endpoint.get(name) if requeued else None
        pick = next((i for i, s in enumerate(free) if s.endpoint != avoid), None)
        if pick is None:
            continue                 # 只剩它死過的那一台 ⇒ 這一輪跳過，不硬等
        out.append((name, free[pick].slot_id))
        free.pop(pick)
    return out


def plan_tick_queue(blocks, statuses: dict[str, str], endpoints: dict[str, str],
                    aborted_counts_: dict[str, int], prev_endpoint: dict[str, str],
                    slots: tuple[Slot, ...]) -> dict:
    """一輪的完整計畫。純函式：觀測進、計畫出，**不改任何東西**。

    ⚠ 為什麼不直接用 `schedule_harness_reps.plan_tick`：它裡面寫死呼叫
      `plan_launches`（重排只准上 1004）。要換掉那一條規則只能改那支模組，
      而 **R460R 正在它底下跑** ⇒ 一個字都不能動。所以這裡把那二十行的
      收／發帳本複製一份、只換發射那一步。其餘（`occupancy`／`block_state`／
      `classify_summary`／`MAX_ATTEMPTS`）全部還是 import 的同一份。
    """
    order = [b.name for b in blocks]
    by_name = {b.name: b for b in blocks}
    abort = [(n, statuses.get(n)) for n in order
             if statuses.get(n) in ("VOID", "DEAD")]
    counts = dict(aborted_counts_)
    for n, _why in abort:
        counts[n] = counts.get(n, 0) + 1
    eff = {n: ("PENDING" if statuses.get(n) in ("VOID", "DEAD")
               else statuses.get(n, "PENDING")) for n in order}
    running = [n for n in order if eff[n] == "RUNNING"]
    busy, unplaceable, blocked = occupancy(running, endpoints, slots)
    done = [n for n in order if eff[n] == "DONE"]
    given_up = [n for n in order
                if eff[n] == "PENDING" and counts.get(n, 0) >= MAX_ATTEMPTS]
    queue = [n for n in order
             if eff[n] == "PENDING" and counts.get(n, 0) < MAX_ATTEMPTS]
    usable = tuple(s for s in slots if s.endpoint not in blocked)
    # 這一輪剛被作廢的塊，它的端點證據還在 `<OUT>.endpoint`（尚未搬走）⇒
    # 先把它併進來，否則「第一次作廢之後的那一次重排」會看不到要避開哪一台。
    avoid = dict(prev_endpoint)
    for n, _why in abort:
        if n in endpoints:
            avoid[n] = endpoints[n]
    launch = plan_launches_queue(queue, busy, counts, avoid, usable)
    return {"abort": abort, "launch": launch, "done": done, "given_up": given_up,
            "busy": busy, "queue": queue, "unplaceable": unplaceable,
            "blocked_endpoints": sorted(blocked),
            "attempts_after": {n: counts.get(n, 0) for n in order},
            "avoid_endpoint": avoid,
            "finished": not queue and not busy,
            "slots": tuple(slots),
            "blocks": by_name}


# ── 發射 ─────────────────────────────────────────────────────────────────
def launch_block(block: QBlock, slot: Slot, queue: Queue, root: pathlib.Path,
                 log) -> int:
    """呼叫單塊發射器。**發射器自己做 preflight**，這裡只給參數與記錄。

    `SEED_SCAN_EXCLUDE` ＝ 佇列裡**全部**塊的 out 路徑（自己人清單）。發射器會
    逐一確認每個名字都真的寫在 DECISION 裡，所以這個清單不能靠這裡自說自話。

    ⚠ **2026-09-11 事故**：`text=True` 會用 UTF-8 嚴格解碼發射器的 stdout，
    而發射器裡的 `head -c 600`／`tail -c 700` 是**按位元組**截斷含中文的 launch.log
    ⇒ 切在一個 3 byte 字元中間就吐出半個字元 ⇒ `UnicodeDecodeError` 讓**排程器整個死掉**
    （R529 11:04:01Z、R460R 07:23Z 都是這樣死的，而且死在剛發完一塊的那一秒，
    看起來像「發完就沒事了」）。`errors="replace"` 讓壞位元組變成 U+FFFD 而不是例外。
    ⚠ 這是**第二道**防線：第一道在發射器（截斷後過一次 `iconv -c`）。
    兩條紅線不一樣——「不要產生壞位元組」與「壞位元組不准讓排程器死」。
    """
    env = dict(
        os.environ,
        TAG=block.launch_tag, OUT=block.out, OFFSET=str(block.offset),
        SEED=block.seed, API=slot.endpoint, DEC=queue.decision,
        BANK=block.bank, BANK_FILTER=(block.bank_filter or ""),
        N_BLOCK=str(block.n), ARMS=queue.arms, MODEL=queue.models,
        REQUEST_TIMEOUT_S=str(queue.request_timeout_s),
        REVIEW_TIMEOUT_S=str(queue.review_timeout_s),
        GAUGE_SCOPE=queue.gauge_scope,
        SEED_SCAN_EXCLUDE=" ".join(queue.all_outs),
        BACKEND_META=json.dumps(queue.backends.get(slot.endpoint, {}),
                                ensure_ascii=False),
        SLOT_ID=slot.slot_id, SLOT_HOST=slot.host,
    )
    log(f"LAUNCH {block.name} → 槽 {slot.slot_id}（{slot.endpoint}）"
        f" bank={block.bank}{'／' + block.bank_filter if block.bank_filter else ''}"
        f" n={block.n} offset={block.offset} seed={block.seed}")
    r = subprocess.run(["bash", queue.launcher], cwd=str(REPO), env=env,
                       capture_output=True, text=True, errors="replace")
    tail = (r.stdout or "")[-800:].replace("\n", "|")
    log(f"LAUNCH rc={r.returncode} {block.name}: {tail}")
    return r.returncode


def _queue_head(queue: Queue, root: pathlib.Path, slots: tuple[Slot, ...],
                why: str, slots_now: int, slots_after: int,
                expand_when: str) -> list[str]:
    by_bank: dict[str, list[QBlock]] = {}
    for b in queue.blocks:
        by_bank.setdefault(f"{b.bank}{'／' + b.bank_filter if b.bank_filter else ''}",
                           []).append(b)
    return [f"═══ 佇列排程器：{queue.name} ═══",
            f"repo={REPO}  runs 根目錄={root}  DECISION={queue.decision}",
            f"發射器={queue.launcher}  arms={queue.arms}  models={queue.models}",
            f"--request-timeout-s {queue.request_timeout_s}"
            f"  --review-timeout-s {queue.review_timeout_s}"
            f"  --gauge-scope {queue.gauge_scope}",
            f"題目集：" + "；".join(
                f"{k}＝{len(v)} 塊／{sum(x.n for x in v)} 題"
                for k, v in by_bank.items()),
            f"塊數 {len(queue.blocks)}　Σn {sum(b.n for b in queue.blocks)} 題　"
            f"rows {sum(b.n for b in queue.blocks) * len(queue.arms.split(','))} 列",
            f"槽：{[s.slot_id for s in slots]}（{why}；"
            f"--slots-now {slots_now} --slots-after {slots_after} "
            f"--expand-when {expand_when}）",
            "後端：" + "；".join(
                f"{m.get('host')}＝{ep.split('//')[-1].split('/')[0]}"
                f"（LM Studio {m.get('lmstudio_version')}＊宣稱）"
                for ep, m in sorted(queue.backends.items(),
                                    key=lambda kv: str(kv[1].get("host")))),
            "  ＊版本是人回報的，runner 查證不到；逐塊落盤在 <OUT>.backend_meta.json",
            ""]


def dry_run(queue: Queue, root: pathlib.Path, *, slots_now: int, slots_after: int,
            expand_when: str, ps_lines: list[str] | None = None) -> str:
    """只算計畫、不發射、不碰後端、不寫任何東西。"""
    slots, why = effective_slots(
        expand_when, slots_now, slots_after,
        ps_lines if ps_lines is not None else _ps_lines(),
        blocks_done=r460r_blocks_all_terminal(root))
    blocks = list(queue.blocks)
    statuses, endpoints = observe(blocks, root)
    counts = aborted_counts(blocks, root)
    plan = plan_tick_queue(blocks, statuses, endpoints, counts,
                           aborted_endpoints(blocks, root), slots)
    L = _queue_head(queue, root, slots, why, slots_now, slots_after, expand_when)
    L.append("── 現況（只印非全新的塊）")
    shown = 0
    for b in blocks:
        st = statuses.get(b.name, "PENDING")
        if st == "PENDING" and counts.get(b.name, 0) == 0:
            continue
        shown += 1
        L.append(f"  {b.name}: {st}（已作廢 {counts.get(b.name, 0)} 次"
                 f"{'，端點 ' + endpoints[b.name] if b.name in endpoints else ''}）")
    if not shown:
        L.append("  （沒有現成的目錄；全部都是新的）")
    L += [f"  佇列順序（{len(plan['queue'])} 塊待跑）："
          f"{', '.join(plan['queue'][:8]) or '(空)'}"
          + (" …" if len(plan["queue"]) > 8 else ""), ""]
    L += ["── 這一輪會做的事"] + _plan_lines(blocks, plan, root)
    L += ["", "── 規則（不在這一輪，但寫在這裡好對帳）",
          f"  · 每 {POLL_S} s 一輪；terminal 且每臂 void ≤ "
          f"{int(VOID_RATE_ABORT * 100)}% ⇒ 放掉那個槽",
          f"  · terminal 但某臂 void > {int(VOID_RATE_ABORT * 100)}%、或行程死了又沒 "
          "terminal ⇒ 搬到 runs/_aborted/<name>_void_<ts>",
          "  · 發射器 preflight 擋下來（rc != 0）⇒ 搬到 "
          "runs/_aborted/<name>_preflight_<ts>，一樣計入重排次數",
          f"  · 一塊最多發射 {MAX_ATTEMPTS} 次；用完還壞 ⇒ 放棄，留給人裁決",
          "  · 擴槽每一輪重問一次，**沒有閂**：R460R 又出現就縮回 --slots-now，"
          "已經跑著的塊不會被停，但這一輪不會再發新的（封鎖端點）",
          "  · `<OUT>.endpoint` 指到認不出來的端點 ⇒ 封鎖**全部**端點（fail closed）"]
    return "\n".join(L)


def poll_loop(queue: Queue, root: pathlib.Path, log, *,
              slots_now: int, slots_after: int, expand_when: str,
              max_ticks: int | None = None, launcher=None, aborter=None,
              preflight_aborter=None, sleeper=time.sleep,
              ps_reader=_ps_lines) -> int:
    """輪詢主迴圈。與 R460R 那一支的差別只有一句：**每一輪重算槽數**。"""
    blocks = list(queue.blocks)
    launcher = launcher or (lambda b, s: launch_block(b, s, queue, root, log))
    aborter = aborter or (lambda n, w: abort_block(n, w, root, log))
    preflight_aborter = preflight_aborter or (
        lambda n, rc: abort_preflight(n, rc, root, log))
    ticks = 0
    last_why = None
    while True:
        slots, why = effective_slots(
            expand_when, slots_now, slots_after, ps_reader(),
            blocks_done=r460r_blocks_all_terminal(root))
        if why != last_why:
            log(f"槽數：{len(slots)}（{why}）→ {[s.slot_id for s in slots]}")
            last_why = why
        statuses, endpoints = observe(blocks, root)
        counts = aborted_counts(blocks, root)
        plan = plan_tick_queue(blocks, statuses, endpoints, counts,
                               aborted_endpoints(blocks, root), slots)
        for line in _plan_lines(blocks, plan, root):
            log(line)
        for name, reason in plan["abort"]:
            aborter(name, reason)
        for name, slot_id in plan["launch"]:
            slot = next(s for s in slots if s.slot_id == slot_id)
            rc = launcher(plan["blocks"][name], slot)
            if rc:
                preflight_aborter(name, rc)
        if plan["finished"]:
            log(f"全部結束：完成 {len(plan['done'])}／放棄 {len(plan['given_up'])}"
                f"（{plan['given_up']}）")
            return 1 if plan["given_up"] else 0
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            log(f"max_ticks={max_ticks} 到了，停止輪詢（佇列剩 {len(plan['queue'])}）")
            return 0
        sleeper(POLL_S)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="佇列排程器（讀佇列 JSON；--slots-now/--slots-after/--expand-when）")
    ap.add_argument("--queue", required=True, help="佇列 JSON 的路徑")
    ap.add_argument("--root", default=str(REPO),
                    help="runs/ 的所在根目錄（乾跑／測試可以指到別處）")
    ap.add_argument("--slots-now", type=int, default=DEFAULT_SLOTS_NOW,
                    help=f"擴槽條件還沒成立之前可以用幾個槽"
                         f"（預設 {DEFAULT_SLOTS_NOW}＝1003×3 ＋ 1004 的第 4 格）")
    ap.add_argument("--slots-after", type=int, default=DEFAULT_SLOTS_AFTER,
                    help=f"擴槽條件成立之後可以用幾個槽"
                         f"（預設 {DEFAULT_SLOTS_AFTER}＝再加 1004 的 #1–#3）")
    ap.add_argument("--expand-when", default="r460r_done", choices=list(EXPAND_CONDITIONS),
                    help="r460r_done＝R460R 的排程器與塊都不在了才擴；"
                         "never＝永遠不擴；now＝一開始就用 --slots-after")
    ap.add_argument("--dry-run", action="store_true",
                    help="只印計畫：不發射、不碰後端、不寫任何檔案")
    ap.add_argument("--check", action="store_true",
                    help="只驗佇列：每一塊的 R529_BLOCK 註冊行都要逐字在 DECISION 裡。"
                         "不發射、不碰後端。CI 與發射前都跑這一條")
    ap.add_argument("--log", default=None, help="預設 ~/vacant/logs/schedule_queue_<name>.log")
    ap.add_argument("--max-ticks", type=int, default=None,
                    help="輪詢幾圈之後停（測試用；正式跑不給）")
    args = ap.parse_args(argv)
    queue = load_queue(args.queue)
    root = pathlib.Path(args.root)
    if not (1 <= args.slots_now <= len(QUEUE_SLOTS)):
        raise SystemExit(f"--slots-now 要在 1..{len(QUEUE_SLOTS)}。停。")
    if not (args.slots_now <= args.slots_after <= len(QUEUE_SLOTS)):
        raise SystemExit(
            f"--slots-after 要在 --slots-now..{len(QUEUE_SLOTS)}"
            "（擴槽只能往上，往下等於偷偷降併發而不說）。停。")
    if args.check:
        missing = check_prereg(queue)
        if missing:
            print(f"FAIL：{len(missing)} 行註冊行不在 {queue.decision} 裡：")
            for line in missing[:10]:
                print("  " + line)
            return 1
        print(f"OK：{len(queue.blocks)} 塊的註冊行都逐字在 {queue.decision} 裡"
              f"（Σn {sum(b.n for b in queue.blocks)} 題）")
        return 0
    if args.dry_run:
        print(dry_run(queue, root, slots_now=args.slots_now,
                      slots_after=args.slots_after, expand_when=args.expand_when))
        return 0
    for rel in (queue.decision, queue.launcher):
        if not (REPO / rel).exists():
            raise SystemExit(f"佇列指到的檔案不存在：{rel}。停。")
    # 發射前的最後一格：註冊行對不上就不准起排程器。發射器自己也會再檢一次，
    # 但那是「一塊一塊擋」；這裡是「整個佇列沒註冊完就不要開始」。
    missing = check_prereg(queue)
    if missing:
        raise SystemExit(
            f"{len(missing)} 塊的 R529_BLOCK 註冊行不在 {queue.decision} 裡"
            f"（例：{missing[0]}）——佇列與預註冊對不上。停。")
    log_path = pathlib.Path(
        args.log or (pathlib.Path.home() / "vacant" / "logs"
                     / f"schedule_queue_{queue.name}.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        line = f"{_dt.datetime.now(_dt.timezone.utc):%Y-%m-%d %H:%M:%S UTC}  {msg}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # 獨立的鎖（**不與 R460R 共用**）：同一個佇列同時跑兩個排程器會把同一塊發兩次。
    lock_path = log_path.parent / f".schedule_queue_{queue.name}.lock"
    import fcntl
    lock_fh = lock_path.open("w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"已經有一個 schedule_queue（{queue.name}）在跑（flock）——這次不做事")
        return 2
    log(f"佇列排程器啟動 pid={os.getpid()} queue={queue.name} root={root} "
        f"塊數={len(queue.blocks)} slots_now={args.slots_now} "
        f"slots_after={args.slots_after} expand_when={args.expand_when}")
    return poll_loop(queue, root, log, slots_now=args.slots_now,
                     slots_after=args.slots_after, expand_when=args.expand_when,
                     max_ticks=args.max_ticks)


if __name__ == "__main__":
    raise SystemExit(main())
