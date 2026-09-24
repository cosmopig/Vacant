"""VM 跑法與「展期結束即刪」（2026-09-24 人類裁決）的判準。

* `close_exhibition.py`：dry-run 一個檔都不動、真刪之後原文類產物全不在、收據仍驗得過、
  撤回過的人正確略過、同一個展期名重跑不重複寫、**負控制**（故意留一份 wire log、
  刪不掉的 wire log、事件檔裡混進原文）⇒ 抹除證明說不乾淨；
* 磁碟水位閘門：低於門檻不起新的 run、畫面（`intake`）講得出來、量不到不是「夠」；
* 圍牆那一層（`twinenclose.py`）在任何平台都量得到的部分：事件轉送的驗收規則、
  `build_twin` 的三個新退化、`enclose=on` 起不來就不起 pi；
* VM 冒煙證據真的在盤上、說的是它說的那件事。

⚠ 本檔零模型呼叫（假上游＋fixture agent，照 `test_twin_agent_run.py`）。
圍牆本身（bwrap／netns）只在 Linux 上存在——那一半的證據是 VM 實跑的
`ops/exhibit/twin/evidence_vm_20260924/`，這裡驗它落盤的內容。
"""
from __future__ import annotations

import json
import os
import pathlib
import platform
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from test_twin_agent_run import (  # noqa: E402,F401
    TRAITS_TEXT, _all_bytes_under, _ingest, env, upstream)

from ops.exhibit.twin import close_exhibition as closer  # noqa: E402
from ops.exhibit.twin import twinagent, twinenclose, twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import KIND_NOTE, TwinStore  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402
from vacant_network.vrun import verify_receipts as vrr  # noqa: E402

EVID = ROOT / "ops" / "exhibit" / "twin" / "evidence_vm_20260924"
CLOSE = ROOT / "ops" / "exhibit" / "twin" / "close_exhibition.py"


