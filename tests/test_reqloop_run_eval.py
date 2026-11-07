"""G2.5 vq-el4.3：run_eval.py——G1 用擷取需求重跑、對照手寫版。

全部離線（不呼叫模型）：run_eval 只跑 checks.py 的重算檢查。
驗收（bd vq-el4.3）：
- 擷取版＝手寫版的同一份 requirements.json 時，run_eval 復現 G1 基線（抓錯／冤枉一致）；
- 擷取版漏抓時，門禁判 FAIL 且退出碼 20；
- good 三態（VERIFIED/FP/UNKNOWN）與 bad 抓錯判定正確。
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
RUN_EVAL = REPO / "ops" / "reqloop" / "extract" / "run_eval.py"
G1_TASKS = REPO / "ops" / "reqloop" / "g1" / "tasks"


def _load_run_eval():
    if "reqloop_run_eval" in sys.modules:
        return sys.modules["reqloop_run_eval"]
    spec = importlib.util.spec_from_file_location("reqloop_run_eval", RUN_EVAL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["reqloop_run_eval"] = mod  # @dataclass 需從 sys.modules 找到模組
    spec.loader.exec_module(mod)
    return mod


def _cr(claim_id: str, status: str):
    from vacant_network.intake.verifiers import ClaimResult
    return ClaimResult(claim_id=claim_id, status=status, detail="t", evidence={},
                       verifier="test", verifier_version="1", required=True, authority="client")


def test_good_verdict_three_states():
    m = _load_run_eval()
    items = [
        m.FakeItem(id="R1", required=True),
        m.FakeItem(id="R2", required=True),
    ]
    all_pass = [_cr("R1", "PASS"), _cr("R2", "PASS")]
    assert m.good_verdict(items, all_pass) == "VERIFIED"

    one_fail = [_cr("R1", "FAIL"), _cr("R2", "PASS")]
    assert m.good_verdict(items, one_fail) == "FP"  # 任一 FAIL＝冤枉

    one_unknown = [_cr("R1", "UNKNOWN"), _cr("R2", "PASS")]
    assert m.good_verdict(items, one_unknown) == "UNKNOWN"  # 必要條目未驗證≠PASS、≠FP

    missing = [_cr("R2", "PASS")]
    assert m.good_verdict(items, missing) == "UNKNOWN"  # 必要條目缺失


def test_bad_caught_any_fail():
    m = _load_run_eval()
    assert m.bad_caught([_cr("R1", "FAIL")])
    assert not m.bad_caught([_cr("R1", "PASS"), _cr("R2", "UNKNOWN")])


def _mk_task_tree(tmp_path: pathlib.Path, source_task: str = "orders_monthly") -> pathlib.Path:
    """把真實 G1 任務複製到 tmp（讀真實資料，不呼叫模型）。"""
    src = G1_TASKS / source_task
    dst = tmp_path / "g1_tasks" / source_task
    shutil.copytree(src, dst)
    return tmp_path / "g1_tasks"


def test_main_reproduces_baseline_when_extracted_equals_handwritten(tmp_path, capsys):
    m = _load_run_eval()
    g1 = _mk_task_tree(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # 擷取版＝手寫版同一份：必須復現基線（該題 6/6 抓錯、good 0 冤枉）
    shutil.copy(g1 / "orders_monthly" / "requirements.json",
                out_dir / "orders_monthly.glm53.json")
    rc = m.main(["--model", "glm53", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(tmp_path / "no_such.jsonl")])
    txt = capsys.readouterr().out
    assert rc == 0, txt
    assert "orders_monthly" in txt
    assert "手寫 6/6" in txt and "擷取 6/6" in txt
    assert "冤枉 0" in txt
    assert "UNKNOWN（無紀錄）" in txt  # 成本缺值→UNKNOWN，絕不填 0


def test_main_gate_fail_exit_20_when_extracted_misses(tmp_path, capsys):
    m = _load_run_eval()
    g1 = _mk_task_tree(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # 擷取版只剩一條很弱的結構檢查：bad 多半漏抓 → 門禁 FAIL、退出碼 20
    weak = {
        "task_id": "orders_monthly",
        "items": [
            {"id": "R1", "quote": "產出月度指標表", "deliverable": "monthly_sales.csv",
             "verifier": "csv_structure",
             "params": {"required_columns": ["month"]},
             "description": "弱檢查", "required": True, "kind": "explicit"},
        ],
    }
    (out_dir / "orders_monthly.glm53.json").write_text(
        json.dumps(weak, ensure_ascii=False), encoding="utf-8")
    rc = m.main(["--model", "glm53", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(tmp_path / "no_such.jsonl")])
    txt = capsys.readouterr().out
    assert rc == 20, txt
    assert "門禁" in txt and ("FAIL" in txt or "未達" in txt)


def test_main_missing_extracted_file_exit_2(tmp_path, capsys):
    m = _load_run_eval()
    g1 = _mk_task_tree(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()  # 空目錄：沒有該題的擷取結果
    rc = m.main(["--model", "glm53", "--g1", str(g1), "--out-dir", str(out_dir),
                 "--vibe-calls", str(tmp_path / "no_such.jsonl")])
    txt = (capsys.readouterr().out + capsys.readouterr().err)
    assert rc == 2, txt
    assert "缺" in txt
