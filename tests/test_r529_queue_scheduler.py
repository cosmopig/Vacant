"""`ops/gain/schedule_queue.py` ＋ R529 佇列的釘樁測試（Fable 2026-09-11 裁決第 6 點）。

這支在架構裡承重什麼：佇列排程器**不會噴錯**地跑錯——塞錯一個 offset、
把兩塊寫成同名、或是把佇列改了卻沒改預註冊，它都會照樣把塊發出去，
而發出去的東西長得跟發對了一模一樣。所以每一種壞法都要有一條紅線。

釘六組：
  1. 佇列 JSON 的 fail-closed（缺鍵／多鍵／重名／重 tag／區間重疊／n≤0）
  2. **註冊行**：佇列裡每一塊都要逐字寫在 DECISION 裡，而且 shell 發射器
     組出來的那一行必須與 Python 這一支**同格式**（兩份實作，一個格式）
  3. 擴槽條件：R460R 還在 ⇒ 不擴；`ps` 讀不到 ⇒ **也不擴**（fail closed）
  4. 乾跑不碰磁碟、不碰網路
  5. R529 佇列的算術（塊數／Σn／每集的題數）對得上**真的載進來的題庫**
  6. `--slots-after` 不准比 `--slots-now` 小、不准超過槽表
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.schedule_queue import (  # noqa: E402
    DEFAULT_SLOTS_AFTER, DEFAULT_SLOTS_NOW, ENDPOINT_1003, ENDPOINT_1004,
    PER_HOST_CAP, _assert_per_host_cap,
    QUEUE_SLOTS, QBlock, check_prereg, dry_run, effective_slots, load_queue,
    main, plan_launches_queue, r460r_presence, registration_line,
)

QUEUE_PATH = ROOT / "ops" / "gain" / "queues" / "r529_cross_bank.json"
LAUNCHER = ROOT / "ops" / "gain" / "launch_r529_block.sh"

_BACKENDS = {
    ENDPOINT_1003: {"host": "1003", "lmstudio_version": "0.4.24.0",
                    "version_source": "claim"},
    ENDPOINT_1004: {"host": "1004", "lmstudio_version": "0.4.17.0",
                    "version_source": "claim"},
}

_MIN = {
    "name": "t", "decision": "DECISION_20260911_R529_CROSS_BANK_PREREG.md",
    "launcher": "ops/gain/launch_r529_block.sh", "arms": "OFF,CONFORM,HMIX",
    "request_timeout_s": 900, "review_timeout_s": 380,
    "gauge_scope": "bank", "models": "m", "backends": _BACKENDS,
    "blocks": [
        {"name": "g_t_a1", "bank": "lcb3", "n": 20, "offset": 0,
         "seed": "s", "tag": "t1", "bank_filter": "difficulty=hard"},
        {"name": "g_t_a2", "bank": "lcb3", "n": 20, "offset": 20,
         "seed": "s", "tag": "t2", "bank_filter": "difficulty=hard"},
    ],
}


def _write(tmp_path: pathlib.Path, obj) -> str:
    p = tmp_path / "q.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


# ── 1. 佇列 JSON 的 fail-closed ────────────────────────────────────────────
def test_minimal_queue_loads(tmp_path):
    q = load_queue(_write(tmp_path, _MIN))
    assert len(q.blocks) == 2 and q.request_timeout_s == 900
    assert q.all_outs == ("runs/g_t_a1", "runs/g_t_a2")


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.pop("arms"), "缺欄位"),
    (lambda d: d.update(surprise=1), "認不得的欄位"),
    (lambda d: d.update(blocks=[]), "blocks 是空的"),
    (lambda d: d["blocks"][1].update(name="g_t_a1"), "重複的塊名"),
    (lambda d: d["blocks"][1].update(tag="t1"), "重複的 tag"),
    (lambda d: d["blocks"][1].update(offset=10), "重疊"),
    (lambda d: d["blocks"][0].update(n=0), "n 要 > 0"),
    (lambda d: d["blocks"][0].update(offset=-1), "offset 不能是負的"),
    (lambda d: d["blocks"][0].update(nickname="x"), "認不得的欄位"),
    (lambda d: d["blocks"][0].pop("seed"), "缺欄位"),
    (lambda d: d["blocks"][0].update(n="20"), "型別錯"),
    (lambda d: d.update(request_timeout_s=0), "request_timeout_s"),
    (lambda d: d.update(backends={}), "backends"),
    (lambda d: d["backends"].pop(ENDPOINT_1003), "端點集合與槽表對不上"),
    (lambda d: d["backends"][ENDPOINT_1004].pop("lmstudio_version"), "缺"),
])
def test_bad_queues_stop_instead_of_quietly_running(tmp_path, mutate, needle):
    d = json.loads(json.dumps(_MIN))
    mutate(d)
    with pytest.raises(SystemExit) as e:
        load_queue(_write(tmp_path, d))
    assert needle in str(e.value)


def test_missing_and_malformed_files_stop(tmp_path):
    with pytest.raises(SystemExit, match="不存在"):
        load_queue(tmp_path / "nope.json")
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit, match="合法 JSON"):
        load_queue(p)


def test_same_offsets_in_different_strata_are_not_overlap(tmp_path):
    """lcb3-hard 的 offset 0 與 lcb3-medium 的 offset 0 是**不同的題**。"""
    d = json.loads(json.dumps(_MIN))
    d["blocks"][1].update(offset=0, bank_filter="difficulty=medium")
    assert len(load_queue(_write(tmp_path, d)).blocks) == 2


# ── 2. 註冊行：一個格式，兩份實作 ──────────────────────────────────────────
def test_registration_line_format():
    b = QBlock(name="g_x", bank="lcb3", n=20, offset=40, seed="s1", tag="t",
               bank_filter="difficulty=hard")
    assert registration_line(b) == (
        "R529_BLOCK: g_x bank=lcb3 filter=difficulty=hard n=20 offset=40 seed=s1")
    nofilter = QBlock(name="g_y", bank="evalplus", n=11, offset=360, seed="s2", tag="u")
    assert registration_line(nofilter) == (
        "R529_BLOCK: g_y bank=evalplus filter=- n=11 offset=360 seed=s2")


def test_shell_launcher_builds_the_same_registration_line():
    """發射器是第二份實作。兩邊的格式字串必須逐字對得上，否則每一塊都會被擋。"""
    sh = LAUNCHER.read_text(encoding="utf-8")
    assert ('REG_LINE="R529_BLOCK: $(basename "$OUT") bank=$BANK '
            'filter=$REG_FILTER n=$N_BLOCK offset=$OFFSET seed=$SEED"') in sh
    assert 'REG_FILTER="${BANK_FILTER:--}"' in sh
    assert 'grep -qF -- "$REG_LINE" "$DEC"' in sh


def test_every_queue_block_is_registered_in_the_decision():
    """佇列改了卻沒改預註冊 ⇒ 這一條紅。發射前排程器也會擋同一條。"""
    q = load_queue(QUEUE_PATH)
    assert check_prereg(q) == []


def test_check_prereg_catches_a_drifted_block(tmp_path):
    q = load_queue(QUEUE_PATH)
    tampered = q.blocks[0].__class__(**{**q.blocks[0].__dict__, "offset": 999})
    q2 = q.__class__(**{**q.__dict__, "blocks": (tampered,)})
    assert check_prereg(q2) == [registration_line(tampered)]


# ── 3. 擴槽條件（純函式；ps 的輸出從外面餵）────────────────────────────────
_SCHED = "  123 python3 ops/gain/schedule_harness_reps.py --reps 1 2 3 --hosts 1004"
_RUNNER = "  456 python3 ops/gain/gain_run.py --out runs/g_r460r1_harness_lcb2_a2 --n 20"
_OTHER = "  789 python3 ops/gain/gain_run.py --out runs/g_r529_lcb3m_a1 --n 20"


_ALL_DONE = (True, "r460r_all_blocks_terminal")
_NOT_DONE = (False, "r460r_blocks_not_done(13/18)")


@pytest.mark.parametrize("lines,still,n_slots", [
    ([_SCHED, _OTHER], True, 5),
    ([_RUNNER, _OTHER], True, 5),
    ([_SCHED, _RUNNER], True, 5),
    ([_OTHER], False, 8),
    ([], False, 8),
    (None, True, 5),          # ps 讀不到 ⇒ **不知道**不是「沒有」
])
def test_expand_only_when_r460r_is_really_gone(lines, still, n_slots):
    """現在＝1003×4 ＋ 1004 第 4 格（5 串）；R460R 真的收完才 ＋1004×3（8 串）。"""
    assert r460r_presence(lines)[0] is still
    slots, _why = effective_slots("r460r_done", DEFAULT_SLOTS_NOW,
                                  DEFAULT_SLOTS_AFTER, lines, blocks_done=_ALL_DONE)
    assert len(slots) == n_slots
    # R460R 還在的時候**一格 1004 都不准多開**（它佔 #1–#3）
    if n_slots == DEFAULT_SLOTS_NOW:
        assert sum(1 for s in slots if s.host == "1004") == 1
        assert sum(1 for s in slots if s.host == "1003") == 4
    # 任何一輪都不准讓同一張卡超過 4 串
    per = {}
    for s in slots:
        per[s.host] = per.get(s.host, 0) + 1
    assert max(per.values()) <= PER_HOST_CAP


def test_dead_scheduler_is_not_the_same_thing_as_a_finished_r460r():
    """2026-09-11 事故：排程器 07:23Z 猝死、三個 runner 還在跑、18 塊只做了 5 塊。

    那段空窗一旦 runner 也收完，「只看行程」就會判成「R460R 收完了」而擴到 4 槽；
    人一重啟 R460R 又開三串 ⇒ 1004 變 7 串。⇒ 兩個條件都要成立。
    """
    slots, why = effective_slots("r460r_done", 5, 8, [], blocks_done=_NOT_DONE)
    assert len(slots) == 5 and "blocks_not_done" in why
    # 連磁碟證據都拿不到 ⇒ 一樣不擴（不知道不是「沒有」）
    slots2, why2 = effective_slots("r460r_done", 5, 8, [], blocks_done=None)
    assert len(slots2) == 5 and "block_state_unknown" in why2
    # 人類另有判斷時的顯式出口
    assert len(effective_slots("now", 5, 8, [_SCHED], blocks_done=_NOT_DONE)[0]) == 8


def test_r460r_blocks_all_terminal_reads_the_disk(tmp_path):
    from ops.gain.schedule_queue import r460r_blocks_all_terminal
    ok, why = r460r_blocks_all_terminal(tmp_path)
    assert ok is False and "18" in why


def test_expand_when_now_and_never():
    assert len(effective_slots("now", 4, 7, [_SCHED], blocks_done=_ALL_DONE)[0]) == 7
    assert len(effective_slots("never", 5, 8, [], blocks_done=_ALL_DONE)[0]) == 5


def test_unknown_expand_condition_stops():
    with pytest.raises(SystemExit):
        effective_slots("whenever", 5, 8, [], blocks_done=_ALL_DONE)


def test_slot_table_order_and_hosts():
    """前四格＝現在就能用的（1003×3 ＋ 1004#4）；後三格＝R460R 收完才加的 1004。"""
    assert len(QUEUE_SLOTS) == DEFAULT_SLOTS_AFTER == 8
    assert DEFAULT_SLOTS_NOW == 5
    assert [s.slot_id for s in QUEUE_SLOTS] == [
        "q1003#1", "q1003#2", "q1003#3", "q1003#4", "q1004#4",
        "q1004#1", "q1004#2", "q1004#3"]
    # 每張卡不得超過 4 串（LM Studio parallel=4；6 串量到無收益）
    per = {}
    for s in QUEUE_SLOTS:
        per[s.host] = per.get(s.host, 0) + 1
    assert per == {"1003": 4, "1004": 4} and max(per.values()) <= PER_HOST_CAP
    assert [s.host for s in QUEUE_SLOTS[:DEFAULT_SLOTS_NOW]].count("1004") == 1
    assert {s.host for s in QUEUE_SLOTS[DEFAULT_SLOTS_NOW:]} == {"1004"}
    assert {s.endpoint for s in QUEUE_SLOTS} == {ENDPOINT_1003, ENDPOINT_1004}
    # **不准**與 R460R 現行實例的槽名相同——兩份 log 都印「槽 1004#1」的話，
    # 事後對帳分不出是誰在講話。
    from ops.gain.schedule_harness_reps import SLOTS as R460R_SLOTS
    assert not ({s.slot_id for s in QUEUE_SLOTS} & {s.slot_id for s in R460R_SLOTS})
    assert "8765" not in QUEUE_SLOTS[0].endpoint     # hub 禁止


