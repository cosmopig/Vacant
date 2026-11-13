"""r1245（2026-11-08）：repair.py / extract.py 冻结锚点守卫（审查指示#3 机器化）。

背景：审查指示#3（2026-11-08）要求
  - repair.py  冻结在 2,795 行、git blob 5147f8c3（不得为特定题新增修复规则/局部 regex）；
  - extract.py 基线：e757aec5 / 1,217 行（G2.5 历史基线）→ 2026-11-13 裁決 §3 受控解冻，
    D2 加法落地后重立为 b502741b / 1,295 行（见 EXTRACT 锚；再改须重立并留记录）。
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
import json
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# 锚点来源：审查指示#3（2026-11-08）＋ STATE r1243/r1244 錨點行（三分支同 blob 已核）。
REPAIR = {
    "path": REPO_ROOT / "vacant_network" / "reqloop" / "repair.py",
    "blob": "5147f8c3ea1b5e9ee50531aca0382971e912c243",
    "lines": 2795,  # wc -l 口径（换行字节数）
}
# 2026-11-13 人類裁決 §3「受控解凍」：extract.py 只准加法、走新參數、預設值＝舊行為；
# gate＝run_eval.py --all 三門數字與 g25 filing 一模一樣＋結果寫 ops/audits/g26_*.json。
# r1546（本輪，票 P20261113_0300-2 D2）：D2 加法（trusted_deliverable 新參數）落地後
# 重立此錨——e757aec5…/1217 行（G2.5 歷史基線）→ b502741b…/1295 行。
# 再改 extract.py 仍須重立本錨並留記錄（受控≠自由改動）。
EXTRACT = {
    "path": REPO_ROOT / "vacant_network" / "reqloop" / "extract.py",
    "blob": "b502741bcd290d1bfefc257986be838d6356d4f3",
    "lines": 1295,
}
CHECKS = {
    "path": REPO_ROOT / "vacant_network" / "reqloop" / "checks.py",
    "blob": "d401a8ae291e3f5c53972c1a76600e72d629f916",
    "lines": 2907,
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
    v = anchor_violations(EXTRACT["path"], blob=EXTRACT["blob"], lines=EXTRACT["lines"]) + \
        anchor_violations(CHECKS["path"], blob=CHECKS["blob"], lines=CHECKS["lines"])
    assert v == [], "extract.py/checks.py 受控解凍錨點（11-13 裁決 §3）: " + "; ".join(v)


def test_guard_detects_tampered_copy(tmp_path: pathlib.Path):
    """负控制：篡改副本必须被守卫判违规，否则上面两条绿灯无意义。"""
    tampered = tmp_path / "repair_tampered.py"
    tampered.write_bytes(REPAIR["path"].read_bytes() + "# 未核准的修复规则\n".encode("utf-8"))
    v = anchor_violations(tampered, blob=REPAIR["blob"], lines=REPAIR["lines"])
    assert any("blob 漂移" in s for s in v), "守卫未检出 blob 漂移"
    assert any("行数漂移" in s for s in v), "守卫未检出行数漂移"


# r1261（2026-11-08）：审查指示#3 —— G2.5 备案的 code sha256 与 repo 实际文件吻合。
# r1546（2026-11-13，人類裁決 §3＋票 P20261113_0300-2「不要做」）：g25 filing 不改——
# 它是 G2.5 历史备案（extract.py 条目记解冻前基线 51abfec3…）。本节语义改为：
# (1) filing 档本身逐位冻结（FILING_SHA256）；(2) 仍冻结的 checks.py/run_eval.py 现行
# sha 与备案吻合；(3) filing 的 extract.py 条目仍记解冻前历史基线。extract.py 的
# 「现行」基线由上方 EXTRACT 锚把守——分工不重叠（同 now_redline 原则）。
FILING = REPO_ROOT / "ops" / "audits" / "g25_all_gates_filing.json"
FILING_SHA256 = "6e5afb46570de1191fff702c9db66a3f89824de2f7313eb47e5cbc25c8ff87e5"
LIVE_CODE_FILES = (
    "ops/reqloop/extract/run_eval.py",
)
HISTORICAL_EXTRACT_SHA256 = (
    "51abfec319d21813d7223bc5aa48417417680ba09aa0bd4d097b2c49ea223da7"
)
HISTORICAL_CHECKS_SHA256 = (
    "c7589c610c629380f8919a08e1e707bb7ad65143cd4e0131a301158ab82fd4f4"
)


def filing_code_violations(filing_path: pathlib.Path, root: pathlib.Path) -> list[str]:
    """g25 filing 守卫违规清单（2026-11-13 裁決後语义）；空列表＝无违规。

    (1) filing 档本身与 FILING_SHA256 逐位吻合（g25 filing 不改，它是历史备案）；
    (2) 仍冻结的 run_eval.py 现行 sha 与备案记录吻合；
    (3) filing 的 extract.py 與 checks.py 条目仍记解冻前历史基线（历史备案未被改写）。
    extract.py/checks.py 现行基线由上方 EXTRACT/CHECKS 锚把守，不在此尺。只读，不写任何共享状态。"""
    if not filing_path.is_file():
        return [f"备案不存在: {filing_path}"]
    raw = filing_path.read_bytes()
    got_filing = hashlib.sha256(raw).hexdigest()
    out: list[str] = []
    if got_filing != FILING_SHA256:
        out.append(
            f"filing 档本身漂移: 期望 {FILING_SHA256[:8]}, 实际 {got_filing[:8]}"
            "（11-13 裁決 §3：g25 filing 不改——它是历史备案，不是可更新的现行记录）"
        )
    filing = json.loads(raw)
    code = filing.get("code", {})
    if not code:
        return out + ["备案没有 code 段（schema 变更？）"]
    for rel in LIVE_CODE_FILES:
        spec = code.get(rel)
        if not isinstance(spec, dict):
            out.append(f"备案 code 段缺 {rel}")
            continue
        p = root / rel
        if not p.is_file():
            out.append(f"文件不存在: {rel}")
            continue
        want = str(spec.get("sha256", ""))
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            out.append(f"{rel} sha 漂移: 期望 {want[:8]}, 实际 {got[:8]}")
    ex = code.get("vacant_network/reqloop/extract.py")
    if not isinstance(ex, dict) or str(ex.get("sha256", "")) != HISTORICAL_EXTRACT_SHA256:
        out.append(
            "filing 的 extract.py 条目须仍记 G2.5 解冻前历史基线 "
            f"{HISTORICAL_EXTRACT_SHA256[:8]}（历史备案不可改写；现行基线见 EXTRACT 锚）"
        )
    ck = code.get("vacant_network/reqloop/checks.py")
    if not isinstance(ck, dict) or str(ck.get("sha256", "")) != HISTORICAL_CHECKS_SHA256:
        out.append(
            "filing 的 checks.py 条目须仍记 G2.5 解冻前历史基线 "
            f"{HISTORICAL_CHECKS_SHA256[:8]}（历史备案不可改写；现行基线见 CHECKS 锚）"
        )
    return out


def test_g25_filing_code_hashes_match_repo():
    """绿灯（2026-11-13 裁決後语义）：g25 filing 档逐位不改（历史备案）；仍冻结的
    run_eval.py 现行与备案 100% 吻合；filing 的 extract.py/checks.py 条目仍记解冻前
    基线。extract.py/checks.py 现行基线由 test_extract_py_boundary_is_frozen 把守。"""
    v = filing_code_violations(FILING, REPO_ROOT)
    assert v == [], (
        "g25 filing 须逐位不改（11-13 裁決 §3）且仍冻结档（run_eval.py）"
        "现行与备案 100% 吻合: "
    ) + "; ".join(v)


def test_filing_guard_detects_drift(tmp_path: pathlib.Path):
    """负控制（2026-11-13 裁決後语义）：
    (a) 仍冻结的 run_eval.py 被改 → 必须判漂移；
    (b) filing 档本身被改（历史备案改写）→ 必须判「filing 档本身漂移」。
    对临时 repo 操作，不碰真档。"""
    fake_root = tmp_path / "repo"
    for rel in LIVE_CODE_FILES:
        dst = fake_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((REPO_ROOT / rel).read_bytes())

    # (a) 改 run_eval.py → 必须红
    run_eval = fake_root / "ops" / "reqloop" / "extract" / "run_eval.py"
    run_eval.write_bytes(run_eval.read_bytes() + "# 未核准的修改\n".encode("utf-8"))
    v = filing_code_violations(FILING, fake_root)
    assert any("run_eval.py" in s and "sha 漂移" in s for s in v), f"守卫未检出 run_eval.py 漂移: {v}"

    # (b) filing 档本身被改 → 必须红（历史备案改写）
    f2 = tmp_path / "filing.json"
    d = json.loads(FILING.read_text(encoding="utf-8"))
    d["code"]["ops/reqloop/extract/run_eval.py"]["sha256"] = "0" * 64
    f2.write_text(json.dumps(d), encoding="utf-8")
    v2 = filing_code_violations(f2, REPO_ROOT)
    assert any("filing 档本身漂移" in s for s in v2), f"filing 档被改须被点名: {v2}"