def _snapshot(root: pathlib.Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


def _two_twins_ran(env, monkeypatch) -> tuple[TwinStore, list[str]]:
    st, cfg = env["store"], env["cfg"]
    a = _ingest(st, monkeypatch, "sub-秘密-A")
    b = _ingest(st, monkeypatch, "sub-秘密-B")
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["generated"] == 2 and r["degraded"] == 0, r
    return st, [a, b]


def _close(env, **kw):
    st = env["store"]
    return closer.close(pathlib.Path(st.path), kw.pop("name", "t-2026"),
                        work_root=env["cfg"].work_root,
                        events=[env["cfg"].events_path], **kw)


# ---------------------------------------------------------------------------
# 一、閉展即刪
# ---------------------------------------------------------------------------

def test_dry_run_deletes_nothing_and_writes_no_proof(env, monkeypatch) -> None:
    st, _ = _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    before = _snapshot(wr)
    n_events = st.count()
    out = _close(env, dry_run=True)
    assert _snapshot(wr) == before, "dry-run 動了檔"
    assert st.count() == n_events, "dry-run 往鏈上寫了東西"
    s = out["summary"]
    assert s["dry_run"] is True and s["would_erase_files"] > 0 and s["would_erase_bytes"] > 0
    assert {r["action"] for r in out["rows"] if r["kind"] == "twin"} == {"would_erase"}
    assert not list(pathlib.Path(st.path).parent.glob("*.close_*.jsonl")), "dry-run 寫了證明檔"
    # 負控制：dry-run 列出來的東西裡**真的有**原文（下面真刪要刪的就是它）
    assert TRAITS_TEXT.encode("utf-8") in _all_bytes_under(wr)


def test_close_erases_plaintext_keeps_receipts_that_still_verify(env, monkeypatch) -> None:
    st, sids = _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    assert TRAITS_TEXT.encode("utf-8") in _all_bytes_under(wr)          # 負控制
    out = _close(env, dry_run=False)
    s = out["summary"]
    assert s["clean"] is True, json.dumps(s, ensure_ascii=False)[:800]
    assert s["residue"] == [] and s["problems"] == []
    assert s["receipts_verified"] == 2 and s["receipts_failed"] == 0
    assert s["twinstore_chain"]["ok"] is True
    assert TRAITS_TEXT.encode("utf-8") not in _all_bytes_under(wr), "閉展後還找得到原文"
    for sid in sids:
        ws, rd = twinagent.paths_for(wr, sid)
        assert not ws.exists()
        assert sorted(c.name for c in rd.iterdir()) == sorted(twinagent.KEEP_ON_ERASE)
        assert [x["verdict"] for x in vrr.verify_run(rd)] == ["OK"], "留了收據卻驗不過"
    rows = [r for r in out["rows"] if r["kind"] == "twin"]
    assert all(r["action"] == "erased" and r["files_erased"] > 0 for r in rows)
    what = {e["what"] for r in rows for e in r["erased"]}
    assert {"workspace", "wire_RUN-ON", "_frozen_RUN-ON", "agent_stdout.log",
            "run_RUN-ON.json"} <= what
    # 抹除證明：一位一列＋總結；**不帶原文、不帶 sub_id**（那是撤回的能力憑證）
    proof = pathlib.Path(s["proof_path"])
    lines = [json.loads(x) for x in proof.read_text(encoding="utf-8").splitlines()]
    assert [x["kind"] for x in lines] == ["twin", "twin", "summary"]
    blob = proof.read_text(encoding="utf-8")
    for bad in [TRAITS_TEXT] + sids:
        assert bad not in blob, f"抹除證明裡有 {bad[:8]}"
    assert {x["twin_id"] for x in lines[:2]} == {twinagent.public_twin_id(s_) for s_ in sids}
    # 鏈上每位一列 note（只有類別與計數）
    for sid in sids:
        notes = [e["payload"] for e in st.events(sub_id=sid, kind=KIND_NOTE)
                 if e["payload"].get("twinlink_event") == closer.CLOSE_EVENT]
        assert len(notes) == 1 and TRAITS_TEXT not in json.dumps(notes, ensure_ascii=False)


def test_withdrawn_people_are_skipped_without_error_or_duplicate(env, monkeypatch) -> None:
    st, (a, b) = _two_twins_ran(env, monkeypatch)
    w = twinlink.withdraw(st, a)
    assert w["fully_erased"] is True
    out = _close(env, dry_run=False)
    by = {r["twin_id"]: r for r in out["rows"] if r["kind"] == "twin"}
    ra, rb = by[twinagent.public_twin_id(a)], by[twinagent.public_twin_id(b)]
    assert ra["action"] == "already_erased" and ra["problems"] == [] and ra["clean"]
    assert ra["receipts_after"] == ["OK"], "撤回者留下的收據閉展後仍要驗得過"
    assert rb["action"] == "erased"
    assert out["summary"]["clean"] is True
    closes_a = [e for e in st.events(sub_id=a, kind=KIND_NOTE)
                if e["payload"].get("twinlink_event") == closer.CLOSE_EVENT]
    assert closes_a == [], "撤回過的人不該再多一列閉展 note"


def test_rerun_same_exhibition_is_idempotent(env, monkeypatch) -> None:
    st, sids = _two_twins_ran(env, monkeypatch)
    _close(env, dry_run=False)
    n = st.count()
    out2 = _close(env, dry_run=False)
    assert {r["action"] for r in out2["rows"] if r["kind"] == "twin"} == {"already_closed"}
    assert st.count() == n, "重跑又往鏈上寫了"
    assert out2["summary"]["clean"] is True


def test_negative_control_stray_wire_log_makes_proof_unclean(env, monkeypatch) -> None:
    """有人把 wire log 複製到別處 ⇒ 「刪了我們知道的那幾個」不准回綠。"""
    st, (a, _) = _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    _, rd = twinagent.paths_for(wr, a)
    src = sorted((rd / "wire_RUN-ON").glob("*.req.bin"))[0]
    stray = wr / "backup" / "wire_RUN-ON"
    stray.mkdir(parents=True)
    (stray / src.name).write_bytes(src.read_bytes())
    out = _close(env, dry_run=False)
    s = out["summary"]
    assert s["clean"] is False
    assert any(x["category"] == "wire_log" and "backup" in x["path"] for x in s["residue"])


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0,
                    reason="要靠目錄權限讓 unlink 失敗；root 無視權限")
