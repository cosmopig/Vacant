# DECISION 2026-11-27 — Haiku 帶內題池搜尋（25–70%）：預註冊

執行者：雲端接手代理。授權：擁有者方向指示（校準便宜、可多做；選題規則在看資料前寫死；若落在 25–70% 則跑**一個**四臂批次；總花費上限 $30，校準含在內；不在天花板池跑正式批次）。
本檔不修改主設計檔 `DECISION_20261127_EVIDENCE_CONTROLLER.md`；控制器門檻與規則表不動。每個候選的建置與選題規則在該候選的資料之前寫入並推送。
花費：以 Claude CLI JSON 的 `total_cost_usd` 加總，記在 `ops/redo/results/ctl_haikuband_20261127/SPEND.jsonl`。

## 候選 1：cchard-L（同 39 題 cchard ＋ 大／最壞測資）— 建置規則（凍結，在任何 cchard-L 的 Haiku 資料之前）

來源：與 cchard 相同的 valid＋test parquet（sha256 同 cchard manifest）、同一批題（`bank_cchard_MANIFEST.json` 的 39 題）。
**聲明：這些題 Haiku 在 cchard 校準時已經做過一次（35/39）；cchard-L 是新題池（新目錄 `/opt/ctlwork/bm_tasks/cchardL`、新 manifest），不是重新評分。**

1. 對每題，原本的 60 案（30 可見＋30 hidden，同 cchard 的種子切分）原樣保留。
2. 大測資生成器：每題由 `claude -p --model haiku`（單次呼叫、不給工具、輸入＝題目描述＋一筆範例輸入；要求輸出一支 Python3 腳本 `gen.py`，
   用法 `python3 gen.py SEED KIND`，KIND∈{max, mid, edge}，依題目限制寫到標準輸出一筆輸入：max＝各參數取上限的隨機輸入、mid＝約上限的 1/10、
   edge＝極端但小的邊界）。生成器提示語不含責任／懲罰措辭（KS-1）。生成器寫壞（執行錯誤或空輸出）時重問一次，仍壞則該題不加大測資。
   提示語、原始回覆、費用全部落盤 JSONL。
3. 每題產 12 筆候選：max×6（seed 1–6）、mid×3（seed 1–3）、edge×3（seed 1–3）。
4. 答案來源：該題資料庫裡的 C++ 正解（至多前 12 份，沿用 `build_cchard.validate` 的挑選與通過判準：通過原 60 案、每案 ≤0.5×限時）。
   一筆候選保留的條件：**≥2 份正解都以退出碼 0 執行、輸出逐 token 一致，且每份牆鐘 ≤0.5×限時（限時＝2×原限時＋2 秒，同 cchard）**；
   答案取一致的輸出。輸入 ≤1 MB、輸出 ≤1 MB。不一致或任一份逾時／當掉＝丟棄。（生成器違反題目限制時，兩份正解可能一致地吞下無效輸入——這是已知殘餘風險，輸入合法性**沒有**獨立檢查。）
5. 保留的大測資洗牌（種子 `20261127:<題名>:L`）後對半分入可見／hidden（同切分規則：前半可見、後半 hidden）。每題至多 12 筆。
6. 題收錄條件：至少 4 筆保留的大測資，且可見與 hidden 各 ≥2 筆；參考解（兩半都過）＋空殼（兩半都不過）寫出後再驗（同 cchard 的 `real_check`）。不符者排除並列出。
7. 輸出：`ops/redo/banks/build_cchardL.py`（建置器）；manifest 與資料集的 sha256 在 `ops/redo/results/ctl_haikuband_20261127/`，資料集本身不進 repo。
8. 校準：Haiku A×1／題、jobs=4（CPU 與別的批次共用，保守）、600 s 嘗試、1800 s 預算、hidden 獨立評分，**計時敏感的評分以序列重評為正式**。落在 25–70% ⇒ 進選題；其餘 ⇒ 轉候選 2。
   帶內判準以 hidden 通過率（通過＝hidden 全過）為準。

### 候選 1 建置紀錄（Haiku 校準資料之前寫入）
- 39 份生成器各一次呼叫成功（39/39 第一次就過 edge／max 各一筆的執行檢查；總費用見 `SPEND.jsonl`，約 $0.07）。生成器寫者與受測 worker 同為 Haiku 家族（`claude-haiku-5-5`）；已知偏誤，生成器只決定輸入不決定答案。
- 建置結果：37 題收錄、2 題排除（cc_1567F、cc_1599D：保留的大測資只有 3 筆 <4）；37/37 參考解兩半皆過、空殼兩半皆不過。manifest sha256 `8490ffbf…99c6`（`ops/redo/results/ctl_haikuband_20261127/cchardL/bank_cchardL_MANIFEST.json`）。
- 校準計畫 `ops/redo/plans/ctlcal_haiku_cchardL_A.json`（37 題、A×1、jobs 4）。沙箱沒有改動（cchard 時已含 g++／python 正控制 25/25），這一輪**沒有**重跑負控制。
