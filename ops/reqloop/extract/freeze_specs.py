#!/usr/bin/env python3
"""G4-SPEC（P20261113_0708-1）：dab_725/587/657/517 四題可檢查需求規格凍結落盤（0 model calls）。

資料來源（皆為既有產物之重編譯，不重新擷取）：
- ops/audits/g26_claim_replay.json（D1 重播）：選 replay_status=="deterministic" 且
  saved_verifier 非空者（驗證原語僅 g3_2_fire 批存了 26/26；其餘來源 verifier 0/50 未存）。
- ops/reqloop/g3_2/tasks/<tid>/workspace/{goal.md,contract.md}：hash 落盤進規格（goal_sha256／
  contract_sha256），使 D4 重用時可先核 workspace 未被改。

quote 口徑：來源報告未存逐條 quote（g26 raw_fields_saved.quote=0/76）→ 每條以 goal.md 全文
（使用者原文、已以 goal_sha256 凍結）為 quote，不偽造需求句。

防篡改：spec_sha256＝整份規格（除本欄位）canonical JSON 的 sha256 → 改任何一個字（含
goal_sha256 本身）都使 validate_spec 失敗。

P20261113_1100-1（G4-SPEC params 補齊）：原 25 條 params 全為 {}，checks.
run_requirement_checks 對錯誤交付物判 0 FAIL / 0 PASS / 25 UNKNOWN，G4 full_rloop
修補機制無從觸發。現依各題 workspace goal.md／contract.md 之答案格式、資料檔與
重算規則（皆可見材料）補 params，並修正兩處對 KV 格式答案檔「不可成立」的驗證原語
（見 _ITEM_FIXES 註）；落盤時同步更新 g4/manifest.json 的 spec_sha256，--check 連同複核。

跑法：python3 ops/reqloop/extract/freeze_specs.py          # 落盤 4 份＋同步 manifest
      python3 ops/reqloop/extract/freeze_specs.py --check   # 機械複核（含 manifest 同步）
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from vacant_network.reqloop.requirements import RequirementSet  # noqa: E402

TASKS = ("dab_725", "dab_587", "dab_657", "dab_517")
G26 = REPO / "ops/audits/g26_claim_replay.json"
TASKS_DIR = REPO / "ops/reqloop/g3_2/tasks"
SPEC_DIR = REPO / "ops/reqloop/g4/specs"
MANIFEST = REPO / "ops/reqloop/g4/manifest.json"
TICKET = "P20261113_0708-1-freeze-g4-specs"
TICKET_PARAMS = "P20261113_1100-1-g4-freeze-specs-params-checkability"

# P20261113_1100-1（G4-SPEC）：逐條 params 表（item id → (verifier, params)）。
# 依據：各題 workspace goal.md／contract.md 的答案格式（@name[value] KV、小數位數）、
# 資料檔與重算規則——全部可見材料，不引用 hidden/scorer。
# - answer_kv → keys: [{key, type:"number"}]（本批答案值皆為數字）。
# - tag_format → {tag, value_type:"float"}。
# - 值正確性條目改 kv_recomputed {key, data_file, recompute{type, col|col_a|col_b, round:2}}：
#   * dab_657 原 plain_recomputed 把整檔當單一數字解析，KV 格式答案（多條 @name[value]）
#     連正確答案也必然 FAIL（不可滿足規格）→ 改 kv_recomputed 按 key 取值後重算；
#   * dab_517 原 answer_kv 只查格式，錯值也 PASS（假交付）→ 2 條值條目改 kv_recomputed
#     （checks.py D3b 註即為 dab_517 這 2 條加 pearson 重算規則）；req_answer_file
#     是檔案／格式條目，保留 answer_kv。
#   * 欄名須為 CSV 原始表頭大小寫（kv_recomputed 走 csv.DictReader、不小寫化）。
#   * round:2 出自 goal.md／contract.md 答案格式（四捨五入到小數點後 2 位）。
# 無 params 的條目（dab_725 R2/R3、dab_517 req_exclude_nulls）維持 UNKNOWN（不自評）。

_K725 = ("mean1", "median1", "mean2", "median2", "mean3", "median3")
_BTC = "data/YAHOO-BTC_USD_D.csv"
_TIT = "data/titanic.csv"


def _num_keys(*names: str) -> dict:
    return {"keys": [{"key": n, "type": "number"} for n in names]}


def _kv_params(name: str, data_file: str, rtype: str, **cols: str) -> dict:
    return {"key": name, "data_file": data_file,
            "recompute": {"type": rtype, **cols, "round": 2}}


_ITEM_FIXES: dict[str, dict[str, tuple[str, dict]]] = {
    "dab_725": {
        "R1": ("answer_kv", _num_keys(*_K725)),
        "R4": ("tag_format", {"tag": "mean1", "value_type": "float"}),
        "R5": ("answer_kv", _num_keys(*_K725)),
        "R6": ("answer_kv", _num_keys(*_K725)),
    },
    "dab_587": {
        f"R{i}": ("tag_format", {"tag": "correlation_coefficient", "value_type": "float"})
        for i in range(1, 6)
    },
    "dab_657": {
        "req-1": ("kv_recomputed", _kv_params("mean_close", _BTC, "mean_col", col="Close")),
        "req-2": ("kv_recomputed", _kv_params("median_close", _BTC, "median_col", col="Close")),
        "req-3": ("kv_recomputed", _kv_params("std_close", _BTC, "std_col", col="Close")),
        "req-4": ("tag_format", {"tag": "mean_close", "value_type": "float"}),
        "req-5": ("tag_format", {"tag": "median_close", "value_type": "float"}),
        "req-6": ("tag_format", {"tag": "std_close", "value_type": "float"}),
        "req-7": ("kv_recomputed", _kv_params("mean_close", _BTC, "mean_col", col="Close")),
        "req-8": ("kv_recomputed", _kv_params("mean_close", _BTC, "mean_col", col="Close")),
    },
    "dab_517": {
        "req_correlation_value": ("kv_recomputed",
                                 _kv_params("correlation_pclass_fare", _TIT, "pearson",
                                            col_a="Pclass", col_b="Fare")),
        "req_pearson_method": ("kv_recomputed",
                               _kv_params("correlation_pclass_fare", _TIT, "pearson",
                                          col_a="Pclass", col_b="Fare")),
        "req_round_2dp": ("tag_format", {"tag": "correlation_pclass_fare", "value_type": "float"}),
        "req_answer_format": ("tag_format", {"tag": "correlation_pclass_fare", "value_type": "float"}),
        "req_answer_file": ("answer_kv", _num_keys("correlation_pclass_fare")),
    },
}


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _canon(d: dict) -> str:
    return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _claims_of(tid: str) -> list[dict]:
    return [c for c in json.loads(G26.read_text(encoding="utf-8"))["claims"] if c["task_id"] == tid]


def input_files(tid: str) -> list[str]:
    for c in _claims_of(tid):
        if c.get("input_files"):
            return list(c["input_files"])
    return []


def trusted_deliverable(tid: str) -> str:
    for c in _claims_of(tid):
        if c.get("trusted_deliverable"):
            return str(c["trusted_deliverable"])
    raise ValueError(f"{tid}: g26 replay 無 trusted_deliverable")


def build_spec(tid: str) -> dict:
    ws = TASKS_DIR / tid / "workspace"
    goal = (ws / "goal.md").read_text(encoding="utf-8")
    seen: set[str] = set()
    items = []
    for c in _claims_of(tid):
        vd, dlv = c.get("saved_verifier"), c.get("trusted_deliverable") or ""
        if c.get("replay_status") != "deterministic" or not vd or c["claim_id"] in seen:
            continue  # 無驗證原語＝無可確定性檢查條件，不凍結
        if not dlv or dlv in c.get("input_files", []):
            raise ValueError(f"{tid}/{c['claim_id']}: 交付物非「非輸入檔之可信交付物」: {dlv!r}")
        seen.add(c["claim_id"])
        items.append({"id": c["claim_id"], "quote": goal, "deliverable": dlv, "verifier": vd,
                      "kind": "explicit", "params": {},
                      "description": f"G4 frozen spec: g26 replay {c['source']}/{c['claim_id']} deterministic"})
    if not items:
        raise ValueError(f"{tid}: 無任何帶驗證原語的 deterministic 條件")
    fixes = _ITEM_FIXES.get(tid, {})
    bad = sorted(set(fixes) - {it["id"] for it in items})
    if bad:
        raise ValueError(f"{tid}: _ITEM_FIXES 引用不存在的條目: {bad}")
    for it in items:
        if it["id"] in fixes:
            verifier, params = fixes[it["id"]]
            it["verifier"] = verifier
            it["params"] = {**it["params"], **params}
    spec = {"task_id": tid, "spec_version": 1, "ticket": TICKET,
            "params_fix_ticket": TICKET_PARAMS,
            "frozen_from": "ops/audits/g26_claim_replay.json",
            "goal_sha256": _sha(ws / "goal.md"), "contract_sha256": _sha(ws / "contract.md"),
            "items": items}
    spec["spec_sha256"] = hashlib.sha256(_canon(spec).encode("utf-8")).hexdigest()
    return spec


def validate_spec(path: str | pathlib.Path) -> tuple[bool, str]:
    """機械複核：可載入＋自 hash＋workspace hash＋交付物全為非輸入檔可信交付物。回 (ok, reason)。"""
    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        rs = RequirementSet.from_dict(raw)
        tid = raw["task_id"]
    except Exception as e:
        return False, f"load_failed:{type(e).__name__}:{e}"
    if tid not in TASKS:
        return False, "task_id"
    body = {k: v for k, v in raw.items() if k != "spec_sha256"}
    if raw.get("spec_sha256") != hashlib.sha256(_canon(body).encode("utf-8")).hexdigest():
        return False, "spec_sha256"
    ws = TASKS_DIR / tid / "workspace"
    if raw.get("goal_sha256") != _sha(ws / "goal.md") or raw.get("contract_sha256") != _sha(ws / "contract.md"):
        return False, "workspace_sha256"
    tr, ins = trusted_deliverable(tid), input_files(tid)
    if not rs.items or any(it.deliverable != tr or it.deliverable in ins for it in rs.items):
        return False, "deliverable"
    return True, "ok"


def _sync_manifest() -> bool:
    """把 4 題最新 spec_sha256 寫回 g4/manifest.json（只改 hash 值，其餘字元原樣保留）。

    manifest 是預註冊文件：只改 specs.<tid>.spec_sha256 的 64 位 hex 值，不做整檔
    重新序列化（避免格式化 diff 污染預註冊記錄）。n_items 在本票不變（6/5/8/6）。
    manifest 不存在、或找不到某題的 spec_sha256 欄時不猜、不改動（fail-closed）。
    回傳是否改動。
    """
    if not MANIFEST.is_file():
        return False
    text = MANIFEST.read_text(encoding="utf-8")
    changed = False
    for tid in TASKS:
        spec = json.loads((SPEC_DIR / f"{tid}.json").read_text(encoding="utf-8"))
        pat = re.compile(
            r'("' + re.escape(tid) + r'"\s*:\s*\{[^{}]*"spec_sha256"\s*:\s*)"[0-9a-f]{64}"',
            re.DOTALL)
        m = pat.search(text)
        if m is None:
            raise ValueError(f"manifest 找不到 {tid} 的 spec_sha256 欄（不猜，不改動）")
        cur_sha = m.group(0)[len(m.group(1)) + 1:-1]  # 去掉前綴與前後引號
        if cur_sha != spec["spec_sha256"]:
            text = text[:m.start()] + m.group(1) + '"' + spec["spec_sha256"] + '"' + text[m.end():]
            changed = True
    if changed:
        MANIFEST.write_text(text, encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--check" in argv:
        # P20261113_1100-1：manifest 的 spec_sha256 須與規格同步；manifest 不可讀時
        # fail-closed（全紅），不跳過。
        man_bad: str | None = None
        man: dict = {}
        if MANIFEST.is_file():
            try:
                man = json.loads(MANIFEST.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                man_bad = f"manifest_unreadable:{type(e).__name__}"
        ok = True
        for tid in TASKS:
            if man_bad is not None:
                print(tid, "FAIL", man_bad)
                ok = False
                continue
            good, why = validate_spec(SPEC_DIR / f"{tid}.json")
            if good:
                entry = man.get("specs", {}).get(tid)
                sp = json.loads((SPEC_DIR / f"{tid}.json").read_text(encoding="utf-8"))
                if not isinstance(entry, dict) or entry.get("spec_sha256") != sp.get("spec_sha256"):
                    good, why = False, "manifest_spec_sha256"
            print(tid, "OK" if good else "FAIL", why)
            ok = ok and good
        return 0 if ok else 1
    SPEC_DIR.mkdir(parents=True, exist_ok=True)
    for tid in TASKS:
        sp = SPEC_DIR / f"{tid}.json"
        sp.write_text(json.dumps(build_spec(tid), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", sp.relative_to(REPO))
    print("manifest", "updated" if _sync_manifest() else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
