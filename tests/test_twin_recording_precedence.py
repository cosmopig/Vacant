"""錄影撞 id 時誰贏＋事後稽核轉寫成旁註（2026-09-24 L-real 重錄收尾）。

兩條承重的判準：

  · `test_real_recording_beats_fixture_regardless_of_file_order`
      同一格同時在 fixture（L-none）與真跑（L-real）錄影裡 ⇒ **真跑的贏**，
      不管哪一份先載入。舊規則「先來的贏」讓 `lreal_*` 一格都播不出來。
  · `test_transcribed_sidecar_refuses_a_run_it_did_not_measure`
      `sidecar_from_postaudit` 只轉寫**綁得上錄影裡那一跑**的事後稽核：
      run 目錄的 `ws_end_sha256` 與錄影的 `run_ended` 對不上 ⇒ 整批不轉。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import serve_twin as S                          # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib                    # noqa: E402
from ops.exhibit.twin import sidecar_from_postaudit as sfp            # noqa: E402
from vacant_network.vrun import lifecycle                             # noqa: E402

REC_DIR = ROOT / "ops" / "exhibit" / "twin" / "recordings"
FIXTURE = REC_DIR / "fixture_20260924.jsonl"
LREAL = REC_DIR / "lreal_20260924.jsonl"
LREAL_RUNS = ROOT / "runs" / "twin_lreal_20260924"


def _write(path: pathlib.Path, evs: list[dict]) -> pathlib.Path:
    path.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in evs),
                    encoding="utf-8")
    return path


def _as_real(evs: list[dict]) -> list[dict]:
    """把 fixture 錄影改成「推得出 L-real」的樣子（只動推等級用到的兩個欄位）。"""
    out = []
    for e in evs:
        e = json.loads(json.dumps(e))
        if e["type"] == "run_started" and isinstance(e.get("caller"), dict):
            e["caller"]["declared_evidence"] = "L-real"
        if e["type"] == "run_ended":
            e["requests_seen"] = 3
        out.append(e)
    return out


@pytest.mark.parametrize("real_first", [False, True])
def test_real_recording_beats_fixture_regardless_of_file_order(tmp_path, real_first):
    evs = lifecycle.read(FIXTURE)
    fix = _write(tmp_path / "a_fixture.jsonl", evs)
    real = _write(tmp_path / "b_real.jsonl", _as_real(evs))
    order = [real, fix] if real_first else [fix, real]
    cells, info = S.load_recordings(order)
    assert cells and all(c["evidence"] == "L-real" for c in cells.values())
    assert {c["recording"] for c in cells.values()} == {S._rel(real)}
    by = {r["path"]: r for r in info}
    assert by[S._rel(fix)]["cells"] == 0
    assert by[S._rel(real)]["cells"] == len(cells)
    # 輸的那一份不是靜靜消失：每一格都講明為什麼沒播
    assert len(by[S._rel(fix)]["problems"]) == len(cells)


def test_same_level_collision_keeps_first(tmp_path):
    """負控制：同等級撞 id ⇒ 仍然先來的贏（新規則只在等級不同時換人）。"""
    evs = lifecycle.read(FIXTURE)
    a = _write(tmp_path / "a.jsonl", evs)
    b = _write(tmp_path / "b.jsonl", evs)
    cells, info = S.load_recordings([a, b])
    assert {c["recording"] for c in cells.values()} == {S._rel(a)}
    assert {r["path"]: r["cells"] for r in info}[S._rel(b)] == 0


def test_repo_recordings_play_the_real_run():
    """repo 的預設錄影組合：L-real 那份整批上得了電視，fixture 退居備援。"""
    if not LREAL.exists():
        pytest.skip("repo 裡沒有 L-real 錄影")
    cells, _ = S.load_recordings(S.default_recordings())
    assert cells and {c["recording"] for c in cells.values()} == {S._rel(LREAL)}


# ── 事後稽核轉寫 ─────────────────────────────────────────────────────────


def _mini_runs(tmp_path: pathlib.Path) -> pathlib.Path:
    """只複製轉寫會讀的兩個 JSON（run 目錄本體 19 MB，不必整份搬）。"""
    root = tmp_path / "runs_root"
    for d in (LREAL_RUNS / "runs").iterdir():
        dst = root / "runs" / d.name
        dst.mkdir(parents=True)
        for f in ("postaudit_RUN-OFF.json", "run_RUN-OFF.json"):
            if (d / f).exists():
                shutil.copy(d / f, dst / f)
    return root


@pytest.fixture()
def lreal_ready():
    if not (LREAL.exists() and LREAL_RUNS.exists()):
        pytest.skip("repo 裡沒有 L-real 錄影或它的 run 目錄")


def test_transcribed_sidecar_binds_every_off_run(lreal_ready, tmp_path):
    rows, problems = sfp.build(LREAL, _mini_runs(tmp_path))
    assert problems == []
    evs = lifecycle.read(LREAL)
    n_off = sum(1 for e in evs if e["type"] == "run_ended" and e["arm"] == "RUN-OFF"
                and not e.get("infra_void"))
    assert len(rows) == n_off
    assert sidecarlib.validate(rows, lifecycle_events=evs) == []
    for r in rows:
        assert r["is_verdict"] is False and r["signed"] is False
        assert r["when"] == sidecarlib.WHEN_AFTER and r["derived_from"]


def test_transcribed_sidecar_refuses_a_run_it_did_not_measure(lreal_ready, tmp_path):
    root = _mini_runs(tmp_path)
    victim = sorted((root / "runs").iterdir())[0] / "run_RUN-OFF.json"
    sm = json.loads(victim.read_text(encoding="utf-8"))
    sm["ws_end_sha256"] = "0" * 64
    victim.write_text(json.dumps(sm), encoding="utf-8")
    rows, problems = sfp.build(LREAL, root)
    assert rows == [] and any("ws_end_sha256" in p for p in problems)


def test_transcriber_will_not_overwrite_an_existing_sidecar(tmp_path):
    rec = _write(tmp_path / "r.jsonl", lifecycle.read(FIXTURE))
    sidecarlib.sidecar_path(rec).write_text("", encoding="utf-8")
    assert sfp.main(["--recording", str(rec), "--runs", str(tmp_path)]) == 1


def test_repo_lreal_sidecar_is_accepted_by_the_server(lreal_ready):
    cells, info = S.load_recordings([LREAL])
    rec = info[0]
    assert rec["sidecar"]["accepted"], rec["sidecar"]["problems"]
    assert rec["sidecar"]["rows"] == 54