# ── 4. 乾跑不碰磁碟 ───────────────────────────────────────────────────────
def test_dry_run_writes_nothing(tmp_path):
    q = load_queue(QUEUE_PATH)
    root = tmp_path / "fake_root"
    root.mkdir()
    out = dry_run(q, root, slots_now=5, slots_after=8, expand_when="r460r_done",
                  ps_lines=[_SCHED])
    assert "發射 g_r529_lcb3m_a1" in out
    assert "q1003#1" in out and "q1004#4" in out
    assert "LM Studio 0.4.24.0" in out and "LM Studio 0.4.17.0" in out
    assert list(root.iterdir()) == []


def test_dry_run_does_not_expand_on_an_empty_root(tmp_path):
    """行程不在、但磁碟上 18 塊一個都沒有 ⇒ **不擴**（排程器死了 ≠ R460R 跑完了）。"""
    q = load_queue(QUEUE_PATH)
    root = tmp_path / "fake_root"
    root.mkdir()
    out = dry_run(q, root, slots_now=5, slots_after=8, expand_when="r460r_done",
                  ps_lines=[])
    assert out.count("發射 g_r529_") == 5
    assert "blocks_not_done" in out


def test_dry_run_expands_when_all_18_r460r_blocks_are_terminal(tmp_path):
    import json as _json
    from ops.gain.schedule_harness_reps import build_queue
    q = load_queue(QUEUE_PATH)
    root = tmp_path / "fake_root"
    for b in build_queue((1, 2, 3)):
        d = root / b.out
        d.mkdir(parents=True)
        (d / "summary.json").write_text(_json.dumps(
            {"run_terminal": True,
             "arms": {"OFF": {"processed": 20, "infra_void": 0}}}), encoding="utf-8")
    out = dry_run(q, root, slots_now=5, slots_after=8, expand_when="r460r_done",
                  ps_lines=[])
    assert out.count("發射 g_r529_") == 8
    assert "r460r_all_blocks_terminal" in out


