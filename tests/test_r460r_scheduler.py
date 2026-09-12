"""R460R：排程器、單塊發射器、V/GT 稽核 v2、彙總分析——四邊不准漂開。

這支在架構裡承重什麼：R460R 有 30 個 run，而它們**不是一支發射器一次發出去的**。
排程決定了「誰跑在哪顆卡上、掛了要不要重來」，而那兩件事一旦錯了，
錯法都是**看起來只是比較慢**或**看起來只是那一次比較倒楣**：

  · 1003 上同時兩塊 ⇒ 那台會 `bad alloc`／`Context size has been exceeded`
    ⇒ 整組 `infra_void` ⇒ 讀起來像「這次複製的資料比較差」；
  · 重排沒有上限 ⇒ 一直重試到資料看起來正常為止 ＝ 選擇性重跑；
  · 排程器重啟之後忘記重排過幾次 ⇒ 上一條自動成立。

所以本檔的重點不是「函式會不會跑」，是**牙齒**：每一條規則都配一個
「規則不在的話會怎樣」的反例。零 API、零 ssh、零 `runs/` 寫入
（排程器的模擬全部在 `tmp_path` 裡）。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain import schedule_harness_reps as S  # noqa: E402
from ops.gain.analyze_r460 import (ENDPOINT_1003,  # noqa: E402
                                   ENDPOINT_1004,
                                   ENDPOINT_CONCURRENCY_CAPS,
                                   REPLICATION_BLOCKS, REPLICATION_SEEDS)

DEC = ROOT / "DECISION_20260911_R460R_FIVE_REPLICATIONS_PREREG.md"
LAUNCHER = ROOT / "ops" / "gain" / "launch_harness_rep_block.sh"
SCHEDULER = ROOT / "ops" / "gain" / "schedule_harness_reps.py"
R460_BLOCKS = ("a1", "a2", "a3", "b1", "b2", "b3")


@pytest.fixture(scope="module")
def dec() -> str:
    return DEC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def sh() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


# ══ 一、佇列與槽（純函式）════════════════════════════════════════════════
def test_queue_is_thirty_blocks_in_the_registered_order():
    q = S.build_queue()
    assert len(q) == 30
    assert [b.name for b in q[:6]] == list(REPLICATION_BLOCKS[1])
    assert [b.name for b in q[-6:]] == list(REPLICATION_BLOCKS[5])
    # 依複製排、不交錯：前六塊全是 rep 1
    assert {b.rep for b in q[:6]} == {1}
    assert [b.offset for b in q[:6]] == [0, 20, 40, 60, 80, 100]
    assert {b.seed for b in q[:6]} == {REPLICATION_SEEDS[1]}


def test_slots_are_three_on_1004_and_one_on_1003():
    by_host: dict[str, int] = {}
    for s in S.SLOTS:
        by_host[s.host] = by_host.get(s.host, 0) + 1
    assert by_host == {"1004": 3, "1003": 1}
    assert {s.endpoint for s in S.SLOTS} == {ENDPOINT_1004, ENDPOINT_1003}
    # 排程器與 analyzer 讀的是同一組上限——兩邊分別寫死會漂開。
    assert ENDPOINT_CONCURRENCY_CAPS == {ENDPOINT_1004: 3, ENDPOINT_1003: 1}
    assert by_host["1004"] == ENDPOINT_CONCURRENCY_CAPS[ENDPOINT_1004]
    assert by_host["1003"] == ENDPOINT_CONCURRENCY_CAPS[ENDPOINT_1003]


def test_no_slot_points_at_the_hub():
    assert not any("8765" in s.endpoint for s in S.SLOTS)


# ══ 一-2、`--reps`／`--hosts`：表是註冊、旗標是這次排什麼 ════════════════
# 2026-09-11 人類指示：1003 由人類自己在用 ⇒ 這次一塊都不准上；先跑 r1–r3。
def test_slot_table_is_data_and_hosts_only_filters_it():
    """`--hosts` 是**篩**：SLOTS 那張表一格都沒被刪掉。"""
    assert S.select_slots(None) == S.SLOTS
    assert S.select_slots(("1004", "1003")) == S.SLOTS
    only = S.select_slots(("1004",))
    assert [s.slot_id for s in only] == ["1004#1", "1004#2", "1004#3"]
    assert {s.endpoint for s in only} == {ENDPOINT_1004}
    # 表本身沒動 ⇒ 1003 的上限（實測換來的）還在，卡還回來時不必改碼。
    assert len(S.SLOTS) == 4 and S.HOSTS == ("1004", "1003")
    assert ENDPOINT_CONCURRENCY_CAPS[ENDPOINT_1003] == 1


def test_hosts_typo_is_an_error_not_a_silent_fallback_to_everything():
    """打錯字時默默退回四個槽 ＝ 把人類的「1003 不要用」變成「照跑」。"""
    with pytest.raises(SystemExit):
        S.select_slots(("1005",))
    with pytest.raises(SystemExit):
        S.select_slots(())


def test_reps_restricts_the_queue_without_changing_the_registration():
    q = S.build_queue((1, 2, 3))
    assert len(q) == 18
    assert {b.rep for b in q} == {1, 2, 3}
    assert [b.name for b in q[:6]] == list(REPLICATION_BLOCKS[1])
    assert [b.name for b in q[-6:]] == list(REPLICATION_BLOCKS[3])
    # r4／r5 仍然是**註冊過的**，只是沒進佇列——預註冊表一個字沒動。
    assert S.REPS == (1, 2, 3, 4, 5)
    assert len(S.build_queue()) == 30
    with pytest.raises(SystemExit):
        S.build_queue((6,))
    with pytest.raises(SystemExit):
        S.build_queue(())


def test_with_only_1004_the_first_tick_launches_three_blocks_there():
    """人類指示下的第一輪：1004×3、佇列 r1a1..r3b3。"""
    blocks = S.build_queue((1, 2, 3))
    slots = S.select_slots(("1004",))
    p = S.plan_tick(blocks, {}, {}, {}, slots)
    assert p["launch"] == [("g_r460r1_harness_lcb2_a1", "1004#1"),
                           ("g_r460r1_harness_lcb2_a2", "1004#2"),
                           ("g_r460r1_harness_lcb2_a3", "1004#3")]
    assert len(p["queue"]) == 18
    assert not any(s.host == "1003" for s in p["slots"])


def test_a_block_running_on_1003_does_not_eat_a_1004_slot():
    """`--hosts 1004` 之下 1003 上還有塊在跑（別人手動發的）——
    那塊的負載明確落在別顆卡，只封鎖 1003，1004 照發。"""
    blocks = S.build_queue((1,))
    slots = S.select_slots(("1004",))
    name = "g_r460r1_harness_lcb2_a1"
    p = S.plan_tick(blocks, {name: "RUNNING"}, {name: ENDPOINT_1003}, {}, slots)
    assert p["unplaceable"] == [name]
    assert p["blocked_endpoints"] == [ENDPOINT_1003]
    assert len(p["launch"]) == 3
    assert all(s.startswith("1004") for _n, s in p["launch"])


def test_an_endpoint_sidecar_outside_the_known_set_blocks_everything():
    """round460r-2：`.endpoint` 寫著認不出來的端點 ⇒ 當成不知道 ⇒ 全部封鎖。

    ⚠ 舊寫法只封鎖「它自己那顆」，而它自己那顆本來就沒有任何槽
    ⇒ `usable` 一格都沒少 ⇒ 等於沒有牙齒。認不出來的端點與沒有端點
    是同一件事：不知道那塊在哪一顆卡上，就不能再往任何一顆加負載。
    """
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_a1"
    for bogus in ("http://10.0.0.9:1234/v1/chat/completions",
                  "http://100.86.226.21:8765/v1/chat/completions",  # hub
                  "not-a-url"):
        p = S.plan_tick(blocks, {name: "RUNNING"}, {name: bogus}, {})
        assert p["unplaceable"] == [name], bogus
        assert sorted(p["blocked_endpoints"]) == sorted(
            {ENDPOINT_1003, ENDPOINT_1004}), bogus
        assert p["launch"] == [], bogus
        # `--hosts 1004` 之下也一樣（fail closed 不因為槽變少而放鬆）
        p2 = S.plan_tick(blocks, {name: "RUNNING"}, {name: bogus}, {},
                         S.select_slots(("1004",)))
        assert p2["launch"] == [], bogus


def test_first_tick_launches_exactly_four_blocks_where_registered():
    blocks = S.build_queue()
    plan = S.plan_tick(blocks, {}, {}, {})
    assert plan["launch"] == [
        ("g_r460r1_harness_lcb2_a1", "1004#1"),
        ("g_r460r1_harness_lcb2_a2", "1004#2"),
        ("g_r460r1_harness_lcb2_a3", "1004#3"),
        ("g_r460r1_harness_lcb2_b1", "1003#1"),
    ]


def test_a_requeued_block_may_only_go_to_1004():
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_a1"
    # 只剩 1003 的槽是空的、而隊頭是重排過的塊 ⇒ 它不准上去
    busy = {"1004#1": "x", "1004#2": "y", "1004#3": "z"}
    got = S.plan_launches([name], busy, {name: 1})
    assert got == []
    # 同一塊、同一個空槽，但沒有被重排過 ⇒ 可以上 1003
    assert S.plan_launches([name], busy, {}) == [(name, "1003#1")]


def test_requeued_block_does_not_block_the_head_of_the_line():
    """隊頭是重排的、只剩 1003 空著 ⇒ 跳過它去發下一塊，1003 不准空轉。"""
    head, nxt = "g_r460r1_harness_lcb2_a1", "g_r460r1_harness_lcb2_a2"
    busy = {"1004#1": "x", "1004#2": "y", "1004#3": "z"}
    got = S.plan_launches([head, nxt], busy, {head: 1})
    assert got == [(nxt, "1003#1")]


# ══ 二、狀態判定與重排規則（純函式）══════════════════════════════════════
def _summary(void: dict[str, int] | None = None, terminal: bool = True) -> dict:
    arms = {a: {"processed": 20, "infra_void": 0}
            for a in ("OFF", "CONFORM", "OFF5", "HPI", "HOC", "HMIX")}
    for a, n in (void or {}).items():
        arms[a] = {"processed": 20, "infra_void": n}
    return {"run_terminal": terminal, "arms": arms}


def test_clean_terminal_block_is_done():
    assert S.classify_summary(_summary())[0] == "DONE"
    assert S.block_state(True, _summary(), alive=False)[0] == "DONE"


def test_void_rate_over_twenty_percent_is_not_done():
    # 5/20 ＝ 25% > 20% ⇒ VOID；4/20 ＝ 20%（不超過）⇒ DONE
    assert S.classify_summary(_summary({"HPI": 5}))[0] == "VOID"
    assert S.classify_summary(_summary({"HPI": 4}))[0] == "DONE"
    assert S.VOID_RATE_ABORT == 0.20


def test_missing_summary_is_never_done():
    """量不到不是通過：沒有 summary 的塊不准被當成跑完。"""
    assert S.classify_summary(None)[0] == "UNFINISHED"
    assert S.block_state(True, None, alive=False)[0] == "DEAD"
    assert S.block_state(True, None, alive=True)[0] == "RUNNING"
    assert S.block_state(False, None, alive=False)[0] == "PENDING"


def test_unterminated_summary_with_dead_process_is_dead():
    assert S.block_state(True, _summary(terminal=False), alive=False)[0] == "DEAD"


def test_void_block_is_aborted_and_requeued_once_then_given_up():
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_b1"
    st = {name: "VOID"}
    # 第一次作廢 ⇒ 重排（而且因為 attempts 變 1，只准 1004）
    p1 = S.plan_tick(blocks, st, {}, {})
    assert (name, "VOID") in p1["abort"]
    assert name not in p1["given_up"]
    assert name in p1["queue"]
    # 四個槽全空、佇列在它前面還有 a1/a2/a3 ⇒ 1004 三個槽被前面三塊拿走，
    # 剩下的 1003 這一塊**不准**給重排的塊 ⇒ 它這一輪不發，下一輪 1004 一空就輪到它。
    assert name not in dict(p1["launch"])
    p1b = S.plan_tick(blocks, st, {},
                      {}, )
    assert dict(p1b["launch"])["g_r460r1_harness_lcb2_a1"] == "1004#1"
    # 前三塊改成正在跑（a1 佔住 1003、a2/a3 佔住 1004 兩個槽）
    # ⇒ 只剩一個 1004 的槽，重排的 b1 立刻拿到它
    running = {"g_r460r1_harness_lcb2_a1": "RUNNING",
               "g_r460r1_harness_lcb2_a2": "RUNNING",
               "g_r460r1_harness_lcb2_a3": "RUNNING"}
    eps = {"g_r460r1_harness_lcb2_a1": ENDPOINT_1003,
           "g_r460r1_harness_lcb2_a2": ENDPOINT_1004,
           "g_r460r1_harness_lcb2_a3": ENDPOINT_1004}
    p1c = S.plan_tick(blocks, dict(st, **running), eps, {})
    assert dict(p1c["launch"])[name] == "1004#3"
    # 第二次作廢（已經作廢過一次）⇒ 放棄，不再發
    p2 = S.plan_tick(blocks, st, {}, {name: 1})
    assert (name, "VOID") in p2["abort"]
    assert name in p2["given_up"]
    assert name not in dict(p2["launch"])
    assert S.MAX_ATTEMPTS == 2


def test_given_up_block_stays_given_up_after_a_restart():
    """重排次數是從 runs/_aborted/ 數出來的 ⇒ 排程器重啟不會把它洗掉。"""
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_b1"
    p = S.plan_tick(blocks, {}, {}, {name: 2})
    assert name in p["given_up"] and name not in p["queue"]
    assert name not in dict(p["launch"])


def test_running_block_is_adopted_into_a_slot_not_relaunched():
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_a1"
    p = S.plan_tick(blocks, {name: "RUNNING"}, {name: ENDPOINT_1004}, {name: 0})
    assert p["busy"] == {"1004#1": name}
    assert name not in dict(p["launch"])
    # 那顆卡剩兩個槽、1003 一個 ⇒ 這一輪只發三塊
    assert len(p["launch"]) == 3


def test_a_running_block_with_unknown_endpoint_blocks_every_endpoint():
    """認不出它在哪一顆卡上就不能再加負載——量不到不是通過。"""
    blocks = S.build_queue()
    name = "g_r460r1_harness_lcb2_a1"
    p = S.plan_tick(blocks, {name: "RUNNING"}, {}, {})
    assert p["unplaceable"] == [name]
    assert sorted(p["blocked_endpoints"]) == sorted({ENDPOINT_1003, ENDPOINT_1004})
    assert p["launch"] == []


def test_two_running_blocks_on_1003_block_that_endpoint():
    """1003 只有一個槽；硬塞第二塊 ⇒ 封鎖那顆，不准再往上加。"""
    blocks = S.build_queue()
    n1, n2 = "g_r460r1_harness_lcb2_a1", "g_r460r1_harness_lcb2_a2"
    p = S.plan_tick(blocks, {n1: "RUNNING", n2: "RUNNING"},
                    {n1: ENDPOINT_1003, n2: ENDPOINT_1003}, {})
    assert p["unplaceable"] == [n2]
    assert p["blocked_endpoints"] == [ENDPOINT_1003]
    assert all(slot.startswith("1004") for _n, slot in p["launch"])


def test_done_blocks_are_skipped_so_the_scheduler_is_idempotent():
    blocks = S.build_queue()
    done = {b.name: "DONE" for b in blocks[:6]}
    p = S.plan_tick(blocks, done, {}, {})
    assert sorted(p["done"]) == sorted(REPLICATION_BLOCKS[1])
    assert not any(n in REPLICATION_BLOCKS[1] for n, _s in p["launch"])
    assert dict(p["launch"])["g_r460r2_harness_lcb2_a1"] == "1004#1"


def test_scheduler_reports_finished_only_when_queue_and_slots_are_empty():
    blocks = S.build_queue()
    p = S.plan_tick(blocks, {b.name: "DONE" for b in blocks}, {}, {})
    assert p["finished"] is True and len(p["done"]) == 30


# ══ 三、整支模擬：假 runs/、假 terminal summary、零網路 ═══════════════════
class _Sim:
    """把排程器接到一個假的 `runs/`：發射＝建目錄，收官＝寫 summary。"""

    def __init__(self, root: pathlib.Path, monkeypatch):
        self.root = root
        (root / "runs").mkdir(parents=True)
        self.alive: set[str] = set()
        self.launched: list[tuple[str, str]] = []
        self.lines: list[str] = []
        monkeypatch.setattr(S, "running_block_names", lambda _r: set(self.alive))

    def log(self, msg: str) -> None:
        self.lines.append(msg)

    def launch(self, block, slot) -> None:
        (self.root / block.out).mkdir(parents=True)
        (self.root / f"{block.out}.endpoint").write_text(slot.endpoint + "\n")
        (self.root / f"{block.out}.launch.log").write_text("preflight ✓\n")
        (self.root / f"{block.out}.backend.json").write_text('{"data":[]}')
        self.alive.add(block.name)
        self.launched.append((block.name, slot.slot_id))

    def finish(self, name: str, *, void: dict | None = None, die: bool = False):
        self.alive.discard(name)
        if die:
            return
        (self.root / "runs" / name / "summary.json").write_text(
            json.dumps(_summary(void)), encoding="utf-8")

    def tick(self, blocks):
        self.launched = []
        S.poll_loop(blocks, self.root, self.log, max_ticks=1,
                    launcher=self.launch,
                    aborter=lambda n, w: S.abort_block(n, w, self.root, self.log),
                    sleeper=lambda _s: None)
        return list(self.launched)


def test_full_simulation_slot_allocation_and_requeue(tmp_path, monkeypatch):
    sim = _Sim(tmp_path, monkeypatch)
    blocks = S.build_queue()

    # tick 1：四個槽全空 ⇒ 三塊上 1004、一塊上 1003
    assert sim.tick(blocks) == [
        ("g_r460r1_harness_lcb2_a1", "1004#1"),
        ("g_r460r1_harness_lcb2_a2", "1004#2"),
        ("g_r460r1_harness_lcb2_a3", "1004#3"),
        ("g_r460r1_harness_lcb2_b1", "1003#1"),
    ]

    # tick 2：a1 乾淨收官、b1 的 HPI void 45% ⇒ b1 作廢並重排（只准 1004）
    sim.finish("g_r460r1_harness_lcb2_a1")
    sim.finish("g_r460r1_harness_lcb2_b1", void={"HPI": 9})
    got = dict(sim.tick(blocks))
    assert got["g_r460r1_harness_lcb2_b1"].startswith("1004")
    assert got["g_r460r1_harness_lcb2_b2"] == "1003#1"
    aborted = sorted(p.name for p in (tmp_path / "runs" / "_aborted").iterdir()
                     if p.is_dir())
    assert len(aborted) == 1 and aborted[0].startswith("g_r460r1_harness_lcb2_b1_void_")
    # 證據是搬走不是刪掉：summary 還在，而且 launch.log／backend.json 一起搬
    moved = tmp_path / "runs" / "_aborted" / aborted[0]
    assert (moved / "summary.json").exists()
    assert (tmp_path / "runs" / "_aborted" / f"{aborted[0]}.launch.log").exists()
    assert (tmp_path / "runs" / "_aborted" / f"{aborted[0]}.abort.json").exists()
    assert json.loads((tmp_path / "runs" / "_aborted"
                       / f"{aborted[0]}.abort.json").read_text())["reason"] == "VOID"

    # tick 3：重排後的 b1 又 void ⇒ 作廢第二次 ⇒ 放棄，不再發它
    sim.finish("g_r460r1_harness_lcb2_b1", void={"HOC": 9})
    got3 = dict(sim.tick(blocks))
    assert "g_r460r1_harness_lcb2_b1" not in got3
    assert any("放棄 g_r460r1_harness_lcb2_b1" in ln for ln in sim.lines)
    assert len([p for p in (tmp_path / "runs" / "_aborted").iterdir()
                if p.is_dir() and p.name.startswith("g_r460r1_harness_lcb2_b1")]) == 2

    # tick 4：再跑一次（等於排程器被 kill 之後重啟）⇒ 不重發任何已存在的塊
    before = sorted(p.name for p in (tmp_path / "runs").iterdir())
    assert sim.tick(blocks) == []
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == before
    assert any("放棄 g_r460r1_harness_lcb2_b1" in ln for ln in sim.lines)


def test_simulation_dead_process_without_terminal_is_requeued(tmp_path, monkeypatch):
    sim = _Sim(tmp_path, monkeypatch)
    blocks = S.build_queue()
    sim.tick(blocks)
    sim.finish("g_r460r1_harness_lcb2_a2", die=True)     # 行程沒了、沒有 summary
    got = dict(sim.tick(blocks))
    assert got["g_r460r1_harness_lcb2_a2"].startswith("1004")
    assert any("DEAD" in ln for ln in sim.lines)


def test_abort_twice_in_the_same_second_creates_two_directories(tmp_path):
    """戳記只到秒。撞名如果沿用同一個目錄，重排次數會被低估成一次。"""
    (tmp_path / "runs" / "g_x").mkdir(parents=True)
    S.abort_block("g_x", "VOID", tmp_path, lambda _m: None)
    (tmp_path / "runs" / "g_x").mkdir(parents=True)
    S.abort_block("g_x", "VOID", tmp_path, lambda _m: None)
    dirs = [p for p in (tmp_path / "runs" / "_aborted").iterdir() if p.is_dir()]
    assert len(dirs) == 2, [p.name for p in dirs]


def test_aborted_counts_reads_the_directories(tmp_path):
    blocks = S.build_queue()
    name = blocks[0].name
    ab = tmp_path / "runs" / "_aborted"
    (ab / f"{name}_void_20260911T000000Z").mkdir(parents=True)
    (ab / f"{name}_void_20260911T000001Z").mkdir(parents=True)
    assert S.aborted_counts(blocks, tmp_path)[name] == 2


def test_dry_run_launches_nothing_and_writes_nothing(tmp_path):
    out = subprocess.run(
        [sys.executable, str(SCHEDULER), "--dry-run", "--root", str(tmp_path)],
        capture_output=True, text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    assert "1004#1" in out.stdout and "1003#1" in out.stdout
    assert list(tmp_path.iterdir()) == []


def test_dry_run_with_the_humans_flags_shows_1004x3_and_eighteen_blocks(tmp_path):
    """2026-09-11 人類指示的那一行逐字：`--reps 1 2 3 --hosts 1004`。"""
    out = subprocess.run(
        [sys.executable, str(SCHEDULER), "--dry-run", "--root", str(tmp_path),
         "--reps", "1", "2", "3", "--hosts", "1004"],
        capture_output=True, text=True, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr
    assert "1003" not in out.stdout.replace("本次停用 1003", ""), out.stdout
    assert "1004#1" in out.stdout and "1004#3" in out.stdout
    assert "1004#4" not in out.stdout
    assert "18 塊待跑" in out.stdout
    assert "g_r460r1_harness_lcb2_a1" in out.stdout
    assert "g_r460r3_harness_lcb2_b3" in out.stdout
    assert "g_r460r4" not in out.stdout and "g_r460r5" not in out.stdout
    assert out.stdout.count("  發射 ") == 3
    assert list(tmp_path.iterdir()) == []


# ══ 三-2、preflight 失敗也是一次嘗試（round460r-2）══════════════════════
def test_preflight_failure_counts_toward_max_attempts_and_then_gives_up(
        tmp_path, monkeypatch):
    """發射器 rc != 0 ⇒ sidecar 搬走、計入重排次數、兩次就放棄。

    ⚠ 不記一筆的話：磁碟上沒有 summary、沒有行程 ⇒ 下一輪那塊還是 PENDING
    ⇒ **每 60 秒重發一次、永遠**。而最常見的那個 abort
    （`.launch.log` 已存在）自己就不可能自癒。
    """
    (tmp_path / "runs").mkdir(parents=True)
    monkeypatch.setattr(S, "running_block_names", lambda _r: set())
    blocks = S.build_queue((1,))
    lines: list[str] = []
    tried: list[str] = []

    def bad_launch(block, _slot):
        # 發射器在寫 .endpoint／.backend.json 之前就中止，但 launch.log 可能已存在
        (tmp_path / f"{block.out}.launch.log").write_text("ABORT: 探針只過 1/3\n")
        tried.append(block.name)
        return 1                                     # ＝ finish abort_probe_only_1

    def tick():
        del tried[:]
        S.poll_loop(blocks, tmp_path, lines.append, max_ticks=1,
                    slots=S.select_slots(("1004",)), launcher=bad_launch,
                    sleeper=lambda _s: None)
        return list(tried)

    head = "g_r460r1_harness_lcb2_a1"
    assert head in tick()
    ab = tmp_path / "runs" / "_aborted"
    dirs = sorted(p.name for p in ab.iterdir() if p.is_dir())
    assert any(d.startswith(f"{head}_preflight_") for d in dirs), dirs
    # sidecar 搬走了 ⇒ 下一次不會再撞 abort_launchlog_exists
    assert not (tmp_path / "runs" / f"{head}.launch.log").exists()
    assert S.aborted_counts(blocks, tmp_path)[head] == 1
    rec = json.loads(next(ab.glob(f"{head}_preflight_*.abort.json"))
                     .read_text(encoding="utf-8"))
    assert rec["kind"] == "preflight" and rec["launcher_rc"] == 1

    assert head in tick()                            # 第二次嘗試
    assert S.aborted_counts(blocks, tmp_path)[head] == S.MAX_ATTEMPTS
    assert head not in tick()                        # 第三輪：放棄，不再發
    assert any(f"放棄 {head}" in ln for ln in lines)


def test_preflight_and_void_aborts_share_one_attempt_budget(tmp_path):
    """兩種戳記都算數：一次 void ＋ 一次 preflight ＝ 用完 MAX_ATTEMPTS。"""
    blocks = S.build_queue((1,))
    name = blocks[0].name
    ab = tmp_path / "runs" / "_aborted"
    (ab / f"{name}_void_20260911T000000Z").mkdir(parents=True)
    (ab / f"{name}_preflight_20260911T000001Z").mkdir(parents=True)
    assert S.aborted_counts(blocks, tmp_path)[name] == 2
    p = S.plan_tick(blocks, {}, {}, S.aborted_counts(blocks, tmp_path))
    assert name in p["given_up"] and name not in dict(p["launch"])


def test_preflight_abort_leaves_a_directory_even_with_nothing_to_move(tmp_path):
    """目錄本身就是計數單位——沒東西可搬也要留下來，否則那次嘗試等於沒發生。"""
    (tmp_path / "runs").mkdir(parents=True)
    S.abort_preflight("g_x", 1, tmp_path, lambda _m: None)
    dirs = [p for p in (tmp_path / "runs" / "_aborted").iterdir() if p.is_dir()]
    assert len(dirs) == 1 and dirs[0].name.startswith("g_x_preflight_")


def test_a_successful_launch_is_not_counted_as_an_attempt(tmp_path, monkeypatch):
    """rc == 0（含 launch_pending_timeout）⇒ 不記 preflight 作廢。"""
    sim = _Sim(tmp_path, monkeypatch)
    blocks = S.build_queue((1,))
    S.poll_loop(blocks, tmp_path, sim.log, max_ticks=1,
                slots=S.select_slots(("1004",)),
                launcher=lambda b, s: sim.launch(b, s),   # 回 None ＝ 當作 0
                sleeper=lambda _s: None)
    assert not (tmp_path / "runs" / "_aborted").exists()
    assert S.aborted_counts(blocks, tmp_path)[blocks[0].name] == 0


# ══ 四、發射器：preflight 沒有被稀釋 ══════════════════════════════════════
def test_launcher_is_valid_bash():
    r = subprocess.run(["bash", "-n", str(LAUNCHER)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("needle", [
    "PROBE_MAX_TOKENS=512",           # round460e-2：16 會被 reasoning 吃光
    "REQUEST_TIMEOUT_S=1200",         # 實驗條件，不准漂
    "GAUGE_SCOPE=bank",               # R1：這次每一塊都是 bank
    "HUB_MARK=\"8765\"",              # hub 禁止
    "abort_hub_endpoint",
    "abort_dir_exists",
    "abort_launchlog_exists",
    "abort_seed_set_mismatch",
    "abort_concurrency_knob_appeared",
    "ThreadPoolExecutor(",
    "setsid nohup flock",
    "SEED_AUTHORIZED_SET",
])
def test_launcher_keeps_the_r460_preflight(sh: str, needle: str):
    assert needle in sh, needle


def test_launcher_probe_body_check_is_not_relaxed(sh: str):
    """探針要求 content 非空。把空 content 讀成通過等於把探針關掉。"""
    assert 'c.strip()' in sh and 'body_ok=' in sh
    assert '[ "$ok" -eq 3 ]' in sh


def test_launcher_probe_max_tokens_matches_the_runner_constant(sh: str):
    from ops.gain.harness_arms import WIRE_PROBE_MAX_TOKENS
    m = re.search(r"^PROBE_MAX_TOKENS=(\d+)\b", sh, re.M)
    assert m and int(m.group(1)) == WIRE_PROBE_MAX_TOKENS


def test_launcher_writes_the_endpoint_sidecar(sh: str):
    """排程器重啟後靠 `<OUT>.endpoint` 把正在跑的塊認回原本的槽。"""
    assert '> "$OUT.endpoint"' in sh
    assert 'VACANT_GAIN_API="$API"' in sh


def test_launcher_does_not_reintroduce_the_six_block_topology_check(sh: str):
    """R460 的「每顆端點三塊」在排程之下量不到東西——不准抄回來。"""
    for banned in ("BLOCKS_PER_ENDPOINT", "abort_endpoint_imbalance",
                   "abort_endpoint_oversubscribed", "abort_other_run"):
        assert banned not in sh, banned


# ══ 五、seed 授權：五顆都必須是新的，而且牙齒還在 ════════════════════════
def _scan_snippet() -> str:
    """把發射器裡那段 seed 掃描原封不動抽出來（不是另寫一份）。"""
    sh = LAUNCHER.read_text(encoding="utf-8")
    body = sh.split("scan=$(python3 - \"$SEED\" \"$auth\" \"$SEED_SCAN_EXCLUDE\" <<'PY'", 1)[1]
    return body.split("\nPY\n", 1)[0]


def _run_scan(tmp_path, seed: str, auth: str, own: str) -> str:
    r = subprocess.run([sys.executable, "-c", _scan_snippet(), seed, auth, own],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _write_run(tmp_path, name: str, seed: str) -> None:
    d = tmp_path / "runs" / name
    d.mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps({"seed": seed}), encoding="utf-8")


def test_decision_registers_all_thirty_run_names(dec: str):
    for k in range(1, 6):
        for name in REPLICATION_BLOCKS[k]:
            assert f"runs/{name}" in dec, name


def test_decision_registers_the_five_fresh_seeds(dec: str):
    for k in range(1, 6):
        assert f"SEED_AUTHORIZED_SET: {REPLICATION_SEEDS[k]} <- NONE" in dec


def test_decision_registers_the_frozen_flags(dec: str):
    for flag in ("--arms OFF,CONFORM,OFF5,HPI,HOC,HMIX", "--bank lcb2",
                 "--gauge-scope bank", "--request-timeout-s 1200",
                 "--review-timeout-s 380", "--retries 4", "--probe-sample 0",
                 "--n 20"):
        assert flag in dec, flag
    for off in (0, 20, 40, 60, 80, 100):
        assert f"--offset {off}" in dec


def test_each_replication_seed_is_used_only_by_its_own_blocks():
    """五顆 seed 沒有被**別人**用過。

    2026-09-11 發射前這支叫 `test_the_five_seeds_are_actually_unused_right_now`，
    釘的是「五顆 seed 在 runs/ 裡一次都沒出現過」——那是預註冊 §七-1 的事前證明，
    而它**只在發射前成立**。r1／r2／r3 於 2026-09-12 收官、summary 進了 runs/ 之後，
    原版永遠不可能再綠。

    ⚠ 那時候正確的動作**不是**把這支刪掉或改成 `xfail`：seed 的新鮮度仍然是
    R460R 唯一能證明「這三次是重新抽的」的東西。所以判準改成它真正想釘的那句——
    **每顆 seed 只准出現在它自己那六塊裡**（`REPLICATION_BLOCKS[k]`）：

      * 還沒跑的（本 checkout 是 r4／r5）⇒ 一次都不准出現，語意與舊版相同。
      * 跑過的（r1–r3）⇒ 只准出現在自己的六塊，被任何第三個 run 用到就是污染。

    這與排程器自己的掃描邏輯（`test_seed_scan_ignores_this_runs_own_thirty_blocks`）
    是同一條規則，只是這一支對**真的 runs/** 算，不是對 tmp_path 算。
    """
    import glob
    files = sorted(glob.glob(str(ROOT / "runs" / "*" / "summary.json")))
    assert files, "一個 runs/*/summary.json 都沒掃到——量不到不是通過"
    used: dict[str, list[str]] = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                used.setdefault(json.load(fh).get("seed"), []).append(
                    pathlib.Path(f).parent.name)
        except Exception:                                       # noqa: BLE001
            pass
    for k in range(1, 6):
        seen = sorted(used.get(REPLICATION_SEEDS[k], []))
        foreign = [n for n in seen if n not in REPLICATION_BLOCKS[k]]
        assert not foreign, (
            f"seed {REPLICATION_SEEDS[k]} 被不屬於第 {k} 次複製的 run 用了：{foreign}"
            "——那顆 seed 不再是乾淨的重新抽樣")
        # 跑過就要跑滿六塊；跑了一半代表有塊掉了，不該當成一次完整的複製。
        assert len(seen) in (0, len(REPLICATION_BLOCKS[k])), (
            f"seed {REPLICATION_SEEDS[k]} 只出現在 {len(seen)} 塊 "
            f"（應為 0 或 {len(REPLICATION_BLOCKS[k])}）：{seen}")


