"""P20261113_1358-3（D4）：凍結 spec 載入器 vacant_network.reqloop.specs 的正/負控制。

背景：G4 的 per-task 凍結規格綁定在 ops/reqloop/g4/manifest.json 的 specs
（每題 file＋spec_sha256）。此前任何管線要用 spec 都得自己解析 manifest＋自己
驗 hash，無唯一核驗口（H-8：renderer 是 trusted input，必須有唯一核驗口）。
specs.load_frozen_specs 是唯一入口：逐檔核驗、任一失敗 SpecIntegrityError
fail-closed、不返回部分結果（I-4：未測量不是通過）。

spec_sha256 口徑＝整份規格（除本欄）canonical JSON 之 sha256
（freeze_specs.py:13-14、RequirementSet.verify_self_hash 同口徑），非檔案原始位元組 hash。

本測試純離線：0 model calls、不發網路；臨時檔走 pytest tmp_path。
"""
from __future__ import annotations

import ast
import json
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "ops/reqloop/g4/manifest.json"
REAL_TASKS = {"dab_725", "dab_587", "dab_657", "dab_517"}


def _flip_hex(hex64: str) -> str:
    """改一位：第一碼 0↔1。"""
    return ("1" if hex64[0] != "1" else "0") + hex64[1:]


def _entry_for(path: pathlib.Path) -> dict:
    """對一份真實凍結規格算出合法 manifest entry（自校驗必須先過）。"""
    from vacant_network.reqloop.requirements import RequirementSet
    rs = RequirementSet.load(path)
    ok, msg = rs.verify_self_hash()
    assert ok, msg
    return {"file": str(path), "spec_sha256": rs.spec_sha256, "n_items": len(rs.items)}


def _copy_spec(name: str, tmp_path: pathlib.Path) -> pathlib.Path:
    src = REPO_ROOT / "ops/reqloop/g4/specs" / f"{name}.json"
    dst = tmp_path / f"{name}.json"
    dst.write_bytes(src.read_bytes())
    return dst


def _write_manifest(tmp_path: pathlib.Path, specs: dict) -> pathlib.Path:
    m = {"v": 1, "experiment": "G4-test", "tasks": list(specs), "specs": specs}
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(m), encoding="utf-8")
    return p


def test_positive_repo_manifest_all_four_tasks_verified():
    """正控制：repo 現行 manifest → 4 task 全回、hash 全驗。"""
    from vacant_network.reqloop.specs import load_frozen_specs
    out = load_frozen_specs(MANIFEST)
    assert set(out) == REAL_TASKS
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for tid, spec in out.items():
        assert isinstance(spec, dict)
        assert spec["task_id"] == tid
        assert len(spec["items"]) == manifest["specs"][tid]["n_items"]


def test_negative_hash_flip_one_char_names_task(tmp_path):
    """負 1：spec_sha256 改一位 → 必拋 SpecIntegrityError 且點名 task_id。"""
    from vacant_network.reqloop.specs import SpecIntegrityError, load_frozen_specs
    f = _copy_spec("dab_725", tmp_path)
    entry = _entry_for(f)
    entry["spec_sha256"] = _flip_hex(entry["spec_sha256"])
    m = _write_manifest(tmp_path, {"dab_725": entry})
    with pytest.raises(SpecIntegrityError) as ei:
        load_frozen_specs(m)
    assert ei.value.task_id == "dab_725"
    assert "dab_725" in str(ei.value)
    # 期望/實際各帶前 8 hex，供人一眼看出是哪一邊漂了
    assert len(ei.value.expected) == 8 and len(ei.value.actual) == 8


def test_negative_spec_file_deleted_no_partial_result(tmp_path):
    """負 2：spec 檔被刪 → 必拋、不返回部分結果（另一題合法也整批拒）。"""
    from vacant_network.reqloop.specs import SpecIntegrityError, load_frozen_specs
    ok_file = _copy_spec("dab_587", tmp_path)
    ghost = tmp_path / "dab_999.json"
    ghost.write_text("{}", encoding="utf-8")
    ghost.unlink()  # 檔缺
    specs = {
        "dab_587": _entry_for(ok_file),
        "dab_999": {"file": str(ghost), "spec_sha256": "ab" * 32},
    }
    m = _write_manifest(tmp_path, specs)
    with pytest.raises(SpecIntegrityError) as ei:
        load_frozen_specs(m)  # 拋出＝無任何 dict 回傳，即無部分結果
    assert ei.value.task_id == "dab_999"


def test_negative_manifest_without_specs_key_or_missing(tmp_path):
    """負 3：manifest 無 specs 鍵 → 必拋；manifest 檔不存在 → 必拋（不靜默 fallback）。"""
    from vacant_network.reqloop.specs import SpecIntegrityError, load_frozen_specs
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps({"v": 1, "tasks": ["dab_725"]}), encoding="utf-8")
    with pytest.raises(SpecIntegrityError) as ei:
        load_frozen_specs(p)
    assert "specs" in str(ei.value)
    with pytest.raises(SpecIntegrityError):
        load_frozen_specs(tmp_path / "no_such_manifest.json")


def test_load_frozen_specs_accepts_dict_input():
    """D4 dict 入參（P20261113_1810-1）：(a) json.loads 的 manifest dict→4 題；
    (b) dict 內篡改 spec_sha256→點名題號（密碼學檢驗不移除）；(c) 無 specs 鍵→必拋。"""
    from vacant_network.reqloop.specs import SpecIntegrityError, load_frozen_specs
    # (a) 正控制：同一份 repo manifest，記憶體內 dict 輸入→4 題全回
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(load_frozen_specs(m)) == REAL_TASKS
    # (b) 負：dict 內 spec_sha256 改一位→必拋、點名題號
    bad = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad["specs"]["dab_725"]["spec_sha256"] = _flip_hex(bad["specs"]["dab_725"]["spec_sha256"])
    with pytest.raises(SpecIntegrityError) as ei:
        load_frozen_specs(bad)
    assert ei.value.task_id == "dab_725" and "dab_725" in str(ei.value)
    # (c) 負：無 specs 鍵→必拋，且點名 _manifest_path 來源
    with pytest.raises(SpecIntegrityError) as ei2:
        load_frozen_specs({"v": 1, "tasks": ["dab_725"], "_manifest_path": "in-mem.json"})
    assert "in-mem.json" in str(ei2.value)


def test_specs_module_imports_without_model_channel():
    """綠燈：specs.py 直接 import 面只有標準庫＋同包（requirements 鏈），不牽動模型通道。"""
    import vacant_network.reqloop.specs as S  # import 本身即測：不發任何網路
    src = (REPO_ROOT / "vacant_network" / "reqloop" / "specs.py").read_text(encoding="utf-8")
    mods: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            mods.add(node.module.split(".")[0])
    allowed = {"__future__", "hashlib", "json", "pathlib", "typing", "vacant_network"}
    assert mods <= allowed, f"specs.py 引入了模型通道/外部依賴: {mods}"
    assert callable(S.load_frozen_specs)
    assert issubclass(S.SpecIntegrityError, Exception)