def test_negative_control_undeletable_wire_log_is_reported(env, monkeypatch) -> None:
    st, (a, _) = _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    _, rd = twinagent.paths_for(wr, a)
    wire = rd / "wire_RUN-ON"
    os.chmod(wire, 0o500)
    try:
        out = _close(env, dry_run=False)
    finally:
        os.chmod(wire, 0o700)
    s = out["summary"]
    assert s["clean"] is False and s["problems"], s
    row = [r for r in out["rows"] if r.get("twin_id") == twinagent.public_twin_id(a)][0]
    assert row["clean"] is False
    assert any(x["category"] == "wire_log" for x in s["residue"])


def test_negative_control_viewer_text_in_event_file_is_caught(env, monkeypatch) -> None:
    """事件檔設計上不帶原文；**混進去了**要量得到（不然「沒有」只是沒量）。"""
    st, _ = _two_twins_ran(env, monkeypatch)
    ev = env["cfg"].events_path
    clean = _close(env, dry_run=True)["summary"]["content_scan"]
    assert clean["clean"] is True and clean["subjects_scanned"] == 2
    with ev.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"leak": TRAITS_TEXT}, ensure_ascii=False) + "\n")
    dirty = _close(env, dry_run=True)["summary"]["content_scan"]
    assert dirty["clean"] is False and dirty["hits_by_file"] == {str(ev): 2}


def test_orphan_run_dirs_are_erased_too(env, monkeypatch) -> None:
    """庫裡對不到人的 slug（探針、別的庫留下的）一樣刪、一樣留收據。"""
    _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    (wr / "ws" / ("f" * 32)).mkdir(parents=True)
    (wr / "ws" / ("f" * 32) / "TRAITS.md").write_text(TRAITS_TEXT, encoding="utf-8")
    (wr / "doors" / ("f" * 32) / "wire").mkdir(parents=True)
    (wr / "doors" / ("f" * 32) / "wire" / "0001.req.bin").write_text(TRAITS_TEXT, "utf-8")
    out = _close(env, dry_run=False)
    assert out["summary"]["clean"] is True and out["summary"]["orphans"] == 1
    assert TRAITS_TEXT.encode("utf-8") not in _all_bytes_under(wr)


def test_cli_requires_matching_confirmation(env, monkeypatch) -> None:
    st, _ = _two_twins_ran(env, monkeypatch)
    wr = env["cfg"].work_root
    before = _snapshot(wr)
    envv = dict(os.environ, VACANT_TWIN_AGENTRUNS=str(wr))
    r = subprocess.run([sys.executable, str(CLOSE), "--db", str(st.path),
                        "--exhibition", "a-2026", "--yes-close", "b-2026"],
                       capture_output=True, text=True, env=envv)
    assert r.returncode == 2 and "不一樣" in r.stderr
    assert _snapshot(wr) == before
    r2 = subprocess.run([sys.executable, str(CLOSE), "--db", str(st.path),
                         "--exhibition", "a-2026"], capture_output=True, text=True, env=envv)
    assert r2.returncode == 2, "沒有 --dry-run 也沒有 --yes-close 不准跑"
    r3 = subprocess.run([sys.executable, str(CLOSE), "--db", str(st.path) + ".nope",
                         "--exhibition", "a-2026", "--dry-run"],
                        capture_output=True, text=True, env=envv)
    assert r3.returncode == 2 and "庫不在" in r3.stderr
    r4 = subprocess.run([sys.executable, str(CLOSE), "--db", str(st.path),
                         "--exhibition", "a-2026", "--yes-close", "a-2026"],
                        capture_output=True, text=True, env=envv)
    assert r4.returncode == 0, r4.stdout[-800:] + r4.stderr[-800:]
    assert TRAITS_TEXT.encode("utf-8") not in _all_bytes_under(wr)