def test_seed_scan_passes_when_the_seed_is_unused(tmp_path):
    _write_run(tmp_path, "g_other", "some-other-seed")
    out = _run_scan(tmp_path, "g-r460r1-lcb2", "NONE", "")
    assert out.split()[1] == "OK", out


def test_seed_scan_catches_a_foreign_run_using_the_new_seed(tmp_path):
    """牙齒：別的 run 用了這顆 seed ⇒ MISMATCH（不管它叫什麼名字）。"""
    _write_run(tmp_path, "g_someone_else", "g-r460r1-lcb2")
    out = _run_scan(tmp_path, "g-r460r1-lcb2", "NONE", "")
    assert out.split()[1] == "MISMATCH", out


def test_seed_scan_ignores_this_runs_own_thirty_blocks(tmp_path):
    """分批發射的機械後果：自己那 30 塊寫了 summary 之後不准把自己擋掉。"""
    own = " ".join(f"runs/{n}" for k in range(1, 6) for n in REPLICATION_BLOCKS[k])
    _write_run(tmp_path, REPLICATION_BLOCKS[1][0], "g-r460r1-lcb2")
    out = _run_scan(tmp_path, "g-r460r1-lcb2", "NONE", own)
    assert out.split()[1] == "OK", out
    # 但排除清單之外的 run 照樣擋
    _write_run(tmp_path, "g_not_ours", "g-r460r1-lcb2")
    assert _run_scan(tmp_path, "g-r460r1-lcb2", "NONE", own).split()[1] == "MISMATCH"


