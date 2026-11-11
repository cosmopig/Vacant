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


def main() -> int:
    raw = RESULT.read_bytes()
    d = json.loads(raw.decode("utf-8"))
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
    chk(tot.get("cells") == 12 and tot.get("cells_run") == 12, "totals.cells/cells_run")

    for c in cells:
        if c.get("answer") is not None:
            chk(hashlib.sha256(c["answer"].encode("utf-8")).hexdigest() == c.get("answer_sha256"),
                f"{c.get('task')}/{c.get('arm')} answer_sha256 重算不符")

    cell_known = sum(v for v in (_cell_tokens(c) for c in cells) if v is not None)
    ext_known = sum(v for t in d.get("tasks", []) for u in (t.get("extract_usages") or [])
                    for v in [u.get("tokens")] if _num(v))
    chk(_num(tot.get("tokens")) and cell_known + ext_known == tot["tokens"],
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

    out = {
        "schema": "vacant.audit/g3_fire_20261111_summary/1",
        "generated_by": "ops/audits/g3_fire_20261111_summary.py",
        "identity": {
            "result_file": str(RESULT),
            "result_bytes": len(raw),
            "result_sha256": hashlib.sha256(raw).hexdigest(),
            "result_file_mtime_utc": datetime.fromtimestamp(RESULT.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
            "approval_file": str(APPROVAL),
            "approval_sha256": hashlib.sha256(APPROVAL.read_bytes()).hexdigest() if APPROVAL.exists() else None,
            "approval_approved": (ap or {}).get("approved"),
            "approval_epic": (ap or {}).get("epic"),
        },
        "fire": {
            "fired_at": d.get("fired_at"),
            "launcher": "systemd user unit vacant-g3-fire-20261111（r1426 發射；一次性、無 [Install]、不自動再發射）",
            "out_dir": str(FIRE),
            "journal": "journalctl --user -u vacant-g3-fire-20261111",
            "done_marker": "journal 尾行『G3 FIRE DONE』（2026-11-11T06:02:37Z）；unit inactive (dead)",
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
            "note": "8 個 error 格無 usage → 該格 tokens=None（UNKNOWN），不填 0；49744＝20887（dab_129 native_pi）＋28857（4 次擷取）",
        },
        "hidden_after": "12/12 UNKNOWN——不自己打分；打分照 /srv/vlab 作業慣例（人類/vlab 側）",
        "failures": [
            {"cells": 8, "arms": ["reqlist_only", "full_rloop"], "rounds": "round 1",
             "error": "glm rc=4: glm: 失敗（token_limit）Stopped: token_limit",
             "harness_behavior": "停、不重試（quota_fail_closed，spec 內行為）",
             "note": "provider 側 token_limit；非本地 2M/日 額度（known_tokens 49744 ≪ 2000000）"},
            {"cells": 3, "arms": ["native_pi"], "rounds": "round 1",
             "error": "pi timed out after 300s",
             "note": "dab_129 native_pi 278s 完成；dab_144/176/216 超 300s/輪 預算"},
        ],
        "scope_note": [
            "G3 首次真發射（未見任務對照），單 1 rep、本地模型（H-12），不遷移到其他模型/harness",
            "11/12 格 error：本批不能支持任何臂 superiority 結論",
            "full_rloop content_reverify enabled 4/4，但皆 round 1 error、0 重算輪、final_verdict 全 null",
            "dab_129/native_pi 為唯一 ok 格（answer 在位、hidden_after=UNKNOWN、待 vlab/人類側打分）",
            "stop_reason=null＝12 格全跑完（非撞額度中斷）；quota.known_tokens 49744",
        ],
    }
    if problems:
        for p in problems:
            print(f"BROKEN: {p}", file=sys.stderr)
        print("VERDICT: G3_FIRE_SUMMARY_BROKEN")
        return 1
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = sum(p["ok"] for p in per_arm.values())
    er = sum(p["error"] for p in per_arm.values())
    print(f"cells=12 ok/err={ok}/{er} hidden_after=12xUNKNOWN tokens_known={cell_known + ext_known} "
          f"stop_reason={d.get('stop_reason')}")
    print("VERDICT: G3_FIRE_SUMMARY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