# ── 5. R529 佇列的算術對得上真的題庫 ───────────────────────────────────────
def test_r529_queue_arithmetic_matches_the_pinned_banks():
    from ops.gain.gain_run import load_tasks
    q = load_queue(QUEUE_PATH)
    assert q.arms == "OFF,CONFORM,HMIX"
    assert q.request_timeout_s == 900 and q.gauge_scope == "bank"
    want = {("lcb3", "difficulty=medium"): 135, ("lcb3", "difficulty=hard"): 54,
            ("humanevalplus", None): 156, ("evalplus", None): 371}
    got: dict[tuple[str, str | None], int] = {}
    for b in q.blocks:
        got[(b.bank, b.bank_filter)] = got.get((b.bank, b.bank_filter), 0) + b.n
    for key, n in want.items():
        if key[0] in ("evalplus", "humanevalplus") and not (
                ROOT / ".vacant-private" / "evalplus").exists():
            pytest.skip("官方包不在場——略過真題庫對帳")
        assert got[key] == n, key
        assert len(load_tasks(key[0], "queue-check", 0, bank_filter=key[1])) == n
    assert sum(b.n for b in q.blocks) == 716
    assert len(q.blocks) == 37
    # 每一集內部：offset 連續、無洞、無重疊
    for key in want:
        blocks = [b for b in q.blocks if (b.bank, b.bank_filter) == key]
        assert [b.offset for b in blocks] == [
            sum(x.n for x in blocks[:i]) for i in range(len(blocks))], key
        assert max(b.n for b in blocks) == 20