def test_seed_scan_excluding_r447_is_a_provable_noop(tmp_path):
    """R4 指名把 r447 放進排除清單；對這五顆 seed 它是可證明的 no-op。"""
    _write_run(tmp_path, "g_r447_conform_lcb2", "g-r440-lcb2")
    with_r447 = _run_scan(tmp_path, "g-r460r1-lcb2", "NONE",
                          "runs/g_r447_conform_lcb2")
    without = _run_scan(tmp_path, "g-r460r1-lcb2", "NONE", "")
    assert with_r447.split()[1] == without.split()[1] == "OK"


# ══ 六、V/GT 稽核 v2（Fable R5）══════════════════════════════════════════
@pytest.fixture(scope="module")
def lcb_tasks():
    from ops.gain.gain_run import load_tasks
    try:
        return {t["task_id"]: t for t in load_tasks("lcb2", "g-r440-lcb2", 0)}
    except (FileNotFoundError, ValueError) as exc:              # pragma: no cover
        pytest.skip(f"LCB v2 題庫不在本機：{exc}")


def _r460_run(block: str) -> pathlib.Path:
    d = ROOT / "runs" / f"g_r460_harness_lcb2_{block}"
    if not (d / "calls.jsonl").exists():
        pytest.skip(f"本機沒有 R460 的 {block} 資料")
    return d


