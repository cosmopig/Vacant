"""
vacant_network.reqloop.specs
D4 凍結 spec 載入器（P20261113_1358-3，11-13 裁決 §2 D4）。

責任（純離線、0 model calls、無新依賴）：
- load_frozen_specs：讀 manifest（如 ops/reqloop/g4/manifest.json）、對 specs
  每條載入其 file 凍結規格檔、逐檔把 spec_sha256 對 manifest 綁定核驗；
- SpecIntegrityError：任何核驗失敗（hash 不符／spec 檔缺／manifest 無 specs 鍵／
  manifest 檔不存在）→ 整批拒絕、不返回部分結果（fail-closed；I-4：未測量不是通過）。

spec_sha256 口徑：整份規格（除本欄）canonical JSON 之 sha256
（ops/reqloop/extract/freeze_specs.py:13-14、180-182 防篡改註記；
RequirementSet.verify_self_hash 同口徑），非檔案原始位元組 hash。
本模組是 spec_sha256 的唯一核驗口（H-8：renderer 是 trusted input，必須有唯一
核驗口）：重用 freeze_specs 已定義的 canonical 口徑，不重算第二套。
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from vacant_network.reqloop.requirements import RequirementSet

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class SpecIntegrityError(Exception):
    """凍結 spec 核驗失敗（fail-closed，拒絕返回）。

    屬性：
        task_id:  失敗所屬 task；manifest 層失敗為 None。
        expected: manifest 記載 spec_sha256 的前 8 hex（無記載時為 ""）。
        actual:   實際算出值的頭 8 hex（算不出來時為 ""）。
    """

    def __init__(self, message: str, *, task_id: str | None = None,
                 expected: str = "", actual: str = "") -> None:
        self.task_id = task_id
        self.expected = expected
        self.actual = actual
        super().__init__(message)


def _h8(v: str) -> str:
    return (v or "")[:8]


def _resolve(file: str) -> pathlib.Path:
    p = pathlib.Path(file)
    return p if p.is_absolute() else REPO_ROOT / p


def load_frozen_specs(manifest_path: str | pathlib.Path) -> dict[str, dict[str, Any]]:
    """載入 manifest 的凍結規格並逐檔核驗 spec_sha256。

    回傳 {task_id: 規格檔 JSON dict}。任何一題失敗即拋 SpecIntegrityError，
    不返回部分結果、不靜默 fallback（fail-closed）。
    `file` 相對路徑對 repo root 解析（與 g4gate 同口徑），絕對路徑照用。
    """
    mp = pathlib.Path(manifest_path)
    if not mp.is_file():
        raise SpecIntegrityError(f"manifest 不存在: {mp}（不靜默 fallback）")
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SpecIntegrityError(f"manifest 不可讀/不可解析: {mp}: {e}") from e
    specs = manifest.get("specs") if isinstance(manifest, dict) else None
    if not isinstance(specs, dict) or not specs:
        raise SpecIntegrityError(
            f"manifest 無 specs 對應（fail-closed，不猜）: {mp}")

    out: dict[str, dict[str, Any]] = {}
    for task_id, entry in specs.items():
        if not isinstance(entry, dict) or not entry.get("file") or not entry.get("spec_sha256"):
            raise SpecIntegrityError(
                f"specs[{task_id}] 缺 file/spec_sha256", task_id=task_id)
        path = _resolve(str(entry["file"]))
        expected = str(entry["spec_sha256"])
        if not path.is_file():
            raise SpecIntegrityError(
                f"規格檔不存在: {path}（task {task_id}）",
                task_id=task_id, expected=_h8(expected))
        try:
            req_set = RequirementSet.load(path)
            ok, _msg = req_set.verify_self_hash()
            actual = req_set.compute_spec_sha256()
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
            raise SpecIntegrityError(
                f"規格檔不可讀/不可解析: {path}（task {task_id}）: {e}",
                task_id=task_id, expected=_h8(expected)) from e
        if not ok or actual != expected:
            raise SpecIntegrityError(
                f"spec_sha256 不符（task {task_id}）："
                f"expected {_h8(expected)}… actual {_h8(actual)}…",
                task_id=task_id, expected=_h8(expected), actual=_h8(actual))
        out[task_id] = spec
    return out
