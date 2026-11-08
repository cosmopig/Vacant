"""r1245（2026-11-08）：repair.py / extract.py 冻结锚点守卫（审查指示#3 机器化）。

背景：审查指示#3（2026-11-08）要求
  - repair.py  冻结在 2,795 行、git blob 5147f8c3（不得为特定题新增修复规则/局部 regex）；
  - extract.py 白名单防线不变：1,217 行、git blob e757aec5。
此前该约束只靠每轮人工 blob 核对（STATE.md 的「錨點」行）落地，没有任何一条指令能在
文件被改动时直接变红。本文件把锚点固化成测试：

  - anchor_violations()：守卫谓词，纯 Python 计算 git blob sha1（无 git 子进程、无网络），
    返回空列表＝与锚点一致；
  - 绿灯测试：repo 内两份真实文件当前冻结（改动即红，解冻必须显式改本测试并留记录）；
  - 负控制：篡改副本（多一行）必须被守卫判为违规——证明上面两条绿灯不是空转
    （与 ops/gain/replay/verify_run_receipts.py 先跑负控制同一纪律）。

本文件只读受测文件，不写任何共享状态；临时副本走 pytest tmp_path fixture。
"""
from __future__ import annotations

import hashlib
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# 锚点来源：审查指示#3（2026-11-08）＋ STATE r1243/r1244 錨點行（三分支同 blob 已核）。
REPAIR = {
    "path": REPO_ROOT / "vacant_network" / "reqloop" / "repair.py",
    "blob": "5147f8c3ea1b5e9ee50531aca0382971e912c243",
    "lines": 2795,  # wc -l 口径（换行字节数）
}
EXTRACT = {
    "path": REPO_ROOT / "vacant_network" / "reqloop" / "extract.py",
    "blob": "e757aec50c16bc6481cd88545672d50884c83f40",
    "lines": 1217,
}


def git_blob_sha1(raw: bytes) -> str:
    """git blob hash = sha1(b"blob <len>\\0" + content)，与 git hash-object 同式。"""
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def anchor_violations(path: pathlib.Path, *, blob: str, lines: int) -> list[str]:
    """返回违规清单；空列表＝文件与冻结锚点一致。"""
    if not path.is_file():
        return [f"文件不存在: {path}"]
    raw = path.read_bytes()
    out: list[str] = []
    got_blob = git_blob_sha1(raw)
    if got_blob != blob:
        out.append(f"blob 漂移: 期望 {blob}, 实际 {got_blob}")
    got_lines = raw.count(b"\n")
    if got_lines != lines:
        out.append(f"行数漂移: 期望 {lines}, 实际 {got_lines}")
    return out


def test_repair_py_is_frozen():
    v = anchor_violations(REPAIR["path"], blob=REPAIR["blob"], lines=REPAIR["lines"])
    assert v == [], "repair.py 已冻结（审查指示#3；解冻须显式改本测试并留记录）: " + "; ".join(v)


def test_extract_py_boundary_is_frozen():
    v = anchor_violations(EXTRACT["path"], blob=EXTRACT["blob"], lines=EXTRACT["lines"])
    assert v == [], "extract.py 白名单防线冻结（审查指示#3）: " + "; ".join(v)


def test_guard_detects_tampered_copy(tmp_path: pathlib.Path):
    """负控制：篡改副本必须被守卫判违规，否则上面两条绿灯无意义。"""
    tampered = tmp_path / "repair_tampered.py"
    tampered.write_bytes(REPAIR["path"].read_bytes() + "# 未核准的修复规则\n".encode("utf-8"))
    v = anchor_violations(tampered, blob=REPAIR["blob"], lines=REPAIR["lines"])
    assert any("blob 漂移" in s for s in v), "守卫未检出 blob 漂移"
    assert any("行数漂移" in s for s in v), "守卫未检出行数漂移"
