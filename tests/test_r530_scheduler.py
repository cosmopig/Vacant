"""R530 排程器：佇列驗證、端點釘死、每台 ≤4 串、計畫是純函式。"""
from __future__ import annotations

import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import schedule_r530 as sch  # noqa: E402
from ops.gain.r530.run_r530 import registration_line as rl  # noqa: E402

EXAMPLE = ROOT / "ops" / "gain" / "r530" / "queues" / "r530_openwork_example.json"
EP1003 = sch.ENDPOINT_1003
EP1004 = sch.ENDPOINT_1004


def _raw() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write(tmp_path, raw) -> pathlib.Path:
    p = tmp_path / "q.json"
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return p


def test_example_queue_loads():
    q = sch.load_queue(EXAMPLE)
    assert len(q.blocks) == 2
    assert {b.endpoint for b in q.blocks} == {EP1003, EP1004}


def test_per_host_cap_is_checked_at_import():
    sch._assert_per_host_cap()
    bad = sch.R530_SLOTS + (sch.Slot("r1003#5", EP1003, "1003"),)
    with pytest.raises(SystemExit):
        sch._assert_per_host_cap(bad)


def test_duplicate_block_name_is_refused(tmp_path):
    raw = _raw()
    raw["blocks"][1]["name"] = raw["blocks"][0]["name"]
    with pytest.raises(SystemExit) as e:
        sch.load_queue(_write(tmp_path, raw))
    assert "重複的塊名" in str(e.value)


def test_duplicate_tag_is_refused(tmp_path):
    raw = _raw()
    raw["blocks"][1]["tag"] = raw["blocks"][0]["tag"]
    with pytest.raises(SystemExit) as e:
        sch.load_queue(_write(tmp_path, raw))
    assert "重複的 tag" in str(e.value)


def test_the_same_seed_task_pair_in_two_blocks_is_refused(tmp_path):
    """重複＝同一格被算兩次，而那長得跟「跑完了」一模一樣。"""
    raw = _raw()
    raw["blocks"][1]["tasks"] = raw["blocks"][0]["tasks"]
    with pytest.raises(SystemExit) as e:
        sch.load_queue(_write(tmp_path, raw))
    assert "同一格被算兩次" in str(e.value)


def test_all_blocks_on_one_host_is_refused(tmp_path):
    """「題在兩台輪流」沒兌現 ⇒ 後端與題號完全共線。"""
    raw = _raw()
    raw["blocks"][1]["endpoint"] = raw["blocks"][0]["endpoint"]
    with pytest.raises(SystemExit) as e:
        sch.load_queue(_write(tmp_path, raw))
    assert "abort_all_blocks_one_host" in str(e.value)


def test_unknown_key_is_refused(tmp_path):
    raw = _raw()
    raw["blocks"][0]["bank_filter"] = "difficulty=hard"
    with pytest.raises(SystemExit) as e:
        sch.load_queue(_write(tmp_path, raw))
    assert "認不得的欄位" in str(e.value)


def test_endpoint_must_be_declared_in_backends(tmp_path):
    raw = _raw()
    raw["blocks"][0]["endpoint"] = "http://127.0.0.1:9/v1/chat/completions"
    with pytest.raises(SystemExit):
        sch.load_queue(_write(tmp_path, raw))


def test_registration_line_matches_the_launcher_format():
    q = sch.load_queue(EXAMPLE)
    b = q.blocks[0]
    assert sch.registration_line(q, b) == rl(
        out=b.out, task_set=b.task_set, arms=q.arms, seed=b.seed,
        endpoint_url=b.endpoint)


def test_launch_argv_carries_every_experimental_condition():
    q = sch.load_queue(EXAMPLE)
    argv = sch.launch_argv(q, q.blocks[0])
    for flag in ("--out", "--decision", "--task-set", "--arms", "--seed",
                 "--backend", "--model", "--reasoning-effort",
                 "--request-timeout-s"):
        assert flag in argv, flag
    assert "--brain" not in argv, "正式發射不准帶 --brain（預設就是真後端）"
    assert "--smoke" not in argv


def test_plan_pins_each_block_to_its_own_endpoint():
    """三臂同一台是結構性的：塊擺不進自己那顆卡就等，不准挪到另一顆。"""
    q = sch.load_queue(EXAMPLE)
    statuses = {b.name: "PENDING" for b in q.blocks}
    plan = sch.plan_tick(q.blocks, statuses, {}, {})
    by_name = dict(plan["launch"])
    for b in q.blocks:
        assert by_name[b.name].endpoint == b.endpoint


def test_plan_waits_instead_of_moving_a_block_to_the_other_card():
    q = sch.load_queue(EXAMPLE)
    # 把 1003 的四格全佔滿（`busy` 的鍵是**槽**，值是塊名）
    busy = {s.slot_id: f"other{i}" for i, s in enumerate(sch.R530_SLOTS)
            if s.endpoint == EP1003}
    launch = sch.plan_launches_pinned(
        [b.name for b in q.blocks], busy, {b.name: b for b in q.blocks}, {},
        sch.R530_SLOTS)
    names = [n for n, _s in launch]
    assert "g_r530_ow_s1_odd" not in names, "1003 滿了就等，不准挪到 1004"
    assert "g_r530_ow_s1_even" in names