def test_close_is_not_wired_into_the_loop() -> None:
    """閉展是人按的：loop／開機腳本／unit 裡**不准**出現它。"""
    twin = ROOT / "ops" / "exhibit" / "twin"
    for p in [twin / "twinlink.py", twin / "twin_loop.sh", twin / "exhibit_boot.sh",
              *(twin / "systemd").glob("*")]:
        assert "close_exhibition" not in p.read_text(encoding="utf-8"), p.name
    # 正控制：同一個 grep 打在它自己身上會中
    assert "close_exhibition" in CLOSE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 二、磁碟水位閘門
# ---------------------------------------------------------------------------

def test_disk_watermark_holds_new_twins_and_says_so(env, monkeypatch, capsys) -> None:
    st, cfg = env["store"], env["cfg"]
    sid = _ingest(st, monkeypatch)
    monkeypatch.setenv(twinagent.ENV_MIN_FREE_MB, str(10 ** 9))   # 1 PB：一定不夠
    r = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r["held_for_disk"] == 1 and r["submitted"] == 0 and r["generated"] == 0
    assert r["intake"]["accepting"] is False and "暫停收新分身" in r["intake"]["reason"]
    assert sid in st.pending("generated"), "被擋下的人要留在佇列裡，不是被丟掉"
    assert "intake_paused" in capsys.readouterr().err, "log 裡要講"
    v = twinlink.build_view(st)
    assert v["intake"]["accepting"] is False, "畫面要講得出來"
    assert v["counts"]["waiting"] >= 0
    # 負控制：同一條路徑、門檻放回正常 ⇒ 真的起 run
    monkeypatch.setenv(twinagent.ENV_MIN_FREE_MB, "1")
    r2 = twinlink.generate(st, env["upstream"], "m", agent=cfg)
    assert r2["held_for_disk"] == 0 and r2["generated"] == 1
    assert twinlink.build_view(st)["intake"]["accepting"] is True


def test_unmeasurable_disk_is_not_enough(tmp_path, monkeypatch) -> None:
    def boom(_p):
        raise OSError("no statvfs")
    monkeypatch.setattr(twinagent.shutil, "disk_usage", boom)
    s = twinagent.intake_status(tmp_path)
    assert s["accepting"] is False and s["free_bytes"] is None and "量不到" in s["reason"]


def test_bad_watermark_env_falls_back_to_default_not_zero(monkeypatch) -> None:
    monkeypatch.setenv(twinagent.ENV_MIN_FREE_MB, "很多")
    assert twinagent.min_free_bytes() == twinagent.DEFAULT_MIN_FREE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# 三、圍牆那一層（平台無關的部分）
# ---------------------------------------------------------------------------

def _caller() -> dict:
    return {"cell_id": "tw-x", "resident": "r", "stratum": "twin",
            "prompt": twinagent.CALLER_PROMPT, "declared_evidence": ""}


