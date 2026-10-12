<!-- 狀態：**凍結**（agent 在發射之前 commit）。發射之後不准再改；要改＝另一份預註冊。 -->

# 預註冊：Colab 兩批（任務導向 94 題、DABstep 77 題）在 vacant-dev＋1003／1004（LM Studio GGUF）上的複製

依據：人類 2026-10-02「把這些東西都丟去 vm 上測試，用 1003 1004 去跑，可以跑很久沒關係，儘速丟上去」「先以任務導向的那些」；
`PREREG_20261002_COLAB_TASK3_V37.md`、`PREREG_20261002_COLAB_DABSTEP_V37.md` 與兩份結論。

## 一、為什麼

1. 同一套題目與產品，換到人類自己的兩台 GPU（`gemma-4-12B-it-qat-q4_0-gguf`＋LM Studio，就是 09-26 本機批次的那個後端）再量一次：
   Colab 的 DABstep 差「大半來自沒裝那組在 vLLM 下更常說做完卻沒寫檔」——**換回 GGUF 之後這個差還在不在**，直接回答它。
2. 任務導向那批時間有限（每格 1200 秒、2 次）；這裡每格 1800 秒、3 次。

## 二、兩批（同一台執行端、依序跑）

| 前綴 | 題 | 組 | 回合上限 | 每格時限 | 次數 |
|---|---|---|---|---|---|
| `t3L`（先） | 任務導向 94 題（同 `PREREG_20261002_COLAB_TASK3_V37.md`） | A／C37 | 無 | 1800 秒 | 3 |
| `d37L`（後） | DABstep 79 題（同 `PREREG_20261002_COLAB_DABSTEP_V37.md`） | A／C37／C37R | 15（Harbor `max-turns.ts` 逐字） | 1800 秒 | 3 |

- 題目、提示、計分器、Vacant wheel（PR #82 `e4da5ebc` 的 `vacant_network/`，114 檔比對）、cell.sh 同 Colab 兩批；cell.sh 只多一行：`UP=auto` ⇒ 依題目路徑的 cksum 固定分到 1003 或 1004（同一題的各組、各次都在同一台）。
- 執行端：vacant-dev（Ubuntu 24.04、8 核、7 GB），每格新 Linux 使用者＋bwrap；同時 8 格（每台約 4 條，LM Studio 吞吐上限）。
- 模型：1003（`100.119.113.56:1234`）、1004（`100.86.226.21:1234`）上的 `gemma-4-12b-it-qat`（GGUF、LM Studio），記帳代理強制關思考。
- 不設停開新題的時限，跑完為止（人類：可以跑很久）。void、補跑、意向治療同前兩份。
- 磁碟只有約 4 GB：每格打包進 chunk 之後，VM 上只留 DONE／meta／score／vacant_check；完整內容在 chunk（同步到 Mac、sha256 驗過）。

## 三、分析（各批用自己那份凍結的分析程式）

- `t3L`：`ops/colab_task3_v37_20261002/analyze_task3.py`；主要檢定 C37 − A（Wilcoxon，同函式）。
- `d37L`：`ops/colab_dabstep_v37_20261002/analyze_dabstep.py`；主要 C37 − A，次要（Holm）C37R − A、C37R − C37。
- 兩批各自只有一個主要檢定；兩批之間、與 Colab 兩批之間的比較只描述。
- 描述另外要報：A 組「說做完卻沒寫要求的檔」的格數（Colab DABstep 42／231、Colab 任務導向 5／120），以及兩台機器分開列。

## 四、事先寫死的說法

- 照前兩份預註冊各自的第七／四節。另外：若 d37L 的 C37 − A **不顯著**，就說「在 GGUF 後端沒有複製出 Colab 的差」，並同時報 A 組「說做完沒寫檔」的格數。
- 不外推到互動介面（仍是 `pi --print`）。

## 授權

人類 2026-10-02 對話原話（見依據）。agent 凍結、人類沒有逐條簽字。
