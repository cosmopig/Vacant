"""dabstep-10-pi-C 下一切片選題事實常設守衛（11-06#4 內容閉環線、11-07 審查 P3 紀律；0 模型呼叫）。

dab_055-pi-C 已依 11-07 資深審查閉案（三批 A/B、generic 0/3 vs localized 3/3、禁第 4 跑）；
dabstep-10-pi-C 是 effects2_20261106 28 格中 generic 實際未修好的另一格
（stopped=stalled、答案 30 兩輪未變、獨立 scorer pass=false），且其可見檢查給出
具體結構化反例：
  期望 5 ＝ checks._unique_count 對 data/payments.csv merchant 欄實算（138,236 列）
  草稿/generic 30 ＝ len(data/merchant_data.json)——計了商家清單檔（錯的資料來源）
  localized 5（gap_closed；獨立 scorer pass=true、reward 1）
本測試用產品自己的 run_requirement_checks 把該反例釘進 repo（離線、零模型）：
- 凍結真實 task＋draft 在位（smoke_e014/dabstep-10-pi-C），sha 與 effect_manifest 釘住一致
- 草稿「30」必須 FAIL req_unique_merchants——可重現的內容反例（非格式問題）
- 期望值「5」＝ _unique_count 同口徑實算（單一事實來源；不複製計數迴圈）
- 反例結構可辨識：草稿值 30 == len(merchant_data.json)
- 洩漏守衛：重算期望值（獨立數字 5）不得進 detail/evidence（expected_in_evidence=false）；
  草稿自己的值（30）是合法內容、允許出現（deliverable_value）
- 本地審計預檢（若存在）之 single_source_of_truth 與產品實算一致
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from vacant_network.reqloop.checks import _unique_count, run_requirement_checks  # noqa: E402
from vacant_network.reqloop.requirements import RequirementSet  # noqa: E402

SLICE = REPO_ROOT / "ops/reqloop/g2/smoke_e014/dabstep-10-pi-C"
TASK = SLICE / "task"
DRAFT = SLICE / "draft"
MANIFEST = REPO_ROOT / "ops/reqloop/g2/effect_manifest.json"
NEEDLE = "5"


def test_real_slice_dabstep10_draft_fails_unique_count_recomputation():
    assert (TASK / "requirements.json").is_file(), "凍結 task 缺席"
    assert (DRAFT / "answer.txt").is_file(), "凍結 draft 缺席"

    # effect_manifest 釘住的 sha（repo 內既有 pin）須與在位檔一致
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entry = next(e for e in man["drafts"] if e["name"] == "dabstep-10-pi-C")
    assert hashlib.sha256((DRAFT / "answer.txt").read_bytes()).hexdigest() == entry["draft"]["answer_txt_sha256"], \
        "draft sha 漂移（effect_manifest pin 破損）"
    assert hashlib.sha256((TASK / "requirements.json").read_bytes()).hexdigest() == entry["task"]["requirements"]["sha256"], \
        "requirements sha 漂移（effect_manifest pin 破損）"

    req_set = RequirementSet.load(TASK / "requirements.json")
    item = next(it for it in req_set.items if it.id == "req_unique_merchants")
    assert item.verifier == "plain_recomputed" and item.deliverable == "answer.txt"
    rc = dict(item.params["recompute"])
    assert rc.get("type") == "unique_count" and rc.get("col") == "merchant", f"規則漂移：{rc!r}"

    # 單一事實來源：期望值取產品 checks._unique_count（不複製計數迴圈）
    rows = list(csv.DictReader((TASK / str(item.params["data_file"])).open(newline="", encoding="utf-8")))
    expected = _unique_count(rows, rc)
    assert str(expected) == NEEDLE, f"真值漂移：checks._unique_count={expected!r} ≠ 針 {NEEDLE}"
    assert len(rows) > 0

    # 內容反例：草稿（30）必須 FAIL——可重現、與模型無關
    results = run_requirement_checks(TASK, req_set, DRAFT)
    r = next(x for x in results if x.claim_id == "req_unique_merchants")
    assert r.status == "FAIL", f"draft 應 FAIL（內容反例），實得 {r.status}"

    # 反例結構可辨識：草稿值 30 == len(merchant_data.json)（錯的資料來源）
    draft_val = int((DRAFT / "answer.txt").read_text(encoding="utf-8").strip())
    merchant_objs = json.loads((TASK / "data/merchant_data.json").read_text(encoding="utf-8"))
    assert draft_val == len(merchant_objs) == 30, \
        f"反例結構漂移：draft={draft_val}、len(merchant_data.json)={len(merchant_objs)}"
    assert draft_val != expected, "反例失效：草稿值等於真值"

    # 洩漏守衛：重算期望值（獨立數字 5）不得進 detail/evidence；
    # 草稿自己的值 30 是合法內容，須允許出現（deliverable_value）
    blob = json.dumps({"detail": r.detail, "evidence": r.evidence}, ensure_ascii=False)
    assert not re.search(r"(?<!\d)5(?!\d)", blob), f"重算期望值進證據：{blob}"
    assert r.evidence.get("expected_in_evidence") is False, "expected_in_evidence 須為 false"
    assert "30" in str(r.evidence.get("deliverable_value", "")), "草稿自己的值應可見（合法內容）"

    # 本地審計預檢（若存在）交叉一致；缺席不影響本守衛（本地檔案非 repo 資產）
    audit = pathlib.Path.home() / "dev/ops/audits/dabstep10_slice_precheck_20261107.json"
    if audit.is_file():
        a = json.loads(audit.read_text(encoding="utf-8"))
        sst = a.get("single_source_of_truth") or {}
        assert "checks._unique_count" in sst.get("expected_from", ""), "預檢未標註單一事實來源"
        assert sst.get("expected") == expected, "預檢期望值與產品實算不一致"
        assert a.get("recompute", {}).get("expected") == expected
