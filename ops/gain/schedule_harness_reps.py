#!/usr/bin/env python3
"""R460R 的跨後端塊排程器：30 塊、四個槽（1004×3、1003×1）、自動重排。

規格：`DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md` §四（Fable R4）。

這支在架構裡承重什麼——三件事，每一件都有對應的牙齒：

1. **併發上限是機制不是紀律。** 1004 實測 3 併發不掉速；1003 在 49k context ／
   PARALLEL 4 之下，三條長生成同時跑會 `decode() failed: bad alloc`／
   `Context size has been exceeded`（2026-09-08 兩次當機，
   `DECISION_20260908_R460_FABLE_LAUNCH_NOTES.md` §四）⇒ 那顆**一次只准一塊**。
   槽位就是這條規則的實體：沒有空槽就發不出去。
   ⚠ 這是**事前**的閘門；事後還有一道——`analyze_r460.py --topology scheduled`
   從 `calls.jsonl` 的時間窗重算「同一刻同一顆有幾塊在跑」，
   排程器說了不算（`endpoint_concurrency_exceeded` 進 `broken_reasons`）。

2. **「掛掉」與「跑完」不是同一件事。** 一塊 `run_terminal=true` 但某臂
   `infra_void/processed > 20%` ⇒ 那是後端掛了不是資料，資料不進分析
   （R460 §六-(6)-c／§十）。這種塊**連同 launch.log 與 backend.json**
   整個搬到 `runs/_aborted/<name>_void_<ts>`，然後**只重排一次、只准上 1004**。
   重排無上限等於「一直重試到它看起來正常為止」——那是選擇性重跑，
   會把後端的壞運氣洗成資料。

3. **可重跑（idempotent）。** 排程器隨時可以再啟動一次：已經 terminal 且乾淨的
   塊直接跳過、正在跑的塊**認回原本的槽**（靠發射器落的 `<OUT>.endpoint`），
   目錄在但沒有 terminal 又沒有行程的塊當成死掉 ⇒ 搬走並重排。
   ⚠ 「認回」不是「重發」：重發會撞 `abort_dir_exists`，而那個 abort 本來就是
   為了擋「同一塊被發兩次」而存在的。

⚠ **本檔的純函式與 I/O 是分開的**：`build_queue`／`occupancy`／`plan_tick`
  ／`block_state`／`classify_summary` 完全不碰網路、不碰檔案，
  `tests/test_r460r_scheduler.py` 直接餵它們假狀態。會動到外面的只有 `observe`／`abort_block`／`launch_block`／`poll_loop` 那幾支。

用法（vacant-dev，要能撐過 ssh 斷線）：
    setsid nohup python3 ops/gain/schedule_harness_reps.py \\
      >> ~/vacant/logs/schedule_harness_reps.out 2>&1 < /dev/null &
乾跑（只印計畫、不發射、不碰後端、不寫 runs/）：
    python3 ops/gain/schedule_harness_reps.py --dry-run
    python3 ops/gain/schedule_harness_reps.py --dry-run --root /tmp/fake  # 假 runs/
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as _dt
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

REPO = pathlib.Path(__file__).resolve().parents[2]
DECISION = "DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md"
LAUNCHER = "ops/gain/launch_harness_rep_block.sh"

# ── 凍結的設定（改這裡＝改事前註冊 ⇒ 不准）──────────────────────────────
BLOCK_TAGS = ("a1", "a2", "a3", "b1", "b2", "b3")
TAG_OFFSET = {"a1": 0, "a2": 20, "a3": 40, "b1": 60, "b2": 80, "b3": 100}
REPS = (1, 2, 3, 4, 5)

ENDPOINT_1004 = "http://100.86.226.21:1234/v1/chat/completions"
ENDPOINT_1003 = "http://100.119.113.56:1234/v1/chat/completions"


@dataclasses.dataclass(frozen=True)
class Slot:
    slot_id: str
    endpoint: str
    host: str


#: 四個槽。順序＝first-fit 的優先序（1004 先滿，1003 最後）。
#: 1003 只有一個槽，理由寫在模組 docstring 第 1 點。
SLOTS: tuple[Slot, ...] = (
    Slot("1004#1", ENDPOINT_1004, "1004"),
    Slot("1004#2", ENDPOINT_1004, "1004"),
    Slot("1004#3", ENDPOINT_1004, "1004"),
    Slot("1003#1", ENDPOINT_1003, "1003"),
)

#: 重排只准上 1004（R4 逐字）。1003 已經在同一個 harness 上死過兩次，
#: 把重排丟回去等於用同一個已知會壞的形狀再賭一次。
REQUEUE_HOST = "1004"

#: 任一臂的 void 率超過這條線 ⇒ 那一塊不進分析（R460 §十／§六-(6)-c）。
VOID_RATE_ABORT = 0.20

#: 一塊最多發射兩次（初發 ＋ 重排一次）。
MAX_ATTEMPTS = 2

POLL_S = 60


@dataclasses.dataclass(frozen=True)
class Block:
    rep: int
    tag: str

    @property
    def name(self) -> str:
        return f"g_r460r{self.rep}_harness_lcb2_{self.tag}"

    @property
    def out(self) -> str:
        return f"runs/{self.name}"

    @property
    def offset(self) -> int:
        return TAG_OFFSET[self.tag]

    @property
    def seed(self) -> str:
        return f"g-r460r{self.rep}-lcb2"

    @property
    def launch_tag(self) -> str:
        return f"r{self.rep}{self.tag}"


def build_queue(reps: tuple[int, ...] = REPS) -> list[Block]:
    """佇列順序：r1a1 r1a2 r1a3 r1b1 r1b2 r1b3 r2a1 …（R4 逐字）。

    ⚠ 為什麼一次複製的六塊排在一起而不是交錯：**一次複製的六塊全跑完才判得了它**
    （少一塊 ⇒ `block_count_not_6` ⇒ 那一次 INVALID）。依複製排 ⇒ 每收完六塊
    就多一個可判的結果；交錯排則是「跑到最後才知道有沒有東西」。
    """
    return [Block(rep=k, tag=t) for k in reps for t in BLOCK_TAGS]


# ── 狀態判定（純函式）───────────────────────────────────────────────────
def void_rates(summary: dict | None) -> dict[str, float]:
    """逐臂 `infra_void / processed`。`processed` 含 void（R460 summary 的定義）。"""
    out: dict[str, float] = {}
    for arm, v in ((summary or {}).get("arms") or {}).items():
        processed = float(v.get("processed") or 0)
        if processed <= 0:
            out[arm] = 0.0
            continue
        out[arm] = float(v.get("infra_void") or 0) / processed
    return out


def classify_summary(summary: dict | None) -> tuple[str, str]:
    """一塊的 summary 說它算不算數。回 `(state, why)`。

    `("DONE", …)`        terminal 且每一臂 void 率都 ≤ 20%；
    `("VOID", …)`        terminal 但某臂 void 率 > 20% ⇒ 資料不進分析，重排一次；
    `("UNFINISHED", …)`  還沒 terminal（配合「行程還在不在」才判得出死活）。
    ⚠ 沒有 summary **不算** DONE：量不到不是通過。
    """
    if not summary:
        return "UNFINISHED", "no_summary"
    if not summary.get("run_terminal"):
        return "UNFINISHED", "run_terminal_false"
    vr = void_rates(summary)
    bad = {a: round(r, 4) for a, r in vr.items() if r > VOID_RATE_ABORT}
    if bad:
        return "VOID", f"void_rate_over_{VOID_RATE_ABORT}:{bad}"
    return "DONE", "terminal_and_clean"


def block_state(dir_exists: bool, summary: dict | None, alive: bool) -> tuple[str, str]:
    """一塊**現在**是什麼狀態。純函式：三個觀測值進，一個狀態出。

    PENDING    沒有目錄 ⇒ 還沒發射過
    RUNNING    行程還在（不管 summary 寫到哪）
    DONE       terminal 且乾淨
    VOID       terminal 但某臂 void 率 > 20%
    DEAD       有目錄、行程不在、又不是 terminal ⇒ 死在半路
    """
    if not dir_exists:
        return "PENDING", "no_dir"
    if alive:
        return "RUNNING", "process_alive"
    state, why = classify_summary(summary)
    if state == "UNFINISHED":
        return "DEAD", f"process_gone_and_{why}"
    return state, why


def slot_allows(slot: Slot, requeued: bool) -> bool:
    """重排過的塊只准上 1004（R4）。第一次發射兩顆都可以。"""
    return (not requeued) or slot.host == REQUEUE_HOST


def plan_launches(pending: list[str], busy: dict[str, str], attempts: dict[str, int],
                  slots: tuple[Slot, ...] = SLOTS) -> list[tuple[str, str]]:
    """把待跑的塊依佇列順序丟進空槽。回 `[(block_name, slot_id), …]`。

    `attempts[name]` ＝ **這一塊已經被作廢過幾次**（＝ `runs/_aborted/` 裡的
    目錄個數）。≥1 就是「重排的」⇒ 只准上 1004。

    ⚠ **不會 head-of-line blocking**：隊頭那塊如果是重排的、而唯一的空槽是 1003，
    就跳過它去看下一塊——1003 的槽不會因為隊頭卡住而空轉。
    被跳過的那塊留在原位（佇列永遠是正規順序，每輪從磁碟重推），
    下一輪 1004 一空就輪到它。
    """
    free = [s for s in slots if s.slot_id not in busy]
    out: list[tuple[str, str]] = []
    for name in pending:
        if not free:
            break
        requeued = attempts.get(name, 0) >= 1
        for i, s in enumerate(free):
            if slot_allows(s, requeued):
                out.append((name, s.slot_id))
                free.pop(i)
                break
    return out


# ── 排程一輪（純函式；**完全無記憶**）────────────────────────────────────
#
# ⚠ 這裡刻意**沒有**「排程器狀態」這種東西。理由是 idempotency：只要有一格狀態
#   活在行程的記憶體裡，排程器一重啟那一格就沒了，而「重排過幾次」剛好是**最不能**
#   丟的那一格（丟了＝重排次數無上限＝一直重試到資料看起來正常為止）。
#   所以每一輪都從**磁碟**重新推：
#     · 佔用中的槽 ← `ps` 上活著的 runner ＋ `<OUT>.endpoint`
#     · 重排過幾次 ← `runs/_aborted/<name>_void_*` 的目錄個數
#   兩者都是搬不走的證據。排程器可以隨時被 kill 再起來，計畫一個字不會變。


def occupancy(running: list[str], endpoints: dict[str, str],
              slots: tuple[Slot, ...] = SLOTS
              ) -> tuple[dict[str, str], list[str], set[str]]:
    """把**正在跑**的塊擺回槽。回 `(busy, unplaceable, blocked_endpoints)`。

    擺不回去有兩種（兩種都**不准**被當成「那顆端點還有空位」）：
      · 端點認得出來、但那顆的槽已經被別的正在跑的塊佔滿 ⇒ 封鎖那顆端點；
      · 端點認不出來（`<OUT>.endpoint` 不見了）⇒ **封鎖全部端點**。
        不知道它在哪一顆卡上，就不能再往任何一顆加負載——
        這是「量不到不是通過」在排程器這一側的樣子。代價是排程會停下來等人看，
        而那正是想要的：那種狀態代表有人在排程器之外手動發過東西。
    """
    busy: dict[str, str] = {}
    unplaceable: list[str] = []
    blocked: set[str] = set()
    for name in running:
        ep = endpoints.get(name)
        free = [s for s in slots if s.slot_id not in busy and s.endpoint == ep]
        if ep and free:
            busy[free[0].slot_id] = name
        else:
            unplaceable.append(name)
            blocked |= ({ep} if ep else {s.endpoint for s in slots})
    return busy, unplaceable, blocked


def plan_tick(blocks: list[Block], statuses: dict[str, str],
              endpoints: dict[str, str], aborted_counts: dict[str, int],
              slots: tuple[Slot, ...] = SLOTS) -> dict:
    """一輪的完整計畫。純函式：觀測進、計畫出，**不改任何東西**。

    順序固定：先收（把 VOID／DEAD 的搬走）再發。反過來的話這一輪剛空出來的槽
    要等下一輪才用得到，四個槽會有一格永遠是冷的。
    """
    order = [b.name for b in blocks]
    by_name = {b.name: b for b in blocks}
    abort = [(n, statuses.get(n)) for n in order
             if statuses.get(n) in ("VOID", "DEAD")]
    # 搬走之後那一塊立刻變成「沒有目錄」＝ PENDING，而它的重排次數 +1。
    counts = dict(aborted_counts)
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
    launch = plan_launches(queue, busy, counts, usable)
    return {"abort": abort, "launch": launch, "done": done, "given_up": given_up,
            "busy": busy, "queue": queue, "unplaceable": unplaceable,
            "blocked_endpoints": sorted(blocked),
            "attempts_after": {n: counts.get(n, 0) for n in order},
            "finished": not queue and not busy,
            "blocks": by_name}


# ── I/O 那一側 ───────────────────────────────────────────────────────────
def _read_json(path: pathlib.Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None


def running_block_names(root: pathlib.Path) -> set[str]:
    """`ps` 上還活著的 runner（`$2 == "python3"` 濾掉 flock 那一行）。"""
    try:
        out = subprocess.run(["ps", "-eo", "pid,cmd"], capture_output=True,
                             text=True, timeout=30).stdout
    except Exception:                                          # noqa: BLE001
        return set()
    names = set()
    for line in out.splitlines():
        if "gain_run.py --out " not in line or " python3 " not in f" {line} ":
            continue
        parts = line.split("gain_run.py --out ", 1)[1].split()
        if parts:
            names.add(pathlib.Path(parts[0]).name)
    return names


def observe(blocks: list[Block], root: pathlib.Path) -> tuple[dict, dict]:
    """讀現況：回 `(statuses, endpoints)`。這裡是唯一碰檔案系統與 ps 的地方。"""
    alive = running_block_names(root)
    statuses: dict[str, str] = {}
    endpoints: dict[str, str] = {}
    for b in blocks:
        d = root / b.out
        summary = _read_json(d / "summary.json") if d.exists() else None
        st, _why = block_state(d.exists(), summary, b.name in alive)
        statuses[b.name] = st
        ep = root / f"{b.out}.endpoint"
        if ep.exists():
            endpoints[b.name] = ep.read_text(encoding="utf-8").strip()
    return statuses, endpoints


def abort_block(name: str, why: str, root: pathlib.Path, log) -> None:
    """把一塊的目錄、launch.log、backend.json、endpoint 全部搬進 `runs/_aborted/`。

    ⚠ 搬不是刪：那份資料是「後端在這個時段壞掉」的證據
    （R460 那三塊 void 的 a 組就是這樣留著的）。
    """
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_root = root / "runs" / "_aborted"
    dest_root.mkdir(parents=True, exist_ok=True)
    # ⚠ 同一秒內作廢同一塊兩次是真的會發生的（兩次重排之間可能只差幾百毫秒，
    #   而戳記只到秒）。撞名的話 `shutil.move` 會把第二份**搬進第一份裡面**，
    #   於是 `runs/_aborted/<name>_void_*` 只數得到一個目錄 ⇒ 重排次數被低估
    #   ⇒ 「只重排一次」變成無上限。所以撞名要另外加尾碼，不能沿用。
    dest = dest_root / f"{name}_void_{ts}"
    dup = 1
    while dest.exists():
        dup += 1
        dest = dest_root / f"{name}_void_{ts}-{dup}"
    stem = dest.name
    src = root / "runs" / name
    if src.exists():
        shutil.move(str(src), str(dest))
    for suffix in (".launch.log", ".backend.json", ".endpoint"):
        s = root / "runs" / f"{name}{suffix}"
        if s.exists():
            shutil.move(str(s), str(dest_root / f"{stem}{suffix}"))
    (dest_root / f"{stem}.abort.json").write_text(
        json.dumps({"block": name, "reason": why, "ts_utc": ts,
                    "void_rate_threshold": VOID_RATE_ABORT}, ensure_ascii=False,
                   indent=2) + "\n", encoding="utf-8")
    log(f"ABORT {name}（{why}）⇒ {dest}")


def launch_block(block: Block, slot: Slot, root: pathlib.Path, log) -> int:
    """呼叫單塊發射器。**發射器自己做 preflight**，這裡只給參數與記錄。"""
    env = dict(os.environ,
               TAG=block.launch_tag, OUT=block.out, OFFSET=str(block.offset),
               SEED=block.seed, API=slot.endpoint, DEC=DECISION)
    log(f"LAUNCH {block.name} → 槽 {slot.slot_id}（{slot.endpoint}）"
        f" offset={block.offset} seed={block.seed}")
    r = subprocess.run(["bash", LAUNCHER], cwd=str(REPO), env=env,
                       capture_output=True, text=True)
    tail = (r.stdout or "")[-800:].replace("\n", "|")
    log(f"LAUNCH rc={r.returncode} {block.name}: {tail}")
    return r.returncode


def aborted_counts(blocks: list[Block], root: pathlib.Path) -> dict[str, int]:
    """每一塊被作廢過幾次＝ `runs/_aborted/<name>_void_*` 的目錄個數。

    ⚠ 這是排程器**唯一**的持久記憶，而它故意放在磁碟上：
    「重排過幾次」丟了就等於重排次數無上限，而那是選擇性重跑。
    """
    out: dict[str, int] = {}
    ab = root / "runs" / "_aborted"
    for b in blocks:
        out[b.name] = (len([d for d in ab.glob(f"{b.name}_void_*") if d.is_dir()])
                       if ab.exists() else 0)
    return out


def _plan_lines(blocks: list[Block], plan: dict, root: pathlib.Path) -> list[str]:
    by_name = plan["blocks"]
    L = [f"完成 {len(plan['done'])}／佇列 {len(plan['queue'])}"
         f"／佔用 {sorted(plan['busy'].items())}"]
    if plan["blocked_endpoints"]:
        L.append(f"  ⚠ 封鎖端點 {plan['blocked_endpoints']}"
                 f"（有塊擺不回槽：{plan['unplaceable']}）——本輪不往那幾顆加負載")
    for name, why in plan["abort"]:
        L.append(f"  作廢 {name}（{why}）⇒ 搬到 runs/_aborted/{name}_void_<ts>，"
                 f"重排第 {plan['attempts_after'][name]}/{MAX_ATTEMPTS} 次"
                 + ("（放棄）" if plan['attempts_after'][name] >= MAX_ATTEMPTS else ""))
    for name in plan["given_up"]:
        L.append(f"  放棄 {name}（已經作廢 {MAX_ATTEMPTS} 次）⇒ 留給人裁決")
    if plan["launch"]:
        for name, slot_id in plan["launch"]:
            b = by_name[name]
            sl = next(x for x in SLOTS if x.slot_id == slot_id)
            req = "（重排，只准 1004）" if plan["attempts_after"][name] >= 1 else ""
            L.append(f"  發射 {name}{req}（offset={b.offset} seed={b.seed} "
                     f"--gauge-scope bank）→ 槽 {slot_id} = {sl.host} {sl.endpoint}")
    else:
        L.append("  （沒有空槽或沒有待跑的塊）")
    return L


def dry_run(blocks: list[Block], root: pathlib.Path) -> str:
    """只算計畫、不發射、不碰後端、不寫任何東西。"""
    statuses, endpoints = observe(blocks, root)
    counts = aborted_counts(blocks, root)
    plan = plan_tick(blocks, statuses, endpoints, counts)
    L = ["═══ R460R 排程器乾跑 ═══",
         f"repo={REPO}  runs 根目錄={root}  DECISION={DECISION}",
         f"槽：{[(s.slot_id, s.host) for s in SLOTS]}"
         f"（1004×3、1003×1；重排只准上 {REQUEUE_HOST}）",
         f"佇列順序（{len(plan['queue'])} 塊待跑）："
         f"{', '.join(plan['queue']) or '(空)'}",
         ""]
    L.append("── 現況（逐塊）")
    for b in blocks:
        st = statuses.get(b.name, "PENDING")
        if st == "PENDING" and counts.get(b.name, 0) == 0:
            continue        # 全新的塊不逐行印，佇列那一行已經有了
        L.append(f"  {b.name}: {st}"
                 f"（已作廢 {counts.get(b.name, 0)} 次"
                 f"{'，端點 ' + endpoints[b.name] if b.name in endpoints else ''}）")
    if len(L) == 6:
        L.append("  （沒有現成的目錄；全部都是新的）")
    L += ["", "── 這一輪會做的事"] + _plan_lines(blocks, plan, root)
    L += ["", "── 之後的規則（不在這一輪，但寫在這裡好對帳）",
          f"  · 每 {POLL_S} s 輪詢一次；某塊 summary.json 的 run_terminal=true "
          f"且每臂 void ≤ {int(VOID_RATE_ABORT * 100)}% ⇒ 放掉那個槽",
          f"  · terminal 但某臂 void > {int(VOID_RATE_ABORT * 100)}%、"
          "或行程死了又沒 terminal ⇒ 目錄／launch.log／backend.json 搬到 "
          "runs/_aborted/<name>_void_<ts>，**只重排一次、只准上 1004**",
          f"  · 一塊最多發射 {MAX_ATTEMPTS} 次；用完還壞 ⇒ 放棄，留給人裁決",
          "  · 排程器可以重跑／被 kill 再起來：完成的跳過、正在跑的認回槽"
          "（靠 `<OUT>.endpoint`）、作廢次數從 runs/_aborted/ 數出來"
          "——沒有任何一格狀態活在記憶體裡"]
    return "\n".join(L)


def poll_loop(blocks: list[Block], root: pathlib.Path, log,
              *, max_ticks: int | None = None,
              launcher=None, aborter=None, sleeper=time.sleep) -> int:
    """輪詢主迴圈。`launcher`／`aborter`／`sleeper` 可注入，測試不碰後端與磁碟。"""
    launcher = launcher or (lambda b, s: launch_block(b, s, root, log))
    aborter = aborter or (lambda n, w: abort_block(n, w, root, log))
    ticks = 0
    while True:
        statuses, endpoints = observe(blocks, root)
        counts = aborted_counts(blocks, root)
        plan = plan_tick(blocks, statuses, endpoints, counts)
        for line in _plan_lines(blocks, plan, root):
            log(line)
        for name, why in plan["abort"]:
            aborter(name, why)
        for name, slot_id in plan["launch"]:
            slot = next(s for s in SLOTS if s.slot_id == slot_id)
            launcher(plan["blocks"][name], slot)
        if plan["finished"]:
            log(f"全部結束：完成 {len(plan['done'])}／放棄 {len(plan['given_up'])}"
                f"（{plan['given_up']}）")
            return 1 if plan["given_up"] else 0
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            log(f"max_ticks={max_ticks} 到了，停止輪詢（佇列剩 {len(plan['queue'])}）")
            return 0
        sleeper(POLL_S)


def main() -> int:
    ap = argparse.ArgumentParser(description="R460R 30 塊排程器（1004×3、1003×1）")
    ap.add_argument("--root", default=str(REPO),
                    help="runs/ 的所在根目錄（乾跑／測試可以指到別處）")
    ap.add_argument("--reps", nargs="+", type=int, choices=list(REPS), default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="只印計畫：不發射、不碰後端、不寫任何檔案")
    ap.add_argument("--log", default=None,
                    help="預設 ~/vacant/logs/schedule_harness_reps.log")
    ap.add_argument("--max-ticks", type=int, default=None,
                    help="輪詢幾圈之後停（測試用；正式跑不給）")
    args = ap.parse_args()
    root = pathlib.Path(args.root)
    blocks = build_queue(tuple(args.reps) if args.reps else REPS)
    if args.dry_run:
        print(dry_run(blocks, root))
        return 0
    log_path = pathlib.Path(
        args.log or (pathlib.Path.home() / "vacant" / "logs"
                     / "schedule_harness_reps.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        line = (f"{_dt.datetime.now(_dt.timezone.utc):%Y-%m-%d %H:%M:%S UTC}  {msg}")
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # 兩個排程器同時跑會把同一塊發兩次（第二次撞 abort_dir_exists，
    # 但那已經在 log 裡留下一個看起來像失敗的紀錄）⇒ 用 flock 擋掉。
    lock_path = log_path.parent / ".schedule_harness_reps.lock"
    import fcntl
    lock_fh = lock_path.open("w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("已經有一個 schedule_harness_reps 在跑（flock）——這次不做事")
        return 2
    log(f"排程器啟動 pid={os.getpid()} root={root} 塊數={len(blocks)}")
    return poll_loop(blocks, root, log, max_ticks=args.max_ticks)


if __name__ == "__main__":
    raise SystemExit(main())
