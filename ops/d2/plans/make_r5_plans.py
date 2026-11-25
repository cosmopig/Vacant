#!/usr/bin/env python3
"""第五輪計畫檔產生器（真實教材＋已見過的壓力結構對照）。教材 manifest 的 sha256 從私有目錄讀，路徑以 ${D2_PRIVATE} 記。
用法：D2_PRIVATE=... python3 ops/d2/plans/make_r5_plans.py <realrev commit> <real materials dir name> <n_sets>"""
import hashlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
priv = os.environ["D2_PRIVATE"]
rcommit, rdir, nsets = sys.argv[1], sys.argv[2], int(sys.argv[3])
base = json.loads((HERE / "r4main_d2_qwen9b_1003.json").read_text())
hk = json.loads((HERE / "r4haiku_d2.json").read_text())


def msha(d):
    return hashlib.sha256(open(f"{priv}/{d}/manifest.json", "rb").read()).hexdigest()


PV = {"commit": "auto/redo 7d574c3d3（從 worktree ~/dev/wt/d2r5 分支 d2/r5-guardfix 推上 auto/redo；主 checkout 因 stash 衝突暫停，見 ~/dev/ops/STASH_CONFLICT_20261126.md）",
      "wheel": "~/dev/ops/d2_release/7d574c3d3/vacant_network-0.9.2-py3-none-any.whl",
      "wheel_sha256": "f3ca975c9a4cc4847fcade1f3c55bf76457956e376f076333cf9152139cab07d", "venv": "~/dev/ops/d2v51_venv（不可編輯安裝）"}
CFG_PI = {"dir": "~/dev/ops/agentcfg/d2v51", "copy": ["models.json", "extensions"],
          "install_json": "~/dev/ops/agentcfg/d2v51_state/adapters/install.json"}
CFG_CL = {"dir": "~/dev/ops/agentcfg/d2claude_v51/.claude", "copy": ["settings.json"],
          "install_json": "~/dev/ops/agentcfg/d2claude_v51/.vacant/adapters/install.json"}
ARMS = ["a", "b", "cV5", "d_diff_real"]
COMMON = {"snapshot_after_c0": True, "no_tool_mention": True, "nosrc_index": True,
          "private_live": "~/dev/ops/d2_private_live", "egress": {"mode": "per-set proxy, OS-assigned port"},
          "vacant_python": "~/dev/ops/d2v51_venv/bin/python", "agent_timeout_s": 600}
PRODUCT = ("產品 v5.1（commit 7d574c3d3，wheel sha256 f3ca975c…；不可編輯安裝；pi／Claude Code 掛鉤用 d2v51_venv 真的跑 `vacant install` 寫出）。"
           "相對 v4 修兩點：(1) 表格（CSV／TSV／管線表格／定寬表格／HTML 表格）照「表頭＋其他格相同最多的那一列」定位、XML 照元素路徑（`--by-field`）"
           "——同一列別的欄位剛好也是這個值時不再被騙；(2) **越界守衛的 bug 修正**：用改前那一行到「: 」為止的整段標籤對行，不再用「第一個數字之前」"
           "（名稱含數字的實體所有行撞成同一個鍵、交辦的行被兄弟行覆蓋；獨立稽核 11-25 查到）。v5 原訂的「交辦行只准改值」建立在錯的診斷上，已撤回（`--keep-labels` 參數保留、沒有作用）。"
           "其餘同 v4（看值判受影響、網路出口紀錄、範本數字不當宣稱）。")
ARM_TXT = {"a": "不維護", "b": "整份重查",
           "cV5": "v5.1 全開：候選集合（含出口紀錄）＋快照＋看值（照欄位）判受影響＋保留標籤的越界守衛＋沒重讀退回一次（**主要臂**）",
           "d_diff_real": "頁面通知＋文字差異，真實版（執行器每週期實際抓頁面、和上一週期抓到的比）",
           "note": "所有臂的提示都不提抓取工具；沒有出處的行交辦時給索引頁。初稿共用；初稿後跑一次 `--snapshot --egress`。"}