def test_block_names_are_unique_and_prefixed():
    q = load_queue(QUEUE_PATH)
    names = [b.name for b in q.blocks]
    assert len(set(names)) == len(names)
    assert all(n.startswith("g_r529_") for n in names)
    assert len({b.seed for b in q.blocks}) == 3


# ── 6. --slots-now / --slots-after 的界線 ──────────────────────────────────
@pytest.mark.parametrize("argv", [
    ["--slots-now", "0"], ["--slots-now", "9"],
    ["--slots-after", "0"], ["--slots-after", "9"],
    ["--slots-now", "6", "--slots-after", "5"],
])
def test_slot_bounds_are_enforced(argv):
    with pytest.raises(SystemExit):
        main(["--queue", str(QUEUE_PATH), "--dry-run", *argv])


def test_check_mode_passes_on_the_real_queue(capsys):
    assert main(["--queue", str(QUEUE_PATH), "--check"]) == 0
    assert "OK：37 塊" in capsys.readouterr().out


# ── 7. 重排要換一台（2026-09-11 人類指示第 4 點）───────────────────────────
_S = QUEUE_SLOTS[:DEFAULT_SLOTS_NOW]


def test_first_attempt_takes_the_first_free_slot():
    assert plan_launches_queue(["a"], {}, {}, {}, _S) == [("a", "q1003#1")]


def test_requeued_block_avoids_the_host_it_died_on():
    """在 1003 死過的塊，重排時要跳到 1004；不准回同一台再賭一次。"""
    got = plan_launches_queue(["a"], {}, {"a": 1}, {"a": ENDPOINT_1003}, _S)
    assert got == [("a", "q1004#4")]
    got2 = plan_launches_queue(["a"], {}, {"a": 1}, {"a": ENDPOINT_1004}, _S)
    assert got2 == [("a", "q1003#1")]


