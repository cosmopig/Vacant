# G3 三臂名實相符修復——交接與待決事項（fix/g3-arms-actually-do-what-they-say）

> 2026-11-11。來源：11/11 日報 P0（「G3 三臂沒有實作成宣稱的三種系統」）。
> 本分支在 origin/auto/qwen27b@506ab8545（r1418）之上修復；未動任何凍結
> manifest、未加寬任何預算、未刪任何守衛。**在「待決事項」有人類裁決之前，
> G3 不得 --fire。**

## 一、修了什麼（全部有測試背書）

1. **full_rloop 真的接上重算與局部修復**（`vacant_network/reqloop/g3.py`）：
   - 每輪草稿落盤為 `answer.txt`（`out_root/cells/<task>__<arm>/round_N/`，保留供審計），
     用 **`checks.run_requirement_checks` 程式重算**（非模型自評）。
   - 缺口判據＝「必需條目 FAIL」或「必要答案項缺失」；第 2 輪只在缺口時花
     （成本紀律不變）。UNKNOWN 不是缺口也不是通過（I-4），`final_verdict`
     如實記 `UNKNOWN`，不假 PASS。
   - localized 反饋（`build_repair_feedback`）：逐條狀態＋FAIL 可見反例＋
     已 PASS 條目必須保持＋上一稿原文；檢查器反例依設計**不含重算期望值**
     （`expected_in_evidence=False`），修復模型不被直接餵答案。
   - 修後**重驗所有必需條目**（reverify_all），差異用 `repair.diff_results`
     記帳（FAIL→PASS／任何退步一律入帳）。
   - 順帶修掉一個結構性假缺口：`required_answer_names` 以前把契約範本的
     `@name[value]` placeholder 也算成必要答案項——四題 dab 契約全中，「缺項」
     對真實答案恆真。現優先取「expects N item(s):」列舉項。
2. **臂 conformance 門**（`arm_conformance`／`ARM_WIRED`／`ARM_REQUIRED`）：
   預註冊要求（manifest.arm_defs）與實作接線逐臂核對，不符即拒發
   （RC 3＝RC_APPROVED_NOT_WIRED 語義、0 模型呼叫）。**核准過了也不發。**
   `--fire` 門序＝完整性（凍結/預算）→ 核准 → 臂 conformance。
3. **抓假測試**（`tests/test_reqloop_g3_conformance.py`，新增＋已釘 pin）：
   - 「格式完整但數字錯誤」的草稿（`@n_rows[999]`，重算值 7）必須被抓成
     FAIL、第 2 輪反饋帶逐條反例、修正後重驗 PASS、diff 記 FAIL→PASS——
     **這個案子在舊管線下會被放行**（只有答案項存在性檢查，抓不到內容錯誤）。
   - reqlist_only 不得免費獲得同一能力（1 輪、無重算反饋段落）——臂間
     差異才能歸因於 R-loop 本身。
   - native_pi 拒發負控制；ARM_REQUIRED 不可被清空。
4. **既有測試更新至新語義**（`tests/test_reqloop_g3.py`）：凍結三臂計畫現在
   拒發（正確行為）；兩臂皆接線的計畫 8 格跑通；成本/額度數字隨之更新。
5. **解凍記錄**（`tests/test_reqloop_freeze_check.py`）：GUARD_CONTENT_PIN 依
   「合法修改須顯式更新錨並留記錄」紀律更新（兩檔換新 pin、conformance
   測試檔新增 pin；記錄見 pin 區 r1419 條目）。

## 二、待決事項（需要人類，agent 不得自改）

凍結 manifest 內部矛盾：arm_defs 承諾「原生 pi」，預算卻凍結
`model_entry='glm'`（glm CLI 單回合、無工具——接不了 pi_build/run_agent 的
工具迴圈）。現在三臂計畫 `--fire`/`--dry-run` 都會被 conformance 門以
native_pi：pi_agent 未接線為由拒絕。二選一：

1. **接線**：為 native_pi 建 PiChannel（pi_build/run_agent 工具迴圈），並由
   人類放寬凍結預算的 `model_entry`（這是預註冊變更，須重新核准）。
2. **改名**：由人類修預註冊，把該臂改名為它實際上是什麼（例如
   `selfcheck_prompt`：glm 單回合提示式自檢），同步 manifest.arm_defs＋
   `ARM_ORDER`/`ARM_SPECS`/`ARM_WIRED`/`ARM_REQUIRED`，舊核准作廢、重新核准。

在裁決之前：三臂計畫不可發射；如果只想先拿方向性數據，用兩臂（reqlist_only
＋full_rloop）跑也必須先過人類核准（核准文件 epic 已釘 vq-1zf）。

## 三、驗證記錄（2026-11-11，本機 macOS，repo venv）

- `tests/test_reqloop_g3.py`：19 passed。
- `tests/test_reqloop_g3_conformance.py`: 9 passed（含抓假正控）。
- `tests/test_reqloop_g3gate.py`＋g2/extract/g1_gate 相鄰族：全綠。
- `tests/test_reqloop_freeze_check.py`：與乾淨 HEAD 基線完全一致——本機環境
  既有紅 4 項（queue_empty ×2＝macOS/Python repr 截斷；ci_contract＝本 venv
  未 `pip install -e .[dev]`；diff_worker/diff_argon＝auto/* 分支已前進後的
  跨分支 diff），**本分支零新增失敗**，guard_content_pin 在 pin 更新後全綠。
  在 loop 機器上重跑時請以該機 12 項 freeze 為準。

## 四、給 loop agent 的規則（順序即優先級）

1. G3 在上面的待決事項裁決前不得發射；conformance 門是特性不是故障，
   **不要為了讓 fire 跑起來而改 ARM_REQUIRED 或 ARM_WIRED**——那正是
   H-0「同名換內容」型假綠燈的入口。
2. 每加一個臂，必須同一輪交付：(a) 接線；(b) ARM_WIRED 如實更新；
   (c) 一個「格式完整但內容錯誤」的抓假測試（抓得到才算接線）。
   宣稱（ARM_SPECS 旗標）沒有接線與測試支撐＝conformance 紅，先紅後綠。
3. 簿記輪次請記 no-op 並設上限；分支同步/狀態鏡像不計入交付。