PRIMARY = {"family_P_vs_b": "覆蓋率（cV5 第 1 週期候選集合含正確頁）≥80%；漏抓差 cV5−b 單側 97.5% 上界 <10pp；成本比 b/cV5 97.5% 區間下界 ≥3。",
           "family_P_vs_d_real": "同上覆蓋率；漏抓差 cV5−d_diff_real 上界 <10pp；成本比 d_diff_real/cV5 下界 ≥1。",
           "alpha": "兩個家族各 α/2＝0.025。",
           "secondary": "F／N＋Z 分週期成本表與只看 F 週期的比值；改錯；不必要的交辦（按原因）；**各值型態的出處覆蓋率與「沒交辦：值還在原位」的發生率**"
                        "（＝第四輪那種失敗在真實文件裡多常見）；越界讀取逐筆＋剔除敏感度。"}
STATES = base["prereg"]["states"]
REAL = ("真實教材：英文維基百科足球員條目的真實修訂（產生器 realrev-wikipedia/1，由沒看過出處程式的代理 agy 隔離寫成，commit " + rcommit +
        "，複本 ops/d2/realrev_gen/；選頁與選欄位規則事前寫死在其 README：三個低級別聯賽球員類別、依種子 20261172 洗牌、窗口 2026-11-20 往前 120 天、"
        "5 個等距時間點各取當時最新修訂、資訊框裡含數字的列為宣稱、至少一條宣稱在窗口內真的改過）。每組 3 條條目、15–20 條宣稱，共 " + str(nsets) + " 組。"
        "內容凍結在本機、由本機來源伺服器提供，實驗期間不連外；內容放 repo 外，repo 只放產生器與 SOURCES 清單（標題、修訂編號、雜湊）；授權 CC BY-SA 4.0。"
        "週期類型（F 事實改動／N 只改別處／Z 沒改）來自資料本身，不是設計的，照實報比例。")
LIM = ["v5.1 是看過第四輪全部結果與獨立稽核才改的。", "agent 沒有真正的隔離環境（另一個系統使用者／容器今晚做不到）；工作目錄不可列舉擋不住 `find` 家目錄；每批跑完用獨立稽核者 leak4b.py 的口徑（掃工具輸出）檢查。", "真實頁面裡的 HTTPS 連結不在這一輪測：所有來源都由本機 HTTP 伺服器提供；出口紀錄的 HTTPS 限制照實寫。",
       "真實教材只有一個領域（足球員條目的資訊框）；冷門條目降低靠記憶作答的可能，但不排除；評分只對照頁面當時的值。",
       "工作目錄不可列舉不是沙箱；事後掃描越界讀取。"]


def prereg(question, materials_txt, extra_limits, analysis):
    return {"registered": ("2026-11-25，第一通模型呼叫之前 commit 並推到遠端（執行器檢查）。第四輪全部批次已看過結果、降為開發資料；"
                           "產品 v5.1 凍結（7d574c3d3）之後才請隔離的代理寫真實教材的抓取／解析程式、才抓取；教材只跑過檢查器，沒有人看逐條內容。"
                           "第五輪之後不再自動開下一輪。"),
            "question": question, "product": PRODUCT, "materials": materials_txt, "arms": ARM_TXT,
            "primary": {**PRIMARY, "analysis": analysis}, "states": STATES, "known_limits": LIM + extra_limits,
            "stop_rules": ["任一組基礎設施失敗連續 3 次：停批回報。", "04:00Z 還沒跑完：照 INCOMPLETE 規則停批、報已完成的組。"]}


Q = "在真實文件的真實修訂上（不是我們設計的教材），用紀錄只重查受影響的行（v5），對整份重查、對真實版頁面通知＋差異，漏得不多、省得夠不夠？"
AN = ("合併兩台 root 後：audit_d2.py --coverage-arm cV5；analyze_d2.py --primary-arm cV5 --d-arm d_diff_real；cycle_costs.py --primary cV5 --d-arm d_diff_real；"
      "scan_escape.py。")
