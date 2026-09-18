"""R530 正式佇列 `r530_main.json`：180 格的每一條結構約束都要可驗。

它不是一份設定檔，它是**實驗設計本身**：哪一題在哪一台、三臂會不會被拆開、
loose 那三題會不會整層擠在同一塊，全都決定於這份 JSON。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import make_main_queue as mk  # noqa: E402
from ops.gain.r530 import schedule_r530 as sch  # noqa: E402

MAIN = ROOT / "ops" / "gain" / "r530" / "queues" / "r530_main.json"


@pytest.fixture(scope="module")
def q():
    return sch.load_queue(MAIN)


def test_the_committed_file_matches_the_generator():
    """投影是單向的：手改 JSON 會在這裡被抓到。"""
    on_disk = json.loads(MAIN.read_text(encoding="utf-8"))
    assert on_disk == mk.build(), (
        "r530_main.json 與 make_main_queue.py 的產出對不上——"
        "這份 JSON 不准手改，改的是產生器")


def test_shape_is_180_cells(q):
    cells = sum(len(b.tasks) for b in q.blocks) * len(q.arms.split(","))
    assert len(q.blocks) == 12
    assert cells == 180, "20 題 × 3 臂 × 3 seed"
    assert sorted({b.seed for b in q.blocks}) == list(mk.SEEDS)
    assert q.arms == "A-SOLO,A-CONF,A-GATE"


def test_every_task_appears_once_per_seed(q):
    from collections import Counter
    for seed in mk.SEEDS:
        c = Counter(t for b in q.blocks if b.seed == seed for t in b.tasks)
        assert len(c) == 20 and set(c.values()) == {1}, (seed, c.most_common(3))


def test_each_task_uses_both_hosts_across_the_three_seeds(q):
    """「題在兩台輪流」的可驗版本。

    ⚠ 三顆 seed、兩台 ⇒ 每一題是 **2:1** 不是 1.5:1.5——奇數分不平。
      要的是「不與單一台完全共線」，不是「完全平衡」。
    """
    host_of = {s.endpoint: s.host for s in sch.R530_SLOTS}
    seen: dict[str, list[str]] = {}
    for b in q.blocks:
        for t in b.tasks:
            seen.setdefault(t, []).append(host_of[b.endpoint])
    assert len(seen) == 20
    for t, hosts in seen.items():
        assert len(hosts) == 3, t
        assert len(set(hosts)) == 2, f"{t} 三顆 seed 都在同一台 ⇒ 與後端共線"
        assert sorted(Counter_(hosts).values()) == [1, 2], (t, hosts)


def Counter_(xs):
    from collections import Counter
    return Counter(xs)


def test_the_three_arms_of_a_task_never_split_across_hosts(q):
    """一塊 ＝ 一個 endpoint ＋ 三臂全跑 ⇒ 結構上不可能拆開。"""
    assert all(b.endpoint for b in q.blocks)
    # 三臂是佇列層級的一個字串，不是塊層級的 ⇒ 沒有「這一塊只跑某一臂」這種狀態
    assert "," in q.arms and len(q.arms.split(",")) == 3


def test_loose_tasks_are_spread_not_bunched(q):
    strat = mk.strata()
    loose = {t for t, v in strat.items() if v == "loose"}
    assert len(loose) == 3
    blocks_with_loose = [b for b in q.blocks
                         if any(t in loose for t in b.tasks)]
    # 9 格 loose（3 題 × 3 seed）散在 ≥6 塊 ⇒ 一塊作廢不會讓 loose 整層不見
    assert len(blocks_with_loose) >= 6
    for b in q.blocks:
        n = sum(1 for t in b.tasks if t in loose)
        assert n <= 1, f"{b.name} 有 {n} 題 loose——擠在同一塊"


def test_per_host_load_is_balanced(q):
    host_of = {s.endpoint: s.host for s in sch.R530_SLOTS}
    per = {}
    for b in q.blocks:
        per[host_of[b.endpoint]] = per.get(host_of[b.endpoint], 0) + len(b.tasks)
    assert per == {"1003": 30, "1004": 30}


def test_launch_conditions_are_pinned_in_the_queue(q):
    assert q.gauge_scope == "bank", "E-3 是發射閘門"
    assert q.tool_protocol == "native"
    assert q.sandbox_uid == 65534 and q.sandbox_gid == 65534, "E-9 要降權"
    assert q.reasoning_effort == "none", "E-11"
    assert q.model == "gemma-4-12b-it-qat"
    assert q.backend == "unshare"
    # `decision` 是傳給 `--decision` 的**路徑**（2026-09-18 起 `decisions/...`），
    # 這裡釘的是「指到哪一份」⇒ 比 basename。
    assert pathlib.Path(q.decision).name.startswith("DECISION_20260913_R530")


def test_launch_argv_carries_the_three_gates(q):
    argv = sch.launch_argv(q, q.blocks[0])
    for flag, val in (("--gauge-scope", "bank"), ("--tool-protocol", "native"),
                      ("--sandbox-uid", "65534"), ("--sandbox-gid", "65534"),
                      ("--reasoning-effort", "none")):
        assert flag in argv and argv[argv.index(flag) + 1] == val, flag
    assert "--smoke" not in argv and "--brain" not in argv


def test_a_non_bank_gauge_scope_is_refused(tmp_path):
    raw = json.loads(MAIN.read_text(encoding="utf-8"))
    raw["gauge_scope"] = "none"
    p = tmp_path / "q.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        sch.load_queue(p)
    assert "gauge_scope" in str(e.value)


def test_all_twelve_blocks_fit_the_slot_table(q):
    statuses = {b.name: "PENDING" for b in q.blocks}
    plan = sch.plan_tick(q.blocks, statuses, {}, {})
    # 槽表 8 格 ⇒ 第一輪排得進 8 塊，其餘 4 塊等下一輪（不准挪台）
    assert len(plan["launch"]) == len(sch.R530_SLOTS) == 8
    host_of = {s.endpoint: s.host for s in sch.R530_SLOTS}
    by_name = {b.name: b for b in q.blocks}
    for name, slot in plan["launch"]:
        assert slot.host == host_of[by_name[name].endpoint], name


def test_scheduler_paths_do_not_collide_with_the_other_two(q):
    lock, log = sch.scheduler_lock_path(q.name), sch.scheduler_log_path(q.name)
    assert "r530" in lock.name and "r530" in log.name
    for other in ("schedule_harness_reps", "schedule_queue"):
        assert other not in lock.name and other not in log.name
