# NOW.md（r1236 redo，2026-11-08 05:0x UTC）

## 主線
G2.5（vq-el4）18/18 完結；主線推進到 **G3（vq-1zf）**。r1236 交付 **G3 發射前置門**（離線、0 模型呼叫）：
選題＋凍結＋預算＋核准四門可一條指令驗，發射仍待人類核准（核准前禁止、0 呼叫）。

## 本輪成果（r1236＋redo）
- **一條指令**：`python3 -m vacant_network.reqloop.g3gate --plan` → **RC 0**（12 格、NOT FIRED、0 model calls）；`--fire` 無核准 → **RC 2**（fail-closed、0 呼叫）。
- 選題＝未見任務：DABench 30 − 已見 9 dab_ 前 4 ＝ **dab_129/144/176/216**（`unseen_selection` 代碼重算核預註冊；非寫死）；輸入凍結副本 `ops/reqloop/g3_gate/tasks/`（16 檔 sha256，verify_frozen 抓篡改/缺檔）；e008 先驗數據披露在案。
- 門內寫死：≤12 格／300s 每輪／日 ≤2M tok 撞額停不重試／glm 唯一入口／無硬 token 上限、缺值 UNKNOWN；核准門＝人類核准文件（approved/epic/by）fail-closed。
- 驗證：g3gate 15 測試全綠；reqloop 回歸 **607 passed 1 skipped**；commit **88697cd6**；vq-1zf.1 close（證據＝commit＋`--plan` 末行 G3GATE PLAN OK）。
- **redo（審查點名 repair.py 原未開）**：補開＋接地——2795 行、blob 5147f8c3（＝r1227 錨點）、git 乾淨＝未動；已讀頭部＋結構＝G2 **localized 修復**切片（FEEDBACK_MODES、build_repair_prompt localized、repair_slice、權威快照/source_tampered 退出碼 20、成本缺值 UNKNOWN、min_rounds localized=0）；本輪 4 處依賴陳述逐項如實、**無需改數**，交付物不變。

## 邊界與紅線
- **G3 未發射**：核准待人類定案（/srv/vlab/queue 空）；核准後發射＝另一步授權（三臂逐格＋/srv/vlab scorer）。
- 不讀 /srv/eval hidden 與 scorer.py；hidden_after 全 UNKNOWN；cost_usd=0 不報 0 成本。
- repair.py 凍結 2795 行（blob 5147f8c3，本輪已開核）；extract.py 邊界 e757aec5；checks.py f3525b01；本輪 0 模型呼叫。
- G2.5 維持：三門 PASS（G1 39/39、REAL14 9/9、PHASE3 fixed7/rtw0）＋備案 g25_all_gates_filing.json。

## 下一步
等 G3 人類核准→發射（另步授權）；巡 88697cd6 CI；無其他可動工單（vq-el4 18/18、open 0）。
