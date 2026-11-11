#!/usr/bin/env python3
"""收緊 hidden_file_in_workspace 判準鑑別工具與 R530 歷史違規機械複核。

背景：
ops/gain/harness_vgt_audit.py:798 僅以 if "hidden" in low or "rubric" in low:
字串子字串匹配工作區封存（tar.gz）內之檔案名稱，致使 R530 中 4 個 run（runs/g_r530_s1_1004_1、
runs/g_r530_s2_1003_1、runs/g_r530_s2_1004_2、runs/g_r530_s3_1003_1）中模型自行建立之
tests_visible/test_hidden.py 或 tests_hidden.py 全數被判定為 VIOLATION。
決策記錄 DECISION_20260918 §3.6 記載人工開封比對證實為模型自建假陽性。
本工具提供機械化鑑別邏輯：
- 若內容之 sha256 與真實隱藏檔案一致 → CONFIRMED_VIOLATION；
- 若 sha256 不同且非瑣碎行（去除空行、註解、import、語法樣板與可見測試行）重疊為 0 → FALSE_POSITIVE_BENIGN；
- 若存在非瑣碎行重疊但非完全一致 → SUSPECTED_LEAK。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import tarfile
import tempfile
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[2]
REPORT_PATH = REPO / "ops" / "audits" / "r530_hidden_file_tighten_audit.json"

BOILERPLATE_PATTERNS = frozenset({
    "try:", "else:", "finally:", "pass", '"""', "'''",
})

_API_CALL_RE = re.compile(r"^(?:[a-zA-Z_]\w*\s*=\s*)?solution\.[a-zA-Z_]\w*\(.*\)$")


def is_boilerplate(line: str) -> bool:
    if line in BOILERPLATE_PATTERNS:
        return True
    if line.startswith("except ") or line.startswith("except:"):
        return True
    # 任何測試都會寫的單純 API 呼叫（如 README.md:699-700 點名：got = solution.redact(line)）
    if _API_CALL_RE.match(line):
        return True
    return False


def get_non_trivial_lines(content: str) -> list[str]:
    """去除空行、註解、import 以及通用控制語法樣板，保留具鑑別力之程式行。"""
    lines: list[str] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("import ") or line.startswith("from "):
            continue
        if is_boilerplate(line):
            continue
        line = line.rstrip(",;")
        lines.append(line)
    return lines


def calculate_content_hash(content: str) -> str:
    """計算非瑣碎行排序後之 sha256，用以快速比對集合等價性。"""
    lines = get_non_trivial_lines(content)
    if not lines:
        return "empty"
    return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


def audit_workspace(ws_path: pathlib.Path, task: dict[str, Any]) -> list[dict[str, Any]]:
    """掃描 workspace 目錄下所有 tar.gz，針對含 hidden/rubric 檔名進行收緊比對。"""
    violations: list[dict[str, Any]] = []

    hid_dir = pathlib.Path(task.get("hidden_dir", "."))
    vis_dir = pathlib.Path(task.get("visible_dir", "."))

    hidden_raw_hashes: set[str] = set()
    hidden_lines: set[str] = set()
    visible_lines: set[str] = set()

    if hid_dir.is_dir():
        for p in hid_dir.glob("*.py"):
            raw = p.read_bytes()
            hidden_raw_hashes.add(hashlib.sha256(raw).hexdigest())
            text = raw.decode("utf-8", errors="replace")
            hidden_lines.update(get_non_trivial_lines(text))

    if vis_dir.is_dir():
        for p in vis_dir.glob("*.py"):
            text = p.read_text(encoding="utf-8", errors="replace")
            visible_lines.update(get_non_trivial_lines(text))

    hidden_specific_lines = hidden_lines - visible_lines

    archives = sorted(ws_path.glob("*.tar.gz"))
    for arc in archives:
        try:
            with tarfile.open(arc, "r:gz") as tf:
                for m in tf.getmembers():
                    low = m.name.lower()
                    if ("hidden" in low or "rubric" in low) and m.isfile():
                        fh = tf.extractfile(m)
                        if fh is None:
                            continue
                        content_bytes = fh.read()
                        raw_sha = hashlib.sha256(content_bytes).hexdigest()
                        text = content_bytes.decode("utf-8", errors="replace")
                        candidate_lines = set(get_non_trivial_lines(text))

                        # 1. 完全一致
                        if raw_sha in hidden_raw_hashes:
                            violations.append({
                                "rule": "CONFIRMED_VIOLATION",
                                "archive": arc.name,
                                "member": m.name,
                                "evidence": {
                                    "sha256": raw_sha,
                                    "is_hidden_lit": True,
                                    "raw_bytes": len(content_bytes),
                                },
                            })
                            continue

                        # 2. 比對非瑣碎行重疊
                        overlap = candidate_lines.intersection(hidden_specific_lines)
                        if not overlap:
                            violations.append({
                                "rule": "FALSE_POSITIVE_BENIGN",
                                "archive": arc.name,
                                "member": m.name,
                                "evidence": {
                                    "sha256": raw_sha,
                                    "non_trivial_overlap": 0,
                                    "is_model_built": True,
                                    "raw_bytes": len(content_bytes),
                                    "line_count": len(candidate_lines),
                                },
                            })
                        else:
                            violations.append({
                                "rule": "SUSPECTED_LEAK",
                                "archive": arc.name,
                                "member": m.name,
                                "evidence": {
                                    "sha256": raw_sha,
                                    "non_trivial_overlap": len(overlap),
                                    "overlap_lines": sorted(overlap),
                                    "raw_bytes": len(content_bytes),
                                },
                            })
        except Exception as e:  # noqa: BLE001
            violations.append({
                "rule": "workspace_archive_unreadable",
                "archive": arc.name,
                "error": str(e),
            })

    return violations


