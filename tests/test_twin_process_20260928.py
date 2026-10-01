"""分身「決策過程」被看見（2026-09-28）的判準。

契約：`plans/CONTRACT_PROCESS_20260928.md`（vacant_hm-assets-20260926，A／B／C 三節）。

範圍（這個檔守的，Vacant 這一側，不含雲端 `vacant-world-cloud`）：

  A. `twin.sidecar/1` 新型別 `twin_step`（`sidecar.py`）＋轉出電視事件
     （`live_events.Folder`／`tv_contract.py`）＋分身迴圈 tail 原始記錄檔的那一支
     （`twinagent.StepForwarder`）——**不帶檔名**，每一條規則配負控制。
  B. 名冊 `people[].decision` 即時讀工作區（`twinagent.live_decision`，
     `twinlink.build_view`）；`people[].run` 新欄位（`tier`／`enclosed`／
     `count_semantics`／`ws_end_sha256`）三態（量到／量不到／不適用）。
  C.（局部）`twinlink.publish()` 帶步驟與判定摘要上雲端——這裡只驗 Vacant 這一側
     組出來的 payload 形狀；雲端收不收、回不回給本人是
     `vacant-world-cloud/test/process_flow.test.mjs` 的範圍。

⚠ 本檔零模型呼叫：沿用 `tests/test_twin_agent_run.py` 的假上游＋fixture agent。
⚠ 每一個綠燈配一個負控制（量具量得到「壞」才算量到「好」）。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import polaroid as polaroidlib  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from ops.exhibit.twin import twinagent, twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import TwinStore  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402
# 假上游＋fixture agent＋store（同一套，不另寫一份會漂的）
from test_twin_agent_run import DECISION, NEED, TRAITS_TEXT, _ingest, env, upstream  # noqa: E402,F401


# ---------------------------------------------------------------------------
# A-1. sidecar：twin_step 的形狀（原始記錄 → 旁註，不帶檔名）
# ---------------------------------------------------------------------------

def test_classify_path_kind_matches_the_contract_table() -> None:
    assert sc.classify_path_kind("ws_read", "TRAITS.md") == "traits"
    assert sc.classify_path_kind("ws_write", "PLAN.md") == "plan"
    assert sc.classify_path_kind("ws_write", "letter.md") == "artifact"
    assert sc.classify_path_kind("ws_list", None) == "other"
    # 巢狀路徑：認檔名，不是整條路徑
    assert sc.classify_path_kind("ws_read", "sub/TRAITS.md") == "traits"


def test_twin_step_row_drops_the_filename() -> None:
    raw = {"ts_ms": 1_790_000_000_000, "seq": 3, "tool": "ws_write",
          "path": "letter.md", "bytes": 1240, "ok": True}
    row = sc.twin_step_row(raw, cell_id="tw-abc", run_id="r1")
    assert row["schema"] == sc.SCHEMA and row["type"] == "twin_step"
    assert row["step"] == "write" and row["path_kind"] == "artifact"
    assert row["bytes"] == 1240 and row["ok"] is True and row["seq"] == 3
    assert "path" not in row and "name" not in row and "text" not in row
    assert row["cell_id"] == "tw-abc" and row["run_id"] == "r1"


@pytest.mark.parametrize("bad", [
    {"seq": 1, "tool": "bash", "path": "x", "bytes": 1, "ok": True},   # 不在白名單
    {"seq": -1, "tool": "ws_read", "path": "x", "bytes": 1, "ok": True},
    {"seq": 1, "tool": "ws_read", "path": "x", "bytes": 1, "ok": "yes"},
    {"seq": 1, "tool": "ws_read", "path": "x", "bytes": -1, "ok": True},
    "not_a_dict",
])
def test_twin_step_row_negative_control_shape(bad) -> None:
    assert sc.twin_step_row(bad, cell_id="tw-abc", run_id="r1") is None


def test_sidecar_validate_accepts_a_bound_twin_step_and_binds_to_on_arm() -> None:
    lc = [
        {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
         "arm": "RUN-ON", "task_id": "twin:tw-x", "caller": {"cell_id": "tw-x"}},
        {"schema": lifecycle.SCHEMA, "type": "run_ended", "run_id": "r1", "ts_ms": 2000,
         "ws_end_sha256": "0" * 64, "infra_void": None},
    ]
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "TRAITS.md", "bytes": 10, "ok": True},
                           cell_id="tw-x", run_id="r1")
    assert sc.validate([row], lifecycle_events=lc) == []


@pytest.mark.parametrize("field,value", [
    ("step", "bash"), ("path_kind", "everything"), ("ok", "yes"), ("seq", -1),
    ("bytes", -5), ("cell_id", "someone-else"), ("run_id", "nope"),
])
def test_sidecar_validate_twin_step_has_teeth(field, value) -> None:
    """負控制：每一條規則各自抓得到它那一種壞法。"""
    lc = [{"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
          "arm": "RUN-ON", "task_id": "twin:tw-x", "caller": {"cell_id": "tw-x"}}]
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "TRAITS.md", "bytes": 10, "ok": True},
                           cell_id="tw-x", run_id="r1")
    row[field] = value
    assert sc.validate([row], lifecycle_events=lc), (field, value)


def test_sidecar_validate_rejects_run_bound_to_off_arm() -> None:
    lc = [{"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
          "arm": "RUN-OFF", "task_id": "s1", "caller": {"cell_id": "tw-x"}}]
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "TRAITS.md", "bytes": 10, "ok": True},
                           cell_id="tw-x", run_id="r1")
    assert sc.validate([row], lifecycle_events=lc)


def test_sidecar_validate_rejects_a_step_before_its_run_started() -> None:
    lc = [{"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 2000,
          "arm": "RUN-ON", "task_id": "twin:tw-x", "caller": {"cell_id": "tw-x"}}]
    row = sc.twin_step_row({"ts_ms": 1000, "seq": 1, "tool": "ws_read",
                            "path": "TRAITS.md", "bytes": 10, "ok": True},
                           cell_id="tw-x", run_id="r1")
    assert sc.validate([row], lifecycle_events=lc)


@pytest.mark.parametrize("leak_key", sc.CONTENT_KEYS)
def test_sidecar_validate_rejects_any_content_key_on_a_twin_step(leak_key) -> None:
    """負控制：不准帶檔名／內容——`CONTENT_KEYS` 逐一試過去都要被擋。"""
    lc = [{"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
          "arm": "RUN-ON", "task_id": "twin:tw-x", "caller": {"cell_id": "tw-x"}}]
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "TRAITS.md", "bytes": 10, "ok": True},
                           cell_id="tw-x", run_id="r1")
    row[leak_key] = "letter.md"
    assert sc.validate([row], lifecycle_events=lc)


# ---------------------------------------------------------------------------
# A-2. Folder：sidecar 的 twin_step → 電視的 twin_step
# ---------------------------------------------------------------------------

def _run_started(rid: str, *, arm: str, task_kind: str | None, ts_ms: int = 1000) -> dict:
    caller = {"cell_id": "tw-x", "resident": "R1", "prompt": "p", "stratum": "twin"}
    if task_kind is not None:
        caller["task_kind"] = task_kind
    return {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": rid, "ts_ms": ts_ms,
           "arm": arm, "task_id": "twin:tw-x", "retry": "none", "caller": caller}


def test_folder_turns_a_bound_twin_step_into_a_filename_free_tv_event() -> None:
    f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
    opened = f.feed(_run_started("r1", arm="RUN-ON", task_kind=tv.KIND_PRACTICAL))
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 2, "tool": "ws_write",
                            "path": "letter.md", "bytes": 88, "ok": True},
                           cell_id="tw-x", run_id="r1")
    out = f.feed(row)
    assert len(out) == 1
    ev = out[0]
    assert ev["type"] == "twin_step" and ev["arm"] == tv.ARM_ON and ev["task_id"] == "tw-x"
    assert ev["step"] == "write" and ev["path_kind"] == "artifact" and ev["bytes"] == 88
    assert ev["seq"] == 2 and ev["mode"] == tv.MODE_LIVE
    for k in ("path", "name", "text", "file"):
        assert k not in ev
    assert tv.validate(opened + [ev], require_settled=False) == []


def _ev_task_opened() -> dict:
    return {"type": "task_opened", "ts": "2026-01-01T00:00:00.000+00:00", "task_id": "tw-x",
           "mode": tv.MODE_LIVE, "task_kind": tv.KIND_PRACTICAL, "prompt": "p",
           "prompt_sha256": "0" * 64, "evidence": None, "evidence_note": "n", "stratum": "twin"}


def test_folder_drops_twin_step_for_a_code_task_kind() -> None:
    """反事實題庫格（code）不出這一欄——契約 §A／§D。"""
    f = le.Folder(verify_url="/r/{cell}")
    f.feed(_run_started("r1", arm="RUN-ON", task_kind=tv.KIND_CODE))
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_list", "path": None,
                            "bytes": None, "ok": True}, cell_id="tw-x", run_id="r1")
    assert f.feed(row) == []
    assert f.dropped and "practical" in f.dropped[-1]


def test_folder_drops_twin_step_bound_to_off_arm() -> None:
    f = le.Folder(verify_url="/r/{cell}")
    f.feed(_run_started("r1", arm="RUN-OFF", task_kind=tv.KIND_CODE))
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_list", "path": None,
                            "bytes": None, "ok": True}, cell_id="tw-x", run_id="r1")
    assert f.feed(row) == []
    assert f.dropped and "ON" in f.dropped[-1]


def test_folder_drops_twin_step_for_an_unknown_run() -> None:
    f = le.Folder(verify_url="/r/{cell}")
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_list", "path": None,
                            "bytes": None, "ok": True}, cell_id="tw-x", run_id="nope")
    assert f.feed(row) == []


# ---------------------------------------------------------------------------
# A-3. tv_contract：白名單與「不帶檔名」的第二道網
# ---------------------------------------------------------------------------

def _good_twin_step_ev() -> dict:
    return {"type": "twin_step", "ts": "2026-01-01T00:00:00.100+00:00", "task_id": "tw-x",
           "mode": tv.MODE_LIVE, "arm": tv.ARM_ON, "step": "write", "path_kind": "artifact",
           "bytes": 40, "seq": 1}


def test_tv_contract_accepts_a_well_formed_twin_step() -> None:
    assert tv.validate([_ev_task_opened(), _good_twin_step_ev()],
                       require_settled=False) == []


@pytest.mark.parametrize("field,value", [
    ("arm", tv.ARM_OFF), ("step", "bash"), ("path_kind", "everything"), ("bytes", -1),
])
def test_tv_contract_twin_step_has_teeth(field, value) -> None:
    ev = dict(_good_twin_step_ev())
    ev[field] = value
    bad = tv.validate([_ev_task_opened(), ev], require_settled=False)
    assert any("twin_step" in b for b in bad), bad


@pytest.mark.parametrize("forbidden", tv.TWIN_STEP_FORBIDDEN)
def test_tv_contract_rejects_a_filename_leaking_into_the_tv_event(forbidden) -> None:
    ev = dict(_good_twin_step_ev())
    ev[forbidden] = "letter.md"
    bad = tv.validate([_ev_task_opened(), ev], require_settled=False)
    assert any("twin_step" in b and "不帶檔名" in b for b in bad), bad


def test_tv_contract_rejects_twin_step_on_a_code_task() -> None:
    opened = dict(_ev_task_opened(), task_kind=tv.KIND_CODE)
    bad = tv.validate([opened, _good_twin_step_ev()], require_settled=False)
    assert any("twin_step" in b for b in bad), bad


# ---------------------------------------------------------------------------
# A-4. StepForwarder：tail 原始記錄檔 → 旁註（不需要真的起 pi）
# ---------------------------------------------------------------------------

def test_step_forwarder_learns_run_id_and_forwards_without_filenames(tmp_path) -> None:
    rd = tmp_path / "rundir"
    rd.mkdir()
    events_path = tmp_path / "lifecycle.jsonl"
    step_log = rd / twinagent.STEP_LOG_NAME
    fwd = twinagent.StepForwarder(step_log, events_path, task_id="twin:tw-x", cell_id="tw-x")

    # 這一跑的 run_started 還沒寫出來：先攢著，不准亂猜 run_id
    step_log.write_text(json.dumps({"ts_ms": 1, "seq": 1, "tool": "ws_read",
                                    "path": "TRAITS.md", "bytes": 9, "ok": True}) + "\n",
                        encoding="utf-8")
    fwd._pump()                                            # noqa: SLF001
    assert fwd.run_id is None and not sc.sidecar_path(events_path).exists()

    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"schema": lifecycle.SCHEMA, "type": "run_started",
                             "run_id": "r-real", "ts_ms": 0, "arm": "RUN-ON",
                             "task_id": "twin:tw-x",
                             "caller": {"cell_id": "tw-x"}}) + "\n")
    with step_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts_ms": 2, "seq": 2, "tool": "ws_write",
                             "path": "PLAN.md", "bytes": 12, "ok": True}) + "\n")
    fwd._pump()                                            # noqa: SLF001
    assert fwd.run_id == "r-real"
    assert fwd.forwarded == 2 and fwd.rejected == 0

    rows = sc.read(sc.sidecar_path(events_path))
    assert [r["step"] for r in rows] == ["read", "write"]
    assert [r["path_kind"] for r in rows] == ["traits", "plan"]
    assert all(r["run_id"] == "r-real" and r["cell_id"] == "tw-x" for r in rows)
    blob = json.dumps(rows)
    assert "TRAITS.md" not in blob and "PLAN.md" not in blob


def test_step_forwarder_rejects_malformed_raw_lines_without_crashing(tmp_path) -> None:
    rd = tmp_path / "rundir"; rd.mkdir()
    events_path = tmp_path / "lifecycle.jsonl"
    events_path.write_text(json.dumps({"schema": lifecycle.SCHEMA, "type": "run_started",
                                       "run_id": "r1", "ts_ms": 0, "arm": "RUN-ON",
                                       "task_id": "twin:tw-x",
                                       "caller": {"cell_id": "tw-x"}}) + "\n", encoding="utf-8")
    step_log = rd / twinagent.STEP_LOG_NAME
    step_log.write_text("not json at all\n"
                        + json.dumps({"ts_ms": 1, "seq": 1, "tool": "bash", "path": "x",
                                     "bytes": 1, "ok": True}) + "\n"
                        + json.dumps({"ts_ms": 2, "seq": 2, "tool": "ws_list", "path": None,
                                     "bytes": None, "ok": True}) + "\n",
                        encoding="utf-8")
    fwd = twinagent.StepForwarder(step_log, events_path, task_id="twin:tw-x", cell_id="tw-x")
    fwd._pump()                                            # noqa: SLF001
    assert fwd.forwarded == 1 and fwd.rejected == 2
    rows = sc.read(sc.sidecar_path(events_path))
    assert len(rows) == 1 and rows[0]["step"] == "list"


def test_step_forwarder_is_a_noop_without_an_events_path(tmp_path) -> None:
    """`--events` 沒給 ⇒ 一個 byte 都不多寫（跟既有 sidecar 行為同一條規矩）。"""
    rd = tmp_path / "rundir"; rd.mkdir()
    step_log = rd / twinagent.STEP_LOG_NAME
    step_log.write_text(json.dumps({"ts_ms": 1, "seq": 1, "tool": "ws_list", "path": None,
                                    "bytes": None, "ok": True}) + "\n", encoding="utf-8")
    fwd = twinagent.StepForwarder(step_log, None, task_id="twin:tw-x", cell_id="tw-x")
    fwd._pump()                                            # noqa: SLF001
    assert fwd.forwarded == 0 and fwd.sidecar_path is None


# ---------------------------------------------------------------------------
# A-5：完整跑一次（launcher 真的 spawn、StepForwarder 真的在背景 tail）
# ---------------------------------------------------------------------------

_STEP_FIXTURE = r'''
import json, os, pathlib, sys, time, urllib.request
run_dir, sysp, msg = sys.argv[-3], sys.argv[-2], sys.argv[-1]
# twin_agent.sh 是這樣從 $RUN_DIR 算出來的（見它自己的註解）；這支測試 fixture
# 繞過那支 bash 腳本直接 exec python，所以自己重算同一個路徑。
step_log = os.path.join(run_dir, "twin_steps.ndjson")

def log(seq, tool, path, n, ok=True):
    with open(step_log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts_ms": int(time.time() * 1000), "seq": seq, "tool": tool,
                             "path": path, "bytes": n, "ok": ok}) + "\n")

traits = pathlib.Path("TRAITS.md").read_text(encoding="utf-8")
log(1, "ws_list", None, None)
log(2, "ws_read", "TRAITS.md", len(traits.encode("utf-8")))
base = os.environ["OPENAI_BASE_URL"].rstrip("/")
body = json.dumps({"model": "m", "messages": [{"role": "user", "content": msg}]}).encode()
req = urllib.request.Request(base + "/chat/completions", data=body, method="POST")
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req, timeout=30) as r:
    r.read()
plan = "__DECISION__\n理由一句話。\n"
pathlib.Path("PLAN.md").write_text(plan, encoding="utf-8")
log(3, "ws_write", "PLAN.md", len(plan.encode("utf-8")))
# pi --mode json 的 stdout 形狀（真 pi 0.85.1 量到的，見 tests/fixtures/pi_json/）：
# 假 agent 也印兩行，端到端驗 launcher 落盤 → SayForwarder tail → 旁註 → 電視事件。
print(json.dumps({"type": "turn_start"}))
print(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": [
    {"type": "text", "text": "SYNTH：我先把想做的事寫成一份計畫。"}]}}, ensure_ascii=False))
print("done")
'''.replace("__DECISION__", DECISION)


@pytest.fixture()
def step_env(tmp_path, upstream, monkeypatch):
    monkeypatch.setenv("VACANT_RUN_UPSTREAM_OPENAI", upstream)
    monkeypatch.setenv("VACANT_AGENT_MODEL", "m")
    monkeypatch.delenv("VACANT_TWIN_AGENTRUNS", raising=False)
    monkeypatch.delenv(lifecycle.ENV_EVENTS, raising=False)
    fx = tmp_path / "step_fixture.py"
    fx.write_text(_STEP_FIXTURE, encoding="utf-8")
    st = TwinStore(tmp_path / "t.sqlite3")
    cfg = twinagent.AgentConfig(
        work_root=twinagent.default_work_root(st.path),
        events_path=tmp_path / "live.jsonl", model="m", endpoint=upstream,
        parallel=1, timeout_s=60.0,
        argv_prefix=[sys.executable, str(fx)], requires=[])
    yield {"store": st, "cfg": cfg, "upstream": upstream, "tmp": tmp_path}
    st.close()


def test_end_to_end_run_produces_a_filename_free_twin_step_sidecar(step_env, monkeypatch) -> None:
    st, cfg = step_env["store"], step_env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, step_env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1 and r["degraded"] == 0, r

    tw = st.current(sid)["twin"]
    run_id = tw["run_id"]
    rows = sc.read(sc.sidecar_path(cfg.events_path))
    steps = [r for r in rows if r["type"] == "twin_step" and r["run_id"] == run_id]
    assert [r["step"] for r in steps] == ["list", "read", "write"]
    assert [r["path_kind"] for r in steps] == ["other", "traits", "plan"]
    blob = json.dumps(rows)
    assert "TRAITS.md" not in blob and "PLAN.md" not in blob and TRAITS_TEXT not in blob

    lc = lifecycle.read(cfg.events_path)
    assert sc.validate(rows, lifecycle_events=lc) == []
    evs = le.fold(sc.merge(lc, rows), verify_url="/r/{cell}")
    assert tv.validate(evs) == []
    tv_steps = [e for e in evs if e["type"] == "twin_step"]
    assert [e["step"] for e in tv_steps] == ["list", "read", "write"]
    for e in tv_steps:
        for k in ("path", "name", "text"):
            assert k not in e

    # E：agent_stdout.log（launcher 落盤）→ twin_say → 電視事件
    says = [r for r in rows if r["type"] == "twin_say" and r["run_id"] == run_id]
    assert [r["text"] for r in says] == ["SYNTH：我先把想做的事寫成一份計畫。"], rows
    assert [e["text"] for e in evs if e["type"] == "twin_say"] == [says[0]["text"]]
    assert tw.get("run_id") == run_id

    # 手機那一份（含檔名）：只在 run-dir 的原始記錄檔裡才看得到檔名
    _ws, rd = twinagent.paths_for(cfg.work_root, sid)
    raw = twinagent.read_step_log(rd)
    assert [r["path"] for r in raw] == [None, "TRAITS.md", "PLAN.md"]


# ---------------------------------------------------------------------------
# B-1：live_decision（跑的當下讀工作區）
# ---------------------------------------------------------------------------

def test_live_decision_reads_the_first_line_of_plan_md(tmp_path) -> None:
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "PLAN.md").write_text("我決定整理一份清單\n因為房間有點亂。\n", encoding="utf-8")
    got = twinagent.live_decision(ws, {"need": "整理房間"}, None)
    # `parse_plan` 只剝「我決定：」這種帶冒號的字首；沒有冒號就整句照留
    # （跟 `test_twin_agent_run.py` 的真跑 fixture 是同一條規則）。
    assert got == "我決定整理一份清單"


def test_live_decision_is_none_without_a_plan(tmp_path) -> None:
    ws = tmp_path / "ws"; ws.mkdir()
    assert twinagent.live_decision(ws, {}, None) is None
    assert twinagent.live_decision(tmp_path / "missing", {}, None) is None


def test_live_decision_redacts_a_verbatim_leak_of_the_audience_original() -> None:
    """負控制：逐字抄觀眾原文（連續 ≥8 字）⇒ 回 None，不是顯示被剪過的那一半。"""
    import tempfile
    original = "我最近一直很想寫信給國小導師謝謝她"
    with tempfile.TemporaryDirectory() as d:
        ws = pathlib.Path(d)
        (ws / "PLAN.md").write_text(original + "\n", encoding="utf-8")
        assert twinagent.live_decision(ws, None, original) is None
        # 正控制：換一句沒有抄的話，一樣的原文清單下 → 有值
        (ws / "PLAN.md").write_text("寫一張卡片給老師\n", encoding="utf-8")
        assert twinagent.live_decision(ws, None, original) == "寫一張卡片給老師"


# ---------------------------------------------------------------------------
# B-2：build_view 即時顯示 decision；run 新欄位三態
# ---------------------------------------------------------------------------

def test_build_view_shows_decision_live_before_the_run_finishes(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    # 還沒 generate：手動在工作區放一份「還在寫」的 PLAN.md（模擬跑到一半）。
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    ws.mkdir(parents=True); rd.mkdir(parents=True)
    (ws / "TRAITS.md").write_text(TRAITS_TEXT, encoding="utf-8")
    (ws / "PLAN.md").write_text("我決定先寫張感謝卡\n之後再說。\n", encoding="utf-8")
    view = twinlink.build_view(st)
    person = next(p for p in view["people"] if p["id"] == sid)
    assert person["decision"] == "我決定先寫張感謝卡"
    assert person["run"] is None, "還沒有任何一通模型呼叫，run 不該冒出來"

    # 真的跑完之後：改讀凍結快照（工作區已經被下一次 run 蓋掉也沒關係）。
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1 and r["degraded"] == 0, r
    view2 = twinlink.build_view(st)
    person2 = next(p for p in view2["people"] if p["id"] == sid)
    assert person2["decision"] == DECISION


def test_build_view_live_decision_is_redacted_when_it_leaks_the_original(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    ws, rd = twinagent.paths_for(cfg.work_root, sid)
    ws.mkdir(parents=True); rd.mkdir(parents=True)
    (ws / "PLAN.md").write_text(NEED + "\n", encoding="utf-8")   # 逐字抄卡上的原文
    view = twinlink.build_view(st)
    person = next(p for p in view["people"] if p["id"] == sid)
    assert person["decision"] is None


def test_run_new_fields_present_after_a_real_run(env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1, r
    tw = st.current(sid)["twin"]
    view = twinlink.build_view(st)
    person = next(p for p in view["people"] if p["id"] == sid)
    run = person["run"]
    assert run["ws_end_sha256"] == tw["ws_end_sha256"] and run["ws_end_sha256"]
    assert run["count_semantics"] in ("exact", "lower_bound")
    assert run["enclosed"] is False, "enclose=off（測試環境沒有圍牆）是量到的事實，不是沒量到"
    assert run["tier"] == tw.get("tier")


def test_run_new_fields_are_null_not_false_on_a_degraded_twin() -> None:
    """負控制：退化路徑（沒有任何一通模型呼叫）⇒ 四個新欄位沒量到，是 None 不是 False。"""
    res = {"twin_id": "tw-x", "error": None,
          "summary": {"requests_seen": 0, "stop_reason": "ungated", "accepted": None},
          "outputs": {"decision": None, "reason": None, "artifacts": [], "has_plan": False},
          "wall_s": 0.01, "enclosed": None, "require_tier": None}
    fallback = lambda _sub: {"arrival": "a", "working": "w", "handover": "h"}  # noqa: E731
    twin = twinagent.build_twin(res, model="m", fallback=fallback)
    assert twin["engine"] == "fallback_deterministic"
    for k in ("tier", "enclosed", "count_semantics", "ws_end_sha256"):
        assert twin.get(k) is None, k


# ---------------------------------------------------------------------------
# C（局部）：publish 帶步驟與判定摘要
# ---------------------------------------------------------------------------

def _capture_publish(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        sent.append({"url": url, "payload": payload})
        return 200, {"ok": True}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    return sent


def test_publish_sends_judgment_and_an_empty_step_list_when_none_was_recorded(
        env, monkeypatch) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1, r
    twinlink.polaroids(st)
    sent = _capture_publish(monkeypatch)
    out = twinlink.publish(st, "http://cloud.invalid", "t")
    assert out["published"] == 1, out
    body = sent[0]["payload"]
    assert body["steps"] == [], "fixture agent 不是 pi，沒有原始記錄檔 ⇒ 空清單不是缺欄位"
    j = body["judgment"]
    tw = st.current(sid)["twin"]
    assert j["chain_head_prefix"] == tw["verdict_hash"][:8]
    assert j["ws_end_sha256_prefix"] == tw["ws_end_sha256"][:8]
    assert j["count_semantics"] == tw["count_semantics"]
    assert j["requests_seen"] == tw["requests_seen"]
    assert j["accepted_note"] == tv.PRACTICAL_ACCEPTED_NOTE
    assert "信任" not in j["accepted_note"]


def test_publish_forwards_the_real_step_log_with_filenames(step_env, monkeypatch) -> None:
    """雲端那一份含檔名（是觀眾自己的東西）——這裡只驗 Vacant 這一側組對了。"""
    st, cfg = step_env["store"], step_env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, step_env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1, r
    twinlink.polaroids(st)
    sent = _capture_publish(monkeypatch)
    twinlink.publish(st, "http://cloud.invalid", "t")
    body = sent[0]["payload"]
    assert [s["path"] for s in body["steps"]] == [None, "TRAITS.md", "PLAN.md"]
    assert [s["tool"] for s in body["steps"]] == ["ws_list", "ws_read", "ws_write"]


# ---------------------------------------------------------------------------
# 補送：已 published 但雲端缺拍立得／收據的人（2026-10-01 補測試）
# ---------------------------------------------------------------------------

def _published_one(env, monkeypatch) -> str:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 1, r
    twinlink.polaroids(st)
    _capture_publish(monkeypatch)
    assert twinlink.publish(st, "http://cloud.invalid", "t")["published"] == 1
    return sid


def _fake_cloud(monkeypatch, status_body: dict) -> list[dict]:
    calls: list[dict] = []

    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        calls.append({"url": url, "payload": payload})
        if "/api/status/" in url:
            return 200, status_body
        return 200, {"ok": True}
    monkeypatch.setattr(twinlink, "_http_json", fake)
    return calls


def test_resend_missing_polaroid_appends_a_resend_event_and_posts_again(env, monkeypatch) -> None:
    st = env["store"]
    sid = _published_one(env, monkeypatch)
    n_before = len(list(st.events(sub_id=sid, kind=twinlink.KIND_PUBLISHED)))
    calls = _fake_cloud(monkeypatch, {"status": "published"})       # 沒有 polaroid_url／receipt_url
    out = twinlink.resend_missing(st, "http://cloud.invalid", "t")
    assert out["resent"] == 1, out
    posts = [c for c in calls if c["url"].endswith("/api/result")]
    assert len(posts) == 1 and posts[0]["payload"]["id"] == sid
    evs = list(st.events(sub_id=sid, kind=twinlink.KIND_PUBLISHED))
    assert len(evs) == n_before + 1, "追加，不覆寫"
    assert evs[-1]["payload"]["resend"] is True


def test_resend_skips_when_cloud_already_complete(env, monkeypatch) -> None:
    """負控制：雲端兩樣都有 ⇒ 不送。"""
    st = env["store"]
    _published_one(env, monkeypatch)
    calls = _fake_cloud(monkeypatch, {"polaroid_url": "/api/polaroid/x", "receipt_url": "/api/receipt/x"})
    out = twinlink.resend_missing(st, "http://cloud.invalid", "t")
    assert out["resent"] == 0 and out["skipped_complete"] == 1
    assert not [c for c in calls if c["url"].endswith("/api/result")]


def test_resend_is_capped_per_person_on_the_chain(env, monkeypatch) -> None:
    st = env["store"]
    _published_one(env, monkeypatch)
    _fake_cloud(monkeypatch, {"status": "published"})
    for _ in range(twinlink.DEFAULT_MAX_RESENDS):
        assert twinlink.resend_missing(st, "http://cloud.invalid", "t")["resent"] == 1
    out = twinlink.resend_missing(st, "http://cloud.invalid", "t")
    assert out["resent"] == 0 and out["skipped_cap"] == 1


def test_resend_never_touches_a_withdrawn_person(env, monkeypatch) -> None:
    st = env["store"]
    sid = _published_one(env, monkeypatch)
    twinlink.withdraw(st, sid, reason="test")
    calls = _fake_cloud(monkeypatch, {"status": "published"})
    out = twinlink.resend_missing(st, "http://cloud.invalid", "t")
    assert out["candidates"] == 0 and out["resent"] == 0
    assert not calls


def test_resolve_sub_id_accepts_twin_id_and_prefix(env, monkeypatch) -> None:
    st = env["store"]
    sid = _published_one(env, monkeypatch)
    assert twinlink._resolve_sub_id(st, sid[:6]) == sid                      # noqa: SLF001
    assert twinlink._resolve_sub_id(st, twinagent.public_twin_id(sid)) == sid  # noqa: SLF001
    assert twinlink._resolve_sub_id(st, "zzzzzzzz-nope") is None             # noqa: SLF001


# ---------------------------------------------------------------------------
# E：twin_say（契約補充 2026-10-01）——真 pi 0.85.1 --mode json 的事件形狀
# ---------------------------------------------------------------------------

FIXDIR = ROOT / "tests" / "fixtures" / "pi_json"
REAL_LOGS = sorted(FIXDIR.glob("real_pi_0.85.1_synth*.jsonl"))


def _drive_say(tmp_path, lines, originals=None, events_run=True):
    """把一份 agent_stdout.log 內容餵給 SayForwarder，回 (forwarder, 旁註清單)。"""
    ev = tmp_path / "live.jsonl"
    ev.write_text(json.dumps({"schema": lifecycle.SCHEMA, "type": "run_started",
                              "task_id": "twin:tw-x", "run_id": "R1"}) + "\n", encoding="utf-8")
    log = tmp_path / "agent_stdout.log"
    log.write_text("".join(l if isinstance(l, str) else json.dumps(l, ensure_ascii=False) + "\n"
                           for l in lines), encoding="utf-8")
    f = twinagent.SayForwarder(log, ev, task_id="twin:tw-x", cell_id="tw-x",
                               originals=originals)
    f._pump()                                              # noqa: SLF001
    return f, sc.read(sc.sidecar_path(ev))


def _turn(text_blocks, role="assistant"):
    return [{"type": "turn_start"},
            {"type": "message_end", "message": {"role": role, "content": text_blocks}}]


def test_real_pi_fixtures_exist_and_have_the_shape_we_parse() -> None:
    assert len(REAL_LOGS) == 3, REAL_LOGS
    for p in REAL_LOGS:
        types = {json.loads(l)["type"] for l in p.read_text(encoding="utf-8").splitlines() if l}
        assert {"turn_start", "message_end", "turn_end", "agent_end"} <= types, p


@pytest.mark.parametrize("log", REAL_LOGS, ids=lambda p: p.name)
def test_say_forwarder_on_real_pi_output_emits_only_clean_assistant_text(tmp_path, log) -> None:
    lines = log.read_text(encoding="utf-8").splitlines(keepends=True)
    f, rows = _drive_say(tmp_path, lines)
    # 真 pi 的最後一回合一定有一句收尾的話；它常講出檔名（電視不帶檔名 ⇒ 整句不發、有計數）
    assert rows or f.dropped_filename, "收尾那句不是被發出去，就是因為檔名被擋並計數"
    assert sc.validate(rows) == []
    assert not any(sc.looks_like_filename(r["text"]) for r in rows)
    for r in rows:
        assert r["type"] == "twin_say" and 0 < len(r["text"]) <= sc.SAY_MAX
        assert "<|" not in r["text"] and "|>" not in r["text"], r["text"]
        assert "channel" not in r["text"] and not r["text"].startswith("thought")
    # 思考區塊與工具參數（寫進檔案的內容）絕不出現
    raw = log.read_text(encoding="utf-8")
    for l in raw.splitlines():
        o = json.loads(l)
        if o.get("type") == "message_end" and o["message"]["role"] == "assistant":
            for c in o["message"]["content"]:
                if c["type"] == "thinking" and c["thinking"].strip():
                    assert all(c["thinking"][:30] not in r["text"] for r in rows)
                if c["type"] == "toolCall":
                    body = str(c["arguments"].get("content", ""))[:20]
                    if body:                       # ws_list 沒有 content
                        assert all(body not in r["text"] for r in rows)
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))


def test_say_forwarder_strips_the_channel_marker_seen_in_real_pi_output(tmp_path) -> None:
    lines = _turn([{"type": "text", "text": "<|channel>thought\n<channel|>"}]) + \
            _turn([{"type": "text", "text": "<|channel>thought\n<channel|>我交出了星空筆記。"}])
    _f, rows = _drive_say(tmp_path, lines)
    assert [r["text"] for r in rows] == ["我交出了星空筆記。"], "純標記那一句不發；有字的那句清完照發"
    assert rows[0]["turn"] == 2


def test_say_over_80_chars_is_cut_and_flagged(tmp_path) -> None:
    long = "我" * 200
    _f, rows = _drive_say(tmp_path, _turn([{"type": "text", "text": long}]))
    assert len(rows) == 1 and len(rows[0]["text"]) == 80 and rows[0]["truncated"] is True
    # 負控制：剛好 80 字不算截斷
    _f, rows = _drive_say(tmp_path / "x", []) if False else (None, None)
    r = sc.say_row("好" * 80, turn=1, seq=1, cell_id="c", run_id="r")
    assert r["truncated"] is False and len(r["text"]) == 80


def test_say_that_copies_the_audience_original_is_dropped_not_rewritten(tmp_path) -> None:
    original = "我最近一直很想寫信給國小導師謝謝她"
    lines = _turn([{"type": "text", "text": f"我想：{original}。"}]) + \
            _turn([{"type": "text", "text": "我先去整理書架。"}])
    f, rows = _drive_say(tmp_path, lines, originals=[original])
    assert [r["text"] for r in rows] == ["我先去整理書架。"]
    assert f.dropped == 1


def test_say_with_a_filename_is_not_sent_to_the_tv(tmp_path) -> None:
    """電視不帶檔名：真 pi 收尾那句「我交出了 X.md」整句不發；沒檔名的照發（正控制）。"""
    lines = _turn([{"type": "toolCall", "id": "1", "name": "ws_write",
                    "arguments": {"path": "星空筆記本.md", "content": "…"}}]) + \
            _turn([{"type": "text", "text": "我交出了星空筆記本。"}]) + \
            _turn([{"type": "text", "text": "我交出了 star_notes.md。"}]) + \
            _turn([{"type": "text", "text": "我先去整理書架。"}])
    f, rows = _drive_say(tmp_path, lines)
    assert [r["text"] for r in rows] == ["我先去整理書架。"]
    assert f.dropped_filename == 2


def test_clean_say_keeps_underscores_inside_words() -> None:
    assert sc.clean_say("我寫了 star_notes 然後 _強調_ 一下") == "我寫了 star_notes 然後 強調 一下"


def test_say_ignores_thinking_toolcalls_user_and_toolresult_messages(tmp_path) -> None:
    lines = [{"type": "turn_start"},
             {"type": "message_end", "message": {"role": "user", "content": [
                 {"type": "text", "text": "這是 TRAITS 全文 不准出現"}]}},
             {"type": "message_end", "message": {"role": "assistant", "content": [
                 {"type": "thinking", "thinking": "內心獨白不准出現"},
                 {"type": "toolCall", "id": "x", "name": "ws_write",
                  "arguments": {"path": "a.md", "content": "檔案內容不准出現"}}]}},
             {"type": "message_end", "message": {"role": "toolResult", "content": [
                 {"type": "text", "text": "wrote a.md"}]}},
             "not json at all\n",
             {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "半句"}}]
    f, rows = _drive_say(tmp_path, lines)
    assert rows == [] and f.rejected == 0, "非 JSON 行（假 agent 的輸出）不算形狀錯誤"


def test_say_strips_markdown_and_drops_pure_code_blocks(tmp_path) -> None:
    lines = _turn([{"type": "text", "text": "```python\nprint('x')\n```"}]) + \
            _turn([{"type": "text", "text": "## 計畫\n- **先**整理 `書架`\n- 再看[天氣](http://x)"}])
    _f, rows = _drive_say(tmp_path, lines)
    assert [r["text"] for r in rows] == ["計畫 先整理 書架 再看天氣"]


def test_say_without_events_path_is_a_noop(tmp_path) -> None:
    log = tmp_path / "agent_stdout.log"
    log.write_text(json.dumps({"type": "turn_start"}) + "\n", encoding="utf-8")
    f = twinagent.SayForwarder(log, None, task_id="twin:tw-x", cell_id="tw-x")
    f._pump()                                              # noqa: SLF001
    assert f.forwarded == 0 and f.sidecar_path is None


def _say(**kw):
    r = sc.say_row("我先整理書架。", turn=1, seq=1, cell_id="tw-x", run_id="R1")
    r.update(kw)
    return r


@pytest.mark.parametrize("field,value", [
    ("text", ""), ("text", "字" * 81), ("text", 5), ("truncated", "no"),
    ("turn", -1), ("seq", "1"), ("path", "a.md"), ("code", "x=1"),
])
def test_sidecar_validate_twin_say_has_teeth(field, value) -> None:
    assert sc.validate([_say()]) == [], "正控制"
    assert sc.validate([_say(**{field: value})]), (field, value)


def _lc(task_kind="practical", arm="RUN-ON"):
    return [{"schema": lifecycle.SCHEMA, "type": "run_started", "ts_ms": 1000, "run_id": "R1",
             "task_id": "twin:tw-x", "arm": arm, "attempt_limit": 1,
             "caller": {"cell_id": "tw-x", "resident": "x", "stratum": "twin",
                        "task_kind": task_kind}}]


def test_folder_turns_twin_say_into_a_tv_event_and_tv_contract_accepts_it() -> None:
    row = _say(); row["ts_ms"] = 2000
    fold = le.Folder(verify_url=None, mode=tv.MODE_LIVE)
    out = []
    for ev in _lc() + [row]:
        out += fold.feed(ev)
    says = [e for e in out if e["type"] == "twin_say"]
    assert len(says) == 1, (out, fold.dropped)
    e = says[0]
    assert (e["arm"], e["task_id"], e["text"], e["truncated"]) == ("ON", "tw-x", "我先整理書架。", False)
    assert not [b for b in tv.validate(out, require_settled=False) if "twin_say" in b], \
        tv.validate(out, require_settled=False)


def test_folder_drops_twin_say_for_a_code_cell_and_for_an_off_arm() -> None:
    for lc in (_lc(task_kind="code"), _lc(arm="RUN-OFF")):
        fold = le.Folder(verify_url=None, mode=tv.MODE_LIVE)
        out = []
        for ev in lc + [_say()]:
            out += fold.feed(ev)
        assert not [e for e in out if e["type"] == "twin_say"]
        assert fold.dropped


@pytest.mark.parametrize("field,value", [
    ("text", ""), ("text", "字" * 81), ("truncated", None), ("arm", "OFF"),
    ("path", "a.md"), ("content", "x"),
])
def test_tv_contract_twin_say_has_teeth(field, value) -> None:
    base = {"type": "twin_say", "ts": "2026-10-01T00:00:00Z", "task_id": "tw-x", "mode": "live",
            "arm": "ON", "seq": 1, "turn": 1, "text": "我先整理書架。", "truncated": False}
    assert not [b for b in tv.validate([base], require_settled=False) if "twin_say" in b]
    bad = dict(base, **{field: value})
    assert [b for b in tv.validate([bad], require_settled=False) if "twin_say" in b], (field, value)


def test_sidecar_merge_puts_say_inside_the_run_not_after_run_ended() -> None:
    lc = _lc() + [{"schema": lifecycle.SCHEMA, "type": "run_ended", "ts_ms": 9000, "run_id": "R1"}]
    r = _say(); r["ts_ms"] = 5000
    merged = sc.merge(lc, [r])
    assert [e["type"] for e in merged] == ["run_started", "twin_say", "run_ended"]


def test_twin_agent_sh_runs_pi_in_json_mode() -> None:
    sh = (ROOT / "ops/exhibit/twin/twin_agent.sh").read_text(encoding="utf-8")
    assert '-p --mode json' in sh
