#!/usr/bin/env python3
"""R20261105_0346-2：effects_20261105 50 格誠實審計摘要的產生器（可重跑）。

讀（只讀）~/dev/ops/effects_20261105/ 的 manifest、g2_result.json、independent.json、
agent_round_N/agent_stdout.log，寫 ops/audits/effects_20261105_summary.json。

口徑（嚴格區分，混用即錯）：
- before_pass   ：實驗前**獨立**評分（manifest 生成時已記錄；來源＝原草稿）。
- after_indep   ：實驗後**獨立**評分（independent.json；來源＝該格最終候選）。
- local_*       ：g2_result.json 當時（d38d2eb2）以舊 checker／舊 usage parser 記錄的值。
- api_model_calls_true / tokens_true：用**當前**（已併 auto/argon）parse_usage_from_log
  從每輪 agent_stdout.log 的 message_end usage 重新數出（1 個 message_end＝1 次真實
  API 呼叫）；任一回傳 None ⇒ 該格總和 None（缺值不填 0）。
- repair_sessions＝agent 啟動（session）數；與 API 請求數不同（一次啟動可含多次請求）。
- local 重驗（current_code_all_pass）：以當前 checks 碼對快照 task 重跑 run_requirement_checks，
  與 after_indep 對照（r1029 驗收：50/50）。

任何欄位缺值一律 None（UNKNOWN），不填 0、不留佔位。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
EFFECTS = pathlib.Path("/home/user1/dev/ops/effects_20261105")
SNAP = EFFECTS / "snapshot/ops/reqloop/g2"

sys.path.insert(0, str(REPO))
from vacant_network.reqloop.checks import RequirementSet, run_requirement_checks  # noqa: E402
from vacant_network.reqloop.repair import _required_all_pass, parse_usage_from_log  # noqa: E402


def _old_parser() -> "callable":
    """從效果快照（d38d2eb2）抽出舊 parse_usage_from_log，算「記錄當時」的膨脹值。"""
    src = (EFFECTS / "snapshot/vacant_network/reqloop/repair.py").read_text(encoding="utf-8")
    frag = src[src.index("_USAGE_INPUT_KEYS"):src.index("def repair_slice")]
    ns: dict = {"pathlib": pathlib, "json": json, "dataclasses": dataclasses,
                "hashlib": hashlib}
    exec(compile(frag, "snapshot_repair_frag", "exec"), ns)
    return ns["parse_usage_from_log"]


OLD_PARSE = _old_parser()


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def cell_record(phase: str, draft: str, arm: str, man_draft: dict, g2_cell: dict,
                indep: bool, ws_path: pathlib.Path) -> dict:
    role = man_draft["role"]
    before = man_draft["source"]["score"].get("pass")
    cost = g2_cell["cost"]
    sessions = int(cost.get("calls") or 0)

    true_calls = true_tok = rec_calls = rec_tok = 0
    true_ok = rec_ok = True
    rounds = []
    for n in range(1, sessions + 1):
        log = EFFECTS / phase / draft / arm / f"agent_round_{n}" / "agent_stdout.log"
        if not log.exists():
            true_ok = rec_ok = False
            rounds.append({"round": n, "log_missing": True})
            continue
        t = parse_usage_from_log(log)
        r = OLD_PARSE(log)
        if t is None:
            true_ok = False
        else:
            true_calls += t["calls"]
            true_tok += t["total"]
        if r is None:
            rec_ok = False
        else:
            # 舊 parser 沒有 calls 欄位；記錄當時 cost.model_calls 的推算＝「帶 usage 的事件數」
            rec_events = r.get("_events", None)
            rec_calls += r["calls"] if "calls" in r else r.get("_events", 0)
            rec_tok += r["total"]
        rounds.append({
            "round": n,
            "true_usage": t,
            "recorded_usage_d38d2eb2": {k: v for k, v in r.items()} if r is not None else None,
        })

    # 當前 checker 對快照 task 的重驗（與 r1029 驗收同一條路徑）
    # manifest 的 task.dir 即相對 snapshot 的 task 目錄（如 smoke/dab_507/task）
    task_dir = SNAP / man_draft["task"]["dir"]
    req_set = RequirementSet.load(task_dir / "requirements.json")
    # d38d2eb2 記錄當時的本地門：從 final_readable_status 按「必需條目全 PASS」重算
    # （g2_result.json 只存逐條狀態、沒存 gate 欄位）
    required = [i.id for i in req_set.items if i.required]
    local_gate_d38d2eb2 = bool(required) and all(
        g2_cell["final_readable_status"].get(cid) == "PASS" for cid in required)
    # 最終候選工作區以 independent.json 記錄的 workspace 為準（round_1／round_2／no_gap 為原草稿）
    cur_results = run_requirement_checks(task_dir, req_set, ws_path)
    cur_gate = _required_all_pass(req_set, cur_results)

    return {
        "draft": draft,
        "arm": arm,
        "role": role,
        "before_pass_independent": before,
        "after_independent": indep,
        "local_stopped_d38d2eb2": g2_cell["stopped"],
        "local_all_pass_d38d2eb2": local_gate_d38d2eb2,
        "current_code_all_pass": cur_gate,
        "local_matches_independent": bool(local_gate_d38d2eb2 == indep),
        "current_code_matches_independent": bool(cur_gate == indep),
        "repair_sessions": sessions,
        "api_model_calls_true": true_calls if true_ok and (sessions > 0 or true_calls > 0) else (true_calls if true_ok else None),
        "api_model_calls_recorded_d38d2eb2": _num(cost.get("model_calls")),
        "tokens_true": true_tok if true_ok else None,
        "tokens_recorded_d38d2eb2": _num(cost.get("tokens")),
        "wall_ms_total": _num(cost.get("wall_ms_total")),
        "rounds": rounds,
    }


def main() -> int:
    out = {
        "schema": "vacant.audit/effects_20261105_summary/1",
        "snapshot_sha": "d38d2eb21d7ffbb927eb263e657d907dc112bc7d",
        "scope_note": (
            "本實驗為開發選樣（e008/e013/e014 已見題），不是未見任務效力證明；"
            "無硬 token 上限，不得宣稱等 token；小樣本（單 rep）不宣稱 localized 優於 generic。"
            "口徑：before_pass_independent＝實驗前獨立評分（manifest 生成時記錄，來源＝原草稿）；"
            "after_independent＝實驗後獨立評分（independent.json，來源＝該格最終候選）。"
            "local_*＝g2_result.json 於 d38d2eb2 以舊 checker／舊 usage parser 記錄的值；"
            "api_model_calls_true／tokens_true＝以當前（已併 auto/argon）parser 從每輪 "
            "agent_stdout.log 的 message_end usage 重數（1 message_end＝1 真實 API 呼叫）。"
            "local 與 after_independent 的 5 格分歧全部出於 d38d2eb2 舊 checker；"
            "以當前 checks 碼重驗（current_code_all_pass）與獨立評分 50/50 一致。"
            "repair_sessions（agent 啟動數）與 API 請求數是兩個量，本檔嚴格分開。"
            "hidden_after（本地重跑 hidden scorer）全格＝UNKNOWN（本地無權重跑），不填 0。"
            "所有缺值＝None（UNKNOWN），不填 0。"
        ),
        "source_root": str(EFFECTS),
        "code_under_audit": "d38d2eb2 (snapshot) vs current auto/qwen27b (post auto/argon merge)",
        "phases": {},
    }

    total = 0
    for phase, man_path in (
        ("policy30", EFFECTS / "snapshot/ops/reqloop/g2/effect_manifest.json"),
        ("feedback_once20", EFFECTS / "snapshot/ops/reqloop/g2/feedback_once_manifest.json"),
    ):
        man = json.loads(man_path.read_text(encoding="utf-8"))
        g2 = json.loads((EFFECTS / phase / "g2_result.json").read_text(encoding="utf-8"))
        raw_ind = json.loads((EFFECTS / phase / "independent.json").read_text(encoding="utf-8"))
        # independent.json 的結構＝{"complete", "source_result", "cells": [{draft, arm, independent_after:{pass,...}}]}
        indep = {f"{c['draft']}-{c['arm']}": c["independent_after"]["pass"] for c in raw_ind["cells"]}
        ws_of = {f"{c['draft']}-{c['arm']}": pathlib.Path(c["workspace"]) for c in raw_ind["cells"]}
        by_draft = {d["name"]: d for d in man["drafts"]}
        g2_cells = {(c["draft"], c["arm"]): c for c in g2["cells"]}

        cells = []
        for draft, arm in sorted(g2_cells):
            key = f"{draft}-{arm}"
            if key not in indep:
                raise SystemExit(f"missing independent cell: {phase}/{key}")
            cells.append(cell_record(phase, draft, arm, by_draft[draft],
                                     g2_cells[(draft, arm)], bool(indep[key]), ws_of[key]))
            total += 1

        def move(b, a):
            return (b is False and a is True) or (b is True and a is False)

        wr = sum(1 for c in cells if c["before_pass_independent"] is False
                 and c["after_independent"] is True)
        rw = sum(1 for c in cells if c["before_pass_independent"] is True
                 and c["after_independent"] is False)
        preserved = sum(1 for c in cells if c["before_pass_independent"] is True
                        and c["after_independent"] is True)
        still_wrong = sum(1 for c in cells if c["before_pass_independent"] is False
                          and c["after_independent"] is False)
        mism = [c for c in cells if not c["local_matches_independent"]]
        cur_mism = [c for c in cells if not c["current_code_matches_independent"]]

        active_cells = [c for c in cells if c["repair_sessions"] > 0]
        per_arm = {}
        for arm in ("generic", "localized"):
            ac = [c for c in cells if c["arm"] == arm]
            ac_active = [c for c in ac if c["repair_sessions"] > 0]
            per_arm[arm] = {
                "cells": len(ac),
                "wrong_to_right": sum(1 for c in ac if c["before_pass_independent"] is False
                                      and c["after_independent"] is True),
                "right_to_wrong": sum(1 for c in ac if c["before_pass_independent"] is True
                                      and c["after_independent"] is False),
                "preserved_good": sum(1 for c in ac if c["before_pass_independent"] is True
                                      and c["after_independent"] is True),
                "still_wrong": sum(1 for c in ac if c["before_pass_independent"] is False
                                   and c["after_independent"] is False),
                "repair_sessions": sum(c["repair_sessions"] for c in ac),
                "api_model_calls_true": (sum(c["api_model_calls_true"] for c in ac_active)
                                         if ac_active and all(c["api_model_calls_true"] is not None
                                                              for c in ac_active) else None),
                "tokens_true": (sum(c["tokens_true"] for c in ac_active)
                                if ac_active and all(c["tokens_true"] is not None
                                                     for c in ac_active) else None),
                "wall_ms_total": (sum(c["wall_ms_total"] for c in ac_active)
                                  if ac_active and all(c["wall_ms_total"] is not None
                                                       for c in ac_active) else None),
            }

        out["phases"][phase] = {
            "cells": len(cells),
            "wrong_to_right": wr,
            "right_to_wrong": rw,
            "preserved_good": preserved,
            "still_wrong": still_wrong,
            "movement_total": wr + rw,
            "per_arm": per_arm,
            "local_vs_independent_mismatches": [
                {"cell": f"{c['draft']}-{c['arm']}",
                 "local_all_pass_d38d2eb2": c["local_all_pass_d38d2eb2"],
                 "after_independent": c["after_independent"]}
                for c in mism
            ],
            "current_code_vs_independent_mismatches": [
                f"{c['draft']}-{c['arm']}" for c in cur_mism
            ],
            "local_matches": sum(1 for c in cells if c["local_matches_independent"]),
            "current_code_matches": sum(1 for c in cells if c["current_code_matches_independent"]),
            "repair_sessions_total": sum(c["repair_sessions"] for c in cells),
            "api_model_calls_true_total": (sum(c["api_model_calls_true"] for c in active_cells)
                                           if active_cells and all(c["api_model_calls_true"] is not None
                                                                   for c in active_cells) else None),
            "tokens_true_total": (sum(c["tokens_true"] for c in active_cells)
                                  if active_cells and all(c["tokens_true"] is not None
                                                          for c in active_cells) else None),
            "wall_ms_total": (sum(c["wall_ms_total"] for c in active_cells)
                              if active_cells and all(c["wall_ms_total"] is not None
                                                      for c in active_cells) else None),
            "cells_detail": cells,
        }

    out["total_cells"] = total
    out["local_matches_total"] = sum(v["local_matches"] for v in out["phases"].values())
    out["current_code_matches_total"] = sum(v["current_code_matches"] for v in out["phases"].values())

    dest = HERE / "effects_20261105_summary.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest}")
    for ph, v in out["phases"].items():
        print(f"{ph}: {v['cells']} cells, W→R={v['wrong_to_right']}, R→W={v['right_to_wrong']}, "
              f"preserved={v['preserved_good']}, still_wrong={v['still_wrong']}, "
              f"local_match={v['local_matches']}, cur_match={v['current_code_matches']}, "
              f"sessions={v['repair_sessions_total']}, api_calls_true={v['api_model_calls_true_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
