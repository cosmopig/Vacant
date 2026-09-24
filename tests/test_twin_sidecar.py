"""分身自己的旁註（`twin.sidecar/1`）→ 電視的 `postaudit`／`counters`。

2026-09-24 人類裁決「分身側自己記一份補回」：OFF 臂的事後稽核與整批累計**不是
Vacant 當場做的事**，所以不准進 lifecycle 契約（`vacant_network/vrun/*` 不動）。
這一組守的是：

  · 旁註契約與綁定（每一筆綁得上錄影裡的一跑 OFF：`run_id`＋`ws_end_sha256`）
  · `Folder` 只在綁得上時轉出 `postaudit`，而且**永遠不長得像裁決**（負控制）
  · `counters` 與**實際播過的格子**一致；不存在的層不發
  · 舊錄影（沒有旁註）照播，但畫面上**沒有** postaudit
  · 配對收據的 sha256 綁定涵蓋旁註（改一個位元組 ⇒ 擋下）

⚠ 零模型呼叫：`run_twin.py --fixture`（腳本化 agent，`requests_seen`＝0）。
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import pair_receipts as pairlib  # noqa: E402
from ops.exhibit.twin import run_twin  # noqa: E402
from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402


@pytest.fixture(scope="module")
def batch(tmp_path_factory) -> pathlib.Path:
    """1 位居民 × 2 題 × 兩份題面＝4 格；ON 用 revise。兩臂都跑 ⇒ 4 筆旁註。"""
    out = tmp_path_factory.mktemp("sidecar_batch")
    rc = run_twin.main(["--out", str(out), "--fixture", "--residents", "1",
                        "--tasks", "s1_01_addmul,s1_12_hms", "--sandbox", "none",
                        "--retry", "revise", "--max-attempts", "2",
                        "--events", str(out / "lifecycle.jsonl")])
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def lc(batch):
    return lifecycle.read(batch / "lifecycle.jsonl")


@pytest.fixture(scope="module")
def rows(batch):
    return sc.read(sc.sidecar_path(batch / "lifecycle.jsonl"))


@pytest.fixture(scope="module")
def paired(batch, tmp_path_factory) -> pathlib.Path:
    """`record_fixture.sh` 的形狀：`X.jsonl`＋`X.sidecar.jsonl`＋`X.pack.json`。"""
    d = tmp_path_factory.mktemp("sidecar_paired")
    rec = d / "fx.jsonl"
    rec.write_bytes((batch / "lifecycle.jsonl").read_bytes())
    sc.sidecar_path(rec).write_bytes(
        sc.sidecar_path(batch / "lifecycle.jsonl").read_bytes())
    pack = pairlib.build_pair(rec, batch)
    pairlib.pair_path(rec).write_text(pairlib.dumps(pack), encoding="utf-8")
    return rec


def _fold(lc, rows, mode=tv.MODE_REPLAY):
    return le.fold(sc.merge(lc, rows), verify_url="/r/{cell}", mode=mode)


def _mk(recs, tmp_path, **kw):
    kw.setdefault("dwell", 10_000)
    kw.setdefault("quiet", True)
    return S.make_server(recs, bind="127.0.0.1", port=0,
                         out=tmp_path / "events.jsonl", **kw)


def _events(stage) -> list[dict]:
    stage.flush()
    return [json.loads(x) for x in stage.out.read_text("utf-8").splitlines() if x.strip()]


# ── 一、旁註契約 ─────────────────────────────────────────────────
def test_lifecycle_file_stays_pure_vacant(batch, lc):
    """旁註**不在** lifecycle 檔裡：那一份仍然過 Vacant 自己的契約，一行分身的都沒有。"""
    assert lifecycle.validate_stream(lc) == []
    assert {e["schema"] for e in lc} == {lifecycle.SCHEMA}
    assert sc.SCHEMA not in (batch / "lifecycle.jsonl").read_text("utf-8")


def test_every_off_run_has_exactly_one_bound_postaudit(lc, rows):
    offs = {e["run_id"]: e for e in lc if e["type"] == "run_ended"
            and e["arm"] == "RUN-OFF" and not e.get("infra_void")}
    assert len(offs) == 4 and len(rows) == 4
    assert sc.validate(rows, lifecycle_events=lc) == []
    assert {r["run_id"] for r in rows} == set(offs)
    for r in rows:
        assert r["ws_end_sha256"] == offs[r["run_id"]]["ws_end_sha256"]
        assert r["ts_ms"] >= offs[r["run_id"]]["ts_ms"]            # 「事後」成立
        assert (r["when"], r["is_verdict"], r["signed"]) == (sc.WHEN_AFTER, False, False)
        for k in sc.CONTENT_KEYS:
            assert k not in r, k
    # 這一批兩種都有（不然「對得上」只驗了一半）
    assert {r["all_pass"] for r in rows} == {True, False}
    assert all(r["failed_case"] for r in rows if not r["all_pass"])


def test_failed_case_is_read_the_same_way_as_the_on_gate(lc, rows):
    """兩臂同一把尺、同一種讀法：held 格 ON 閘門的 failed_case ＝ OFF 事後稽核的。"""
    cell_of = {e["run_id"]: e["caller"]["cell_id"] for e in lc
               if e["type"] == "run_started"}
    gate_first = {}
    for e in lc:
        if e["type"] == "gate_ran" and e["attempt"] == 1:
            gate_first[cell_of[e["run_id"]]] = e["failed_case"]
    for r in rows:
        assert r["failed_case"] == gate_first[r["cell_id"]], r["cell_id"]


def test_when_constants_agree():
    assert sc.WHEN_AFTER == tv.WHEN_AFTER == "after_the_run"


@pytest.mark.parametrize("field,value", [
    ("is_verdict", True), ("signed", True), ("when", "during_the_run"),
    ("arm", "ON"), ("ws_end_sha256", "0" * 64), ("cell_id", "someone_else"),
    ("ts_ms", 0), ("all_pass", 1), ("passed", 99),
])
def test_sidecar_validate_has_teeth(lc, rows, field, value):
    """**負控制**：每一條規則各自抓得到它那一種壞法。"""
    broken = [dict(r) for r in rows]
    broken[0][field] = value
    assert sc.validate(broken, lifecycle_events=lc), field


def test_sidecar_validate_rejects_missing_flags_and_unbound_runs(lc, rows):
    for k in ("is_verdict", "signed", "when"):
        broken = [dict(r) for r in rows]
        broken[0].pop(k)
        assert sc.validate(broken), k
    on_run = next(e["run_id"] for e in lc if e["type"] == "run_started"
                  and e["arm"] == "RUN-ON")
    assert sc.validate([dict(rows[0], run_id=on_run)], lifecycle_events=lc)
    assert sc.validate([dict(rows[0], run_id="nope")], lifecycle_events=lc)
    assert sc.validate([rows[0], dict(rows[0])], lifecycle_events=lc)   # 一跑兩筆
    assert sc.validate([dict(rows[0], cases=[])])                        # 夾帶內容


# ── 二、Folder：只在綁得上時轉，永遠不長得像裁決 ─────────────────────
def test_folder_turns_each_sidecar_row_into_one_postaudit(lc, rows):
    evs = _fold(lc, rows)
    assert tv.validate(evs) == []
    pas = [e for e in evs if e["type"] == "postaudit"]
    assert len(pas) == len(rows)
    for e in pas:
        assert (e["when"], e["is_verdict"], e["signed"], e["arm"]) == \
            (tv.WHEN_AFTER, False, False, tv.ARM_OFF)
        # 它接在同一格 OFF 的 verdict 之後，不是裁決本身
        i = evs.index(e)
        prior = [x for x in evs[:i] if x["task_id"] == e["task_id"]
                 and x.get("arm") == tv.ARM_OFF and x["type"] == "verdict"]
        assert prior and prior[-1]["accepted"] is None


def test_lifecycle_alone_never_grows_a_postaudit(lc):
    assert not [e for e in le.fold(lc, verify_url="/r/{cell}") if e["type"] == "postaudit"]


def test_postaudit_without_is_verdict_false_is_red(lc, rows):
    """**負控制**（人類指定）：拿掉 `is_verdict:false` ⇒ 電視契約會紅。"""
    evs = _fold(lc, rows)
    i = next(i for i, e in enumerate(evs) if e["type"] == "postaudit")
    for k, v in (("is_verdict", None), ("is_verdict", True), ("signed", True),
                 ("when", "during_the_run"), ("arm", tv.ARM_ON)):
        broken = [dict(e) for e in evs]
        if v is None:
            broken[i].pop(k)
        else:
            broken[i][k] = v
        assert any("postaudit" in b for b in tv.validate(broken)), (k, v)


def test_folder_drops_a_row_that_claims_to_be_a_verdict(lc, rows):
    f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
    for e in lc:
        f.feed(e)
    assert f.feed(dict(rows[0], is_verdict=True)) == []
    assert f.feed(dict(rows[0], signed=True)) == []
    assert len(f.dropped) == 2 and all("旗標" in d for d in f.dropped)
    assert len(f.feed(rows[0])) == 1                          # 正控制


def test_folder_does_not_guess_for_an_unbound_row(lc, rows):
    r = rows[0]
    end_i = next(i for i, e in enumerate(lc) if e["type"] == "run_ended"
                 and e["run_id"] == r["run_id"])
    # 那一跑還沒結束就來了 ⇒ 不發
    f = le.Folder(verify_url="/r/{cell}")
    for e in lc[:end_i]:
        f.feed(e)
    assert f.feed(r) == [] and "run_ended" in f.dropped[-1]
    # 量的不是那一棵樹 ⇒ 不發
    f = le.Folder(verify_url="/r/{cell}")
    for e in lc:
        f.feed(e)
    assert f.feed(dict(r, ws_end_sha256="0" * 64)) == []
    # 沒看過那一跑的開頭（從檔案中間開始讀）⇒ 不發
    assert le.Folder(verify_url="/r/{cell}").feed(r) == []


def test_unknown_schema_is_still_loud():
    with pytest.raises(le.SchemaMismatch):
        le.Folder(verify_url="/r/{cell}").feed({"schema": "twin.sidecar/2",
                                                "type": "postaudit"})


# ── 三、counters：與實際播過的格子一致 ───────────────────────────────
def _expected(evs: list[dict]) -> dict:
    """從事件檔裡**非 counters** 的事件獨立重算一次（第二把尺）。"""
    on, off, pa = {}, {}, {}
    for e in evs:
        if e["type"] == "verdict" and e["arm"] == tv.ARM_ON:
            on[e["task_id"]] = e
        elif e["type"] == "verdict" and e["arm"] == tv.ARM_OFF:
            off[e["task_id"]] = e
            pa.pop(e["task_id"], None)
        elif e["type"] == "postaudit":
            pa[e["task_id"]] = e
    return {"total": len(on),
            "blocked": sum(1 for e in on.values() if e["accepted"] is False),
            "delivered": sum(1 for e in on.values() if e["accepted"] is True),
            "off_ran": len(off),
            "off_postaudited": len(pa),
            "off_postaudit_not_all_pass": sum(1 for e in pa.values()
                                              if not e["all_pass"])}


def test_counters_follow_exactly_the_cells_that_were_played(paired, tmp_path):
    srv, stage = _mk([paired], tmp_path)
    try:
        played = []
        for _ in range(3):                                   # 只播 3 格（不是整批）
            played.append(stage.advance()["now"]["cell_id"])
        evs = _events(stage)
        assert tv.validate(evs) == []
        ctrs = [e for e in evs if e["type"] == "counters"]
        assert ctrs and all(e["mode"] == tv.MODE_REPLAY and e["task_id"] == "-"
                            for e in ctrs)
        last = ctrs[-1]
        want = _expected(evs)
        for k, v in want.items():
            assert last[k] == v, (k, last[k], v)
        assert last["total"] == len(set(played)) == 3
        assert last["evidence_counts"] == {"L-none": 3}
        for k in tv.COUNTERS_NEVER:
            assert all(k not in e for e in ctrs), k
        # 每一筆 counters 都緊接在讓數字變了的那一筆後面、ts 相同
        for e in ctrs:
            prev = evs[evs.index(e) - 1]
            assert prev["type"] in ("verdict", "postaudit") and prev["ts"] == e["ts"]
        # 同一格再播一次 ⇒ 不重複算
        stage.press("held", cell_id=played[0])
        again = [e for e in _events(stage) if e["type"] == "counters"][-1]
        assert again["total"] == 3
    finally:
        srv.server_close()


def test_counters_do_not_claim_postaudit_that_was_never_played(batch, tmp_path):
    """舊錄影（沒有旁註）：`off_postaudit_*` 一欄都不發——0/0 會被讀成「全過」。"""
    old = tmp_path / "old.jsonl"
    old.write_bytes((batch / "lifecycle.jsonl").read_bytes())
    srv, stage = _mk([old], tmp_path)
    try:
        stage.advance()
        evs = _events(stage)
        ctrs = [e for e in evs if e["type"] == "counters"]
        assert ctrs and all("off_postaudited" not in e
                            and "off_postaudit_not_all_pass" not in e for e in ctrs)
        assert ctrs[-1]["off_ran"] == 1
    finally:
        srv.server_close()


def test_tally_sends_nothing_it_did_not_count():
    t = le.Tally()
    ev = t.event(ts="x", mode=tv.MODE_REPLAY)
    for k in ("total", "blocked", "delivered", "evidence_counts", "off_ran",
              "off_postaudited", "off_postaudit_not_all_pass") + tv.COUNTERS_NEVER:
        assert k not in ev, k
    assert t.feed({"type": "working", "task_id": "a", "arm": "ON"}) is False


def test_counters_contract_bites():
    base = {"type": "counters", "ts": "t", "task_id": "-", "mode": "replay"}
    assert tv.validate([dict(base, total=3, blocked=1, delivered=2)]) == []
    assert tv.validate([dict(base, total=True)])                   # bool 不是數
    assert tv.validate([dict(base, total=-1)])
    assert tv.validate([dict(base, off_postaudit_not_all_pass=2, off_postaudited=1)])
    assert tv.validate([dict(base, off_postaudit_not_all_pass=0)])  # 沒有分母
    assert tv.validate([dict(base, evidence_counts={"L-none": 0})])


def test_replay_and_live_are_counted_in_separate_books():
    tallies = {tv.MODE_REPLAY: le.Tally(), tv.MODE_LIVE: le.Tally()}
    evs = [{"type": "verdict", "ts": "1", "task_id": "a", "mode": "replay",
            "arm": "ON", "accepted": True, "evidence": "L-none"},
           {"type": "verdict", "ts": "2", "task_id": "b", "mode": "live",
            "arm": "ON", "accepted": False, "evidence": "L-real"}]
    out = le.with_counters(evs, tallies)
    ctr = [e for e in out if e["type"] == "counters"]
    assert [(e["mode"], e["total"]) for e in ctr] == [("replay", 1), ("live", 1)]
    assert ctr[1]["evidence_counts"] == {"L-real": 1}


# ── 四、錄影：新錄影帶旁註、舊錄影照播但沒有 postaudit ─────────────────
def test_old_recording_without_sidecar_still_plays_without_postaudit(batch, tmp_path):
    old = tmp_path / "old.jsonl"
    old.write_bytes((batch / "lifecycle.jsonl").read_bytes())
    assert not sc.sidecar_path(old).exists()
    assert S.check_recording(old) == []
    cells, info = S.load_recordings([old])
    assert info[0]["accepted"] and info[0]["sidecar"]["present"] is False
    assert not [e for c in cells.values() for e in c["segment"]
                if e["schema"] == sc.SCHEMA]
    srv, stage = _mk([old], tmp_path)
    try:
        for _ in range(len(stage.flat)):
            stage.advance()
        evs = _events(stage)
        assert tv.validate(evs) == []
        assert not [e for e in evs if e["type"] == "postaudit"], \
            "舊錄影沒有旁註：畫面上不准假裝有事後稽核"
    finally:
        srv.server_close()


def test_new_recording_plays_its_postaudit(paired, tmp_path):
    assert S.check_recording(paired) == []
    srv, stage = _mk([paired], tmp_path)
    try:
        assert stage.recordings[0]["sidecar"]["accepted"] is True
        for _ in range(len(stage.flat)):
            stage.advance()
        evs = _events(stage)
        assert tv.validate(evs) == []
        assert len([e for e in evs if e["type"] == "postaudit"]) == 4
        assert {e["mode"] for e in evs} == {tv.MODE_REPLAY}
    finally:
        srv.server_close()


def test_default_recordings_skip_the_sidecar():
    assert all(not sc.is_sidecar(p) for p in S.default_recordings())
    assert sc.is_sidecar(sc.sidecar_path(S.RECORDINGS_DIR / "x.jsonl"))


def test_committed_recording_carries_a_bound_sidecar():
    """進版控的那一份是 `record_fixture.sh` 重錄過的：一定帶旁註、而且綁在配對收據裡。"""
    recs = S.default_recordings()
    if not recs:
        pytest.skip("recordings/ 裡沒有錄影")
    for rec in recs:
        side = sc.sidecar_path(rec)
        assert side.exists(), rec.name
        pack = json.loads(pairlib.pair_path(rec).read_text("utf-8"))
        assert pack["recording"]["sidecar"]["sha256"] == pairlib.sha256_file(side)
        assert sc.validate(sc.read(side), lifecycle_events=lifecycle.read(rec)) == []
        assert S.check_recording(rec) == []


# ── 五、綁定涵蓋旁註 ─────────────────────────────────────────────────
def _copy(paired, tmp_path, name):
    rec = tmp_path / f"{name}.jsonl"
    rec.write_bytes(paired.read_bytes())
    sc.sidecar_path(rec).write_bytes(sc.sidecar_path(paired).read_bytes())
    pairlib.pair_path(rec).write_bytes(pairlib.pair_path(paired).read_bytes())
    return rec


def test_one_sidecar_byte_changed_is_caught_by_the_binding(paired, tmp_path):
    """**負控制**：改旁註一個位元組（契約照樣合格）⇒ 只有 sha256 那一道抓得到，而且抓到了。"""
    rec = _copy(paired, tmp_path, "flipped")
    side = sc.sidecar_path(rec)
    raw = side.read_bytes()
    i = raw.index("事後補的".encode("utf-8"))
    side.write_bytes(raw[:i] + "事前補的".encode("utf-8") + raw[i + len("事後補的".encode()):])
    assert sc.validate(sc.read(side), lifecycle_events=lifecycle.read(rec)) == [], \
        "前提：這種改法旁註契約抓不到"
    pack = json.loads(pairlib.pair_path(rec).read_text("utf-8"))
    bad = pairlib.check_pair(rec, pack)
    assert bad and all("旁註" in b for b in bad), bad
    # 展場這一側：收據頁不收、旁註也不收 ⇒ 電視上沒有這份被改過的 postaudit
    srv, stage = _mk([rec], tmp_path)
    try:
        assert stage.recordings[0]["receipts"]["accepted"] is False
        assert stage.recordings[0]["sidecar"]["accepted"] is False
        for _ in range(len(stage.flat)):
            stage.advance()
        assert not [e for e in _events(stage) if e["type"] == "postaudit"]
    finally:
        srv.server_close()


def test_binding_catches_a_removed_or_an_unbound_sidecar(paired, tmp_path):
    rec = _copy(paired, tmp_path, "removed")
    sc.sidecar_path(rec).unlink()
    bad = pairlib.check_pair(rec, json.loads(pairlib.pair_path(rec).read_text("utf-8")))
    assert any("旁註卻不在" in b for b in bad), bad
    rec = _copy(paired, tmp_path, "unbound")
    pack = json.loads(pairlib.pair_path(rec).read_text("utf-8"))
    pack["recording"].pop("sidecar")
    bad = pairlib.check_pair(rec, pack)
    assert any("沒有綁它" in b for b in bad), bad
    # 正控制：原封不動的那一份是合格的
    assert pairlib.check_pair(paired, json.loads(
        pairlib.pair_path(paired).read_text("utf-8"))) == []


def test_build_pair_refuses_a_sidecar_that_does_not_bind(batch, tmp_path):
    rec = tmp_path / "bad.jsonl"
    rec.write_bytes((batch / "lifecycle.jsonl").read_bytes())
    rows = sc.read(sc.sidecar_path(batch / "lifecycle.jsonl"))
    rows[0]["ws_end_sha256"] = "0" * 64
    sc.sidecar_path(rec).write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(SystemExit):
        pairlib.build_pair(rec, batch)
    assert any("旁註" in b for b in S.check_recording(rec))


# ── 六、現場真跑：tail 旁註 ─────────────────────────────────────────
def test_live_mode_tails_the_sidecar_too(tmp_path):
    live = tmp_path / "live" / "lifecycle.jsonl"
    live.parent.mkdir()
    srv, stage = _mk([], tmp_path, live=live, live_idle_s=60)
    try:
        assert run_twin.main(["--out", str(tmp_path / "live" / "out"), "--fixture",
                              "--residents", "1", "--tasks", "s1_01_addmul",
                              "--sandbox", "none", "--events", str(live)]) == 0
        stage.tick()
        evs = _events(stage)
        assert tv.validate(evs) == []
        pas = [e for e in evs if e["type"] == "postaudit"]
        assert len(pas) == 2 and {e["mode"] for e in pas} == {tv.MODE_LIVE}
        ctr = [e for e in evs if e["type"] == "counters"][-1]
        assert ctr["mode"] == tv.MODE_LIVE and ctr["off_postaudited"] == 2
        assert not [x for x in stage.live_errors if "旁註" in x]
    finally:
        srv.server_close()


def test_run_twin_writes_no_sidecar_without_events(tmp_path):
    out = tmp_path / "noevents"
    assert run_twin.main(["--out", str(out), "--fixture", "--residents", "1",
                          "--tasks", "s1_01_addmul", "--sandbox", "none"]) == 0
    assert not list(out.rglob("*" + sc.SUFFIX))
    meta = json.loads(next(out.glob("runs/*/twin_cell.json")).read_text("utf-8"))
    assert "sidecar" not in meta["arms"]["OFF"]


def test_run_twin_reports_whether_the_sidecar_was_written(batch):
    for p in batch.glob("runs/*/twin_cell.json"):
        off = json.loads(p.read_text("utf-8"))["arms"]["OFF"]
        assert off["sidecar"]["written"] is True and off["sidecar"]["error"] is None
        assert "/" not in off["sidecar"]["file"]          # 不帶建置機路徑
