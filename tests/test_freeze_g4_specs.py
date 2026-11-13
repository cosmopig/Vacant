"""P20261113_0708-1（G4-SPEC）：4 題凍結規格的機械複核（0 model calls）。

跑法：python3 -m pytest tests/test_freeze_g4_specs.py
"""
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("freeze_specs", REPO / "ops/reqloop/extract/freeze_specs.py")
fs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fs)
from vacant_network.reqloop.requirements import RequirementSet  # noqa: E402

TASKS = fs.TASKS
SPEC_DIR = fs.SPEC_DIR
WS = REPO / "ops/reqloop/g3_2/tasks"


def _ensure_specs() -> None:
    if not all((SPEC_DIR / f"{t}.json").is_file() for t in TASKS):
        subprocess.run([sys.executable, str(REPO / "ops/reqloop/extract/freeze_specs.py")], check=True)


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_a_spec_files_exist_and_load():
    _ensure_specs()
    for t in TASKS:
        p = SPEC_DIR / f"{t}.json"
        assert p.is_file(), f"missing spec for {t}"
        rs = RequirementSet.load(p)  # 結構合法（quote/deliverable 非空、kind 合法）
        assert rs.task_id == t
        assert len(rs.items) >= 1


def test_b_goal_contract_hashes_match_workspace():
    _ensure_specs()
    for t in TASKS:
        spec = json.loads((SPEC_DIR / f"{t}.json").read_text(encoding="utf-8"))
        assert spec["goal_sha256"] == _sha(WS / t / "workspace" / "goal.md")
        assert spec["contract_sha256"] == _sha(WS / t / "workspace" / "contract.md")


def test_c_deterministic_items_trusted_deliverable():
    _ensure_specs()
    total = 0
    for t in TASKS:
        rs = RequirementSet.load(SPEC_DIR / f"{t}.json")
        det = [it for it in rs.items if it.verifier not in ("", "unverified")]
        assert len(det) >= 1, f"{t}: 無 deterministic 條目"
        total += len(det)
        tr, ins = fs.trusted_deliverable(t), fs.input_files(t)
        assert tr and tr not in ins, f"{t}: trusted deliverable 本身即輸入檔"
        for it in det:
            assert it.deliverable == tr and it.deliverable not in ins, (t, it.id, it.deliverable)
    assert total >= 10, f"4 題合計 {total} < 10"


def test_d_tamper_negative_controls(tmp_path):
    _ensure_specs()
    src = json.loads((SPEC_DIR / "dab_725.json").read_text(encoding="utf-8"))

    def dump(d: dict, name: str) -> pathlib.Path:
        p = tmp_path / name
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return p

    # 正控制：原始規格通過
    ok, why = fs.validate_spec(SPEC_DIR / "dab_725.json")
    assert ok, why
    # 負 1：篡改 items 任一字段一字
    t1 = json.loads(json.dumps(src))
    t1["items"][0]["verifier"] = "answer_kv2"
    ok, why = fs.validate_spec(dump(t1, "t1.json"))
    assert not ok and why == "spec_sha256", (ok, why)
    # 負 2：篡改 goal hash 一字
    t2 = json.loads(json.dumps(src))
    t2["goal_sha256"] = ("0" if t2["goal_sha256"][0] != "0" else "1") + t2["goal_sha256"][1:]
    ok, why = fs.validate_spec(dump(t2, "t2.json"))
    assert not ok, (ok, why)
    # 負 3：檔案損壞（非 JSON）
    p3 = tmp_path / "t3.json"
    p3.write_text("{broken", encoding="utf-8")
    ok, why = fs.validate_spec(p3)
    assert not ok and why.startswith("load_failed"), (ok, why)
    # 負 4：交付物被換成輸入檔（自 hash 先紅；若自 hash 被一併偽造，deliverable 分支兜底）
    t4 = json.loads(json.dumps(src))
    t4["items"][0]["deliverable"] = fs.input_files("dab_725")[0]
    ok, why = fs.validate_spec(dump(t4, "t4.json"))
    assert not ok, (ok, why)
    # 負 5：偽造「自 hash 自洽＋交付物＝輸入檔」→ deliverable 分支兜底必紅
    t5 = json.loads(json.dumps(src))
    t5["items"][0]["deliverable"] = fs.input_files("dab_725")[0]
    body = {k: v for k, v in t5.items() if k != "spec_sha256"}
    t5["spec_sha256"] = hashlib.sha256(fs._canon(body).encode("utf-8")).hexdigest()
    ok, why = fs.validate_spec(dump(t5, "t5.json"))
    assert not ok and why == "deliverable", (ok, why)