def test_event_forwarder_only_passes_contract_lines(tmp_path) -> None:
    part, dst = tmp_path / "part.jsonl", tmp_path / "live.jsonl"
    em = lifecycle.Emitter(part, task_id="twin:tw-x", arm="RUN-ON")
    em.emit("run_started", vacant=True, retry="none", max_attempts=1,
            feedback_into="file", ws_start_sha256="0" * 64, caller=_caller())
    em.emit("model_call", attempt=1, n_total=1, wire="openai", blocked=False,
            error=None, elapsed_s=0.1)
    with part.open("a", encoding="utf-8") as f:
        for bad in (
            {"schema": lifecycle.SCHEMA, "type": "model_call", "task_id": "twin:tw-OTHER"},
            {"schema": lifecycle.SCHEMA, "type": "model_call", "task_id": "twin:tw-x",
             "messages": [TRAITS_TEXT]},
            {"schema": lifecycle.SCHEMA, "type": "run_started", "task_id": "twin:tw-x",
             "caller": {**_caller(), "prompt": TRAITS_TEXT}},
            {"schema": "evil/1", "type": "model_call", "task_id": "twin:tw-x"},
        ):
            f.write(json.dumps(bad, ensure_ascii=False) + "\n")
        f.write("not json\n")
        f.write(json.dumps({"schema": lifecycle.SCHEMA, "type": "model_call",
                            "task_id": "twin:tw-x", "pad": "x" * 9000}) + "\n")
    fwd = twinenclose.EventForwarder(part, dst, task_id="twin:tw-x", caller=_caller(),
                                     poll_s=0.01)
    fwd.start()
    fwd.finish()
    assert fwd.forwarded == 2 and fwd.rejected == 6
    got = lifecycle.read(dst)
    assert [e["type"] for e in got] == ["run_started", "model_call"]
    assert lifecycle.validate_stream(got) == []
    assert TRAITS_TEXT not in dst.read_text(encoding="utf-8")


def _res(**over) -> dict:
    base = {"sub_id": "s", "twin_id": "tw-x", "error": None, "enclosed": True,
            "require_tier": "B", "wall_s": 1.0,
            "summary": {"stop_reason": "ungated", "accepted": None, "requests_seen": 3,
                        "count_semantics": "exact", "tier": "B",
                        "enclosure_applied": True, "receipt_verdicts": ["OK"],
                        "twin_enclosure": {"door_calls": 3, "door_excess": 0}},
            "outputs": {"decision": "寫一封信", "reason": "因為", "artifacts": [],
                        "has_plan": True}}
    for k, v in over.items():
        if k in base["summary"]:
            base["summary"][k] = v
        else:
            base[k] = v
    return base


@pytest.mark.parametrize("over,kind", [
    ({"twin_enclosure": {"door_calls": 4, "door_excess": 1}}, "door_unreconciled"),
    ({"twin_enclosure": {"door_calls": None, "door_excess": None}}, "door_unreconciled"),
    ({"receipt_verdicts": ["BROKEN"]}, "receipt_unverified"),
    ({"tier": "C"}, "tier_below_required"),
    ({"tier": None}, "tier_below_required"),
])
def test_enclosed_run_degrades_on_bypass_bad_receipt_or_low_tier(over, kind) -> None:
    t = twinagent.build_twin(_res(**over), model="m", fallback=twinlink.fallback_twin)
    assert t["engine"] == "fallback_deterministic" and t["degrade_kind"] == kind


def test_enclosed_clean_run_is_a_real_run_and_carries_tier() -> None:
    """正控制：上面那幾格的退化不是因為 build_twin 一律退化。"""
    t = twinagent.build_twin(_res(), model="m", fallback=twinlink.fallback_twin)
    assert t["engine"] == "vacant_run:pi:m"
    assert t["tier"] == "B" and t["enclosed"] is True and t["door_calls"] == 3


def test_tier_rank() -> None:
    assert twinagent.meets_tier("A", "B") and twinagent.meets_tier("B", "B")
    assert not twinagent.meets_tier("B'", "B") and not twinagent.meets_tier("C", "B")
    assert not twinagent.meets_tier(None, "B") and twinagent.meets_tier(None, None)


def test_enclose_on_without_enclosure_refuses_to_start_pi(env, monkeypatch) -> None:
    cfg = env["cfg"]
    cfg.enclose = "on"
    monkeypatch.setattr(twinenclose, "available", lambda force=False: (False, "沒有 bwrap"))
    ok, why = twinagent.agent_available(cfg)
    assert ok is False and "圍牆起不來" in why and "沒有 bwrap" in why
    cfg.enclose = "auto"
    assert twinagent.agent_available(cfg)[0] is True, "auto 起不來就退回不圍（照實記）"
    assert twinagent.use_enclosure(cfg) == (False, "沒有 bwrap")


