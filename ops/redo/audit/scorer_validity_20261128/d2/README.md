# D2′ 第四、五輪評分器雙向審查（2026-11-28）

離線重算，未呼叫模型。實際評分函式是 `score_d2` 預設模式：版本號優先、否則只取第一個數字；`--strict` 是開跑後才加入的對照（依序比對全部數字），不是這兩輪實際使用的函式。交叉檢查：r5real qwen c0 在 default 為 197/360、strict 為 190/360，repo 內已發表 score_summary 為 197/360；且 r4/r5 開跑 commit 早於 strict 旗標。

## 採用 root
- r4main_1003＋r4main_1004（兩台各一部分；逐位元檢查等同 r4_merged，採分 root 以保留 gc 來源）、r4h3seen、r4haiku
- r5real_merged（正式合併 root；逐位元檢查等同 r5real_1003b＋r5real_1004b）、r5real_haiku（正式 Haiku root；99/100 arm dirs，缺的部分不補、照實計入 population 缺口）

未採用／只作對照：
- r5real_1003／r5real_1004：第一次啟動不完整（RUN.json 與 cells 數目見 root_inventory.json）
- r5real_1003b／r5real_1004b：完整組件，但與 r5real_merged 逐位元相同；為避免重複只算 merged
- r4_merged：與 r4main_1003＋r4main_1004 逐位元相同；為保留 gc 來源，直接用兩個組件 root

## (a) 答案鍵形式
- r4: 5600 行；number+unit 3785、version 720、currency 565、percent 530。相對年齡、指數成分、註腳、年份/期間括號、尺度字、範圍、多值都是 0。
- r5: 1800 行；全部是 apps (goals) 括號多值（1800 行），答案本身沒有相對年齡、指數成分、註腳、幣別或尺度字；年份/期間在欄位標籤（1800 行），不在答案值。

## (b) 合成控制

| 輪次 | 函式 | 誤放（該不同判同） | 誤擋（該相同判不同） |
|---|---|---:|---:|
| r4 | default | 27/37 | 2/18 |
| r4 | strict | 19/37 | 4/18 |
| r5 | default | 27/34 | 2/16 |
| r5 | strict | 19/34 | 3/16 |

## (c) 人工抽樣

| 輪次 | 抽樣方向 | 誤判 | 單尾 95% 上界 |
|---|---|---:|---:|
| r4 | 判對 | 0/40 (0.0%) | 7.22% |
| r4 | 判錯 | 0/40 (0.0%) | 7.22% |
| r5 | 判對 | 0/40 (0.0%) | 7.22% |
| r5 | 判錯 | 0/40 (0.0%) | 7.22% |

gc 補不回頁面的組另列（只在 r4）：rows 2100，狀態 {'correct': 1970, 'missing': 71, 'stale': 51, 'wrong': 8}，高置信誤放 0、誤擋 0；人工抽樣中此類行數見 manual_check.json。

r4 dynamic_noise 形式普查：來源模板 FETCH_TS/COUNT/ID 暴露細項在 answer_key_styles.json；report 有值行中沒有 ISO 時間戳、12 位 hex 或 fetch/count 字樣，形狀異常 9/36554 行（多為額外數字成分／鄰欄冒號；細項在 dynamic_noise_value_scan.json）。

高置信全母體數字成分篩（補充人工抽樣，不是人工核的替代；抽樣 0/40 與全母體仍有少量誤放並不矛盾，因單尾上界為 7.22%）：
- r4: 誤放 4/35044（0.01%；分類 {'extra_numeric_component': 4}），誤擋 0。
- r5: 誤放 180/9314（1.93%；分類 {'mismatched_numeric_component': 12, 'missing_numeric_component': 168}），誤擋 0。

## (d) 誤判率 >5% 的欄位

- r4: 0 個欄位（見 `field_error_rates.json`；這是高置信數字成分機械篩，會低估單位/文字層問題）。
- r5: 24 個欄位（見 `field_error_rates.json`；這是高置信數字成分機械篩，會低估單位/文字層問題）。

輸出檔：`answer_key_styles.json`（a）、`synthetic_controls.json`（b）、`manual_samples_public_keys.json` 與 `manual_check.json`（c）、`field_error_rates.json`（d）、`population_summary.json`、`dynamic_noise_value_scan.json`、`root_inventory.json`。含值抽樣只在私有目錄；此目錄與 JSON 不含實驗值。
