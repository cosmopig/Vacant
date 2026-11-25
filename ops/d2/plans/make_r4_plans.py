#!/usr/bin/env python3
"""第四輪計畫檔產生器（一次寫出四份；教材 manifest 的 sha256 從私有目錄讀，路徑以 ${D2_PRIVATE} 記）。
用法：D2_PRIVATE=... python3 ops/d2/plans/make_r4_plans.py <gen4 commit>"""
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
priv = os.environ["D2_PRIVATE"]
gen4_commit = sys.argv[1]
base = json.loads((HERE / "r3main_d2_qwen9b_1003.json").read_text())
hk = json.loads((HERE / "r3haiku_d2.json").read_text())


def msha(d):
    return hashlib.sha256(open(f"{priv}/{d}/manifest.json", "rb").read()).hexdigest()


PV = {"commit": "auto/redo 2a502e9e4", "wheel": "~/dev/ops/d2_release/2a502e9e4/vacant_network-0.9.2-py3-none-any.whl",
      "wheel_sha256": "8019b04f349b896519891ed875d69447fede850c94433f37db7d85fb7d3dd863", "venv": "~/dev/ops/d2v4_venv（不可編輯安裝）"}
CFG_PI = {"dir": "~/dev/ops/agentcfg/d2v4", "copy": ["models.json", "extensions"],
          "install_json": "~/dev/ops/agentcfg/d2v4_state/adapters/install.json"}
CFG_CL = {"dir": "~/dev/ops/agentcfg/d2claude_v4/.claude", "copy": ["settings.json"],
          "install_json": "~/dev/ops/agentcfg/d2claude_v4/.vacant/adapters/install.json"}
ARMS = ["a", "b", "cV", "d_diff", "d_diff_real"]
COMMON = {"snapshot_after_c0": True, "dynamic_noise": True, "no_tool_mention": True, "nosrc_index": True,
          "private_live": "~/dev/ops/d2_private_live", "egress": {"mode": "per-set proxy, OS-assigned port"},
          "vacant_python": "~/dev/ops/d2v4_venv/bin/python", "agent_timeout_s": 600}

PRODUCT = ("產品 v4（commit 2a502e9e4，wheel sha256 8019b04f…；不可編輯安裝；pi／Claude Code 的掛鉤用 d2v4_venv 真的跑 `vacant install` 寫出）。"
           "相對 v3 的通用修正，都針對第三輪兩批的歸因：(1) 受影響看值（`--by-value`）：候選頁裡這個值所在的位置還是不是這個值——JSON 照欄位路徑"
           "（陣列元素用其餘欄位相同最多的對回來，不怕重排），其他格式找除了這個值之外最像的那一行；每次抓取的雜訊不讓任何宣稱受影響。"
           "(2) 網路出口紀錄（`--egress`、`vacant trace egress`）：agent 工具的 HTTP 請求經 Vacant 的本機代理，實際抓過的網址與內容記成 `source_fetch` 事件，"
           "候選來源＝寫入之前實際抓過、內容含這個值的網址（不靠指令文字；變數拼網址、python、node 都算得到）；「沒重讀就改」也認出口紀錄。"
           "(3) agent 動手之前檔裡就有的數字（範本、實體名裡的數字）不當宣稱。限制：HTTPS 只記主機；不吃 http_proxy 的工具記不到；"
           "代理在實驗裡由 runner 啟動，產品安裝後自動生效還沒做；出口紀錄先落檔再進鏈。")
ARM_TXT = {"a": "不維護", "b": "整份重查", "cV": "v4 全開：候選集合（含出口紀錄）＋快照＋看值判受影響＋越界守衛＋沒重讀退回一次（**主要臂**）",
           "d_diff": "頁面通知＋文字差異，理想版（用教材檔算，不受雜訊影響；上限）",
           "d_diff_real": "頁面通知＋文字差異，真實版（執行器每週期實際抓頁面、和上一週期抓到的比；雜訊會讓它每週期觸發）",
           "note": "所有臂的提示都不提抓取工具；沒有出處的行交辦時給索引頁（nosrc_index）。初稿共用；初稿後跑一次 `--snapshot --egress`。"}
PRIMARY = {"family_P_vs_b": "覆蓋率（cV 第 1 週期候選集合含正確頁）≥80%；漏抓差 cV−b 單側 97.5% 上界 <10pp；成本比 b/cV 97.5% 區間下界 ≥3。",
           "family_P_vs_d_real": "同上覆蓋率；漏抓差 cV−d_diff_real 上界 <10pp；成本比 d_diff_real/cV 下界 ≥1。",
           "alpha": "兩個家族各 α/2＝0.025。",
           "secondary": "cV 對理想版 d_diff（同門檻，描述）；F／N＋Z 分週期成本表與只看 F 週期的比值；改錯；不必要的交辦（按原因）；"
                        "漏判歸因（值還在比對到的位置＝看值的反面風險）；覆蓋率按格式；越界讀取逐筆＋剔除敏感度。"}
STATES = base["prereg"]["states"]


def prereg(question, materials_txt, extra_limits, analysis):
    return {"registered": ("2026-11-25，第一通模型呼叫之前 commit 並推到遠端（執行器檢查）。第三輪全部批次（含 heldout-v3 與 Haiku 第三輪）都已看過結果、"
                           "降為開發資料；v4 是看過它們的歸因才改的。產品凍結（2a502e9e4）之後才請隔離的代理寫第四個產生器、才產生教材；教材只跑過檢查器。"),
            "question": question, "product": PRODUCT, "materials": materials_txt, "arms": ARM_TXT,
            "primary": {**PRIMARY, "analysis": analysis}, "states": STATES,
            "known_limits": ["v4 是看過第三輪全部結果才改的。", "d_diff 理想版不受雜訊影響（上限）；主要比較用真實版。",
                             "工作目錄不可列舉不是沙箱；事後掃描越界讀取。", "虛構網頁。"] + extra_limits,
            "stop_rules": ["任一組基礎設施失敗連續 3 次：停批回報。", "03:00Z 還沒跑完：照 INCOMPLETE 規則停批、報已完成的組。"]}


