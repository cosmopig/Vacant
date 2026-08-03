"""把實驗記錄掃成 agent 可直接載入的索引（不是給人翻的目錄）。

## 為什麼要有這支

實驗記錄目前是 3000+ 個 JSONL、超過 150 萬行，分散在多輪目錄裡。一個
agent 要回答「支持結論 X 的原始資料在哪、欄位是什麼意思、有沒有被動過」
時，若沒有索引就只能全盤掃描——那既慢又容易看漏。

所以這支產生**五份機器可讀的檔**，放在 `實驗記錄/_index/`：

  catalog.json    單一進入點。輪次 → 實驗 → 格 → 指標 → 原始檔的完整樹。
                  agent 讀完這一份就知道有什麼、在哪裡、代表什麼，不需要
                  再去掃檔案系統。
  files.jsonl     每個資料檔一行：路徑、位元組、sha256、行數、型別、歸屬。
                  串流讀取用；catalog 只放聚合資訊，避免單檔過大。
  schema.json     欄位字典。每種紀錄型別的每個欄位：型別、意思、單位。
                  沒有這份，agent 只能猜 `obs` 或 `bad` 是什麼意思。
  claims.json     結論 → 支撐它的檔案、欄位與數值。這一份是可究責性用在
                  檔案庫自己身上：任何一句結論都指得出它的原始依據。
  methods.json    每一種測試的實際步驟、什麼是真機制什麼是模擬的、控制了
                  什麼、沒控制什麼、以及已經踩過的量測陷阱。agent 光有資料
                  不夠，還要能判斷這份資料可不可信。

## 紀律

  - 只讀不寫（除了 _index/ 自己）。原始紀錄一個位元組都不動。
  - sha256 讓後續可以偵測「檔案被改過」——索引本身要能被驗。
  - 產生器進版控，索引可重跑；索引與資料不一致時以資料為準。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/專題/實驗記錄"
OUT = ROOT / "_index"

# ── 欄位字典 ────────────────────────────────────────────────────────
# 沒有這份，agent 只能從欄位名猜語意；猜錯就會做出錯誤的分析。
SCHEMA: dict[str, Any] = {
    "sim_round": {
        "描述": "機制模擬的逐輪紀錄（entrycost / pulse 兩輪共用）。一行＝一輪。",
        "產生者": "vacant/entrycost.py::simulate 的 log_path",
        "欄位": {
            "round": {"型別": "int", "意思": "輪次，從 0 開始"},
            "to": {"型別": "str", "意思": "這一輪被路由到誰（honest_N 或 attacker_gN）"},
            "attacker": {"型別": "bool", "意思": "被路由的是不是攻擊者。過濾攻擊者行為看這欄"},
            "bad": {"型別": "bool", "意思": "這一筆交付的是不是壞東西（攻擊者的決策結果）"},
            "audit_ran": {"型別": "bool", "意思": "稽核有沒有抽中這一筆（見習期會強制抽中）"},
            "caught": {"型別": "bool", "意思": "有沒有被抓到＝bad ∧ audit_ran ∧ 稽核看得見"},
            "score": {"型別": "float", "意思": "該身份當下的五維信譽分數（0–1）", "單位": "無"},
            "obs": {"型別": "float", "意思": "有效觀測數（衰減後）。路由門檻會看它"},
            "deliveries": {"型別": "int", "意思": "該身份累計交付數（見習期判定用）"},
            "accepted_bad": {"型別": "int", "意思": "到此輪為止，攻擊者累計得手數（累計值，非本輪）"},
            "clean_paid": {"型別": "int", "意思": "到此輪為止，攻擊者累計交出的乾淨交付數"},
            "identities": {"型別": "int", "意思": "到此輪為止，攻擊者用掉的身份數"},
        },
        "常用過濾": {
            "只看攻擊者": "attacker == true",
            "得手的那些輪": "bad == true and caught == false",
            "被抓的那些輪": "caught == true",
            "永久除名的證據": "取 attacker==true 的最後一個 round，與總輪數相比",
        },
    },
    "realmodel_row": {
        "描述": "真模型實驗（E10 信任開關 / E11 記憶三臂）的逐題紀錄。一行＝一題。",
        "產生者": "examples/realmodel_suite.py",
        "欄位": {
            "i": {"型別": "int", "意思": "題目索引，兩臂共用（跨臂配對的依據之一）"},
            "task_id": {"型別": "str", "意思": "sha256(prompt+tests)[:12]。同一題在兩臂必然相同，配對用這個"},
            "arm": {"型別": "str", "意思": "實驗臂：on / off（E10）或 M0 / M1 / M2（E11）"},
            "passed": {"型別": "bool", "意思": "品質判定。**由臂外的檢查獨立判定**，不是讀稽核欄"},
            "audit_performed": {"型別": "bool", "意思": "這一題有沒有跑稽核（off 臂依設計恆為 false）"},
            "deliverer": {"型別": "str", "意思": "交付者名稱"},
            "credit": {"型別": "float", "意思": "交付者當下的信譽分數"},
            "reviews": {"型別": "int", "意思": "這一題收到的評審數"},
        },
        "陷阱": "不要用 audit_performed 或稽核結果當品質判準——off 臂依設計不稽核，"
                "那樣會做出「off 臂全部失敗」的假結果。2026-07-26 真的發生過。",
    },
    "ledger_event": {
        "描述": "簽章 hash-chain 的事件流（真模型實驗的 root/ledger/events.jsonl）",
        "欄位": {"seq": {"型別": "int", "意思": "鏈上序號"},
                 "type": {"型別": "str", "意思": "事件類型：ROUTE / ATTEMPT / AUDIT / SLASH / …"},
                 "task_id": {"型別": "str", "意思": "對應的任務"}},
    },
    "model_io": {
        "描述": "每一次模型呼叫的輸入輸出（E11 的 model_io.jsonl）",
        "欄位": {},
        "註": "E10 走記帳閘道（port 8765），呼叫紀錄在閘道端不在這裡",
    },
}

# ── 測試方法 ────────────────────────────────────────────────────────
# agent 光有資料還不夠：它要能判斷這份資料**可不可信**、以及怎麼重跑。
# 所以把每一種測試的實際步驟、控制了什麼、沒控制什麼，都寫成機器可讀。
METHODS: dict[str, Any] = {
    "mechanism_sim": {
        "名稱": "機制模擬（E1–E9, E12–E24）",
        "回答什麼": "在這套規則下，某個攻擊策略或機制參數值多少",
        "步驟": [
            "1. 建 5 個誠實居民，每個都是真的 Identity（Ed25519）+ 真的 Logbook + 真的能力卡",
            "2. 暖身 8 輪：誠實居民互相給好評，讓生態有可背書的紀錄",
            "3. 依 EntryPolicy 生成攻擊者身份",
            "4. 每一輪：Registry.route 選人 → 該身份交付 → Auditor 抽樣稽核 →"
            "   三位同儕評審 → 抓到就 Reputation.slash → 落一行 JSONL",
            "5. 依策略決定是否丟棄身份重生（whitewash/sybil）",
            "6. 每格跑 N 個 seed，聚合成 mean/sd/min/max + shutout_rate",
        ],
        "什麼是真的": [
            "路由：真的 Registry.route（UCB + 見習期上限 0.55 + 每 10 輪見習配額）",
            "稽核：真的 Auditor（sha256(seed:task_id) 確定性抽樣）",
            "信譽：真的 Reputation（五維 Beta、乘法 slash、per-stream 半衰期 200 事件）",
            "簽章：真的 Ed25519 與 hash-chain",
        ],
        "什麼是模擬的": "只有「這一筆交付是好是壞」——那本來就是實驗處理，不是機制",
        "控制了什麼": [
            "全確定性：rng 種子 = f'{seed}:{config_digest}'，同參數必得同結果",
            "跨 seed 去相關：任務價值用 sha256(seed:hv:round)，不用輪次（曾因此做出假結果）",
            "config_digest 只涵蓋非預設欄位，新增選用參數不會擾動既有實驗的隨機序列",
        ],
        "沒控制什麼": [
            "攻擊者策略空間是寫死的三～四種；真實攻擊者可能更強",
            "單一攻擊者 + 5 誠實居民的固定生態規模",
            "blindspot 的真實值未知（沒有外生錨定）",
        ],
        "重跑": "python examples/pulse_suite.py --out <DIR>",
    },
    "real_model": {
        "名稱": "真模型實驗（E10 信任開關、E11 記憶三臂）",
        "回答什麼": "整條管線在真模型上跑得起來嗎；開關信任層有沒有可測差異",
        "步驟": [
            "1. 從 EvalPlus MBPP+ v0.2.0（378 題、sha256 釘死）取樣 N 題",
            "2. 每一臂各跑同一批題；三臂的 prompt 模板逐字相同（KS-1）",
            "3. 交付後用**臂外的** compile_check(t.check)(answer) 獨立判定品質",
            "4. 逐題落 rows.jsonl；模型呼叫走記帳閘道（port 8765）",
            "5. 以 task_id（sha256(prompt+tests)，跨臂穩定）配對，算 2×2 + McNemar 精確檢定"
            " + 固定種子 bootstrap 95% CI + 檢定力",
        ],
        "控制了什麼": [
            "配對設計：兩臂跑同一批題，消掉「這題本來就難」的共同因素",
            "品質判定與臂無關：不讀稽核欄（off 臂依設計不稽核）",
            "斷點續跑以 (arm, i) 為鍵，中斷不用從頭",
        ],
        "已知踩過的坑": "第一次量測讀了 audit.passed 當品質判準，而 off 臂依設計恆為 None，"
                        "做出 off 0/11 vs on 5/10 的假結果。修正後為 off 7/12 vs on 5/10（差異消失）。",
        "重跑": "python examples/realmodel_suite.py --out <DIR> --tasks 60",
    },
    "regression_tests": {
        "名稱": "迴歸判準（pytest）",
        "回答什麼": "機制本身有沒有退回去",
        "步驟": ["先寫會失敗的判準，再改機制（先紅後綠）",
                 "每支判準的說明記錄「當時的錯誤數字」，讓退化無法無聲發生"],
        "產物": "_index/testruns/pytest-*.xml（junit）與 pytest_summary.json",
        "重跑": ".venv/bin/python -m pytest tests/ -q",
    },
    "web_audit": {
        "名稱": "網站稽核（對比度／功能／響應式）",
        "回答什麼": "公開網站是否可讀、互動是否正確、有無水平溢出",
        "步驟": [
            "對比度：iframe 探針走訪每個可見元素，取 computed style，"
            "把半透明前景與有效背景合成後算 WCAG 比值（文字 4.5:1、大字與 UI 邊框 3:1）",
            "功能：以 JS 驅動點擊走完互動流程，比對 DOM 狀態與指紋是否真的重算",
            "響應式：iframe 固定寬度量 scrollWidth vs clientWidth",
        ],
        "量測陷阱（已踩過）": [
            "headless Chrome 視窗寬度有下限（約 500px）：量 375px 必須用 iframe 探針，"
            "直接 --window-size=375 會拍到夾寬後裁切的假象",
            "headless 虛擬時間不推進 CSS transition：有轉場的東西只能讀 computed style，"
            "看截圖會拍到中間狀態誤判成 bug",
        ],
    },
}

# ── 結論 → 證據 ─────────────────────────────────────────────────────
# 這一份是可究責性用在檔案庫自己身上：每一句對外說過的話，都指得出原始依據。
CLAIMS: list[dict[str, Any]] = [
    {
        "id": "pulse.definition",
        "輪次": "pulse-2026-08-03",
        "宣稱": "脈衝攻擊＝放電 B 筆連續作惡 → 蓄積 R 筆乾淨交付 → 重複；既有三種策略是其特例",
        "型別": "定義",
        "依據": {"程式": "vacant/entrycost.py::_should_defect 的 pulse 分支",
                 "判準": "tests/test_pulse.py::test_pulse_with_zero_recover_is_continuous"},
    },
    {
        "id": "pulse.timing_minor",
        "輪次": "pulse-2026-08-03",
        "宣稱": "攻擊的時間結構幾乎不影響總得手數：15 格 (burst,recover) 網格落在 2.83–5.13（1.81 倍）",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E24.json",
                 "欄位": "cells[].accepted_bad.mean",
                 "數值": {"最小": 2.8333, "最小格": "(1,20)", "最大": 5.1333, "最大格": "(8,20)"},
                 "原始紀錄": "脈衝攻擊_2026-08-03/E24/logs/*.jsonl"},
    },
    {
        "id": "pulse.blindspot_dominates",
        "輪次": "pulse-2026-08-03",
        "宣稱": "盲區的影響遠大於攻擊者的參數選擇：pulse 8.9 倍、patient 54 倍，對照參數網格的 1.81 倍",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E20.json",
                 "欄位": "cells[].accepted_bad.mean",
                 "數值": {"pulse blind=0": 2.3667, "pulse blind=1": 21.0,
                          "patient blind=0": 1.4667, "patient blind=1": 79.0}},
    },
    {
        "id": "pulse.crossover",
        "輪次": "pulse-2026-08-03",
        "宣稱": "盲區超過約 0.5–0.75 之後，脈衝反而不如單純的持續作惡（盲區拉滿時差 3.8 倍）",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E20.json",
                 "數值": {"blind=0.75": {"patient": 8.3333, "pulse": 7.7667},
                          "blind=1.0": {"patient": 79.0, "pulse": 21.0}},
                 "解釋": "脈衝是對被抓風險的避險；風險消失時自我節流（3/13≈23%）變成純損失，21/79≈0.27"},
    },
    {
        "id": "pulse.audit_cannot_close_blindspot",
        "輪次": "pulse-2026-08-03",
        "宣稱": "加大稽核率救得回零盲區（100% 稽核＝完全封鎖），救不回有盲區的情況（仍有 0.97 得手、僅 57% 全擋）",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E21.json",
                 "數值": {"blind=0 audit=1.0": {"accepted_bad": 0.0, "shutout": 1.0},
                          "blind=0.5 audit=1.0": {"accepted_bad": 0.9667, "shutout": 0.5667}}},
    },
    {
        "id": "pulse.starvation",
        "輪次": "pulse-2026-08-03",
        "宣稱": "一次被抓＝永久除名。被抓過的 16 個 seed 裡，16 個在那之後再也沒被路由過",
        "型別": "量測（來自逐輪紀錄，非聚合值）",
        "依據": {"原始紀錄": "脈衝攻擊_2026-08-03/E17/logs/burst3__p*.jsonl",
                 "重算方式": "取 attacker==true 的列；找第一個 caught==true 的 round；"
                             "數其後還有幾列 attacker==true",
                 "數值": {"被抓的 seed 數": 16, "其後再被路由的 seed 數": 0,
                          "最後被路由輪次中位數": 171, "總輪數": 600}},
    },
    {
        "id": "pulse.reaction_lag",
        "輪次": "pulse-2026-08-03",
        "宣稱": "即使零盲區，一波仍漏掉 2.53 筆、平均 28 輪才反應",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E22.json",
                 "欄位": "cells[label=blind=0.0].hits_per_burst.mean / react_lag_mean.mean",
                 "數值": {"hits_per_burst": 2.5333, "react_lag_rounds": 27.95}},
    },
    {
        "id": "pulse.crude_wins_under_blindspot",
        "輪次": "pulse-2026-08-03",
        "宣稱": "等預算（各 12 筆）＋盲區 0.5 之下，whitewash 8.17 反而勝過脈衝 4.23",
        "型別": "量測",
        "依據": {"檔案": "脈衝攻擊_2026-08-03/E19.json",
                 "數值": {"whitewash": 8.1667, "sybil": 6.1333,
                          "pulse(5,20)": 4.3, "pulse(3,10)": 4.2333, "patient": 3.7333}},
    },
    {
        "id": "entry.fee_backfires",
        "輪次": "entrycost-2026-07-26",
        "宣稱": "入場費設得太低反而幫攻擊者熬過見習期：stake=0 全擋，stake=2 得手 5.00、ROI 2.35",
        "型別": "量測",
        "依據": {"檔案": "入場成本_2026-07-26/E4.json", "欄位": "cells[].accepted_bad.mean / roi.mean"},
    },
    {
        "id": "entry.reviewer_accuracy_binds",
        "輪次": "entrycost-2026-07-26",
        "宣稱": "真正的約束是評審準確率：acc=0 時得手 16.65、ROI 1.04（作惡開始有利可圖）",
        "型別": "量測",
        "依據": {"檔案": "入場成本_2026-07-26/E12.json"},
    },
    {
        "id": "realmodel.e10_paired_null",
        "輪次": "realmodel-2026-07-26",
        "宣稱": "E10 信任開關 N=60 配對：on 36/60 vs off 31/60，差 +8.3%，95% CI [-5.0%, 21.7%] 跨 0、McNemar p=0.332，不顯著",
        "型別": "量測",
        "依據": {"原始紀錄": "真模型_2026-07-26/E10/{on,off}/rows.jsonl",
                 "重算方式": "以 task_id 配對（內容雜湊，跨臂穩定），算 2×2 與 McNemar 精確檢定",
                 "產生者": "examples/publish_experiments.py::_e10_from_rows",
                 "檢定力": {"power_observed": 0.163, "mde80_delta": 0.1983, "n_for_80": 337}},
    },
    {
        "id": "realmodel.measurement_error",
        "輪次": "realmodel-2026-07-26",
        "宣稱": "第一次量測是錯的：讀了 audit.passed 當品質判準，而 off 臂依設計不稽核，做出 0/11 vs 5/10 的假結果",
        "型別": "自我更正",
        "依據": {"程式": "examples/realmodel_suite.py 的註解（該處保留了錯誤的完整說明）",
                 "正確做法": "用臂外的 compile_check(t.check)(answer) 獨立判定"},
    },
]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows(p: Path) -> int:
    with p.open("rb") as f:
        return sum(1 for _ in f)


def _classify(p: Path) -> str:
    n = p.name
    if n == "rows.jsonl":
        return "realmodel_row"
    if n == "events.jsonl":
        return "ledger_event"
    if n == "model_io.jsonl":
        return "model_io"
    if n in ("records.jsonl", "ledger.jsonl"):
        return "realmodel_row" if n == "records.jsonl" else "ledger_event"
    if p.suffix == ".jsonl":
        return "sim_round"
    return "other"


ROUNDS = [
    {"id": "entrycost-2026-07-26", "dir": "入場成本_2026-07-26",
     "問題": ["身份入場成本該怎麼設計？", "什麼才是真正的約束？"],
     "報告": "報告_入場成本該怎麼設計.md",
     "實驗": ["E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9",
              "E12", "E13", "E14", "E15", "E16"]},
    {"id": "realmodel-2026-07-26", "dir": "真模型_2026-07-26",
     "問題": ["信任層開/關對交付品質有沒有可測的差異？", "被審過的記憶勝過原文記憶嗎？"],
     "報告": None, "實驗": ["E10", "E11"]},
    {"id": "pulse-2026-08-03", "dir": "脈衝攻擊_2026-08-03",
     "問題": ["脈衝攻擊是怎樣的攻擊？", "它的具體影響是什麼？", "稽核若也是模型會怎樣？"],
     "報告": "報告_脈衝攻擊與稽核盲區.md",
     "實驗": ["E17", "E18", "E19", "E20", "E21", "E22", "E23", "E24"]},
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files_out = (OUT / "files.jsonl").open("w", encoding="utf-8")
    n_files = 0
    total_rows = 0
    total_bytes = 0
    rounds_meta = []

    for rd in ROUNDS:
        base = ROOT / rd["dir"]
        if not base.exists():
            continue
        exps = []
        for eid in rd["實驗"]:
            ejson = base / f"{eid}.json"
            meta: dict[str, Any] = {"id": eid, "結果檔": f"{rd['dir']}/{eid}.json"}
            if ejson.exists():
                d = json.loads(ejson.read_text())
                meta["問題"] = d.get("question")
                meta["軸"] = d.get("axis")
                meta["註"] = d.get("note")
                meta["格"] = [{
                    "label": c.get("label"),
                    "config_digest": c.get("config_digest"),
                    "n_seeds": c.get("n_seeds"),
                    "得手_mean": (c.get("accepted_bad") or {}).get("mean"),
                    "高價值_mean": (c.get("high_value_hits") or {}).get("mean"),
                    "全擋率": c.get("shutout_rate"),
                } for c in d.get("cells", [])] if "cells" in d else None
            # 這一支實驗的原始紀錄
            logs = sorted((base / eid).rglob("*.jsonl")) if (base / eid).exists() else []
            meta["原始紀錄數"] = len(logs)
            meta["原始紀錄_glob"] = f"{rd['dir']}/{eid}/**/*.jsonl" if logs else None
            exps.append(meta)

        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.name.startswith("."):
                continue
            rel = p.relative_to(ROOT)
            rows = _rows(p) if p.suffix in (".jsonl",) else None
            rec = {
                "path": str(rel),
                "round": rd["id"],
                "type": _classify(p),
                "bytes": p.stat().st_size,
                "rows": rows,
                "sha256": _sha256(p),
            }
            files_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_files += 1
            total_bytes += rec["bytes"]
            total_rows += rows or 0

        rounds_meta.append({**{k: v for k, v in rd.items() if k != "實驗"},
                            "實驗": exps})

    files_out.close()

    catalog = {
        "catalog_version": 1,
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "root": "專題/實驗記錄",
        "讀者": "agent。人請直接讀各輪的 報告_*.md。",
        "怎麼用": {
            "1_先讀這份": "catalog.json 就是完整目錄樹：輪次 → 實驗 → 格 → 指標。"
                          "不需要再掃檔案系統。",
            "2_要欄位語意": "schema.json。不要從欄位名猜——例如 accepted_bad 是**累計值**不是本輪值。",
            "3_要找某句結論的依據": "claims.json。每條宣稱都指出檔案、欄位、數值與重算方式。",
            "3b_要知道資料怎麼被測出來": "methods.json。每種測試的步驟、控制了什麼、"
                                        "沒控制什麼、以及已經踩過的量測陷阱。",
            "4_要逐檔中繼資料": "files.jsonl 串流讀（每檔一行：路徑/型別/行數/sha256）。",
            "5_要驗檔案沒被動過": "比對 files.jsonl 的 sha256。",
        },
        "統計": {"檔案數": n_files, "總行數": total_rows, "總位元組": total_bytes},
        "輪次": rounds_meta,
        "重跑": {
            "索引": "python examples/build_archive_index.py",
            "脈衝輪": "python examples/pulse_suite.py --out <DIR>",
            "入場成本輪": "python examples/entrycost_suite.py --out <DIR> --seeds 20",
            "真模型輪": "python examples/realmodel_suite.py --out <DIR> --tasks 60",
        },
        "誠實邊界": [
            "機制模擬回答「在這套規則下策略值多少」，不回答「真實攻擊者會不會這樣做」。",
            "blindspot > 0 描述的是「若稽核也是模型」的設計變體；現行稽核是 sandbox 確定性重跑，對應 blindspot=0。",
            "攻擊者策略空間是寫死的，所以給的是攻擊成本上界的下界，證不了安全。",
        ],
    }
    (OUT / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "schema.json").write_text(
        json.dumps(SCHEMA, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "methods.json").write_text(
        json.dumps({"note": "每一種測試的實際步驟、控制了什麼、沒控制什麼、踩過的坑",
                    "methods": METHODS}, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "claims.json").write_text(
        json.dumps({"note": "每條對外宣稱 → 支撐它的檔案、欄位、數值、重算方式",
                    "claims": CLAIMS}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"catalog.json  輪次 {len(rounds_meta)}")
    print(f"files.jsonl   {n_files} 檔、{total_rows:,} 行、{total_bytes/1e6:.1f} MB")
    print(f"schema.json   {len(SCHEMA)} 種紀錄型別")
    print(f"claims.json   {len(CLAIMS)} 條宣稱")
    print(f"methods.json  {len(METHODS)} 種測試方法")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
