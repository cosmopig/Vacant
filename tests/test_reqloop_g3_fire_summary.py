# -*- coding: utf-8 -*-
"""g3_fire_20261111_summary（r1428, vq-el4.97）：G3 發射審計摘要產生器的負控制。

背景：r1427 落地的審計摘要產生器（ops/audits/g3_fire_20261111_summary.py）零負
控制——全部紅路從未實證（r1344「死守衛」同型：漏掉一項得到的綠燈就是漏洞成因）。
本輪 RED 實證：把全部 usage 剝除＋totals.tokens=0 的自洽「零測量」檔（12 格、
schema／status／hidden_after／answer sha 全合法）→ 舊碼
``VERDICT: G3_FIRE_SUMMARY_OK`` rc=0、``tokens_known=0``＝無成本綠燈
（I-4：未測量不是通過；r1272 空檔 vacuous、r1344 死守衛同族；口徑 4：
成效數字必須同時寫成本——零已測量成本不得判 OK）。

修（本輪）：
- tokens 重算加非空守衛：已知 usage 數 n_known > 0 為必要條件——
  0 已知 usage＋totals.tokens=0 → BROKEN（舊碼 0+0==0 判 OK＝vacuous 假綠燈）。
- argv 注入：argv[1]=result 檔、argv[2]=輸出目的（預設＝live raw／repo 的
  ops/audits/g3_fire_20261111_summary.json，預設行為維持）——供 CI/沙盒
  用 tmp 檔（r1339 queue 路徑注入同型）。
- 單一裁決行契約（vq-el4.39）：缺檔／非 JSON 不得崩成 traceback 讓裁決消失——
  點名 BROKEN＋VERDICT 行。

對 live raw（~/dev/ops/g3_fire_20261111/g3_result.json）全唯讀；負控制只操作
自造合成檔（tmp_path，CI-safe：不依賴 repo 外檔案）；repo 內不寫任何檔
（輸出目的全部 tmp）。0 model calls；subprocess 只用 [sys.executable, script, ...]
（無 python -c 片段，不觸及 test_reqloop_ci_contract.py 的安裝合約掃描範圍）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "audits" / "g3_fire_20261111_summary.py"
LIVE_RAW = Path.home() / "dev" / "ops" / "g3_fire_20261111" / "g3_result.json"
REPO_SUMMARY = REPO / "ops" / "audits" / "g3_fire_20261111_summary.json"

OK_VERDICT = "VERDICT: G3_FIRE_SUMMARY_OK"
BROKEN_VERDICT = "VERDICT: G3_FIRE_SUMMARY_BROKEN"


def _run(result: str | Path, out: str | Path) -> subprocess.CompletedProcess[str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(result), str(out)],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    assert "Traceback" not in r.stderr, f"裁決消失（traceback）：{r.stderr}"
    return r


def _base() -> dict:
    """自造合法 g3_result（CI-safe，不依賴 repo 外 live 檔）。
    4 題×3 臂＝12 格；t1/native_pi ok（answer At1、300 tok）；11 error 無 usage；
    4 tasks extract 各 100/200/300/400 tok；totals.tokens=1300。"""
    def cell(task: str, arm: str, status: str, answer: str | None = None,
             toks: int | None = None) -> dict:
        return {
            "task": task, "arm": arm, "status": status,
            "answer": answer,
            "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest()
            if answer is not None else None,
            "hidden_after": "UNKNOWN",
            "content_reverify": None,
            "rounds": [{"usages": ([{"model": "m", "calls": 1, "tokens": toks}]
                                   if toks is not None else [])}],
        }
    cells = []
    for i, task in enumerate(("t1", "t2", "t3", "t4")):
        cells.append(cell(task, "native_pi", "ok" if i == 0 else "error",
                          answer=f"A{task}" if i == 0 else None, toks=300 if i == 0 else None))
        cells.append(cell(task, "reqlist_only", "error"))
        cells.append(cell(task, "full_rloop", "error"))
    tasks = [
        {"task_id": f"t{i + 1}", "input_sha256": f"{i:064x}",
         "required_answer_names": ["@x"], "n_requirements": 2, "extract_error": None,
         "extract_usages": [{"model": "m", "calls": 1, "tokens": 100 * (i + 1)}]}
        for i in range(4)
    ]
    return {
        "schema": "vacant.reqloop.g3.result/1",
        "fired_at": "2026-11-11T05:41:18Z",
        "stop_reason": None,
        "arms": ["native_pi", "reqlist_only", "full_rloop"],
        "extract_model": "m", "answer_model": "m",
        "budget": {"pi_provider": "p", "pi_model": "q"},
        "tasks": tasks, "cells": cells,
        "totals": {"cells": 12, "cells_run": 12, "model_calls": 5,
                   "tokens": 1300, "tokens_missing": False},
    }


def _write(tmp_path: Path, d: dict, name: str = "synthetic_g3_result.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（r1427 未落地）"


def test_synthetic_positive_control(tmp_path: Path) -> None:
    """正控制：自造合法 12 格檔 → OK rc=0、token_accounting 逐欄一致。"""
    r = _run(_write(tmp_path, _base()), tmp_path / "out.json")
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert OK_VERDICT in r.stdout, r.stdout
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    ta = out["token_accounting"]
    assert ta["cell_tokens_known"] == 300, ta
    assert ta["extract_tokens_known"] == 1000, ta
    assert ta["known_total"] == 1300 == out["totals"]["tokens"], ta
    assert ta["known_usages"] == 5, f"known_usages 缺失或錯：{ta}"
    pa = out["per_arm"]
    assert sum(v["cells"] for v in pa.values()) == 12
    assert pa["native_pi"]["ok"] == 1 and pa["reqlist_only"]["error"] == 4


@pytest.mark.skipif(not LIVE_RAW.is_file(),
                    reason="live raw 在 repo 外（~/dev/ops）——CI 環境無此檔；合成正控制已覆蓋")
def test_live_positive_control(tmp_path: Path) -> None:
    r = _run(LIVE_RAW, tmp_path / "live_out.json")
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert OK_VERDICT in r.stdout, r.stdout
    out = json.loads((tmp_path / "live_out.json").read_text(encoding="utf-8"))
    assert out["token_accounting"]["known_total"] == 49744 == out["totals"]["tokens"]
    assert out["token_accounting"]["known_usages"] == 5


def test_repo_summary_consistent() -> None:
    """repo 已入庫摘要（r1427 產物，本輪以新碼重生成）內部自洽。"""
    assert REPO_SUMMARY.is_file(), "缺少 repo 摘要 ops/audits/g3_fire_20261111_summary.json"
    d = json.loads(REPO_SUMMARY.read_text(encoding="utf-8"))
    assert d["schema"] == "vacant.audit/g3_fire_20261111_summary/1"
    assert len(d["cells"]) == 12
    assert all(c["hidden_after"] == "UNKNOWN" for c in d["cells"])
    assert sum(v["cells"] for v in d["per_arm"].values()) == 12
    ta = d["token_accounting"]
    assert ta["cell_tokens_known"] + ta["extract_tokens_known"] == ta["known_total"]
    assert ta["known_total"] == d["totals"]["tokens"] == 49744
    assert ta["known_usages"] == 5


def test_negative_vacuous_tokens(tmp_path: Path) -> None:
    """核心洞（本輪 RED 實證）：零 measurement 檔（全部 usage 缺失＋totals.tokens=0）
    舊碼判 OK rc=0＝無成本假綠燈（I-4：未測量不是通過；r1272/r1344 同族）。
    新碼必須 BROKEN rc=1 且點名空集。"""
    d = _base()
    for c in d["cells"]:
        for rd in c["rounds"]:
            rd["usages"] = []
    for t in d["tasks"]:
        t["extract_usages"] = []
    d["totals"]["tokens"] = 0
    d["totals"]["tokens_missing"] = False
    r = _run(_write(tmp_path, d, "vacuous.json"), tmp_path / "vacuous_out.json")
    assert r.returncode == 1, f"vacuous：rc=0 假綠燈（無成本綠燈）\n{r.stdout}\n{r.stderr}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "空集" in r.stderr, f"未點名空集：{r.stderr}"


def test_negative_tokens_drift(tmp_path: Path) -> None:
    """既有重算紅路實證：ok 格 usage 300→301（totals 不變 1300）→ BROKEN。"""
    d = _base()
    d["cells"][0]["rounds"][0]["usages"][0]["tokens"] = 301
    r = _run(_write(tmp_path, d, "drift.json"), tmp_path / "drift_out.json")
    assert r.returncode == 1, f"rc=0 假綠燈\n{r.stdout}\n{r.stderr}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "重算" in r.stderr, r.stderr


def test_negative_tokens_none(tmp_path: Path) -> None:
    """totals.tokens=null（UNKNOWN）不得被讀成 0 → BROKEN 且點名缺值。"""
    d = _base()
    d["totals"]["tokens"] = None
    r = _run(_write(tmp_path, d, "none.json"), tmp_path / "none_out.json")
    assert r.returncode == 1, f"rc=0 假綠燈\n{r.stdout}\n{r.stderr}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "缺值" in r.stderr, r.stderr


def test_positive_partial_cells_run_quota_stop(tmp_path: Path) -> None:
    """正控制：部分格子因配額未跑（status='not_run'，cells=12, cells_run=10）→ 必須 OK rc=0。
    舊碼死守 cells_run==12 判 BROKEN（配額提早停止合法場景被誤殺）。"""
    d = _base()
    d["cells"][10]["status"] = "not_run"
    d["cells"][10]["rounds"] = []
    d["cells"][11]["status"] = "not_run"
    d["cells"][11]["rounds"] = []
    d["totals"]["cells_run"] = 10
    r = _run(_write(tmp_path, d, "partial.json"), tmp_path / "partial_out.json")
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    assert OK_VERDICT in r.stdout, r.stdout


def test_negative_cells_run_mismatch(tmp_path: Path) -> None:
    """負控制：totals.cells_run 與實際非 not_run 格數不符（10 != 11）→ 必須 BROKEN rc=1。"""
    d = _base()
    d["cells"][10]["status"] = "not_run"
    d["cells"][10]["rounds"] = []
    d["cells"][11]["status"] = "not_run"
    d["cells"][11]["rounds"] = []
    d["totals"]["cells_run"] = 11
    r = _run(_write(tmp_path, d, "mismatch.json"), tmp_path / "mismatch_out.json")
    assert r.returncode == 1, f"rc=0 假綠燈\n{r.stdout}\n{r.stderr}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "cells_run" in r.stderr, r.stderr


def test_negative_schema_drift(tmp_path: Path) -> None:
    d = _base()
    d["schema"] = "vacant.reqloop.g3.result/2"
    r = _run(_write(tmp_path, d, "schema.json"), tmp_path / "schema_out.json")
    assert r.returncode == 1, f"rc=0 假綠燈\n{r.stdout}\n{r.stderr}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "schema" in r.stderr, r.stderr


def test_negative_missing_file(tmp_path: Path) -> None:
    """缺檔不得崩成 traceback（vq-el4.39 單一裁決行契約）→ BROKEN rc=1。"""
    r = _run(tmp_path / "nonexistent_g3_result.json", tmp_path / "missing_out.json")
    assert r.returncode == 1, f"缺檔仍 rc=0 假綠燈\n{r.stdout}"
    assert BROKEN_VERDICT in r.stdout, r.stdout
    assert "無法讀取" in r.stderr, r.stderr