V1_EXPECTED = {"a1": 1, "a2": 5, "a3": 1, "b1": 31, "b2": 2, "b3": 50}


@pytest.mark.parametrize("block", R460_BLOCKS)
def test_audit_v2_is_clean_on_every_r460_block(block, lcb_tasks):
    """R5 的主要驗收：90 筆已知偽陽性在 v2 之下必須一筆不剩。"""
    from ops.gain.harness_vgt_audit import audit_run
    r = audit_run(_r460_run(block), lcb_tasks, scope="v2")
    assert r["verdict"] == "CLEAN", r["violations"][:3]


@pytest.mark.parametrize("block", R460_BLOCKS)
def test_audit_v1_still_reproduces_the_recorded_ninety(block, lcb_tasks):
    """v1 沒有被刪掉：R460 收官那 90 筆逐塊仍然重跑得出來。"""
    from ops.gain.harness_vgt_audit import audit_run
    r = audit_run(_r460_run(block), lcb_tasks, scope="v1")
    assert len(r["violations"]) == V1_EXPECTED[block]


#: §五-3 那張表逐格（round460r-2 之後多一欄：`got=` 沙箱回聲由機器自己吐）。
V2_EXCUSED_BY_RULE = {
    "a1": {"visible_check_source": 0, "model_own_selftest_same_request": 0,
           "got_sandbox_echo": 0},
    "a2": {"visible_check_source": 0, "model_own_selftest_same_request": 0,
           "got_sandbox_echo": 0},
    "a3": {"visible_check_source": 0, "model_own_selftest_same_request": 0,
           "got_sandbox_echo": 0},
    "b1": {"visible_check_source": 4, "model_own_selftest_same_request": 12,
           "got_sandbox_echo": 1},
    "b2": {"visible_check_source": 0, "model_own_selftest_same_request": 2,
           "got_sandbox_echo": 0},
    "b3": {"visible_check_source": 0, "model_own_selftest_same_request": 0,
           "got_sandbox_echo": 0},
}