@pytest.mark.skipif(platform.system() == "Linux", reason="Linux 上可能真的起得來")
def test_enclosure_says_why_it_is_unavailable_here() -> None:
    ok, why = twinenclose.available(force=True)
    assert ok is False and "不是 Linux" in why


def test_erase_removes_the_door_journal(tmp_path) -> None:
    sid = "sub-door"
    door = tmp_path / "doors" / twinagent.slug_for(sid) / "wire"
    door.mkdir(parents=True)
    (door / "0001.req.bin").write_text(TRAITS_TEXT, encoding="utf-8")
    assert twinagent.run_artifacts_present(tmp_path, sid) is True
    rec = twinagent.erase_run_artifacts(tmp_path, sid)
    assert [e["what"] for e in rec["erased"]] == ["door_journal"] and not rec["problems"]
    assert twinagent.run_artifacts_present(tmp_path, sid) is False


def test_loop_print_cmd_shows_enclosure_and_tier() -> None:
    envv = dict(os.environ, VACANT_TWIN_CLOUD_TOKEN="SEKRIT-9f2", VACANT_TWIN_ENCLOSE="on",
                VACANT_TWIN_REQUIRE_TIER="B")
    r = subprocess.run(["bash", str(ROOT / "ops/exhibit/twin/twin_loop.sh"), "--print-cmd"],
                       capture_output=True, text=True, env=envv)
    assert r.returncode == 0
    assert "--enclose on" in r.stdout and "--require-tier B" in r.stdout
    assert "SEKRIT-9f2" not in r.stdout and "--token ***" in r.stdout
    # 負控制：不設就是 off（舊行為），而且照樣寫在命令列上
    envv.pop("VACANT_TWIN_ENCLOSE")
    envv.pop("VACANT_TWIN_REQUIRE_TIER")
    r2 = subprocess.run(["bash", str(ROOT / "ops/exhibit/twin/twin_loop.sh"), "--print-cmd"],
                        capture_output=True, text=True, env=envv)
    assert "--enclose off" in r2.stdout and "--require-tier" not in r2.stdout


def test_both_units_read_the_same_paths_file() -> None:
    sysd = ROOT / "ops" / "exhibit" / "twin" / "systemd"
    for u in ("vacant-exhibit.service", "vacant-twin-loop.service"):
        assert "EnvironmentFile=-/etc/vacant/twin-paths.env" in (sysd / u).read_text("utf-8")
    # token 只在 loop 那一支（電視那一支拿到 token 會自己再起一個 loop）
    assert "/etc/vacant/twin.env" not in (sysd / "vacant-exhibit.service").read_text("utf-8")


# ---------------------------------------------------------------------------
# 四、VM 冒煙證據（實跑落盤；這裡驗它說的是它說的那件事）
# ---------------------------------------------------------------------------

def test_vm_enclosure_probe_evidence() -> None:
    d = json.loads((EVID / "probe_twin_enclosure.json").read_text(encoding="utf-8"))
    j = d["judgement"]
    assert j["mismatched"] == 0
    assert all(j["checks"].values()), j["checks"]
    rows = {r["target"]: r for r in j["targets"]}
    for t in ("tcp_upstream_direct", "tcp_internet", "dns", "tcp_host_loopback",
              "unix_host_path", "read_other_twin", "read_store", "read_home",
              "write_outside"):
        assert rows[t]["negctl"] is True and rows[t]["enc"] is False, t
    for t in ("model_via_vacant", "write_own_ws"):
        assert rows[t]["negctl"] is True and rows[t]["enc"] is True, t
    assert d["cells"]["negctl"]["tier"] == "C" and d["cells"]["enc"]["tier"] == "B"
    assert d["cells"]["enc_bypass"]["twin_enclosure"]["door_excess"] >= 1


