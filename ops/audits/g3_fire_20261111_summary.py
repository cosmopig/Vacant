#!/usr/bin/env python3
"""P20261111_0512-1：G3 真發射誠實審計摘要的產生器（可重跑）。

讀（只讀）：
- ~/dev/ops/g3_fire_20261111/g3_result.json（發射結果，schema vacant.reqloop.g3.result/1；raw 留 repo 外）
- ~/dev/ops/approvals/g3_vq-1zf_fire_20261111.json（人類核准文件；只讀、不自改自簽）
寫：ops/audits/g3_fire_20261111_summary.json

口徑（混用即錯）：
- 缺值一律 None（UNKNOWN），不填 0、不留佔位。
- hidden_after 全 UNKNOWN——本迴圈不自己打分；打分照 /srv/vlab 慣例（人類/vlab 側）。
- 同批重跑須簿記如實標記、不得當獨立樣本（本摘要不宣稱任何臂優）。
- 11/12 格 error＋單 1 rep（H-12 本地模型）：本批不能支持任何臂 superiority 結論。
- token 獨立重算：cells usage 之和 ＋ tasks extract_usages 之和 必須等於 totals.tokens。

用法：python3 ops/audits/g3_fire_20261111_summary.py [result.json [out.json]]
  （預設＝上述 live raw／repo 的 ops/audits/g3_fire_20261111_summary.json；
  argv 注入供 CI/沙盒用 tmp 檔——r1339 queue 路徑注入同型）

r1428（vq-el4.97，TDD RED→GREEN）：
- tokens 重算補非空守衛：舊碼對「全部 usage 缺失＋totals.tokens=0」的零測量檔
  判 0+0==0 → VERDICT OK rc=0＝無成本假綠燈（I-4 未測量不是通過；r1272 空檔
  vacuous、r1344 死守衛同族；RED 實證於 tests/test_reqloop_g3_fire_summary.py
  ::test_negative_vacuous_tokens）。
- 缺檔／非 JSON 不再崩成 traceback：點名 BROKEN＋單一裁決行（vq-el4.39）。
- 負控制：tests/test_reqloop_g3_fire_summary.py（正 2＋repo 摘要 1＋負 5）。

r1432（P20261111_0710-1，重發 20261111b 收案）：摘要敘事改由 result 資料驅動——
cells_run 容許 not_run 格（重發 12 格＝4ok＋6err＋2not_run、cells_run=10）；
failures／scope_note／token note 不再硬編碼某次發射的數字（首發 49744 那套敘事
對重發就是假摘要，同型名實不符）。同一腳本對首發 live raw 仍 VERDICT OK（正控制）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[2]
FIRE = pathlib.Path.home() / "dev/ops" / "g3_fire_20261111"
RESULT = FIRE / "g3_result.json"
APPROVAL = pathlib.Path.home() / "dev/ops" / "approvals" / "g3_vq-1zf_fire_20261111.json"
DEST = REPO / "ops" / "audits" / "g3_fire_20261111_summary.json"


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _cell_tokens(cell: dict):
    us = [u for r in cell.get("rounds") or [] for u in (r.get("usages") or []) if isinstance(u, dict)]
    if not us:
        return None
    vals = [u.get("tokens") for u in us]
    if any(not _num(v) for v in vals):
        return None
    return sum(vals)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    result_path = pathlib.Path(argv[0]) if len(argv) >= 1 else RESULT
    dest = pathlib.Path(argv[1]) if len(argv) >= 2 else DEST
    try:
        raw = result_path.read_bytes()
    except OSError as e:
        print(f"BROKEN: result 檔無法讀取：{e}", file=sys.stderr)
        print("VERDICT: G3_FIRE_SUMMARY_BROKEN")
        return 1
    try:
        d = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        print("BROKEN: result 非合法 JSON", file=sys.stderr)
        print("VERDICT: G3_FIRE_SUMMARY_BROKEN")
        return 1
    problems: list[str] = []

    def chk(cond: bool, msg: str) -> None:
        if not cond:
            problems.append(msg)

    cells = d.get("cells") or []
    chk(d.get("schema") == "vacant.reqloop.g3.result/1", f"schema={d.get('schema')!r}")
    chk(len(cells) == 12, f"cells={len(cells)}")
    chk(all(c.get("status") in ("ok", "error", "not_run", "partial_quota") for c in cells), "bad status")
    chk(all(c.get("hidden_after") == "UNKNOWN" for c in cells), "hidden_after 非全 UNKNOWN")
    chk(all(c.get("answer") is None for c in cells if c.get("status") != "ok"), "error 格有 answer")
    tot = d.get("totals") or {}
    not_run_cells = [c for c in cells if c.get("status") == "not_run"]
    ok_n = sum(1 for c in cells if c.get("status") == "ok")
    chk(tot.get("cells") == 12 and _num(tot.get("cells_run"))
        and tot["cells_run"] == 12 - len(not_run_cells),
        f"totals.cells_run={tot.get('cells_run')!r} 應＝12-not_run({len(not_run_cells)})")

    for c in cells:
        if c.get("answer") is not None:
            chk(hashlib.sha256(c["answer"].encode("utf-8")).hexdigest() == c.get("answer_sha256"),
                f"{c.get('task')}/{c.get('arm')} answer_sha256 重算不符")

    cell_vals = [v for v in (_cell_tokens(c) for c in cells) if v is not None]
    ext_vals = [v for t in d.get("tasks", []) for u in (t.get("extract_usages") or [])
                for v in [u.get("tokens")] if _num(v)]
    cell_known = sum(cell_vals)
    ext_known = sum(ext_vals)
    n_known = len(cell_vals) + len(ext_vals)
    # r1428（vq-el4.97）：非空守衛——舊碼對「零測量」檔（0 已知 usage＋
    # totals.tokens=0）判 0+0==0 → OK＝無成本假綠燈（I-4：未測量不是通過）。
    chk(n_known > 0,
        "tokens 重算空集：0 個已知 usage（未測量不是通過；I-4）——零 measurement 不得判 OK")
    chk(_num(tot.get("tokens")), f"totals.tokens 缺值：{tot.get('tokens')!r}（UNKNOWN 不是 0）")
    chk(n_known > 0 and _num(tot.get("tokens")) and cell_known + ext_known == tot["tokens"],
        f"tokens 重算 {cell_known}+{ext_known} != {tot.get('tokens')!r}")

    per_arm: dict = {}
    for arm in d.get("arms", []):
        sub = [c for c in cells if c.get("arm") == arm]
        per_arm[arm] = {
            "cells": len(sub),
            "ok": sum(1 for c in sub if c.get("status") == "ok"),
            "error": sum(1 for c in sub if c.get("status") == "error"),
            "errors": sorted({c.get("error") or "" for c in sub if c.get("status") == "error"}),
            "content_reverify_final_verdicts": sorted({str((c.get("content_reverify") or {}).get("final_verdict")) for c in sub}),
        }

    ap: dict | None = None
    if APPROVAL.exists():
        ap = json.loads(APPROVAL.read_text(encoding="utf-8"))

    # r1432：failures 由 cells 實際狀態分組——硬編碼某次發射的敘事對別次發射就是假摘要。
    failures: list[dict] = []
    for msg in sorted({c.get("error") for c in cells if c.get("status") == "error"}, key=str):
        grp = [c for c in cells if c.get("status") == "error" and c.get("error") == msg]
        failures.append({"cells": len(grp), "arms": sorted({c.get("arm") for c in grp}),
                         "error": msg, "harness_behavior": "停、不重試（quota_fail_closed，spec 內行為）"})
    if not_run_cells:
        failures.append({"cells": len(not_run_cells), "arms": sorted({c.get("arm") for c in not_run_cells}),
                         "status": "not_run",
                         "note": f"stop_reason={d.get('stop_reason')!r}；無 usage／answer（UNKNOWN 不填 0）"})

    out = {
        "schema": "vacant.audit/g3_fire_20261111_summary/1",
        "generated_by": "ops/audits/g3_fire_20261111_summary.py",
        "identity": {
            "result_file": str(result_path),
            "result_bytes": len(raw),
            "result_sha256": hashlib.sha256(raw).hexdigest(),
            "result_file_mtime_utc": datetime.fromtimestamp(result_path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
            "approval_file": str(APPROVAL),
            "approval_sha256": hashlib.sha256(APPROVAL.read_bytes()).hexdigest() if APPROVAL.exists() else None,
            "approval_approved": (ap or {}).get("approved"),
            "approval_epic": (ap or {}).get("epic"),
            "approval_inline_in_result": d.get("approval"),
        },
        "fire": {
            "fired_at": d.get("fired_at"),
            "ticket": d.get("ticket"),
            "out_dir": str(result_path.parent),
            "stop_reason": d.get("stop_reason"),
        },
        "scope": "4 未見題（dab_129/144/176/216）× 3 臂（native_pi/reqlist_only/full_rloop）＝12 格；同批重跑須簿記如實標記、不得當獨立樣本",
        "models": {
            "extract": d.get("extract_model"),
            "answer_glm_arms": d.get("answer_model"),
            "native_pi_provider": (d.get("budget") or {}).get("pi_provider"),
            "native_pi_model": (d.get("budget") or {}).get("pi_model"),
        },
        "tasks": [{"task_id": t.get("task_id"), "input_sha256": t.get("input_sha256"),
                   "required_answer_names": t.get("required_answer_names"),
                   "n_requirements": t.get("n_requirements"), "extract_error": t.get("extract_error"),
                   "extract_usages": t.get("extract_usages")} for t in d.get("tasks", [])],
        "cells": [{"task": c.get("task"), "arm": c.get("arm"), "status": c.get("status"),
                   "rounds": len(c.get("rounds") or []), "error": c.get("error"),
                   "answer": c.get("answer"), "answer_sha256": c.get("answer_sha256"),
                   "tokens": _cell_tokens(c), "hidden_after": c.get("hidden_after"),
                   "content_reverify": c.get("content_reverify")} for c in cells],
        "per_arm": per_arm,
        "totals": tot,
        "token_accounting": {
            "cell_tokens_known": cell_known,
            "extract_tokens_known": ext_known,
            "known_total": cell_known + ext_known,
            "known_usages": n_known,
            "note": (f"已知 usage：cells {len(cell_vals)}/12 格、extract {len(ext_vals)} 次（known_usages={n_known}）；"
                     "缺 usage 格 tokens=None（UNKNOWN），不填 0；非空守衛：0 已知 usage 不得判 OK"),
        },
        "hidden_after": "12/12 UNKNOWN——不自己打分；打分照 /srv/vlab 作業慣例（人類/vlab 側）",
        "failures": failures,
        "scope_note": [
            f"ok {ok_n}/12 格 answer 在位、hidden_after 全 UNKNOWN——不自己打分（打分照 /srv/vlab 慣例、人類/vlab 側）",
            f"非 ok {12 - ok_n}/12 格（error/not_run）：本批不宣稱任何臂 superiority",
            "單 1 rep、本地模型（H-12）、不遷移到其他模型/harness；同批重跑須簿記如實標記、不得當獨立樣本",
            f"stop_reason={d.get('stop_reason')!r}；quota.known_tokens={(d.get('quota') or {}).get('known_tokens')!r}",
        ],
    }
    if problems:
        for p in problems:
            print(f"BROKEN: {p}", file=sys.stderr)
        print("VERDICT: G3_FIRE_SUMMARY_BROKEN")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(p["ok"] for p in per_arm.values())
    er = sum(p["error"] for p in per_arm.values())
    print(f"cells=12 ok/err/not_run={ok}/{er}/{len(not_run_cells)} hidden_after=12xUNKNOWN "
          f"tokens_known={cell_known + ext_known} stop_reason={d.get('stop_reason')}")
    print("VERDICT: G3_FIRE_SUMMARY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