out = {}
half = (nsets + 1) // 2
sets_all = [f"s{i:02d}" for i in range(1, nsets + 1)]
for name, machine, prov, sets, jobs, port in [
        ("r5real_d2_qwen9b_1003", "1003", "lms1003q9", sets_all[:half], 2, 18241),
        ("r5real_d2_qwen9b_1004", "1004", "lms1004q9", sets_all[half:], 2, 18242)]:
    out[name] = {"schema": base["schema"], "id": name, "seed": 20261173 if machine == "1003" else 20261174, "jobs": jobs,
                 "server": {"port": port}, "arms": ARMS, **COMMON,
                 "model": {"provider": prov, "model": "qwen/qwen3.5-9b", "thinking": "off (reasoning_effort none)"},
                 "agentcfg": CFG_PI, "product_version": PV,
                 "materials": {"dir": "${D2_PRIVATE}/" + rdir, "generator": REAL, "manifest_sha256": msha(rdir), "sets": sets},
                 "purpose": f"D2′ 第五輪真實教材確認批次（事前登記、確認性）：{machine} 的那一份（{sets[0]}–{sets[-1]}）；和另一台合併判定。主要臂 cV5。",
                 "prereg": prereg(Q, REAL, [f"9B 兩台：1003 {sets_all[0]}–{sets_all[half - 1]}（jobs 2）、1004 其餘（jobs 2），合併判定、分台描述。"], AN)}
out["r5real_haiku_d2"] = {"schema": hk["schema"], "id": "r5real_haiku_d2", "seed": 20261175, "jobs": 3, "server": {"port": 18243},
                          "arms": ARMS, **COMMON, "model": hk["model"], "agentcfg": CFG_CL,
                          "product_version": {**PV, "hooks": "`vacant install --agents claude --mode observe` 用 d2v5_venv"},
                          "materials": {"dir": "${D2_PRIVATE}/" + rdir, "generator": REAL, "manifest_sha256": msha(rdir), "sets": sets_all},
                          "purpose": "D2′ 第五輪真實教材 Haiku（事前登記、確認性）：同一份教材，成本用美元。主要臂 cV5。",
                          "prereg": prereg(Q + "（雲端 Claude Haiku；成本用美元，第二輪 Haiku 的定義。）", REAL,
                                           ["成本用美元是第二輪看過 Haiku 小量試跑才定的口徑。"],
                                           "audit_d2.py --coverage-arm cV5；analyze_d2.py --primary-arm cV5 --d-arm d_diff_real --cost-metric cost_usd；cycle_costs.py --metric cost_usd；scan_escape.py。")}
def desc(name, seed, port, mdir, gen, nsets_d, question, note):
    return {"schema": base["schema"], "id": name, "seed": seed, "jobs": 1, "server": {"port": port},
            "arms": ARMS, **COMMON, "dynamic_noise": True,
            "model": {"provider": "lms1003q9", "model": "qwen/qwen3.5-9b", "thinking": "off (reasoning_effort none)"},
            "agentcfg": CFG_PI, "product_version": PV,
            "materials": {"dir": "${D2_PRIVATE}/" + mdir, "generator": gen, "manifest_sha256": msha(mdir),
                          "sets": [f"s{i:02d}" for i in range(1, nsets_d + 1)]},
            "purpose": f"D2′ 第五輪對照（描述性）：{note}",
            "prereg": prereg(question, gen, ["描述性，不當確認證據。", "jobs 1，和真實教材的 1003 那份共用 1003（同時 9B 不超過 4 段）。"], "同主批次，只描述。")}


if not os.environ.get("R5_ONLY_REAL"):
    out["r5seen4b_d2_qwen9b_1003"] = desc("r5seen4b_d2_qwen9b_1003", 20261179, 18246, "heldout_v4_seed20261171",
        "ops/d2/heldout_gen4/gen_heldout4.py --seed 20261171 --sets 16（heldout-v4 新種子；取代作廢的 r5seen4）", 16,
        "扣掉守衛 bug 之後，v5.1 在第四輪那種刻意出難題、實體名含數字的結構上表現如何（描述）。", "heldout-v4 結構（名稱含數字）、新種子 16 組，v5.1。")
    out["r5h3b_d2_qwen9b_1003"] = desc("r5h3b_d2_qwen9b_1003", 20261180, 18247, "heldout_v3_seed20261178",
        "ops/d2/heldout_gen3/gen_heldout3.py --seed 20261178 --sets 16（heldout-v3 新種子）", 16,
        "扣掉守衛 bug 之後，v5.1 在第三輪那種有雜訊、實體名含數字的結構上表現如何（描述）。", "heldout-v3 結構、新種子 16 組，v5.1。")
if os.environ.get("R5_ONLY_DESC"):
    out = {k: v for k, v in out.items() if "real" not in k}
for k, v in out.items():
    (HERE / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
    print(k, v["materials"]["manifest_sha256"][:12], len(v["materials"]["sets"]))