def test_plan_tick_does_not_touch_the_disk(tmp_path):
    q = sch.load_queue(EXAMPLE)
    before = sorted(p.name for p in tmp_path.iterdir())
    sch.plan_tick(q.blocks, {b.name: "PENDING" for b in q.blocks}, {}, {})
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_running_blocks_occupy_their_slot():
    q = sch.load_queue(EXAMPLE)
    statuses = {q.blocks[0].name: "RUNNING", q.blocks[1].name: "PENDING"}
    endpoints = {q.blocks[0].name: q.blocks[0].endpoint}
    plan = sch.plan_tick(q.blocks, statuses, endpoints, {})
    # `busy` ＝ {slot_id: block_name}
    assert q.blocks[0].name in plan["busy"].values()
    assert [n for n, _s in plan["launch"]] == [q.blocks[1].name]


def test_a_running_block_without_an_endpoint_blocks_everything():
    """擺不回槽 ⇒ 封鎖端點 ⇒ 這一輪一塊都不發（`occupancy` 的既有牙齒）。"""
    q = sch.load_queue(EXAMPLE)
    statuses = {q.blocks[0].name: "RUNNING", q.blocks[1].name: "PENDING"}
    plan = sch.plan_tick(q.blocks, statuses, {}, {})
    assert plan["blocked_endpoints"]
    assert plan["launch"] == []


def test_given_up_after_max_attempts():
    q = sch.load_queue(EXAMPLE)
    statuses = {b.name: "PENDING" for b in q.blocks}
    counts = {b.name: sch.MAX_ATTEMPTS for b in q.blocks}
    plan = sch.plan_tick(q.blocks, statuses, {}, counts)
    assert sorted(plan["given_up"]) == sorted(b.name for b in q.blocks)
    assert plan["launch"] == []


def test_check_prereg_reports_the_missing_lines(tmp_path):
    q = sch.load_queue(EXAMPLE)
    fake_root = tmp_path
    (fake_root / q.decision).write_text("nothing\n", encoding="utf-8")
    miss = sch.check_prereg(q, fake_root)
    assert len(miss) == len(q.blocks)
    (fake_root / q.decision).write_text(
        "\n".join(sch.registration_line(q, b) for b in q.blocks) + "\n",
        encoding="utf-8")
    assert sch.check_prereg(q, fake_root) == []


def test_slot_names_do_not_collide_with_the_other_two_schedulers():
    from ops.gain.schedule_harness_reps import SLOTS as REPS_SLOTS
    from ops.gain.schedule_queue import QUEUE_SLOTS
    ours = {s.slot_id for s in sch.R530_SLOTS}
    assert not (ours & {s.slot_id for s in REPS_SLOTS})
    assert not (ours & {s.slot_id for s in QUEUE_SLOTS})


def test_queue_copy_is_not_mutated_by_loading(tmp_path):
    raw = _raw()
    snapshot = copy.deepcopy(raw)
    sch.load_queue(_write(tmp_path, raw))
    assert raw == snapshot


# ── runner 存活偵測（2026-09-14 第一次正式發射的死因）────────────────────
def test_running_block_names_recognises_the_r530_runner(monkeypatch):
    """**沿用純函式要連它的「比對對象」一起看。**

    `schedule_harness_reps.running_block_names` 寫死比對 `gain_run.py --out `，
    認不得 `run_r530.py` ⇒ R530 的 runner 永遠被當成「不在」⇒ 每一塊在發射後的
    下一輪就被判 DEAD、作廢、重排，兩輪用完額度整批放棄。
    第一次正式發射就是這樣死的：8 塊全部起來了，60 秒後全被自己的排程器搬走。
    """
    import subprocess as sp

    ps_out = "\n".join([
        "  PID CMD",
        " 1001 python3 ops/gain/r530/run_r530.py --out runs/g_r530_s1_1003_1 "
        "--decision D.md --arms A-SOLO,A-CONF,A-GATE",
        " 1002 flock -n /home/u/.launch_r530_x.lock python3 "
        "ops/gain/r530/run_r530.py --out runs/g_r530_s1_1003_2",
        " 1003 python3 ops/gain/gain_run.py --out runs/g_r460_other",
        " 1004 grep run_r530.py --out runs/not_a_runner",
    ])
    monkeypatch.setattr(
        sch.subprocess, "run",
        lambda *a, **k: sp.CompletedProcess(a[0] if a else [], 0, ps_out, ""))
    alive = sch.running_block_names(pathlib.Path("."))
    assert "g_r530_s1_1003_1" in alive, "自己的 runner 要認得出來"
    assert "g_r530_s1_1003_2" not in alive, "flock 那一行要被 $2==python3 濾掉"
    assert "g_r460_other" not in alive, "別人的 runner 不是我的塊"
    assert "not_a_runner" not in alive, "grep 自己那一行不算"