def selftest() -> int:
    """離線自測：在臨時目錄中建立 mock 封存與隱藏檔，驗證三種裁決狀態。"""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_dir = pathlib.Path(tmp_str)
        hid_dir = tmp_dir / "hidden"
        vis_dir = tmp_dir / "visible"
        ws_dir = tmp_dir / "workspace"
        hid_dir.mkdir()
        vis_dir.mkdir()
        ws_dir.mkdir()

        # 隱藏檔：含有特定隱藏測資
        (hid_dir / "test_hidden.py").write_text(
            "val = 42\nunique_hidden_check = 9999\n", encoding="utf-8"
        )
        # 可見檔：含有公開測資
        (vis_dir / "test_visible.py").write_text(
            "val = 10\n", encoding="utf-8"
        )

        # 1. 確信違規：位元組完全一致
        (ws_dir / "test_hidden.py").write_text(
            "val = 42\nunique_hidden_check = 9999\n", encoding="utf-8"
        )
        # 2. 良性假陽性：同名檔但內容為自建、且無隱藏獨有行
        (ws_dir / "test_hidden_fake.py").write_text(
            "model_val = 12345\nassert model_val > 0\n", encoding="utf-8"
        )
        # 3. 疑似洩漏：含隱藏獨有行但全文不完全相同
        (ws_dir / "test_hidden_suspect.py").write_text(
            "extra_prefix = 1\nunique_hidden_check = 9999\n", encoding="utf-8"
        )

        tar_path = ws_dir / "test.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            tf.add(ws_dir / "test_hidden.py", arcname="tests_visible/test_hidden.py")
            tf.add(ws_dir / "test_hidden_fake.py", arcname="tests_visible/test_hidden_fake.py")
            tf.add(ws_dir / "test_hidden_suspect.py", arcname="tests_visible/test_hidden_suspect.py")

        task = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": "mock_task"}
        res = audit_workspace(ws_dir, task)

        rules = {r["rule"] for r in res}
        expected = {"CONFIRMED_VIOLATION", "FALSE_POSITIVE_BENIGN", "SUSPECTED_LEAK"}
        if rules == expected:
            print("VERDICT: HIDDEN_FILE_TIGHTEN_OK")
            return 0

        print(f"VERDICT: HIDDEN_FILE_TIGHTEN_BROKEN (got {rules}, want {expected})")
        return 1


def audit_r530() -> int:
    """自動開封比對 R530 既有 4 筆違規 run，輸出機械審計報告。"""
    r530_cases = [
        {
            "run": "runs/g_r530_s1_1004_1",
            "archive": "ow_09_minitemplate__A-CONF__a2.tar.gz",
            "member": "ow_09_minitemplate__A-CONF__g-r530-s1/tests_visible/test_hidden.py",
            "task_id": "ow_09_minitemplate",
        },
        {
            "run": "runs/g_r530_s2_1003_1",
            "archive": "ow_09_minitemplate__A-CONF__a2.tar.gz",
            "member": "ow_09_minitemplate__A-CONF__g-r530-s2/tests_hidden.py",
            "task_id": "ow_09_minitemplate",
        },
        {
            "run": "runs/g_r530_s2_1004_2",
            "archive": "ow_19_redact__A-GATE__a1.tar.gz",
            "member": "ow_19_redact__A-GATE__g-r530-s2/tests_visible/test_hidden.py",
            "task_id": "ow_19_redact",
        },
        {
            "run": "runs/g_r530_s3_1003_1",
            "archive": "ow_04_layerconf__A-GATE__a1.tar.gz",
            "member": "ow_04_layerconf__A-GATE__g-r530-s3/tests_hidden.py",
            "task_id": "ow_04_layerconf",
        },
    ]

    records: list[dict[str, Any]] = []
    all_benign = True

    for c in r530_cases:
        task_id = c["task_id"]
        hid_dir = REPO / "ops" / "gain" / "r530" / "hidden" / task_id
        vis_dir = REPO / "ops" / "gain" / "r530" / "bank" / task_id / "tests_visible"
        task_spec = {"hidden_dir": hid_dir, "visible_dir": vis_dir, "task_id": task_id}

        ws_dir = REPO / c["run"] / "ws"
        if not ws_dir.is_dir():
            print(f"R530 run ws directory not found: {ws_dir}", file=sys.stderr)
            return 1

        res = audit_workspace(ws_dir, task_spec)
        matched = [r for r in res if r.get("archive") == c["archive"] and r.get("member") == c["member"]]
        if not matched:
            print(f"Missing violation match for {c['run']} {c['archive']}:{c['member']}", file=sys.stderr)
            return 1

        v = matched[0]
        verdict = v["rule"]
        if verdict != "FALSE_POSITIVE_BENIGN":
            all_benign = False

        rec = {
            "run": c["run"],
            "archive": c["archive"],
            "member": c["member"],
            "task_id": task_id,
            "verdict": verdict,
            "evidence": v.get("evidence", {}),
        }
        records.append(rec)

    report = {
        "schema": "vacant.audit/r530_hidden_file_tighten/1",
        "purpose": "R530 4 筆 hidden_file_in_workspace 違規機械複核（收緊判準）",
        "n_audited": len(records),
        "all_benign": all_benign,
        "records": records,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH}")

    if all_benign:
        print("VERDICT: R530_TIGHTEN_AUDIT_OK")
        return 0

    print("VERDICT: R530_TIGHTEN_AUDIT_FAIL")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="收緊 hidden_file_in_workspace 判準鑑別工具")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="執行離線自我測試")
    g.add_argument("--audit-r530", action="store_true", help="執行 R530 4 筆違規歷史複核")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()
    if args.audit_r530:
        return audit_r530()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
