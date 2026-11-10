#!/usr/bin/env python3
"""verify_effects_summary —— ops/audits/effects_20261105_summary.json 核數單一指令（r1333, vq-el4.53）。

背景：自 r1266 起「開啟 effects summary 並核數」的 redo 已重複 8 次以上
（r1268/r1272/r1274/r1275/r1279/r1280/r1281/r1283/r1330 redo），每次都靠人工
程式載入＋口頭記錄——漏核一項無人可偵測（H-0 同構：漏掉一項得到的綠燈就是
漏洞成因；I-4：未測量不是通過）。本指令把核數收斂為單一指令、一個裁決行：

  identity        schema / snapshot / 相位集合 / 頂層欄位
  discipline      成本欄位 int>=0 或 None（缺值＝UNKNOWN 不填 0，不得字串/bool）
  policy30_internal     相位級所有聚合＝逐格重算（總和＋per-arm＋mismatch 清單）
  once20_internal       同上
  totals          total_cells / local_matches_total / current_code_matches_total＝相位加總
  reference       人類任務參考值（11-05 設計＋11-06 第 6 條，見 REFERENCE 註）
  scope_note      關鍵聲明子串在位（開發選樣／無硬 token 上限／單 rep／
                  sessions≠API／hidden_after 全 UNKNOWN／缺值 None 不填 0）

用法：
  python3 ops/reqloop/verify_effects_summary.py [path]
    # rc 0 + VERDICT: EFFECTS_SUMMARY_OK      —— 全項 OK
    # rc 1 + VERDICT: EFFECTS_SUMMARY_BROKEN  —— 任一项 BROKEN（detail 點名）

全唯讀、0 model calls、stdlib only（乾淨 CI venv 安全，不觸及安裝合約掃描）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO / "ops" / "audits" / "effects_20261105_summary.json"

# 身份釘住（2026-11-05 審計產物；r1266–r1330 各輪 redo 重算一致）。
EXPECTED_SCHEMA = "vacant.audit/effects_20261105_summary/1"
EXPECTED_SNAPSHOT = "d38d2eb21d7ffbb927eb263e657d907dc112bc7d"
EXPECTED_PHASES = ("policy30", "feedback_once20")
EXPECTED_TOP_KEYS = frozenset({
    "code_under_audit", "current_code_matches_total", "local_matches_total",
    "phases", "schema", "scope_note", "snapshot_sha", "source_root", "total_cells",
})

# 人類參考值。來源：2026-11-05 任務（policy30＝15 草稿×兩臂、once20＝10 錯誤草稿×兩臂
# 各一輪）；2026-11-06 任務第 6 條（policy30 generic7/10、localized6/10；once20
# generic7/10、localized4/10；皆為開發選樣單 rep，不宣稱 localized 較好）。
# 分母 10＝該臂錯誤草稿數。改動這些數字＝改動人類參考，必須是人類決策。
REFERENCE = {
    "policy30": {
        "cells": 30, "wrong_to_right": 13, "right_to_wrong": 0,
        "preserved_good": 10, "still_wrong": 7,
        "arm_w2r": {"generic": 7, "localized": 6},
        "repair_sessions_total": 35, "api_model_calls_true_total": 915,
        "tokens_true_total": 33670510,
        "local_matches": 27, "current_code_matches": 30,
    },
    "feedback_once20": {
        "cells": 20, "wrong_to_right": 11, "right_to_wrong": 0,
        "preserved_good": 0, "still_wrong": 9,
        "arm_w2r": {"generic": 7, "localized": 4},
        "repair_sessions_total": 20, "api_model_calls_true_total": 457,
        "tokens_true_total": 19503953,
        "local_matches": 18, "current_code_matches": 20,
    },
}
TOTALS_REF = {"total_cells": 50, "local_matches_total": 45, "current_code_matches_total": 50}

# scope_note 關鍵聲明（逐字子串）。任何一條被改寫＝scope 被削弱，必須照紅。
SCOPE_PHRASES = (
    "開發選樣",
    "無硬 token 上限",
    "單 rep",
    "repair_sessions（agent 啟動數）與 API 請求數是兩個量",
    "hidden_after（本地重跑 hidden scorer）全格＝UNKNOWN",
    "所有缺值＝None（UNKNOWN），不填 0",
)

COST_FIELDS = ("repair_sessions", "api_model_calls_true", "tokens_true", "wall_ms_total")
BOOL_FIELDS = ("before_pass_independent", "after_independent",
               "local_matches_independent", "current_code_matches_independent")
ARM_KEYS = ("cells", "wrong_to_right", "right_to_wrong", "preserved_good",
            "still_wrong", "repair_sessions", "api_model_calls_true",
            "tokens_true", "wall_ms_total")


def _num(v) -> int:
    """重算用：int>=0 取原值；None（UNKNOWN）與任何非法型別取 0。
    非法型別由 discipline 項點名，這裡只保证重算不崩。"""
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        return 0
    return v


def _recompute_phase(p: dict) -> dict:
    cds = p.get("cells_detail") or []
    agg = {
        "cells": len(cds),
        "wrong_to_right": sum(1 for c in cds if not c.get("before_pass_independent") and c.get("after_independent")),
        "right_to_wrong": sum(1 for c in cds if c.get("before_pass_independent") and not c.get("after_independent")),
        "preserved_good": sum(1 for c in cds if c.get("before_pass_independent") and c.get("after_independent")),
        "still_wrong": sum(1 for c in cds if not c.get("before_pass_independent") and not c.get("after_independent")),
        "local_matches": sum(1 for c in cds if c.get("local_matches_independent")),
        "current_code_matches": sum(1 for c in cds if c.get("current_code_matches_independent")),
    }
    for f in ("repair_sessions", "api_model_calls_true", "tokens_true", "wall_ms_total"):
        agg[f] = sum(_num(c.get(f)) for c in cds)
    per_arm: dict[str, dict] = {}
    for arm in sorted({c.get("arm") for c in cds}):
        sub = [c for c in cds if c.get("arm") == arm]
        per_arm[arm] = {
            "cells": len(sub),
            "wrong_to_right": sum(1 for c in sub if not c.get("before_pass_independent") and c.get("after_independent")),
            "right_to_wrong": sum(1 for c in sub if c.get("before_pass_independent") and not c.get("after_independent")),
            "preserved_good": sum(1 for c in sub if c.get("before_pass_independent") and c.get("after_independent")),
            "still_wrong": sum(1 for c in sub if not c.get("before_pass_independent") and not c.get("after_independent")),
        }
        for f in ("repair_sessions", "api_model_calls_true", "tokens_true", "wall_ms_total"):
            per_arm[arm][f] = sum(_num(c.get(f)) for c in sub)
    agg["per_arm"] = per_arm
    return agg


def _phase_internal_check(name: str, p: dict | None) -> tuple[str, bool, str]:
    if not isinstance(p, dict):
        return name, False, f"{name}: phases 缺該相位"
    try:
        agg = _recompute_phase(p)
    except Exception as e:  # noqa: BLE001 — fail-closed
        return name, False, f"{name}: 重算例外 {type(e).__name__}: {e}"
    # 相位級檔案鍵：repair_sessions / api_model_calls_true / tokens_true 帶 _total 後綴；
    # 其餘（cells、w2r/r2w/pg/sw、local/current、wall_ms_total）不帶。
    PHASE_KEYMAP = {
        "repair_sessions": "repair_sessions_total",
        "api_model_calls_true": "api_model_calls_true_total",
        "tokens_true": "tokens_true_total",
    }
    problems: list[str] = []
    for key, want in agg.items():
        if key == "per_arm":
            continue
        fkey = PHASE_KEYMAP.get(key, key)
        have = p.get(fkey)
        if have != want:
            problems.append(f"{fkey}={have}（逐格重算={want}）")
    # r1354（vq-el4.60）：movement_total（人審 headline）覆核——
    # 必須＝逐格重算 w2r+r2w；缺值或不符即 BROKEN。此前 13→12 仍 7/7 OK rc=0
    # 假綠燈（實測 RED）；H-0：漏一項得到的綠燈就是洞的成因；I-4：未覆核不是通過。
    want_movement = agg["wrong_to_right"] + agg["right_to_wrong"]
    have_movement = p.get("movement_total")
    if have_movement != want_movement:
        problems.append(f"movement_total={have_movement}（逐格重算 w2r+r2w={want_movement}）")
    have_arms = p.get("per_arm") or {}
    if set(have_arms) != set(agg["per_arm"]):
        problems.append(f"per_arm 臂集合={sorted(have_arms)}（重算={sorted(agg['per_arm'])}）")
    else:
        for arm, want_arm in agg["per_arm"].items():
            have_arm = have_arms.get(arm) or {}
            for key in ARM_KEYS:
                if have_arm.get(key) != want_arm.get(key):
                    problems.append(f"per_arm.{arm}.{key}={have_arm.get(key)}（重算={want_arm.get(key)}）")
    # mismatch 清單與逐格一致（local 與 current 兩張表）
    for flag, list_key, count_key in (
        ("local_matches_independent", "local_vs_independent_mismatches", "local_matches"),
        ("current_code_matches_independent", "current_code_vs_independent_mismatches", "current_code_matches"),
    ):
        n_false = sum(1 for c in (p.get("cells_detail") or []) if not c.get(flag))
        n_list = len(p.get(list_key) or [])
        if n_list != n_false:
            problems.append(f"{list_key} 長度={n_list}（逐格 {flag}=False 格數={n_false}）")
        if count_key in p and p.get(count_key) is not None:
            pass  # 已於上方總和比對涵蓋
    if agg["cells"] == 0:
        problems.append("cells_detail 為空（I-4：未測量不是通過）")
    if problems:
        return name, False, f"{name}: " + "；".join(problems[:6])
    return name, True, f"{name}: {agg['cells']} 格；w2r={agg['wrong_to_right']}/r2w={agg['right_to_wrong']}；" \
                       f"movement={want_movement}；" \
                       f"arm w2r=" + "/".join(f"{a}{v['wrong_to_right']}" for a, v in sorted(agg['per_arm'].items()))


def _discipline_check(d: dict) -> tuple[str, bool, str]:
    problems: list[str] = []
    n_cells = 0
    for ph, p in (d.get("phases") or {}).items():
        if not isinstance(p, dict):
            continue
        for c in p.get("cells_detail") or []:
            n_cells += 1
            tag = f"{ph}:{c.get('draft')}"
            if c.get("arm") not in ("generic", "localized"):
                problems.append(f"{tag} arm={c.get('arm')!r}")
            if c.get("role") not in ("good", "bad"):
                problems.append(f"{tag} role={c.get('role')!r}")
            for f in BOOL_FIELDS:
                if not isinstance(c.get(f), bool):
                    problems.append(f"{tag} {f}={c.get(f)!r}（應為 bool）")
            for f in COST_FIELDS:
                v = c.get(f)
                if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                    problems.append(f"{tag} {f}={v!r}（應為 int>=0 或 None）")
    if n_cells == 0:
        problems.append("全檔 0 格（I-4：未測量不是通過）")
    if problems:
        return "discipline", False, "discipline: " + "；".join(problems[:6])
    return "discipline", True, f"discipline: {n_cells} 格成本欄位全為 int>=0 或 None；bool 欄位全為 bool"


def _reference_check(d: dict) -> tuple[str, bool, str]:
    problems: list[str] = []
    phases = d.get("phases") or {}
    for ph, ref in REFERENCE.items():
        p = phases.get(ph)
        if not isinstance(p, dict):
            problems.append(f"{ph}: 相位缺失")
            continue
        for key, want in ref.items():
            if key == "arm_w2r":
                for arm, w2r in want.items():
                    have = (p.get("per_arm") or {}).get(arm, {}).get("wrong_to_right")
                    if have != w2r:
                        problems.append(f"{ph}.per_arm.{arm}.wrong_to_right={have}（參考={w2r}）")
                continue
            have = p.get(key)
            if have != want:
                problems.append(f"{ph}.{key}={have}（參考={want}）")
    for key, want in TOTALS_REF.items():
        have = d.get(key)
        if have != want:
            problems.append(f"{key}={have}（參考={want}）")
    if problems:
        return "reference", False, "reference: " + "；".join(problems[:6])
    return "reference", True, (
        "reference: policy30 13w/0r（g7/l6）· once20 11w/0r（g7/l4）· "
        "35/20 sessions · 915/457 API · 33670510/19503953 tokens · 50 格 —— 與人類任務參考值一致"
    )


def _scope_check(d: dict) -> tuple[str, bool, str]:
    note = d.get("scope_note") or ""
    missing = [s for s in SCOPE_PHRASES if s not in note]
    if missing:
        return "scope_note", False, "scope_note: 缺關鍵聲明 " + "、".join(missing)
    return "scope_note", True, "scope_note: 6 條關鍵聲明在位（開發選樣／無硬 token 上限／單 rep／sessions≠API／hidden_after 全 UNKNOWN／缺值 None）"


def verify(path: Path) -> list[tuple[str, bool, str]]:
    """對一份 effects summary 檔案做全部核數。返回 (name, ok, detail) 列表。
    永不拋出：任何異常＝該項 BROKEN（fail-closed）。"""
    checks: list[tuple[str, bool, str]] = []
    p = Path(path)
    raw: bytes | None = None
    d: dict | None = None
    try:
        raw = p.read_bytes()
        d = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        checks.append(("identity", False, f"identity: 檔案不可讀/非 JSON：{type(e).__name__}: {e}"))
        checks.append(("discipline", False, "discipline: 無法載入"))
        for ph in EXPECTED_PHASES:
            checks.append((f"{ph}_internal", False, f"{ph}_internal: 無法載入"))
        checks.append(("totals", False, "totals: 無法載入"))
        checks.append(("reference", False, "reference: 無法載入"))
        checks.append(("scope_note", False, "scope_note: 無法載入"))
        return checks

    # identity
    problems: list[str] = []
    if not raw:
        problems.append("空檔")
    if d.get("schema") != EXPECTED_SCHEMA:
        problems.append(f"schema={d.get('schema')!r}")
    snap = d.get("snapshot_sha") or ""
    if not snap.startswith(EXPECTED_SNAPSHOT[:8]):
        problems.append(f"snapshot_sha={snap[:12]}…")
    phases = d.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(EXPECTED_PHASES):
        problems.append(f"phases 鍵={sorted(phases) if isinstance(phases, dict) else type(phases).__name__}")
    if set(d) != EXPECTED_TOP_KEYS:
        problems.append(f"頂層鍵差={sorted(set(d) ^ EXPECTED_TOP_KEYS)}")
    if problems:
        checks.append(("identity", False, "identity: " + "；".join(problems[:6])))
    else:
        checks.append(("identity", True, f"identity: {len(raw)} bytes；schema/snapshot/相位/頂層鍵齊"))

    # 每項獨立 try，任何一項崩潰不牽連其他（fail-closed）
    for fn, d_arg in (
        (_discipline_check, d),
        (lambda dd: _phase_internal_check("policy30_internal", dd.get("phases", {}).get("policy30")), d),
        (lambda dd: _phase_internal_check("once20_internal", dd.get("phases", {}).get("feedback_once20")), d),
    ):
        try:
            checks.append(fn(d_arg))
        except Exception as e:  # noqa: BLE001
            checks.append((fn.__name__, False, f"例外 {type(e).__name__}: {e}"))

    # totals（內部加總；參考值由 reference 項釘住）
    try:
        phases = d.get("phases") or {}
        cells_sum = sum((phases.get(ph) or {}).get("cells") or 0 for ph in EXPECTED_PHASES)
        local_sum = sum((phases.get(ph) or {}).get("local_matches") or 0 for ph in EXPECTED_PHASES)
        current_sum = sum((phases.get(ph) or {}).get("current_code_matches") or 0 for ph in EXPECTED_PHASES)
        problems = []
        if d.get("total_cells") != cells_sum:
            problems.append(f"total_cells={d.get('total_cells')}（相位加總={cells_sum}）")
        if d.get("local_matches_total") != local_sum:
            problems.append(f"local_matches_total={d.get('local_matches_total')}（相位加總={local_sum}）")
        if d.get("current_code_matches_total") != current_sum:
            problems.append(f"current_code_matches_total={d.get('current_code_matches_total')}（相位加總={current_sum}）")
        if problems:
            checks.append(("totals", False, "totals: " + "；".join(problems)))
        else:
            checks.append(("totals", True, f"totals: {cells_sum} 格；local={local_sum}；current={current_sum}（＝相位加總）"))
    except Exception as e:  # noqa: BLE001
        checks.append(("totals", False, f"totals: 例外 {type(e).__name__}: {e}"))

    try:
        checks.append(_reference_check(d))
    except Exception as e:  # noqa: BLE001
        checks.append(("reference", False, f"reference: 例外 {type(e).__name__}: {e}"))
    try:
        checks.append(_scope_check(d))
    except Exception as e:  # noqa: BLE001
        checks.append(("scope_note", False, f"scope_note: 例外 {type(e).__name__}: {e}"))
    return checks


def _print_summary(d: dict) -> None:
    """供 STATE 條目引用的逐相/逐臂數字表（唯讀輸出）。"""
    for ph in EXPECTED_PHASES:
        p = (d.get("phases") or {}).get(ph) or {}
        arms = p.get("per_arm") or {}
        parts = []
        for arm in ("generic", "localized"):
            a = arms.get(arm) or {}
            parts.append(
                f"{arm}: {a.get('cells')}格 w2r={a.get('wrong_to_right')} r2w={a.get('right_to_wrong')} "
                f"pg={a.get('preserved_good')} sw={a.get('still_wrong')} "
                f"sess={a.get('repair_sessions')} api={a.get('api_model_calls_true')} tok={a.get('tokens_true')}"
            )
        print(f"  {ph}: {p.get('cells')}格 w2r={p.get('wrong_to_right')}/r2w={p.get('right_to_wrong')} "
              f"pg={p.get('preserved_good')} sw={p.get('still_wrong')} local={p.get('local_matches')}/"
              f"current={p.get('current_code_matches')} | " + "；".join(parts))
        print(f"    總量: sess={p.get('repair_sessions_total')} api={p.get('api_model_calls_true_total')} "
              f"tok={p.get('tokens_true_total')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=str(DEFAULT_PATH), help="effects summary JSON（預設＝repo 的 ops/audits/effects_20261105_summary.json）")
    args = ap.parse_args(argv)
    path = Path(args.path)
    sha = "unreadable"
    size = 0
    try:
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        size = len(raw)
    except Exception:  # noqa: BLE001
        pass
    print(f"effects_summary_verify  path={path}")
    print(f"  size={size}  sha256={sha}")
    checks = verify(path)
    for name, ok, detail in checks:
        print(f"  {name:18s} {'OK' if ok else 'BROKEN'}  {detail}")
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            print("  重算表（逐格 → 相位 → 臂）：")
            _print_summary(d)
    except Exception:  # noqa: BLE001
        pass
    all_ok = all(ok for _, ok, _ in checks)
    print(f"VERDICT: {'EFFECTS_SUMMARY_OK' if all_ok else 'EFFECTS_SUMMARY_BROKEN'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
