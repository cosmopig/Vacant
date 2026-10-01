"""P6 線 H：`twin_step.path_kind` 新增 `ground:<地點>`（2026-10-01）。

地點是 8 個固定代號的列舉；不帶檔名、不帶內容。每一條規則配負控制。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import live_events as le  # noqa: E402
from ops.exhibit.twin import sidecar as sc  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

PLACES = {"投遞口": "drop", "捏土處": "clay", "長桌廣場": "longtable", "石頭閘門": "gate",
          "帳本鏈": "chain", "草稿角": "draft", "紙卡地": "cards", "畫架與長椅": "easel"}


@pytest.mark.parametrize("place,code", sorted(PLACES.items()))
@pytest.mark.parametrize("tool", ["ws_read", "ws_write"])
def test_each_ground_place_maps_to_its_code(place, code, tool) -> None:
    assert sc.classify_path_kind(tool, f"地上/{place}/信.md") == f"ground:{code}"
    assert sc.classify_path_kind(tool, f"./地上/{place}/sub/x.txt") == f"ground:{code}"


def test_whitelists_agree_and_cover_all_eight() -> None:
    assert set(sc.PATH_KINDS) == set(tv.TWIN_PATH_KINDS)
    assert len(sc.GROUND_KINDS) == 8 and sc.GROUND_KINDS == tv.TWIN_GROUND_KINDS


@pytest.mark.parametrize("path", [
    "地上/不存在的地點/x.md",       # 地點代號不在列舉
    "地上/../TRAITS.md", "地上/投遞口/../../secret", "../地上/投遞口/x",  # 路徑穿越
    "地上", "地上/",
])
def test_unknown_place_or_traversal_is_other(path) -> None:
    assert sc.classify_path_kind("ws_read", path) == "other"


def test_non_ground_paths_keep_old_kinds_and_list_is_other() -> None:
    assert sc.classify_path_kind("ws_read", "TRAITS.md") == "traits"
    assert sc.classify_path_kind("ws_write", "letter.md") == "artifact"
    assert sc.classify_path_kind("ws_list", "地上/投遞口") == "other"
    assert sc.classify_path_kind("ws_read", "地上/投遞口/x.md") != "artifact"


def test_row_has_no_filename_and_passes_whole_chain() -> None:
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "地上/紙卡地/祕密檔名.md", "bytes": 9, "ok": True},
                           cell_id="tw-x", run_id="r1")
    assert row["path_kind"] == "ground:cards"
    assert "祕密檔名" not in str(row)
    lc = {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
          "arm": "RUN-ON", "task_id": "twin:tw-x", "retry": "none",
          "caller": {"cell_id": "tw-x", "resident": "R1", "prompt": "p", "stratum": "twin",
                     "task_kind": tv.KIND_PRACTICAL}}
    assert sc.validate([row], lifecycle_events=[lc]) == []
    f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
    opened = f.feed(lc)
    out = f.feed(row)
    assert len(out) == 1 and out[0]["path_kind"] == "ground:cards"
    assert tv.validate(opened + out, require_settled=False) == []


def test_negative_control_bad_ground_code_rejected_by_both_gates() -> None:
    row = sc.twin_step_row({"ts_ms": 1500, "seq": 1, "tool": "ws_read",
                            "path": "地上/紙卡地/x", "bytes": 9, "ok": True},
                           cell_id="tw-x", run_id="r1")
    row["path_kind"] = "ground:moon"
    lc = {"schema": lifecycle.SCHEMA, "type": "run_started", "run_id": "r1", "ts_ms": 1000,
          "arm": "RUN-ON", "task_id": "twin:tw-x", "retry": "none",
          "caller": {"cell_id": "tw-x", "resident": "R1", "prompt": "p", "stratum": "twin",
                     "task_kind": tv.KIND_PRACTICAL}}
    assert sc.validate([row], lifecycle_events=[lc])
    f = le.Folder(verify_url="/r/{cell}", mode=tv.MODE_LIVE)
    f.feed(lc)
    assert f.feed(row) == [] and f.dropped