def test_vm_smoke_evidence() -> None:
    d = json.loads((EVID / "smoke_vm_report.json").read_text(encoding="utf-8"))
    s = d["steps"]
    assert d["synthetic"] is True
    t = s["4_twin"]
    assert t["engine"].startswith("vacant_run:pi:") and t["tier"] == "B"
    assert t["enclosed"] is True and t["enclosure_applied"] is True
    assert t["door_calls"] == t["requests_seen"] > 0
    assert t["receipts"] == [{"verdict": "OK", "tier": "B", "mediated": True}]
    assert t["lifecycle"]["validate_stream"] == []
    assert s["6_disk_gate"]["held_for_disk"] == 1 and s["6_disk_gate"]["submitted"] == 0
    assert s["6_disk_gate"]["held_person_still_pending"] is True
    c = s["7_close"]
    assert c["dry_run_changed_nothing"] is True and c["close_rc"] == 0
    assert c["summary"]["clean"] is True and c["summary"]["residue"] == []
    assert c["receipts_after_close"] == ["OK"]
    assert set(c["synthetic_text_hits"].values()) == {0}
    assert all(p.split("/")[-1] in twinagent.KEEP_ON_ERASE for p in c["work_root_files_left"])
    assert d["units_left_after_stop"] == []
    f = (EVID / "from_1003.txt").read_text(encoding="utf-8")
    for port in ("18899/state 200", "18901/visitors.json 200", "18420/world3/index.html 200"):
        assert port in f, f"1003 敲不到 VM 的 {port}"
    assert "UNITS_LEFT=0" in (EVID / "teardown.txt").read_text(encoding="utf-8")
    assert "BASE_EXISTS=no" in (EVID / "teardown.txt").read_text(encoding="utf-8")
    # 事件檔（公開、append-only）不帶原文：合成特質在它裡面零命中
    ev = (EVID / "lifecycle.jsonl").read_text(encoding="utf-8")
    assert "陽台" not in ev and "合成的特質" not in ev


def test_enclosure_refuses_run_products_inside_the_repo(tmp_path) -> None:
    """repo 是唯讀綁進圍牆的 ⇒ run 產物住在 repo 底下＝別人的 wire log 在圍牆裡讀得到。"""
    inside = ROOT / "ops" / "exhibit" / "twin" / "store" / "x.agentruns"
    with pytest.raises(RuntimeError, match="repo"):
        twinenclose.run_enclosed(
            argv=["true"], workspace=inside / "ws" / "a", run_dir=inside / "runs" / "a",
            door_dir=inside / "doors" / "a", task_id="twin:tw-x", timeout_s=5,
            events_path=None, events_caller=_caller(), endpoint="http://127.0.0.1:9/v1",
            model="m")
    assert not inside.exists(), "擋門要在建任何目錄之前"


def test_loop_refuses_enclosure_with_store_inside_repo(tmp_path) -> None:
    envv = dict(os.environ, VACANT_TWIN_CLOUD_TOKEN="x", VACANT_TWIN_ENCLOSE="on",
                VACANT_TWIN_INIT="1", VACANT_TWIN_OUT=str(tmp_path / "v.json"))
    envv.pop("VACANT_TWIN_DB", None)
    r = subprocess.run(["bash", str(ROOT / "ops/exhibit/twin/twin_loop.sh"), "--rounds", "1"],
                       capture_output=True, text=True, env=envv, timeout=60)
    assert r.returncode == 2 and "庫在 repo 底下" in r.stderr, r.stderr[-500:]
    # 負控制：庫在 repo 外面就不擋這一條（改成 --print-cmd 以免真的跑 loop）
    envv["VACANT_TWIN_DB"] = str(tmp_path / "t.sqlite3")
    r2 = subprocess.run(["bash", str(ROOT / "ops/exhibit/twin/twin_loop.sh"), "--print-cmd"],
                        capture_output=True, text=True, env=envv, timeout=60)
    assert r2.returncode == 0 and "庫在 repo 底下" not in r2.stderr