def test_recorded_audit_v2_evidence_matches_a_fresh_run(lcb_tasks):
    """落盤的事前量具驗證與現在重跑的結果一致（§五-3 那張表）。"""
    from ops.gain.harness_vgt_audit import audit_run
    total_v1 = total_v2 = 0
    by_rule: dict[str, int] = {}
    for b in R460_BLOCKS:
        saved = json.loads(
            (ROOT / "ops" / "gain" / "replay" / "r460" / f"vgt_v2_{b}.json")
            .read_text(encoding="utf-8"))
        fresh = audit_run(_r460_run(b), lcb_tasks, scope="v2")
        assert saved["verdict"] == fresh["verdict"] == "CLEAN"
        assert saved["excused_n"] == fresh["excused_n"]
        # round460r-2：豁免要**逐條**對得上，不是只對一個總數——
        # 「豁免了什麼」跟「違規了什麼」一樣是稽核證據。
        assert saved["excused_by_rule"] == fresh["excused_by_rule"] \
            == V2_EXCUSED_BY_RULE[b], (b, fresh["excused_by_rule"])
        for k, v in fresh["excused_by_rule"].items():
            by_rule[k] = by_rule.get(k, 0) + v
        total_v2 += len(fresh["violations"])
        total_v1 += V1_EXPECTED[b]
    assert (total_v1, total_v2) == (90, 0)
    # §五-3 的對帳表：SELFTEST 14、可見驗收碼 4、`got=` 沙箱回聲 1。
    assert by_rule == {"visible_check_source": 4,
                       "model_own_selftest_same_request": 14,
                       "got_sandbox_echo": 1}, by_rule