def test_requeued_block_is_skipped_rather_than_blocking_the_queue():
    """只剩它死過的那一台 ⇒ 這一輪跳過它、把槽讓給下一塊（不 head-of-line 卡住）。"""
    busy = {"q1003#1": "x", "q1003#2": "y", "q1003#3": "z", "q1003#4": "w"}
    got = plan_launches_queue(["a", "b"], busy, {"a": 1},   # 只剩 q1004#4
                              {"a": ENDPOINT_1004}, _S)
    assert got == [("b", "q1004#4")]


def test_first_attempt_is_not_constrained_by_a_stale_endpoint_record():
    got = plan_launches_queue(["a"], {}, {}, {"a": ENDPOINT_1003}, _S)
    assert got == [("a", "q1003#1")]       # attempts=0 ⇒ 不是重排，不避開


def test_queue_declares_both_backends_with_version_provenance():
    q = load_queue(QUEUE_PATH)
    assert set(q.backends) == {ENDPOINT_1003, ENDPOINT_1004}
    for ep, m in q.backends.items():
        assert m["lmstudio_version"] in ("0.4.24.0", "0.4.17.0")
        # 版本是**宣稱**不是量測——出處必須寫在資料裡，不是只寫在文件裡
        assert "lms version" in m["version_source"] or "回報" in m["version_source"]
        assert m["gguf_sha256"] == (
            "faff1a63667fac17ac5e777f47114688fcefea96e220e211aaa8d62c2c4561f1")
    assert {m["host"] for m in q.backends.values()} == {"1003", "1004"}


def test_launcher_records_backend_meta_per_block():
    sh = LAUNCHER.read_text(encoding="utf-8")
    assert '"$OUT.backend_meta.json"' in sh or "backend_meta.json" in sh
    assert "BACKEND_META" in sh and "SLOT_ID" in sh
    assert "version_source" in sh or "人回報" in sh


def test_per_host_cap_is_a_mechanism_not_a_discipline():
    """槽表多開一格在 log 上長得跟正常一模一樣 ⇒ import 時就擋。"""
    from ops.gain.schedule_queue import Slot
    _assert_per_host_cap()                      # 現行表合格
    too_many = QUEUE_SLOTS + (Slot("q1003#5", ENDPOINT_1003, "1003"),)
    with pytest.raises(SystemExit, match="上限"):
        _assert_per_host_cap(too_many)
    assert PER_HOST_CAP == 4


# ── 8. poll_loop 整合（注入假發射器，不碰後端、不碰真磁碟）──────────────────
def test_poll_loop_launches_exactly_the_free_slots_and_records_nothing_else(tmp_path):
    """一圈：5 個空槽 ⇒ 發 5 塊，順序照佇列，槽照 first-fit，且不寫任何檔案。"""
    from ops.gain.schedule_queue import poll_loop
    q = load_queue(QUEUE_PATH)
    root = tmp_path / "root"
    root.mkdir()
    launched: list[tuple[str, str]] = []
    logs: list[str] = []
    rc = poll_loop(q, root, logs.append, slots_now=DEFAULT_SLOTS_NOW,
                   slots_after=DEFAULT_SLOTS_AFTER, expand_when="r460r_done",
                   max_ticks=1,
                   launcher=lambda b, s: launched.append((b.name, s.slot_id)) or 0,
                   aborter=lambda n, w: pytest.fail(f"不該作廢 {n}"),
                   preflight_aborter=lambda n, rc_: pytest.fail("不該有 preflight 失敗"),
                   sleeper=lambda _s: None,
                   ps_reader=lambda: [_SCHED])
    assert rc == 0
    assert [n for n, _ in launched] == [b.name for b in q.blocks[:5]]
    assert [s for _, s in launched] == [
        "q1003#1", "q1003#2", "q1003#3", "q1003#4", "q1004#4"]
    assert list(root.iterdir()) == []       # 乾跑之外也不准偷寫東西


def test_poll_loop_counts_a_preflight_failure_as_an_attempt(tmp_path):
    """發射器 rc != 0（runner 根本沒起來）⇒ 走 preflight_aborter，不是默默重發。"""
    from ops.gain.schedule_queue import poll_loop
    q = load_queue(QUEUE_PATH)
    root = tmp_path / "root"
    root.mkdir()
    preflight: list[str] = []
    poll_loop(q, root, lambda _m: None, slots_now=1, slots_after=1,
              expand_when="never", max_ticks=1,
              launcher=lambda b, s: 7,
              aborter=lambda n, w: None,
              preflight_aborter=lambda n, rc_: preflight.append(f"{n}:{rc_}"),
              sleeper=lambda _s: None,
              ps_reader=lambda: [_SCHED])
    assert preflight == [f"{q.blocks[0].name}:7"]