def test_running_block_names_is_not_the_inherited_one():
    """釘死「不准再沿用那一份」——沿用回去會讓整批發射再死一次。"""
    from ops.gain import schedule_harness_reps as reps
    assert sch.running_block_names is not reps.running_block_names
    assert sch.RUNNER_SCRIPT_MARK == "run_r530.py --out "
    assert sch.RUNNER_SCRIPT_MARK in sch.LAUNCHER + " --out "


def test_a_live_block_is_not_judged_dead(monkeypatch):
    """端到端：runner 活著 ⇒ `observe` 要回 RUNNING，不是 DEAD。"""
    import subprocess as sp
    q = sch.load_queue(EXAMPLE)
    b = q.blocks[0]
    ps_out = (f"  PID CMD\n 2001 python3 ops/gain/r530/run_r530.py "
              f"--out runs/{b.name} --seed x")
    monkeypatch.setattr(
        sch.subprocess, "run",
        lambda *a, **k: sp.CompletedProcess(a[0] if a else [], 0, ps_out, ""))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / b.out).mkdir(parents=True)      # 有目錄、沒有 summary.json
        statuses, _eps = sch.observe(q.blocks, root)
        assert statuses[b.name] == "RUNNING", (
            "有目錄＋行程活著 ⇒ RUNNING。判成 DEAD 會讓排程器把跑著的塊搬走")


# ── summary 分類（2026-09-14 09:58:37Z 排程器猝死的死因）──────────────────
def _summary(processed=5, void=0, terminal=True, verdict="ok"):
    """R530 的 summary 形狀：`arms` 是 **list**、逐臂統計在 `arms_stats`。"""
    return {
        "arms": ["A-SOLO", "A-CONF", "A-GATE"],
        "arms_stats": {a: {"processed": processed, "infra_void": void}
                       for a in ("A-SOLO", "A-CONF", "A-GATE")},
        "run_terminal": terminal,
        "block_verdict": verdict,
    }


def test_inherited_classifier_would_crash_on_our_summary():
    """釘死**為什麼**不能沿用：它把 `arms` 當 dict，而我們的是 list。

    這一條不是在測別人的程式碼壞掉，是在測「我們知道它為什麼不能用」——
    哪天有人把 import 改回去，這裡會告訴他後果是什麼。
    """
    from ops.gain import schedule_harness_reps as reps
    with pytest.raises(AttributeError):
        reps.classify_summary(_summary())


def test_r530_classifier_reads_arms_stats():
    assert sch.classify_summary_r530(_summary())[0] == "DONE"
    assert sch.void_rates_r530(_summary(processed=5, void=0)) == {
        "A-SOLO": 0.0, "A-CONF": 0.0, "A-GATE": 0.0}


def test_r530_classifier_voids_a_block_over_the_void_rate():
    state, why = sch.classify_summary_r530(_summary(processed=5, void=2))
    assert state == "VOID" and "void_rate_over" in why


def test_r530_classifier_voids_a_block_e11_called_broken():
    """E-11 收官判 broken ⇒ 推論模式與登記的不同 ⇒ 資料不進分析。"""
    state, why = sch.classify_summary_r530(_summary(verdict="broken"))
    assert state == "VOID" and "block_verdict_broken" in why


def test_r530_classifier_never_calls_a_missing_summary_done():
    """量不到不是通過。"""
    assert sch.classify_summary_r530(None)[0] == "UNFINISHED"
    assert sch.classify_summary_r530(_summary(terminal=False))[0] == "UNFINISHED"


def test_block_state_r530_covers_the_four_states():
    assert sch.block_state_r530(False, None, False)[0] == "PENDING"
    assert sch.block_state_r530(True, None, True)[0] == "RUNNING"
    assert sch.block_state_r530(True, _summary(), False)[0] == "DONE"
    # 有目錄、行程不在、又不是 terminal ⇒ 死在半路
    assert sch.block_state_r530(True, _summary(terminal=False), False)[0] == "DEAD"


def test_observe_survives_a_finished_block(tmp_path):
    """端到端：一塊寫出 summary.json 之後 `observe()` **不准炸**。

    2026-09-14 就是在這裡死的：排程器安靜跑了三個半小時，第一塊完成的那一刻
    `AttributeError` 整個死掉，6 個 runner 還在跑、4 塊永遠不會被發出去。
    """
    q = sch.load_queue(EXAMPLE)
    b = q.blocks[0]
    d = tmp_path / b.out
    d.mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps(_summary()), encoding="utf-8")
    statuses, _eps = sch.observe(q.blocks, tmp_path)      # 不准丟例外
    assert statuses[b.name] == "DONE"