def _calls(tmp_path, records):
    (tmp_path / "calls.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8")
    return tmp_path


@pytest.fixture(scope="module")
def leak_task(lcb_tasks):
    from ops.gain.harness_vgt_audit import hidden_only_needles
    t = lcb_tasks["lcb_3634"]
    needles, _ = hidden_only_needles(t)
    assert needles, "這題一個 needle 都不剩 ⇒ 負控沒有對象"
    return t, needles[0]


def test_v2_still_catches_a_hidden_repr_planted_in_a_feedback_message(
        leak_task, tmp_path):
    """負控 1：harness 自己寫的 user 訊息裡出現隱藏 repr ⇒ VIOLATION。"""
    from ops.gain.harness_arms import FEEDBACK_TEMPLATE
    from ops.gain.harness_vgt_audit import audit_run
    task, needle = leak_task
    msg = FEEDBACK_TEMPLATE.format(
        block=f"AssertionError: args=[1] got=[2] want={needle}")
    rec = [{"meta": {"arm": "HMIX", "task_id": task["task_id"]}, "system": "s",
            "messages": [{"role": "user", "content": msg}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "VIOLATION"
    assert r["violations"][0]["rule"] == "hidden_case_leak"


def test_v2_still_catches_a_hidden_repr_in_the_system_prompt(leak_task, tmp_path):
    """負控 2：system 訊息一格豁免都不給。"""
    from ops.gain.harness_vgt_audit import audit_run
    task, needle = leak_task
    rec = [{"meta": {"arm": "HPI", "task_id": task["task_id"]},
            "system": f"you are a coder. remember {needle}",
            "messages": [{"role": "user", "content": "hi"}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "VIOLATION"
    assert r["violations"][0]["role"] == "system"


def test_v2_redacts_got_but_not_want_or_args(leak_task, tmp_path):
    """`got=` 是沙箱回聲 ⇒ 扣掉；`want=`／`args=` 照查。兩邊都要驗。"""
    from ops.gain.harness_vgt_audit import audit_run
    task, needle = leak_task
    ok = [{"meta": {"arm": "HPI", "task_id": task["task_id"]}, "system": "s",
           "messages": [{"role": "user", "content":
                         f"AssertionError: args=[1] got={needle} want=[9]"}]}]
    bad = [{"meta": {"arm": "HPI", "task_id": task["task_id"]}, "system": "s",
            "messages": [{"role": "user", "content":
                          f"AssertionError: args={needle} got=[2] want=[9]"}]}]
    a = audit_run(_calls(_mk(tmp_path, "ok"), ok),
                  {task["task_id"]: task}, scope="v2")
    b = audit_run(_calls(_mk(tmp_path, "bad"), bad),
                  {task["task_id"]: task}, scope="v2")
    assert a["verdict"] == "CLEAN", a["violations"][:2]
    assert b["verdict"] == "VIOLATION"


def _mk(tmp_path, name) -> pathlib.Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_v2_records_the_got_excusal_instead_of_redacting_it_silently(
        leak_task, tmp_path):
    """round460r-2 must-fix 3：`got=` 是**留證的豁免**，不是靜音塗抹。

    v2 初版在掃描前把 `got=…` 整段換成佔位字串 ⇒ 那一筆連「被豁免過」都沒有
    紀錄，而 §五-3 的對帳表卻寫著「`got=` 沙箱回聲 1」——那個 1 是人工數的。
    現在它必須跟另外兩條豁免同一個形狀：進 `excused`、計入 `excused_by_rule`。
    """
    from ops.gain.harness_vgt_audit import GOT_ECHO_EXCUSE, audit_run
    task, needle = leak_task
    rec = [{"meta": {"arm": "HPI", "task_id": task["task_id"]}, "system": "s",
            "messages": [{"role": "user", "content":
                          f"AssertionError: args=[1] got={needle} want=[9]"}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "CLEAN", r["violations"][:2]
    assert r["excused_by_rule"][GOT_ECHO_EXCUSE] == 1, r["excused_by_rule"]
    assert [e["excused_as"] for e in r["excused"]] == [GOT_ECHO_EXCUSE]


def test_v2_got_does_not_launder_a_code_needle_on_the_same_line(
        lcb_tasks, tmp_path):
    """round460r-2 must-fix 2：`CODE_NEEDLES` 不吃 `got=` 那一格。

    `got=` 的合法性論證逐字是「那一段是 `repr(候選函式(*可見測資的 args))`」
    ——它撐得住**值層級**的 repr，撐不住 `__tests` 這種**識別字**
    （`__tests` 不是任何函式的回傳值）。所以同一行的
    `got=x __tests = […]` 必須是紅的：把驗收碼原始碼藏在 `got=` 後面
    不准變成通過。
    """
    from ops.gain.harness_vgt_audit import audit_run
    task = lcb_tasks["lcb_3634"]
    rec = [{"meta": {"arm": "HMIX", "task_id": task["task_id"]}, "system": "s",
            "messages": [{"role": "user", "content":
                          "hint: got=x __tests = [{'args': [1], 'expected': 2}]"}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "VIOLATION"
    v = [x for x in r["violations"] if x["rule"] == "check_code_identifier"]
    assert [x["needle"] for x in v] == ["__tests"], r["violations"]


def test_v2_system_message_gets_no_got_excuse_either(leak_task, tmp_path):
    """round460r-2 must-fix 1：「system 一格豁免都不給」——`got=` 也是一格豁免。

    v2 初版的 `redact_harness_text` 不分角色 ⇒ system 裡的 `got=<隱藏 repr>`
    被塗掉，那句話在文件裡是對的、在程式碼裡不是。
    """
    from ops.gain.harness_vgt_audit import audit_run
    task, needle = leak_task
    rec = [{"meta": {"arm": "HPI", "task_id": task["task_id"]},
            "system": f"persona note. last sandbox line: got={needle}",
            "messages": [{"role": "user", "content": "hi"}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "VIOLATION"
    assert r["violations"][0]["role"] == "system"
    assert r["violations"][0]["rule"] == "hidden_case_leak"
    assert r["excused"] == [], r["excused"]


def test_v2_still_catches_check_code_source_pasted_into_a_user_message(
        lcb_tasks, tmp_path):
    """負控 3：CODE needle 不給 (c) 的豁免——驗收碼貼進 user 訊息永遠是紅的。"""
    from ops.gain.harness_vgt_audit import audit_run
    task = lcb_tasks["lcb_3634"]
    rec = [{"meta": {"arm": "HOC", "task_id": task["task_id"]}, "system": "s",
            "messages": [{"role": "user",
                          "content": task["visible_check"]["code"]}]}]
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "VIOLATION"
    assert "check_code_identifier" in {v["rule"] for v in r["violations"]}


def test_v2_excuse_is_equality_not_substring(leak_task, tmp_path):
    """SELFTEST 豁免判的是**相等**：模型寫過一個大陣列不會順手豁免它的每一段。"""
    from ops.gain.harness_vgt_audit import model_selftest_reprs, needle_excuse
    task, _needle = leak_task
    reprs = model_selftest_reprs(["SELFTEST: [[1, 2, 3]] -> 7"])
    assert needle_excuse("[1, 2, 3]", task, reprs) == "model_own_selftest_same_request"
    assert needle_excuse("[1, 2]", task, reprs) is None


def test_v2_flattened_wire_mode_restores_roles(lcb_tasks, tmp_path):
    """攤平模式下模型的回覆被包進一則 user 訊息——角色必須先還原再套 (b)。"""
    from ops.gain.harness_arms import flatten_messages
    from ops.gain.harness_vgt_audit import (audit_run, classify_texts,
                                            hidden_only_needles)
    task = lcb_tasks["lcb_3634"]
    needle = hidden_only_needles(task)[0][0]
    flat = flatten_messages([{"role": "user", "content": "write it"},
                             {"role": "assistant", "content": f"I tried {needle}"},
                             {"role": "user", "content": "fix it"}])
    rec = [{"meta": {"arm": "HPI", "task_id": task["task_id"]},
            "system": "s", "messages": flat}]
    roles = [r for r, _i, _t in classify_texts(rec[0])]
    assert "assistant" in roles
    r = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v2")
    assert r["verdict"] == "CLEAN", r["violations"][:2]
    # v1 會把同一段當成 harness 寫的 ⇒ 紅。兩個 scope 的差別要看得見。
    r1 = audit_run(_calls(tmp_path, rec), {task["task_id"]: task}, scope="v1")
    assert r1["verdict"] == "VIOLATION"


def test_trivial_needle_relaxation_is_unchanged():
    """v2 只改「查誰的文字」，沒有動 round460e 那張凍結表。"""
    from ops.gain.harness_vgt_audit import (MIN_NEEDLE_CHARS,
                                            TRIVIAL_NEEDLE_REPRS)
    assert MIN_NEEDLE_CHARS == 6
    assert TRIVIAL_NEEDLE_REPRS == frozenset({
        "True", "False", "None", "0", "1", "-1", "[]", "{}", "()", "''", '""'})


def test_decision_records_the_gauge_validation_before_any_data(dec: str):
    assert "90" in dec and "六塊全 CLEAN" in dec
    assert "immediately preceding" in dec          # 與 R5 原文的偏離要寫在明處
    for b in R460_BLOCKS:
        assert f"vgt_v2_{b}.json" in dec or "vgt_${sc}_${b}.json" in dec


# ══ 七、拓撲閘門與彙總分析 ═══════════════════════════════════════════════
def test_analyzer_selftest_and_mutation_check_pass():
    for flag in ("--selftest", "--mutation-check"):
        r = subprocess.run([sys.executable, "ops/gain/analyze_r460.py", flag],
                           capture_output=True, text=True, cwd=str(ROOT))
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS" in r.stdout


def test_aggregate_selftest_reproduces_the_r460_numbers():
    r = subprocess.run([sys.executable, "ops/gain/analyze_r460r.py", "--selftest"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_aggregate_never_pools_n_across_replications():
    from ops.gain.analyze_r460r import aggregate
    row = {"rep": 1, "status": "ANALYZED", "verdict": "EFFECTIVE",
           "delta_c_pp": 13.33, "ci95_lo_pp": 4.2, "ci95_hi_pp": 19.5,
           "p_adj": 0.011, "holm_significant": True, "n_common": 120,
           "predictions": {k: True for k in
                           ("P-R1", "P-R2", "P-R3", "P-R4", "P-R5")}}
    ag = aggregate([dict(row, rep=k) for k in range(1, 6)])
    assert "n_common" not in ag and not any(k.startswith("pooled") for k in ag)
    assert ag["delta_c_pp_by_rep"] == {k: 13.33 for k in range(1, 6)}
    assert "複製穩定" in ag["statement"]


def test_statement_rule_needs_four_of_five_significant():
    from ops.gain.analyze_r460r import aggregate
    base = {"status": "ANALYZED", "verdict": "EFFECTIVE", "delta_c_pp": 11.0,
            "ci95_lo_pp": 1.0, "ci95_hi_pp": 20.0, "p_adj": 0.01,
            "holm_significant": True,
            "predictions": {k: True for k in
                            ("P-R1", "P-R2", "P-R3", "P-R4", "P-R5")}}
    rows = [dict(base, rep=k) for k in range(1, 6)]
    rows[0] = dict(rows[0], holm_significant=False)
    assert "複製穩定" in aggregate(rows)["statement"]        # 4/5 ⇒ 成立
    rows[1] = dict(rows[1], holm_significant=False)
    assert "逐次照實列" in aggregate(rows)["statement"]      # 3/5 ⇒ 不成立


def test_aggregate_prints_the_power_and_winners_curse_expectations():
    from ops.gain.analyze_r460r import aggregate
    ag = aggregate([])
    assert "0.43" in ag["power_expectation"] and "2–3" in ag["power_expectation"]
    assert "上偏" in ag["winners_curse_disclaimer"]
    assert "不得併 n" in ag["no_pooling"]
    assert "區間未做多重比較調整" in ag["ci_note"]


def test_ph0_is_not_judged_for_a_replication():
    """新 seed ⇒ r447 的錨不存在 ⇒ 不判，而不是拿別的 60 題硬讀。"""
    from ops.gain.analyze_r460 import (_fixture_blocks_scheduled,
                                       _pooled_scheduled, analyze,
                                       merge_summaries)
    blocks = _fixture_blocks_scheduled()
    rows = [r for b in blocks for r in b["rows"]]
    calls = [c for b in blocks for c in b["calls"]]
    out = analyze(rows, merge_summaries([b["summary"] for b in blocks]), calls,
                  blocks=blocks, topology_mode="scheduled", ph0_blocks=None)
    assert out["prereg"]["P-H0"]["hit"] == "NOT_APPLICABLE"
    assert out["prereg"]["P-H0"]["value"] is None
    # 預設（R460 的讀法）沒有被改掉：同一批資料、不給 ph0_blocks=None ⇒ 照判
    assert _pooled_scheduled(blocks)["prereg"]["P-H0"]["hit"] in ("HIT", "MISS")


def test_scheduled_topology_records_the_mapping_and_caps():
    from ops.gain.analyze_r460 import (_fixture_blocks_scheduled,
                                       _pooled_scheduled)
    out = _pooled_scheduled(_fixture_blocks_scheduled())
    topo = out["topology"]
    assert out["broken_reasons"] == []
    assert topo["variant"] == "scheduled"
    assert len(topo["endpoint_of_block"]) == 6
    assert topo["max_concurrent_by_endpoint"] == {ENDPOINT_1004: 3,
                                                  ENDPOINT_1003: 1}
    assert topo["endpoint_caps"] == dict(ENDPOINT_CONCURRENCY_CAPS)
    assert topo["task_ids_union"] == 120


@pytest.mark.parametrize("kw,marker", [
    ({"overload_1003": True}, "endpoint_concurrency_exceeded"),
    ({"unregistered": True}, "endpoint_not_registered"),
    ({"no_ts": True}, "block_ts_unrecorded"),
])
def test_scheduled_topology_violations_are_broken_reasons(kw, marker):
    from ops.gain.analyze_r460 import (_fixture_blocks_scheduled,
                                       _pooled_scheduled)
    out = _pooled_scheduled(_fixture_blocks_scheduled(**kw))
    assert any(s.startswith(marker) for s in out["broken_reasons"]), \
        out["broken_reasons"]


# ══ 六-2、跨複製的逐端點併發對帳（round460r-2、§六-11）══════════════════
def _gb(name, rep, ep, lo, hi):
    return {"name": name, "rep": rep, "endpoints": [ep],
            "calls": [{"ts_ms": lo, "latency_ms": 0},
                      {"ts_ms": hi, "latency_ms": 0}]}


def test_global_sweep_is_clean_at_the_cap():
    from ops.gain.analyze_r460r import global_concurrency
    g = global_concurrency([_gb(f"b{i}", 1, ENDPOINT_1004, 0, 100)
                            for i in range(3)])
    assert g["violations"] == []
    assert g["max_concurrent_by_endpoint"] == {ENDPOINT_1004: 3}
    assert g["caps"] == dict(ENDPOINT_CONCURRENCY_CAPS)


def test_global_sweep_catches_a_fourth_block_from_another_replication():
    """逐次的帳看不到它：r1 六塊全綠、r2 六塊全綠，但兩次之間重疊了。

    這正是本欄存在的理由——排程器的槽位是**跨複製**共用的
    （r1 的最後一塊還在跑時 r2 的第一塊就發出去了）。
    """
    from ops.gain.analyze_r460r import global_concurrency
    r1 = [_gb(f"r1_{i}", 1, ENDPOINT_1004, 0, 100) for i in range(3)]
    r2 = [_gb("r2_0", 2, ENDPOINT_1004, 50, 200)]
    # 各自看都不超賣
    assert global_concurrency(r1)["violations"] == []
    assert global_concurrency(r2)["violations"] == []
    g = global_concurrency(r1 + r2)
    assert any(s.startswith("endpoint_concurrency_exceeded_global")
               for s in g["violations"]), g["violations"]
    assert g["max_concurrent_by_endpoint"][ENDPOINT_1004] == 4
    assert g["reps_covered"] == [1, 2]
    # 違規要指得出人，不是只報一個數字
    w = g["peak_witness"][ENDPOINT_1004]
    assert w["n"] == 4 and sorted(w["blocks"]) == sorted(
        ["r1_0", "r1_1", "r1_2", "r2_0"])


def test_global_sweep_uses_the_same_frozen_caps_as_the_per_rep_report():
    from ops.gain.analyze_r460r import global_concurrency
    # 1003 的上限是 1：兩塊重疊就紅（哪怕來自同一次複製）。
    g = global_concurrency([_gb("x", 1, ENDPOINT_1003, 0, 10),
                            _gb("y", 1, ENDPOINT_1003, 5, 20)])
    assert any("endpoint_concurrency_exceeded_global" in s
               for s in g["violations"]), g["violations"]


@pytest.mark.parametrize("blocks,marker", [
    ([{"name": "u", "rep": 1, "endpoints": ["http://10.0.0.9:1234/v1/chat/completions"],
       "calls": [{"ts_ms": 1, "latency_ms": 0}]}], "endpoint_not_registered"),
    ([{"name": "z", "rep": 1, "endpoints": [ENDPOINT_1004], "calls": []}],
     "block_ts_unrecorded"),
])
def test_global_sweep_fails_closed(blocks, marker):
    """沒登記上限 ≠ 沒有上限；算不出時間窗 ≠ 通過。"""
    from ops.gain.analyze_r460r import global_concurrency
    g = global_concurrency(blocks)
    assert any(s.startswith(marker) for s in g["violations"]), g["violations"]


def test_global_sweep_violations_make_the_cli_exit_nonzero():
    """跨複製併發違規與逐次的 broken_reasons 同級——退出碼要變。"""
    src = (ROOT / "ops" / "gain" / "analyze_r460r.py").read_text(encoding="utf-8")
    assert 'out["global_topology"] or {}).get("violations")' in src
    assert "global_topology" in src


def test_fixed_topology_is_unchanged_by_the_new_variant():
    from ops.gain.analyze_r460 import _fixture_blocks, _pooled
    out = _pooled(_fixture_blocks())
    assert out["topology"]["variant"] == "two_backends_3_3"
    assert out["topology"]["mode"] == "fixed"
    assert out["broken_reasons"] == []


def test_decision_registers_the_scheduled_topology_invariants(dec: str):
    for needle in ("scheduled", "1004 ≤ 3", "1003 ≤ 1",
                   "endpoint_not_registered", "block_ts_unrecorded",
                   "topology.endpoint_of_block"):
        assert needle in dec, needle


def test_decision_records_the_humans_2026_09_11_amendment_before_any_data(dec: str):
    """人類的兩條指示要寫成**事前修訂**，而且要說清楚它沒有動任何判準。"""
    assert "## 一〇、2026-09-11 人類指示的**事前修訂**" in dec
    for needle in ("--reps 1 2 3 --hosts 1004",
                   "1003 這一輪完全停用",
                   "先跑 r1／r2／r3；r4／r5 暫不排隊",
                   "r4／r5 仍然是預註冊過的**",
                   "本節沒有動任何門檻、家族、分母、區間、四狀態、宣稱規則或預測窗"):
        assert needle in dec, needle
    # 「先跑三次」不等於「跑三次就結算」——§二-3 第 6 條照舊。
    assert "這不是「跑到三次就結算」的授權" in dec
    assert "不准**只跑完三次就結算" in dec           # §二-3 原文沒被改掉
    # 五顆 seed、30 個名字、五行授權一個都沒被刪
    for k in range(1, 6):
        assert f"SEED_AUTHORIZED_SET: g-r460r{k}-lcb2 <- NONE" in dec
        for t in R460_BLOCKS:
            assert f"runs/g_r460r{k}_harness_lcb2_{t}" in dec


def test_decision_registers_the_round460r2_boundaries(dec: str):
    """§六 的三條新誠實邊界（單一後端／跨複製併發／預檢失敗計次）。"""
    for needle in ("endpoint_concurrency_exceeded_global",
                   "global_topology",
                   "peak_witness",
                   "runs/_aborted/<name>_preflight_<ts>/",
                   "這一輪全部塊都在同一顆後端上（1004）",
                   "跨複製的逐端點併發要另外對帳一次",
                   "發不出去也是一次嘗試"):
        assert needle in dec, needle
    # 放寬計數面、收緊重試面——上限本身沒有變。
    assert "上限仍然是 2" in dec
    assert S.MAX_ATTEMPTS == 2


def test_decision_records_the_gauge_must_fixes(dec: str):
    """§五-1b：v2 初版的三處 must-fix 要逐條寫在文件裡，數字與實作對得上。"""
    assert "### 五-1b" in dec
    for needle in ("got_sandbox_echo", "excused_by_rule",
                   "藏在 `got=` 後面也一樣",
                   "`got=` 也是一格豁免 ⇒ system 連它都不吃"):
        assert needle in dec, needle
    # §五-3 的表多了 `got=` 那一欄，且逐格與落盤證據一致（由上面那條測試對釘）
    assert "v2 豁免（可見驗收碼／SELFTEST／`got=`）" in dec
    assert "| b1 | 31 | **0** | 4 ／ 12 ／ **1** |" in dec
    assert "| **合計** | **90** | **0（六塊全 CLEAN）** | 4 ／ 14 ／ **1** |" in dec


def test_decision_keeps_the_r460_thresholds_verbatim(dec: str):
    for needle in ("+25.0pp", "+10.0pp", "p_adj < 0.05", "CONFORM + 5.0pp",
                   "Holm 家族仍然是 6 個檢定", "不准併 n",
                   "winner's curse", "0.43–0.63"):
        assert needle in dec, needle