G4 = ("第四個產生器 heldout-v4（agy 隔離、只給規格寫的，commit " + gen4_commit + "，複本 ops/d2/heldout_gen4/；規格 ~/dev/ops/agy_tasks/heldout4.md）："
      "兩層索引導覽、json／csv／tsv／yaml／xml／txt／md／html 混用、每次抓取的雜訊、修訂歷史保留舊值、同一筆紀錄兩欄同值且只改其一、表格／清單重排、"
      "分頁且列會換頁、近似實體名、部分實體名含數字。種子 20261166、36 組。")
Q4 = "v4 在第四個產生器（和開發資料不同、壓在 v4 可能弱的地方）上，對整份重查、對真實版頁面通知＋差異，漏得不多、省得夠不夠？"
AN = "合併兩台的 root（連結）後：audit_d2.py --coverage-arm cV；analyze_d2.py --primary-arm cV --d-arm d_diff_real；另跑 --d-arm d_diff（次要）；cycle_costs.py --primary cV --d-arm d_diff_real；scan_escape.py。"

out = {}
for name, machine, prov, sets, jobs, port in [
        ("r4main_d2_qwen9b_1003", "1003", "lms1003q9", [f"s{i:02d}" for i in range(1, 25)], 3, 18231),
        ("r4main_d2_qwen9b_1004", "1004", "lms1004q9", [f"s{i:02d}" for i in range(25, 37)], 2, 18232)]:
    p = {"schema": base["schema"], "id": name, "seed": 20261167 if machine == "1003" else 20261168, "jobs": jobs,
         "server": {"port": port}, "arms": ARMS, **COMMON,
         "model": {"provider": prov, "model": "qwen/qwen3.5-9b", "thinking": "off (reasoning_effort none)"},
         "agentcfg": CFG_PI, "product_version": PV,
         "materials": {"dir": "${D2_PRIVATE}/heldout_v4_seed20261166", "generator": G4, "manifest_sha256": msha("heldout_v4_seed20261166"), "sets": sets},
         "purpose": f"D2′ 第四輪確認批次（事前登記、確認性）：{machine} 的那一份（{sets[0]}–{sets[-1]}）；和另一台合併判定。主要臂 cV。",
         "prereg": prereg(Q4, G4, ["只有 qwen3.5-9b（Haiku 另一批）。", "1003 s01–s24（jobs 3）、1004 s25–s36（jobs 2），同一個 9B、ctx 65536，llama.cpp 版本不同；合併判定、分台描述。",
                                   "36 組約 144 對；檢定力中等。"], AN)}
    out[name] = p
ph = {"schema": hk["schema"], "id": "r4haiku_d2", "seed": 20261169, "jobs": 3, "server": {"port": 18233}, "arms": ARMS, **COMMON,
      "model": hk["model"], "agentcfg": CFG_CL, "product_version": {**PV, "hooks": "`vacant install --agents claude --mode observe` 用 d2v4_venv"},
      "materials": {"dir": "${D2_PRIVATE}/heldout_v4_seed20261166", "generator": G4, "manifest_sha256": msha("heldout_v4_seed20261166"),
                    "sets": [f"s{i:02d}" for i in range(1, 37)]},
      "purpose": "D2′ 第四輪 Haiku（事前登記、確認性）：同一份 36 組教材，成本用美元。主要臂 cV。",
      "prereg": {**prereg("同上，換成雲端 Claude Haiku（Claude Code）；成本用美元（第二輪 Haiku 的定義）。", G4,
                          ["成本用美元是第二輪看過 Haiku 小量試跑才定的口徑。"],
                          "audit_d2.py --coverage-arm cV；analyze_d2.py --primary-arm cV --d-arm d_diff_real --cost-metric cost_usd；cycle_costs.py --metric cost_usd；scan_escape.py。")}}
out["r4haiku_d2"] = ph
ps = {"schema": base["schema"], "id": "r4h3seen_d2_qwen9b_1003", "seed": 20261170, "jobs": 1, "server": {"port": 18234}, "arms": ARMS, **COMMON,
      "model": {"provider": "lms1003q9", "model": "qwen/qwen3.5-9b", "thinking": "off (reasoning_effort none)"},
      "agentcfg": CFG_PI, "product_version": PV,
      "materials": {"dir": "${D2_PRIVATE}/heldout_v3_seed20261165", "generator": "ops/d2/heldout_gen3/gen_heldout3.py --seed 20261165 --sets 20（heldout-v3 新種子）",
                    "manifest_sha256": msha("heldout_v3_seed20261165"), "sets": [f"s{i:02d}" for i in range(1, 21)]},
      "purpose": "D2′ 第四輪對照（描述性）：已見過結構（heldout-v3 產生器、新種子 20 組）上的 v4。",
      "prereg": {**prereg("v4 在 heldout-v3 結構（第三輪失敗的那一種、已看過）上的表現，描述，不判定。", "heldout-v3 新種子 20261165、20 组。",
                          ["已見過的結構：描述性，不當確認證據。", "jobs 1，和主批次共用 1003（同時 9B 不超過 4 段）。"],
                          "同主批次的分析，只描述。")}}
out["r4h3seen_d2_qwen9b_1003"] = ps
for k, v in out.items():
    (HERE / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
    print(k, v["materials"]["manifest_sha256"][:12])
