# R680 判準：併庫 r444 + r445 → 371 題，在**科學上**合不合法？

寫於 2026-09-03 23:2x UTC，**在任何比對之前**。round680，Opus 5。

## 零、為什麼現在問

round675 造了 `pooled_paired_ci.py`，round678 用它做投影，round677 的 `r445_predcheck.py`
的 P-E2／P-E3 直接轉述它的輸出。三輪都驗了**算術**（加法恆等式、key 有牙齒、
兩型安靜量不到），**沒有一輪驗過前提**：r444 與 r445 是不是同一個實驗。

`grep -c "併庫前提\|poolab\|pool_precheck" ~/vacant/GAIN_STATE.md` → **0**。

若兩個 run 的**處置定義**（arm 的碼、模型、判準 prompt）不同，
併庫算出來的 CI 是「兩種不同處置的混合」，數字會照印、擋門會全綠——
這是典型的**安靜量錯東西**，而收官文字會把它當成 CONFORM 的區間引用。

## 一、我寫這份判準時已經看過／還沒看過什麼（污染揭露）

**已看過**：`ls runs/`、`ls ops/gain/ ops/gain/replay/`；r445 的 ps 命令列
（`--n 192 --offset 179 --seed g-r212-route-20260828 --arms OFF,CONFORM,OFF5
--bank evalplus --models gemma-4-12b-it-qat --request-timeout-s 600
--review-timeout-s 380 --probe-sample 0`）；GAIN_STATE round677/678/679
（r444＝179 題、n_d=13、b=9 c=4、p=0.2668；r445 中途 rows=175）。

**還沒看過**：`runs/g_r444_conform_mbpp/summary.json` 的任何設定欄位、
r445 `summary.json` 的任何設定欄位、兩者的 task_id 清單、
兩個 run 之間 `ops/gain/` 的任何 git diff。以下規則在看到那些之前寫死。

## 二、判定規則（事前）

| 編號 | 問題 | HIT（可併） | MISS（不可併／要揭露） | BROKEN |
|---|---|---|---|---|
| **Q1** | 題目不重疊 | r444 與 r445 的 task_id 集合交集＝∅ **且** 聯集大小＝371 | 交集≠∅（同一題被算兩次＝McNemar 配對重複）或聯集≠371 | 任一 run 讀不出 task_id |
| **Q2** | 處置定義相同 | 兩 run 各自「跑的時候的 commit」之間，**影響臂行為的檔**逐位元相同 | 有差異 ⇒ 逐一分類 (a) 只影響分析／文件 (b) 影響臂行為。**任一 (b) ⇒ 併庫是混合處置** | 兩個 run 都沒有記錄自己跑在哪個 commit ⇒ 這件事**在本設計裡無法驗證**，本身就是發現 |
| **Q3** | 執行參數相同 | models／arms／seed／bank／probe-sample 逐字相同 | 任一不同 ⇒ 列出來並判斷是否影響處置 | summary.json 沒有記這些欄位 |
| **Q4** | timeout 差異的後果 | r444 與 r445 的 `--request-timeout-s`／`--review-timeout-s` 若不同，唯一可觀測後果是 void 率；兩 run 的 infra_void 率差 <5pp ⇒ 視為無後果 | 差 ≥5pp ⇒ 揭露 | void 欄位讀不出 |

**Q2 的「影響臂行為的檔」清單（事前寫死，避免事後挑）**：
`ops/gain/gain_run.py`、`ops/gain/brain_cline.py`、`ops/gain/codebench.py`
（若存在）、`ops/gain/` 下任何被 `gain_run.py` import 的模組。
**不算**在內：`ops/gain/replay/**`（收官分析用，run 跑的時候不 import）、
`ops/gain/analyze_*.py`、`*.md`、`launch_*.sh`、`test_*.py`。
判定方式**不是**看 commit message，是 `git diff <r444的commit> <r445的commit> -- <清單>`。

## 三、事前推翻條件（觸發就照實寫，不當場補判準）

- **T1**：若 r444 與 r445 的 `--models` 不同 ⇒ 併庫直接無效，收官**不准**引用 371 題的 CI，
  只能分開報 179 與 192。
- **T2**：若 Q2 的 diff 碰到 `arm_conform`／`arm_off5`／評審 prompt 任一 ⇒ 併庫是混合處置，
  收官文字必須寫明「371 題的 CI 混了兩種 CONFORM 實作」。
- **T3（防我自己過度宣稱）**：即使 Q1–Q4 全 HIT，**也不代表兩批題目難度相同**。
  McNemar 是**題內配對**，不要求跨題同難度 ⇒ 難度異質**不是**併庫的障礙。
  本輪不准把「Q1–Q4 全 HIT」寫成「兩批題目等價」。
- **T4**：若 Q2 判為 BROKEN（沒有記錄 commit），**不准**用 mtime／git log 時間戳去猜
  然後當成量測——那是推論。可以做，但必須標成「推論」，且要另外指出
  「run 不記錄自己的碼版本」是一個該修的設計缺口。

## 四、自我約束（事前）

- **新增可調參數 0**。門檻只有 Q1 的 371／Q4 的 5pp，兩個都寫在本檔，工具裡要能指回本檔。
- **唯讀**：不 `git add`／不 stash／不 checkout／不殺 r445；比對前後驗 r445 rows sha256 前 8 碼相同。
- 不改 `pooled_paired_ci.py`／`conform_settle.py`／`r445_predcheck.py` 的既有輸出。
- 若造工具，**必須含植入缺陷測試**，且判準不准只寫 `rc≠0`：每條要指名偵測器該看到的那個量。
  含兩型「安靜量不到」：欄位不見了、比對集合變空。
- 造了工具就要**接進收官路徑**（寫進 GAIN_STATE 的收官指令清單），否則等於沒有牙齒。
