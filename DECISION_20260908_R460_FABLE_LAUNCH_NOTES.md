# R460 發射紀錄（Fable）：六塊拓撲、量具範圍、seed 重用檢查的裁決與追認——全部在 b 組資料之前、a 組資料之外

（2026-09-08 05:05Z。本檔記錄 R460 從預註冊到六塊全部在跑之間的每一個裁決，供收官時 E-4／E-7 對帳。零 API。）

## 一、發射前後的裁決時間線

| 時刻（UTC） | 事 | 裁決 |
|---|---|---|
| 09-07 | 冒煙掛死 4 小時：socket 逾時綁不住牆鐘（`recv_into` 每圈重設 deadline） | 加牆鐘護欄（timeout+60）於 `chat()`（460d）與 `generate()`（460e，A3）；`generate()` 的 sha 釘死更新，分類 (a) |
| 09-07 | 冒煙量到單通 160–560 s、單題 13k token；序列兩塊要 >2 天 | **A1 六塊**（每台三塊、每塊 20 題），request timeout 1200；P-H0 錨不變（前 60 題＝1003 那三塊的聯集） |
| 09-07 | V/GT 稽核把模型自寫 SELFTEST 的 True/False 判成洩漏 | **A2** 瑣碎字面值凍結集＋最短 6 字元；負控測試保留真洩漏必紅 |
| 09-08 04:0x | 第一次發射死在發射器 curl 探針（max_tokens 16 被推理吃光） | 460e-2：探針 512，判準不放寬；零 run 目錄、零呼叫 |
| 09-08 04:1x | 重發：a1–a3 起來；b1 量具 0/0 停（後 60 題只有 2 題有參考解，任何三等分必有一塊 0） | **不縮塊、不放寬**：加 `--gauge-scope bank`（對整個題庫 12 題驗兩方向，預設 slice 不變），b 組用 bank；a 組不殺（量具不進臂路徑）。b1 殘留目錄由 Fable 清 |
| 09-08 04:5x | 補發 b 組被 `abort_seed_reuse_set_mismatch` 擋（a 組已寫入同 seed 的 summary） | Opus 改成扣掉本 run 自己六個授權塊名；**Fable 追認**：這是分批發射拓撲的機械後果，唯一解，牙齒經實跑驗證（外來 run／r447 消失仍 MISMATCH） |

## 二、收官時要對帳的事實

- runner sha：a1–a3 ＝ `70ab06b`、b1–b3 ＝ `d3e79c7`。兩版之間 `harness_arms.py`／`brain_cline.py`／`vacant/checks.py`／`vacant/codebench.py` **零差異**（本輪 `git diff --stat` 空）；`gain_run.py` 差異只有 `--gauge-scope` 與其覆蓋檢查（不進臂路徑）。E-4 分類 (a)。
- 量具模式：a 組 slice（3/3、3/3、4/4，證據在各自 `launch.log`；`summary.json` 無 `gauge_scope` 鍵，讀作 slice，不准事後補寫）；b 組 bank（12/12、12/12、覆蓋 20/20）。
- 端點：`calls.jsonl` 的 `api` 逐筆核，a 組 100% `100.119.113.56:1234`、b 組 100% `100.86.226.21:1234`，無 hub。
- 05:03Z 六塊 rows 合計 40/720、失敗呼叫 0、log 零 traceback；約 91 s/call，估 7–8 小時收官（預註冊 §十 的 ≈4 h 是短請求外推，§八-13 已保留）。
- 吞吐驗證：a 組單獨三併發 86 s/call，加上 b 組後 91 s/call ⇒ 兩台各跑各的。

## 三、不變的東西

門檻、家族、區間、分母、四狀態、P-H0..P-H9 的窗——**一個字沒動**。動的全是程序（拓撲、量具範圍、探針、發射器檢查），且每一項都在對應塊產生任何一列資料之前。

## 四、補記（2026-09-08 07:38Z–08:20Z）：1003 當機、a 組全 void、重發

- **05:11Z** 1003 的 LM Studio 引擎在三塊同時長生成時回 `Engine protocol predict stream returned an error: {"code":500,"message":"decode() failed: bad alloc"}`，
  之後模型被卸載（`No models loaded`）。a1／a2／a3 重試用盡，剩餘格子全判 `infra_void`（100／98／84），runner 自行 terminal。
  b 組（1004）全程正常（07:38Z 57／99／74 列，void 0）。
- 根因：`lms ps` 顯示 1003 載入的 context length 是 **262,144**、並行槽 4；三個長生成同時把 KV cache 撐到這個上限 ⇒ 記憶體不足。
  1004 的載入設定不同，未撞到。
- 處置（Fable，遠端）：a 組三個目錄與 launch.log／backend.json 移到 `runs/_aborted/g_r460_harness_lcb2_a{1,2,3}_void_20260908T0511Z`
  留證，不進任何分析；用 `lms load gemma-4-12b-it-qat --context-length 49152`（實測最長 completion 33,974 token 仍裝得下）重載；
  `BLOCKS=a1,a2,a3` 重發，**拓撲不變**（仍三塊、仍直連 1003），量具 slice 3/3、3/3、4/4；08:2xZ 六個行程全活，runner sha 六塊一致 `d3e79c7`。
- 對收官的影響：a 組的 P-H0 錨與 persona 對齊敘述不變（同 seed 同 offset）；a 組發射時間晚 b 組約 3.5 小時，兩台後端設定不同
  （context 49k vs 1004 的原設定）——**這是題目層的干擾，不進臂比較**，但 §六-(0) 的「兩塊點估計不得互比」再加一個理由。
- 中止準則 §十 的 void 門檻是對**進入分析的資料**算的；被移走的 void 資料不進分析，重發的 a 組從零計。
