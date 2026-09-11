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

# 裁決的單一真相來源——網頁與這份索引共用同一份，否則兩邊會漂開。
from verdicts import verdict_for

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
        # 2026-08-06：對抗式複驗推翻了四條結論，而它們的錯法是同一個。
        # 把教訓寫成紀律放進索引，否則下一輪會用同樣的方式再錯一次。
        "分析紀律（複驗後補上）": [
            "對聚合量下「維度 X 不重要」的結論之前，先把它分解。E24 的『時間結構只差"
            " 1.81 倍』就是這樣錯的：得手 = 曝光 × 效率，兩者反向抵消（6.06 倍對 8.45 倍），"
            "總數看起來平。分解不出來時只能寫『在這個操作點上量不到』，不能寫『不重要』。",
            "不要在退化端點上量效應量。blindspot=1.0 時 30 個 seed 塌成同一條軌跡"
            "（sd=0、有效 n=1）；audit_rate=1 且 audit_accuracy=1 時 caught==bad 是程式"
            "寫死的恆等式。端點的數字最漂亮，通常也最沒有資訊。",
            "偵測機率是單一乘積 (1−盲區)×抽樣率×準確率。不要把同一個乘積裡的因子當成"
            "正交維度——『加大稽核救不回盲區』就是這樣錯的。",
            "等預算比較要驗 defected == BUDGET，不是 defected <= BUDGET。上界恆成立，"
            "永遠抓不到『這一臂根本沒被綁住』。E19 因此把『多作惡 2.5 倍』誤讀成『時機較優』。",
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
        # 2026-08-06 文獻調研：這個攻擊不是本專題提出的，2005 年就有名字。
        # 定義本身站得住，站不住的是隱含的新穎性——索引必須把這件事講出來，
        # 否則讀它的 agent 會以為這是我們的貢獻。
        "先行研究": {
            "結論": "不是新的。2005 年即為 strategic oscillation，2009 年進 ACM Computing "
                    "Surveys 的攻擊分類表，命名為 oscillation attack。",
            "出處": ["Srivatsa et al. 2005 (TrustGuard) §2：『Or it could oscillate between "
                     "building and milking reputation.』其 model I（固定週期方波）即本專題的 "
                     "(B,R) 參數化；model II–IV（指數間隔／隨機好度／正弦漸變）本專題未掃",
                     "Hoffman et al. 2009, ACM Computing Surveys §5.4：列為命名類別，"
                     "歸功 Srivatsa 2005；其版本含多身分輪班，比本專題的單一攻擊者更強"],
            "連我們的頭條也被搶先": "Srivatsa 量過四種震盪模型的攻擊者成本比 1 : 2.28 : 2.08 : "
                                    "1.36，並證明知道記憶窗 maxH 者的最佳策略是以週期＝maxH 震盪。"
                                    "本專題的『1.81 倍』既較舊也較弱，且已自判為雜訊"
                                    "（permutation p=0.115、檢定力 25%）。",
            "可能仍是新的（保守）": ["四道防禦同時在跑的組態下量它",
                                      "把盲區當第二軸並量它與時間結構的交互作用（η²=0.264）"
                                      "——盲區文獻不路由不扣分，信譽攻防文獻無盲區參數",
                                      "slash 的 β += (α+β) 關閉自己赦免通道的病理"],
            "檔案": "參考文獻/2026-08-06_agent信任/PRIOR_ART.md 第一節",
        },
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
    {
        "id": "gain.signal_exists",
        "輪次": "gain-2026-08-30",
        "宣稱": "量具有訊號：無信任層（OFF）時失敗率 26.44%，落在事前訂的 20–60% 窗內",
        "型別": "量測（事前判準 1）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260901_R437_DECISIVE_RUN_COMPLETE_FINAL.md",
                 "數值": {"OFF processed": 179, "OFF infra_void": 5, "measured": 174,
                          "失敗率": 0.2644, "Wilson CI95": [0.204, 0.334]}},
    },
    {
        "id": "gain.arms_differ",
        "輪次": "gain-2026-08-30",
        "宣稱": "三臂（OFF／ON／OFF5）的交付品質有可分辨的差異",
        "型別": "量測（事前判準 2，配對 McNemar）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260901_R437_DECISIVE_RUN_COMPLETE_FINAL.md",
                 "數值": {"raw ON vs OFF5": {"n": 101, "ON": 0.7525, "OFF5": 0.7723, "b": 6, "c": 8, "p": 0.7905},
                          "typing 修正版": {"n": 101, "ON": 0.8416, "OFF5": 0.8119, "b": 5, "c": 2, "p": 0.4531}},
                 "解釋": "兩種口徑都不顯著，且點估計方向會因為修一個無關的 typing 白名單 bug 而翻轉"},
    },
    {
        "id": "gain.equal_budget_on_beats_off5",
        "輪次": "gain-2026-08-30",
        "宣稱": "等預算下，Vacant（ON）打得贏同題跑五次取多數決（OFF5）",
        "型別": "量測（事前判準 3）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260901_R438_HARD_SUBSET_AND_REVISE_MECHANISM.md",
                 "數值": {"完整配對": {"n": 101, "p": 0.4531},
                          "難題子集（OFF 失敗集合）": {"n": 21, "ON": 0.2857, "OFF5": 0.2857, "b": 1, "c": 1, "p": 1.0}}},
    },
    {
        "id": "gain.mechanism",
        "輪次": "gain-2026-08-30",
        "宣稱": "打不贏的機制：評審票幾乎是常數函數，修訂幾乎不產生淨修正",
        "型別": "機制分析（在完整 179 題資料上重算）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260901_R438_HARD_SUBSET_AND_REVISE_MECHANISM.md",
                 "數值": {"生效評審票準確率": 0.7552, "almost-PASS 基線": 0.7522, "差": 0.0029,
                          "revise 反事實 no_opportunity": "93/113", "盲目採用 revised 的 hidden 通過率": "82.3%→78.8%",
                          "discarded_win": "0/113", "revision_transition=improved": "1/113"}},
    },
    {
        "id": "gain.ceiling_hypothesis",
        "輪次": "gain-2026-08-30",
        "宣稱": "35b worker 太強造成天花板效應，換成 12b 單模型後 Vacant 就會顯出增益",
        "型別": "量測（人類 2026-09-01 提出的假說 H-A；E1 gemma-4-12b 單模型池 179 題）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260903_R440N_E1_INDEPENDENT_AUDIT_CONCUR.md",
                 "數值": {"OFF 失敗率": 0.318, "ON vs OFF5": {"n": 167, "b": 11, "c": 12, "p": 1.0},
                          "評審 grounded −基線": "+4.19pp（95% [0, 8.58]）", "ON void": "12/179"}},
    },
    {
        "id": "gain.hard_bench_hypothesis",
        "輪次": "gain-2026-08-30",
        "宣稱": "MBPP+ 對現代模型太簡單，換成有日期戳的比賽難題（LiveCodeBench）就會顯出增益",
        "型別": "量測（人類 2026-09-01 提出的假說 H-B；E3 LCB 91 題 medium+hard × gemma-only）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260904_R440T_E3_WRAPUP.md",
                 "數值": {"OFF 失敗率": 0.484, "Wilson CI95": [0.384, 0.585],
                          "ON vs OFF5": {"n": 87, "b": 15, "c": 10, "p": 0.4244},
                          "題庫確實更難": "比 MBPP+ 的 31.8% 高 16.6pp"}},
    },
    {
        "id": "gain.reviewer_tracks_difficulty",
        "輪次": "gain-2026-08-30",
        "宣稱": "評審追蹤的是題目難度這個全域性質，不是個別答案的對錯",
        "型別": "機制分析（跨兩題庫對照）",
        "依據": {"檔案": "增益實驗_2026-08-30/DECISION_20260904_R440T_E3_WRAPUP.md",
                 "數值": {"MBPP+": {"原始 FAIL 主張": "少數（近乎一律 PASS）", "初稿錯誤率": 0.305,
                                    "原始層−常數基線": "-2.99pp"},
                          "LCB 難題": {"原始 FAIL 主張": "234/261 = 89.7%（近乎一律 FAIL）",
                                       "初稿錯誤率": 0.46, "原始層−常數基線": "+0.77pp"},
                          "解釋": "換題庫只是換了它偏向哪一個常數"}},
    },
    {
        "id": "gain.clean_dataset",
        "輪次": "gain-2026-08-30",
        "宣稱": "決定性 run 是第一個乾淨的完整資料集：無已知 bug 污染、void 率在窗口內",
        "型別": "資料品質宣稱",
        "依據": {"檔案": "增益實驗_2026-08-30/g_r356_3arm_summary.json",
                 "數值": {"ON infra_void": "66/179", "OFF5 infra_void": "30/179", "OFF infra_void": "5/179",
                          "R437 自記": "void率 ON=36.2% OFF5=16.9% ⚠VOID-GATE-WARNING",
                          "equal_budget_comparison_valid（summary 欄位）": False}},
    },

    # ── CONFORM／EQ5／peerexec（2026-09-04 ~ 09-07；round459 從 verdicts.py 搬進來）──
    # 這八條的宣稱本文、裁決、一句話、邊界仍然只寫在 `examples/verdicts.py`
    # （單一真相來源，`verdict_for` 會把它們併進來）；這裡放的是**依據**——
    # 讀索引的 agent 要的是「原始資料在 repo 的哪個檔」，那件事 verdicts.py 不知道。
    # 在這八條搬進來之前，`_index/claims.json` 少了它們，`archive.json` 得帶一個
    # `index_gap` 欄位把缺口列出來；缺口補上之後那個欄位就撤掉了（round459）。
    # 註：`ops/gain/replay/` 底下的 peerexec 資料全部是重放與模擬，唯二的真跑是
    # `replay/r453/`（k=2）與 `replay/r454/`（k=3）——這件事寫在各條的「哪一半是真跑」。
    {
        "id": "gain.conform_early_stop_beats_single",
        "輪次": "gain-2026-08-30",
        "型別": "量測（三個題庫、配對）",
        "宣稱": "「跑客戶自己的驗收測資、交第一份通過的、全不通過就拒交」（CONFORM 早停閘門）"
                "比「單抽一份就收」（OFF）多交付",
        "依據": {
            "檔案": "runs/g_r444_conform_mbpp/rows.jsonl、runs/g_r445_conform_mbpp_ext/rows.jsonl"
                    "（MBPP+ 併庫 371 題）；runs/g_r447_conform_lcb2/rows.jsonl（LCB v2 120 題）；"
                    "runs/g_r461_lcb3_three_arm/rows.jsonl（LCB v3 189 題）",
            "裁決文件": "CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md、"
                        "DECISION_20260905_R440Z_WRAPUP_LCB2.md、"
                        "DECISION_20260906_R461_FABLE_AUDIT.md、"
                        "DECISION_20260903_R440P_CONFORMANCE_GATE.md",
            "重算": "ops/gain/replay/conform_settle.py、ops/gain/replay/paired_ci.py、"
                    "ops/gain/replay/pooled_paired_ci.py（零 API，只讀 rows.jsonl）",
            "欄位": "rows.jsonl 的 arm／task_id／delivered／hidden_pass／calls_used",
            "數值": {"MBPP+ 併庫 371 題": "+4.58pp（CI [+0.57, +8.04]）",
                     "LCB v2 120 題": {"delta_pp": 19.17, "b": 31, "c": 8, "p": 0.0003},
                     "LCB v3 189 題": {"delta_pp": 7.94, "b": 25, "c": 10, "p": 0.0167},
                     "呼叫／題": "1.51／1.71／1.55 對 1.00"},
        },
    },
    {
        "id": "gain.gate_rule_beats_majority_vote_same_candidates",
        "輪次": "gain-2026-08-30",
        "型別": "量測（EQ5 等預算臂，四個 run）",
        "宣稱": "在同一組 5 份候選、同樣 5 通呼叫下，閘門規則（交第一份通過的、全不通過就不交）"
                "比五份投票取多數交付得多",
        "依據": {
            "檔案": "runs/g_r446_eq5_mbpp/rows.jsonl（MBPP+ 371 題）、"
                    "runs/g_r448_eq5_mbpp_seed2/rows.jsonl（MBPP+ 371 題、換種子）、"
                    "runs/g_r449_eq5_lcb2/rows.jsonl（LCB v2 難題 120 題）、"
                    "runs/g_r449c_eq5_lcb3/rows.jsonl（LCB v3 189 題，判 UNRESOLVED）",
            "裁決文件": "CONCLUSION_20260904_R446_EQUAL_BUDGET.md、"
                        "DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md、"
                        "DECISION_20260906_R449B_EQ5_LCB2_PREREG.md（§六 三個狀態、事前寫死）、"
                        "DECISION_20260906_R449B_FABLE_AUDIT_REPLICATED_ON_HARD.md、"
                        "DECISION_20260907_R449C_FABLE_AUDIT_UNRESOLVED.md",
            "重算": "ops/gain/analyze_eq5.py（零 API，只讀 rows.jsonl；它自己印的 prereg 區塊"
                    "**不是**仲裁者，見 R449B §三 末）",
            "數值": {"r446": {"gate": 75.47, "vote": 71.43, "b": 24, "c": 9,
                              "delta_pp": 4.04, "ci95": [0.796, 6.529], "p": 0.0135},
                     "r448": {"gate": 77.09, "vote": 73.58, "b": 21, "c": 8,
                              "delta_pp": 3.50, "ci95": [0.81, 6.47], "p": 0.0241},
                     "r449b": {"gate": 70.83, "vote": 62.50, "b": 15, "c": 5,
                               "delta_pp": 8.33, "ci95": [0.30, 13.78], "p": 0.0414},
                     "r449c（UNRESOLVED）": {"gate": 83.07, "vote": 78.84, "b": 13, "c": 5,
                                             "delta_pp": 4.23, "ci95": [-0.66, 7.68], "p": 0.0963}},
        },
    },
    {
        "id": "gain.conform_vs_off5_unresolved",
        "輪次": "gain-2026-08-30",
        "型別": "量測（獨立抽樣，兩個 LCB run）",
        "宣稱": "閘門（CONFORM）在交付準確率上贏得過同題跑五次取多數決（OFF5）",
        "依據": {
            "檔案": "runs/g_r447_conform_lcb2/rows.jsonl（LCB v2 120 題）、"
                    "runs/g_r461_off_gate_lcb3/rows.jsonl 與 runs/g_r461_lcb3_three_arm/rows.jsonl"
                    "（LCB v3 189 題）；MBPP+ 側 runs/g_r445_conform_mbpp_ext/rows.jsonl",
            "裁決文件": "DECISION_20260905_R440Z_WRAPUP_LCB2.md、"
                        "DECISION_20260906_R461_FABLE_AUDIT.md、"
                        "CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md",
            "重算": "ops/gain/replay/paired_ci.py、ops/gain/replay/off5_k_curve.py",
            "數值": {"LCB v2": {"delta_pp": 6.67, "p": 0.15},
                     "LCB v3": {"delta_pp": 1.59, "ci95": [-3.17, 6.35], "p": 0.6636},
                     "MBPP+ 乾淨複製（新 192 題）": {"delta_pp": 4.69, "ci95": [-1.11, 9.42]},
                     "MDE@371": 4.31, "80%_power_需配對數": 491, "題庫上限": 378},
        },
    },
    {
        "id": "gain.lossless_visible_filter",
        "輪次": "gain-2026-08-30",
        "型別": "量測（六個資料集）",
        "宣稱": "可見篩選是無損的——沒有出現「隱藏測資會過、但可見驗收沒過」的候選",
        "依據": {
            "檔案": "runs/g_r441_gemma_only_mbpp_b/rows.jsonl（0／895）、"
                    "runs/g_r356_3arm_20260830/rows.jsonl（0／735）、"
                    "runs/g_r443_gemma_lcb/rows.jsonl（LCB v1 重放 0／455）、"
                    "runs/g_r447_conform_lcb2/rows.jsonl（LCB v2 真跑 0／120）、"
                    "runs/g_r461_off_gate_lcb3/rows.jsonl（LCB v3 真跑 0／189）",
            "裁決文件": "DECISION_20260903_R440P_CONFORMANCE_GATE.md（§二 誠實邊界 2）、"
                        "DECISION_20260904_R440T_E3_WRAPUP.md、"
                        "DECISION_20260905_R440Z_WRAPUP_LCB2.md、"
                        "DECISION_20260906_R461_FABLE_AUDIT.md",
            "重算": "ops/gain/replay/rows_visible_audit.py、ops/gain/replay/verify_hidden.py、"
                    "ops/gain/replay/check_lcb_visible_subset.py",
            "欄位": "rows.jsonl 的 visible_pass 與 hidden_pass；違反＝hidden_pass ∧ ¬visible_pass",
            "數值": {"MBPP+ 合計": "0／1630", "LCB v1 重放": "0／455",
                     "LCB v2 真跑": "0／120", "LCB v3 真跑": "0／189",
                     "重疊（非獨立樣本）": "LCB v1 重放與 LCB v2 真跑共用 91 題"},
        },
    },
    {
        "id": "gain.off5_helps_on_hard_only",
        "輪次": "gain-2026-08-30",
        "型別": "量測（OFF5 vs OFF，跨題庫對照）",
        "宣稱": "五倍預算的 self-consistency（OFF5 對 OFF）只在難題上買得到東西",
        "依據": {
            "檔案": "runs/g_r441_gemma_only_mbpp_b/rows.jsonl 與 runs/g_r356_3arm_20260830/rows.jsonl"
                    "（MBPP+）、runs/g_r447_conform_lcb2/rows.jsonl（LCB v2 120 題）、"
                    "runs/g_r461_lcb3_three_arm/rows.jsonl（LCB v3 189 題）",
            "裁決文件": "CONCLUSION_20260904_R445_CONFORM_SETTLEMENT.md、"
                        "DECISION_20260905_R440Z_WRAPUP_LCB2.md、"
                        "DECISION_20260906_R461_FABLE_AUDIT.md",
            "重算": "ops/gain/replay/off5_k_curve.py、ops/gain/replay/paired_ci.py",
            "數值": {"MBPP+": {"delta_pp": 0.81, "ci95": [-2.78, 4.28], "格": "RULED_OUT"},
                     "LCB v2": {"delta_pp": 12.50, "b": 22, "c": 7, "p": 0.0081},
                     "LCB v3": {"delta_pp": 6.35, "b": 22, "c": 10, "p": 0.0501},
                     "對照（改花法比加預算更有用）": "+19.2pp @1.71 通 vs +12.5pp @5 通",
                     "r461 不算難題複製": "lcb3 的 OFF 失敗率 27.5%，已回到 MBPP+ 量級 31.8%"},
        },
    },
    {
        "id": "peerexec.mutual_execution_below_threshold",
        "輪次": "peerexec-2026-09-05",
        "型別": "模擬掃描＋真跑（哪一半是哪一半見裁決的「邊界」欄）",
        "宣稱": "在多數門檻以下（腐化執行器數 ≤ ⌊(k−1)/2⌋），互跑不互審的交付與無腐化基線逐位相同，"
                "說謊者被指名、誠實者不被誣告",
        "依據": {
            "檔案": "【模擬】ops/gain/replay/peer_exec_sweep.json（200 格：r446 371 題×5 候選、"
                    "r443 91 題×5、k∈{1,3,5,7}、腐化比例 0–70%、五種攻擊）、"
                    "ops/gain/replay/peer_exec_flake.json（抖動×腐化）；"
                    "【真跑】ops/gain/replay/r453/r453_result.json 與 r453_independent_audit.json"
                    "（k=2、Mac＋vacant-dev）、ops/gain/replay/r454/r454_result.json 與 "
                    "r454_naming_table.tsv（k=3、1 把說謊）",
            "裁決文件": "DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md、"
                        "DECISION_20260906_R453_FABLE_AUDIT_REAL_MULTIPARTY.md、"
                        "DECISION_20260906_R454_FABLE_AUDIT_NAMED_DISSENT.md",
            "重算": "ops/gain/replay/peer_exec_sim.py（模擬）、ops/gain/replay/peer_exec_real.py（真跑）、"
                    "ops/gain/replay/receipt_chain_audit.py（鏈驗證）；程式在 vacant/peerexec.py",
            "數值": {"模擬 門檻以下": {"與無腐化基線逐位相同": "100 格",
                                       "說謊者被指名": 1.0, "誠實者被誣告": 0.0,
                                       "1 個腐化 k=1": "−7.8pp、偵測 0",
                                       "1 個腐化 k=3": "偵測 1.000"},
                     "真跑 R453（k=2）": {"跨機可見標籤一致": "1840／1840", "出貨 sha": "340／340",
                                          "拒交": "26／26", "誠實執行器被指名": 0,
                                          "每台鏈驗真": "2／2", "spec/render sha 跨機相同": "368／368"},
                     "真跑 R454（k=3、1 把說謊）": {"說謊格 dissenters 恰為 {K3}": "273／273",
                                                    "誠實金鑰出現在指名欄": "0（分母 1840）",
                                                    "自相矛盾格裁決仍正確": "58／58",
                                                    "三條鏈驗真": "3／3（鏈長 1840／1840／1899）",
                                                    "證言逐筆驗簽失敗": "0（共 5519 筆）"}},
        },
    },
    {
        "id": "peerexec.suite_fixed_point",
        "輪次": "peerexec-2026-09-05",
        "型別": "極限宣稱（held＝這個「買不到」本身被量到了）",
        "宣稱": "互跑不互審對「驗收套件本身腐化」毫無防禦——這是機制的固定點，"
                "R451→R452 把它縮小成一個殘餘，但沒有消滅",
        "依據": {
            "檔案": "ops/gain/replay/peer_exec_trivial_suite.json（「載得進就算過」的套件）、"
                    "ops/gain/replay/r451_stateful_gate.json（量具兩方向滿分的 stateful 變體）、"
                    "ops/gain/replay/peer_exec_suitespec_gate.json 與 r452b_smuggle_gate.json"
                    "（exec 走私）、ops/gain/replay/r452c_generic_gate.json 與 r452c_channel_hunt.json"
                    "（殘餘：generic_gauged／weak_oracle）、ops/gain/replay/r453/r453_gauge.json",
            "裁決文件": "DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md（§三-3）、"
                        "DECISION_20260906_R451_FABLE_AUDIT_SUITE_GAUGE.md、"
                        "DECISION_20260906_R452_FABLE_AUDIT_SUITE_AS_DATA.md",
            "重算": "ops/gain/replay/r452_suitespec.py、ops/gain/replay/r452c_generic_gate.py、"
                    "ops/gain/replay/r452b_smuggle_gate.py；程式在 vacant/suitegauge.py",
            "數值": {"trivial 套件": {"交付率": "−6.47pp／−18.68pp", "假交付": "31%／49%",
                                      "四個 k 的爭議率": "全部 0.0%"},
                     "R451 量具綁進 commit": "trivial 套件 371／371 在 commit 就被拒（沒花一次沙箱）",
                     "R451 stateful 變體": {"交付率": "−75.20pp", "交付": "0.00%",
                                            "gauge_status": "ok（量具作為部分解作廢）"},
                     "R452 套件改成資料": {"exec 走私上鏈": "368／371 → 0／371",
                                           "超大十六進位整數穿門": "11／11 → 0／11",
                                           "無損": "1840（MBPP+）＋455（LCB）個候選逐格相同、0 不一致"},
                     "殘餘（一律講兩個數字，分母 366／371 上鏈題）": {
                         "可實現 generic_gauged": "17.93% → 20.65%＝+2.72pp",
                         "事後諸葛上限 weak_oracle": "+4.35pp"}},
        },
    },
    {
        "id": "peerexec.majority_bound",
        "輪次": "peerexec-2026-09-05",
        "型別": "極限宣稱（機制的數學上界，不是量測結果）",
        "宣稱": "指名有數學上界：多數決最多容忍 ⌊(k−1)/2⌋ 個腐化執行器，過半即反轉",
        "依據": {
            "程式": "vacant/peerexec.py::MAJORITY_BOUND_NOTE（機制性質寫死在這裡，"
                    "不是實驗量到的效應量）與 form_verdict／select_by_quorum",
            "檔案": "ops/gain/replay/peer_exec_sweep.json（配套量測：固定腐化比例下 k 從 1 到 7"
                    "交付率一字不變）、ops/gain/replay/r454/r454_naming_table.tsv（真跑的指名欄）",
            "裁決文件": "DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md（§三-1）、"
                        "DECISION_20260906_R454_FABLE_AUDIT_NAMED_DISSENT.md、"
                        "DECISION_20260906_R455_FABLE_AUDIT_VIEWER.md（T8：離線檢視器的結構性界線）",
            "數值": {"容忍上界": "⌊(k−1)/2⌋",
                     "過半後誣告率": "0.175／0.374（兩批掃描：r446 371 題×5、r443 91 題×5）",
                     "固定腐化比例下 k=1..7 交付率": "一字不變（串謀 67.39%、破壞 0%）",
                     "k=3／quorum=2 缺一票": "1-1 平手 ⇒ 未決、不指名"},
        },
    },
    {
        "id": "harness.hmix_loop_beats_resample_same_budget",
        "輪次": "harness-2026-09-08",
        "型別": "量測（R460 六臂交錯，LCB v2 120 題，五通等預算）",
        "宣稱": "把五通呼叫花在「跑客戶的驗收測資、把失敗原文貼回去、讓同一個 worker 改」（H-MIX），"
                "比花在換人重抽（CONFORM）多交付，且 token 不多花",
        "依據": {
            "檔案": "runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}/rows.jsonl 與 calls.jsonl（六塊各 20 題，合併 120 題）",
            "裁決文件": "DECISION_20260907_R460_HARNESS_PREREG.md（§六 四狀態規則，事前寫死）、"
                        "DECISION_20260908_R460_FABLE_LAUNCH_NOTES.md、DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md",
            "重算": "ops/gain/analyze_r460.py --run <六塊> --bank lcb2 --rescore-turn1（零 API，只跑沙箱）；"
                    "落盤 ops/gain/replay/r460/r460_analyze.json",
            "數值": {"OFF": {"deliv": 58.33, "false_delivery_n": 50, "tokens_per_task": 2913},
                     "CONFORM": {"deliv": 70.83, "false_delivery_n": 29, "tokens_per_task": 5805},
                     "OFF5": {"deliv": 65.00, "false_delivery_n": 42, "tokens_per_task": 15004},
                     "HPI": {"deliv": 75.83, "false_delivery_n": 17, "tokens_per_task": 9448},
                     "HOC": {"deliv": 80.00, "false_delivery_n": 18, "tokens_per_task": 7432},
                     "HMIX": {"deliv": 84.17, "false_delivery_n": 14, "tokens_per_task": 5677},
                     "HMIX_vs_CONFORM": {"b": 22, "c": 6, "delta_pp": 13.33, "ci95": [4.22, 19.46],
                                          "p": 0.0037, "holm_p_adj": 0.0112, "verdict": "EFFECTIVE"},
                     "HMIX_vs_OFF": {"b": 34, "c": 3, "delta_pp": 25.83, "ci95": [17.32, 29.78]}},
        },
    },
    {
        "id": "harness.hpi_hoc_vs_resample_unresolved",
        "輪次": "harness-2026-09-08",
        "型別": "量測（同一個 R460 run）",
        "宣稱": "pi 式原始回饋迴圈（H-PI）與計畫＋診斷＋自測（H-OC）也贏過換人重抽",
        "依據": {
            "檔案": "同上（runs/g_r460_harness_lcb2_*/rows.jsonl）",
            "裁決文件": "DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md§三（四狀態：INCONCLUSIVE）",
            "重算": "ops/gain/replay/r460/r460_analyze.json · decision.HPI / decision.HOC",
            "數值": {"HPI_vs_CONFORM": {"delta_pp": 5.00, "ci95": [-4.40, 13.30], "holm_p_adj": 0.345},
                     "HOC_vs_CONFORM": {"delta_pp": 9.17, "ci95": [-1.00, 17.62], "holm_p_adj": 0.160}},
        },
    },
    {
        "id": "harness.gain_is_the_loop_not_the_prompt",
        "輪次": "harness-2026-09-08",
        "型別": "歸因（D5，turn-1 離線重取碼再計分）",
        "宣稱": "H-MIX 的增益幾乎全來自「把失敗原文貼回去讓它改」的迴圈，不是第一輪 prompt 的措辭",
        "依據": {
            "檔案": "runs/g_r460_harness_lcb2_*/calls.jsonl（turn-1 全文回應）＋ rows.jsonl",
            "裁決文件": "DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md§五、§十",
            "重算": "ops/gain/analyze_r460.py --rescore-turn1；ops/gain/replay/r460/r460_analyze.json · attribution.*",
            "數值": {"HMIX": {"loop_effect_pp_replays": [19.17, 17.50], "prompt_effect_pp_replays": [6.67, 8.33],
                              "loop_gain_n": 21, "turn1_visible_pass_pp": 74.2}},
        },
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
    {"id": "gain-2026-08-30", "dir": "增益實驗_2026-08-30",
     "問題": ["加了 Vacant，產出有沒有更接近需求？", "等預算下打不打得贏最土的 self-consistency？",
              "打不贏的話，機制上為什麼？"],
     "報告": "CONCLUSION_20260830_G_EXPERIMENT.md",
     "實驗": ["E25"]},
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
    # 裁決一定要跟宣稱寫在一起。少了它，這份索引會告訴讀它的 agent
    # 「這 12 條都成立」，而其中 6 條我們自己已經知道有問題——索引的全部價值
    # 就在於它不會說謊，而讀索引的 agent 沒有網頁可以對照。
    claims_out = [{**c, **verdict_for(c["id"])} for c in CLAIMS]
    n_bad = sum(1 for c in claims_out if c["verdict"] in ("refuted", "overstated"))
    (OUT / "claims.json").write_text(
        json.dumps({"note": "每條對外宣稱 → 支撐它的檔案、欄位、數值、重算方式，"
                            "以及對抗式複驗的裁決。"
                            f"verdict=未複驗 代表還沒有人試過推翻它，不代表它通過了。",
                    "裁決值": {"refuted": "宣稱是錯的，正確說法在「更正後」",
                               "overstated": "核心站得住但說得太滿，或原始證據／機制解釋有問題",
                               "held": "事前訂的判準通過（預註冊、跑完對答案）",
                               "no_effect": "量到沒有可分辨的效應——這本身就是答案，不是沒測完",
                               "未複驗": "尚未送複驗——不等於通過"},
                    "claims": claims_out}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"catalog.json  輪次 {len(rounds_meta)}")
    print(f"files.jsonl   {n_files} 檔、{total_rows:,} 行、{total_bytes/1e6:.1f} MB")
    print(f"schema.json   {len(SCHEMA)} 種紀錄型別")
    print(f"claims.json   {len(CLAIMS)} 條宣稱（其中 {n_bad} 條被推翻或判定說得太滿）")
    print(f"methods.json  {len(METHODS)} 種測試方法")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
