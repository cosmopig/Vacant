"""ops/eval/replay_r534_gate_scores.py: the archive holds two campaigns; never merge silently (F06)."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import pathlib
import tarfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("replay_r534", ROOT / "ops/eval/replay_r534_gate_scores.py")
assert SPEC is not None and SPEC.loader is not None
replay_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(replay_mod)


def _chunk(path: pathlib.Path, cells: dict[str, tuple[bool, bool, bool]]) -> tuple[str, int]:
    """cells: name -> (hidden_pass, visible_pass, has solution.py)."""
    with tarfile.open(path, "w:xz") as tf:
        for name, (hidden, visible, has_file) in cells.items():
            blobs = {f"cells/{name}/score.json": json.dumps({"pass": hidden, "visible_pass": visible})}
            if has_file:
                blobs[f"cells/{name}/app_final/solution.py"] = "x = 1\n"
            for member, text in blobs.items():
                data = text.encode()
                info = tarfile.TarInfo(member)
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _archive(tmp_path: pathlib.Path) -> pathlib.Path:
    # calib1: A passes, C361 fails; c5: both pass the first task, only A the second
    chunks = {
        "chunk_0001.tar.xz": {"calib1-A-t1": (True, True, True), "calib1-C361-t1": (False, False, True)},
        "chunk_0006.tar.xz": {"c5-A-t1": (True, True, True), "c5-C361-t1": (True, True, True),
                              "c5-A-t2": (True, True, True), "c5-C361-t2": (False, True, True)},
    }
    rows = []
    for name, cells in chunks.items():
        sha, size = _chunk(tmp_path / name, cells)
        rows.append(f"{name}\t{sha}\t{size}\t{len(cells)}\t20260927T000000Z")
    manifest = tmp_path / "MANIFEST.tsv"
    manifest.write_text("\n".join(rows) + "\n")
    return manifest


def test_default_output_is_per_campaign_only_so_no_merged_number_leads_it(tmp_path):
    out = replay_mod.replay(_archive(tmp_path), tmp_path)
    assert set(out["campaigns"]) == {"c5", "calib1"}
    c5, calib = out["campaigns"]["c5"], out["campaigns"]["calib1"]
    assert (c5["arms"]["A"]["cells"], c5["arms"]["A"]["hidden_pass"]) == (2, 2)
    assert (c5["arms"]["C361"]["cells"], c5["arms"]["C361"]["hidden_pass"]) == (2, 1)
    assert c5["paired_hidden_pass"] == {"A=True,C361=False": 1, "A=True,C361=True": 1}
    assert calib["paired_hidden_pass"] == {"A=True,C361=False": 1}
    # nothing merged is printed unless asked for, and the top-level `arms` of the old
    # output (the merged totals, which led the printed JSON) is gone
    assert "arms" not in out and "paired_cells" not in out and "merged_arms" not in out
    assert "merged_note" not in out and out["archives_sha256_verified"] == 2
    first_keys = list(json.loads(json.dumps(out, sort_keys=True)))[:3]
    assert "arms" not in first_keys


def test_merged_totals_are_opt_in_and_named_merged(tmp_path):
    out = replay_mod.replay(_archive(tmp_path), tmp_path, merged=True)
    assert out["merged_arms"]["A"]["cells"] == 3 and out["merged_paired_cells"] == 3
    assert "arms" not in out and "paired_hidden_pass" not in out
    assert "merged_*" in out["merged_note"] and "campaigns.c5" in out["merged_note"]
    assert "below" not in out["merged_note"]          # the wording used to point the wrong way


def test_cli_prints_per_campaign_by_default(tmp_path, capsys, monkeypatch):
    manifest = _archive(tmp_path)
    monkeypatch.setattr("sys.argv", ["x", "--manifest", str(manifest),
                                     "--archive-root", str(tmp_path)])
    replay_mod.main()
    printed = capsys.readouterr().out
    assert '"merged' not in printed and printed.index('"campaigns"') < printed.index('"scope"')
    monkeypatch.setattr("sys.argv", ["x", "--manifest", str(manifest),
                                     "--archive-root", str(tmp_path), "--merged"])
    replay_mod.main()
    assert '"merged_arms"' in capsys.readouterr().out


def test_campaign_filter_reports_only_that_campaign(tmp_path):
    out = replay_mod.replay(_archive(tmp_path), tmp_path, campaign="c5")
    assert list(out["campaigns"]) == ["c5"]
    assert out["arms"]["A"]["cells"] == 2 and out["arms"]["C361"]["hidden_pass"] == 1
    assert out["paired_cells"] == 2 and out["campaign_filter"] == "c5"
    assert "campaigns.c5" in out["scope_note"]
    only_calib = replay_mod.replay(_archive(tmp_path), tmp_path, campaign="calib1")
    assert only_calib["arms"]["A"]["cells"] == 1 and only_calib["arms"]["C361"]["hidden_pass"] == 0
    # a filter that matches nothing is an empty result, not a silent merge
    assert replay_mod.replay(_archive(tmp_path), tmp_path, campaign="nope")["arms"] == {}


@pytest.mark.skipif(not os.environ.get("R534_ARCHIVE_ROOT"),
                    reason="set R534_ARCHIVE_ROOT to a directory holding MANIFEST.tsv and the 43 chunks")
def test_real_archive_c5_numbers_are_the_c5_readme_baseline():
    """F06: c5 alone (920 pairs) is the C5 README baseline 748/758; calib1 is 14/15 of 20."""
    root = pathlib.Path(os.environ["R534_ARCHIVE_ROOT"])
    out = replay_mod.replay(root / "MANIFEST.tsv", root)
    c5, calib = out["campaigns"]["c5"], out["campaigns"]["calib1"]
    assert [c5["arms"][a]["cells"] for a in ("A", "C361")] == [920, 920]
    assert [c5["arms"][a]["hidden_pass"] for a in ("A", "C361")] == [748, 758]
    assert [c5["arms"][a]["submitted_file"] for a in ("A", "C361")] == [878, 886]
    assert [c5["arms"][a]["gate_released_wrong"] for a in ("A", "C361")] == [89, 88]
    assert [c5["arms"][a]["gate_refused_file"] for a in ("A", "C361")] == [41, 40]
    assert c5["paired_hidden_pass"] == {"A=True,C361=True": 699, "A=False,C361=False": 113,
                                        "A=False,C361=True": 59, "A=True,C361=False": 49}
    assert [calib["arms"][a]["hidden_pass"] for a in ("A", "C361")] == [14, 15]
