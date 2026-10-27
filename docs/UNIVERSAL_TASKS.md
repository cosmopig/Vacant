# 通用任務（非程式）：現有檢查的分類與新檢查規則

> 對應 ASSIGNMENT 方向 A（「通用任務：程式以外也有用」）與 BACKLOG P1 第 1 項。
> 本頁只整理**現有的**證據檢查（`vacant_network/trace/evidence.py`），並定下新檢查的合併門檻。
> 沒有這裡沒寫的保證；每一行都可以用對應的測試離線重播。

## 1. 現有發現（finding）分類

`run()`（`evidence.py`）目前會產生 **12 種 kind**（2026-10-25 對照原始碼盤點、2026-10-26 加
`claimed_run`：
`missing_output`、`invalid_output`、`failed_step`、`test_claim`、`unsourced`、`unread`、
`copy_of_task`、`skeleton`、`stale_output`、`copy_of_input`、`copy_of_inline`、`claimed_run`；
前 6 種可退回給 agent，後 6 種被 `zerostop.pushable_for` 明確排除、只進交件說明）。
下表按 kind＋sub 逐行分類。判定「域相關」的標準：
**檢查邏輯本身是否依賴「有程式碼可跑／可解析」這個前提**，而不是「樣本裡恰好有程式」。

| kind（sub） | 域無關？ | 依賴什麼 | 對非程式交付物的誤報風險 |
|---|---|---|---|
| `missing_output` | **是** | 只問「要求的檔存不存在」（`asked_outputs`） | 低：檔在就不報；對任何檔案型別都成立 |
| `invalid_output/empty` | **是** | `new.strip()` 為空 | 低：只報空檔 |
| `invalid_output/syntax` | **否** | `.py` 要 `ast.parse`、`.json/.jsonl/.toml` 要解析、Markdown 圍欄/衝突標記 | 對 `.md/.txt` 只剩「以 ``` 開頭」「衝突標記」兩條，兩者都是明確的垃圾訊號，誤報低；但整體是程式格式前提 |
| `invalid_output/stub` | **否** | `NotImplementedError`/`todo!()`/Traceback 寫進答案/未展開的 Python repr | 程式碼 stub 判定域綁定；「Traceback 寫進答案檔」對非程式交付物是合理訊號，但目前綁在 `.py`/DOC_EXT 上 |
| `invalid_output/contract_shape` | 部分 | JSON 契約形狀（`at`/函數簽名） | 只在任務寫了明確契約時觸發；非程式任務一般不適用 |
| `invalid_output/empty_filter` | 部分 | 資料分析：單一腳本且沒有驗證，最後計算結果是空的（空 dataframe/series，或單行 N/A/0/[] 答案） | 綁定「有 pandas/表格資料」這一類非程式任務，但不是全域 |
| `failed_step` | **否** | 有 shell 指令跑過且失敗、交付檔寫在它後面 | 非程式任務通常沒有指令；若有（如 `pandoc`），邏輯仍成立，但判定詞彙（Traceback/Error）偏程式 |
| `test_claim` | **否** | 最後訊息宣稱測試/建置通過，要對上 RUNNERS 的輸出 | 純程式：非程式任務不該有「測試」宣稱，觸發即合理 |
| `unsourced` | **是** | 寫入行的**數值與日期**要在「讀過／跑過」的語料裡找得到（`corpus`） | 這是通用檢查：報告、單一答案、表格都適用；誤報靠 exempt 規則（給定的、今天/昨天、任務裡寫明的日期、假設標記）壓低 |
| `unread` | **是** | 點名檔有沒有被讀 | 域無關；誤報低（讀過就不報） |
| `copy_of_task`（2026-10-06 新增，**僅建議**） | **是** | 要求的交付檔內容 ≈ 任務提示詞原文（`_collapse` 正規化後包含、比例 ≥ 0.8、提示詞 ≥ 60 字元） | 只抓「把題目當答案交出去」；照抄**引用內容**（不含指示句）的轉述任務不觸發。見 §3 |
| `skeleton`（2026-09-25 新增，**僅建議**） | **是** | 交付檔半數以上是佔位行（TBD／TODO／待填／___／{{…}}） | 低：佔位行是明確的未完成訊號；「待填」只算整行佔位，正文裡提到不算 |
| `stale_output`（2026-09-25 新增，**僅建議**） | **是** | 檔在本回合前就存在、本回合一字未改，最終訊息卻用了產出型動詞（已寫好／已寫入） | 低：「已確認／Done」這類非產出型結語不觸發（n12 樣本） |
| `copy_of_input`（2026-09-25 新增，**僅建議**） | **是** | 交付檔與任務點名的輸入素材逐字相同（正規化後全等、≥ 80 字） | 低：複製型任務（「把 X 複製為 Y」）直接豁免（COPY_CUE）；短答案不比 |
| `copy_of_inline`（2026-10-25 新增，**僅建議**） | **是** | 交付檔（正規化後）是 prompt 的逐字子串（≥ 120 字）、且題目要求改寫（整理／摘要／分析／重排…） | 抄錄任務（「原樣寫入」，VERBATIM_CUE）、複製任務（COPY_CUE）、抽出型任務（「抽出／摘出／extract…某段寫入」，EXTRACT_CUE，2026-10-25 n17）、**清單型輸出**（題目點名編號／清單／列表／列點輸出、交件本身就是清單區塊——逐字寫出該清單正是預期交件，reformat 是 no-op；`LIST_REQ_CUE`＋`_is_list_block`，2026-10-26 清單負對照）豁免；短答案（< 120 字）不報；交件＝整段 prompt 由 `copy_of_task` 報（比例 1.0），不重複。**多文件切分（內聯文字被切成 ≥2 份、每份 < 120 字）是已知漏**（§2.4，2026-10-28 已註冊 L-fake＋負對照）；跨 prompt 拼接（內聯文字分貼在 ≥2 回合）**round 45 起已抓**（跨輪拼接語料，advisory；§2.5，含 round 55 早期回合線索的兩對語義 pin）。見 §3 例子；120 的敏感性實測見 `tests/test_inline_copy_min_sensitivity.py`（2026-10-27） |
| `claimed_run`（2026-10-26 新增，**僅建議**） | **是** | 最終訊息以**過去式**（ran／executed／跑了／跑過／跑完／執行過／執行完／執行（`執行緒`除外））宣稱「執行」某條反引號命令、首詞在已知 CLI 白名單（`RUN_CLAIM_TOOLS`）、鄰窗無建議措辭，但整份 session 命令記錄（含前回合、sub-agent）查無 | 低：三層保守濾網（過去式線索＋CLI 白名單＋建議豁免）；記錄裡跑過就算（子串比對，`pip`→`pip3`、參數不同、跨回合都算跑過）；非 CLI 的反引號詞、路徑 span（`./scripts/…`）、`執行緒`名詞都不觸發。專屬樣本 `tests/test_universal_claimed_run.py`（12 個：3 抓＋5 advisory/混排 pin＋6 負對照，2026-10-27）；零誤報由常駐門 `test_all_clean_samples_have_no_false_positives`（對所有 kind）覆蓋 |

**結論：** `missing_output`、`invalid_output/empty`、`unsourced`、`unread` 對非程式任務
直接可用且可退回；`copy_of_task`、`skeleton`、`stale_output`、`copy_of_input`、`copy_of_inline`、
`claimed_run` 六種域無關但預設只進交件說明（不退回）；`syntax/stub/test_claim/failed_step/empty_filter/contract_shape`
的前提是「有程式碼/表格可跑」，對純文件任務大多不會觸發（不會擋，但也不會幫上忙）。
`claimed_run` 補上 ASSIGNMENT 點名的「跑過沒」維度（2026-10-26）：agent 說「我跑了 `pandoc`」
但記錄裡查無——對非程式任務（`pandoc`／`curl`／`pip` 一類的工具鏈）與程式任務同構，
且比 `test_claim`（只認程式的「測試通過」宣稱）更通用。

## 2. 現有檢查對非程式任務的已知盲區（誠實邊界）

1. **`unsourced` 只查「具體值」（數值與日期）**：報告裡的文字結論（「建議延後上線」）
   不在檢查範圍；這是有意的——查文字結論等於查觀點，超出紀錄可驗證的範圍。
   （2026-10-24 校正：原寫「只查數值」，但 `_values` 同時檢查 `dates_in` 抓到的日期。）
2. **`failed_step` 的失敗詞彙偏程式**（`Traceback`、`\bError:`、`Exception:`）；
   非程式指令失敗（如 `pandoc: error` 之外的寫法）可能漏判。目前**不擴充**：
   擴充詞彙＝提高對良性指令（`grep` 無匹配、`diff` 有差異）的誤報，而這類任務樣本太少，
   量不出零誤報。
3. **交付物「內容對不對」一律不判**：所有檢查只看「紀錄顯示了什麼」（缺、空、無來源、
   與提示詞重疊），不判答案正確性。這是 H-2 的同構：通過檢查 ≠ 滿足要求。
4. **`copy_of_inline` 的逐檔門檻曾漏「多文件切分」——已補上**（2026-10-28 註冊已知漏，
   BACKLOG P1 (a)；**round 83 上線 union 檢查**）：lazy agent 不改寫、只把內聯紀要
   **原樣切成兩份點名的檔**（各 <120 字）時，逐檔判定的 `copy_of_inline` 漏；兩份拼接起來
   是 prompt 的逐字連續子串（≥120 字）——這是盲點。round 83 的 union 檢查（§3 門檻全過：
   只看紀錄、領域中立、advisory-only、零誤報門過）：
   - **只查成對**（≥3 檔切分仍是註冊漏，寧漏勿誤）；成對中逐檔都 <`INLINE_COPY_MIN`
     （已報逐檔的檔不再重複報）。
   - **拼接從原文重組後再 `_collapse`**（兩種順序），要求是 prompt（或整場對話）的**逐字連續子串**
     且合計 ≥`INLINE_COPY_MIN`——非連續切分（中間夾了其它文字）不命中。
   - **同三门＋清單豁免**：改寫線索在＋無 COPY/VERBATIM/EXTRACT 豁免；成對中任一檔是清單區塊
     ＋題目點名清單輸出 → 豁免（同逐檔的 `LIST_REQ_CUE`＋`_is_list_block` 合取）。
   - 命中時成對兩檔**各報一個** `copy_of_inline` 發現；kind 不變 → `zerostop.pushable_for`
     照樣排除（advisory-only 不變，`test_lfake_multifile_split_not_pushed_back` 釘死）。
   - L-fake（抓）：`tests/test_noncode_samples.py::test_lfake_multifile_split_is_caught`
     （2026-10-28 註冊時名 `..._is_a_known_miss`、斷言零發現；round 83 按註冊時預定的更新路徑改預期集）。
   - 負對照（不抓）：`tests/test_noncode_samples.py::test_clean_multifile_split_keep_verbatim_not_caught`
     ——正當「整理後按渠道分成兩份、條目保持原文」任務（VERBATIM_CUE 豁免）；同時被常駐誤報門
     `test_all_clean_samples_have_no_false_positives` 自動覆蓋。
5. **`copy_of_inline` 的逐 prompt 語料漏「跨 prompt 拼接」——已補上**（2026-10-29 曾是盲區，
   BACKLOG P1 (b)；round 45 上線）：lazy agent 把分貼在兩個回合的內聯文字（前半 A 在 turn 1、
   後半 B 在 turn 2）**原樣拼接**交回時，`window()` 只取**最後一則**人類 prompt 當 task text，
   A 根本不在語料裡 → 不命中。與 §2.4 的根因不同：這裡每半都可 ≥120 字、門檻不是漏因，
   漏因是資料不在最後 prompt。**round 45 修復（commit a6a8331e）：`copy_of_inline` 加入跨輪拼接語料**
   （整個 session 的人類 prompt **先拼接、再 `_collapse`**），與單輪同一組三重條件（改寫線索觸發＋
   豁免線索＋≥ `INLINE_COPY_MIN` 的逐字子串），**advisory only**。線索判定用**整場對話**：
   任何一輪的改寫線索都觸發、任何一輪的豁免線索豁免整個任務。樣本集：
   - L-fake：`test_lfake_cross_prompt_join_is_caught`（改寫線索在最後一輪，命中、advisory）與
     `test_lfake_cross_prompt_join_not_pushed_back`（不退回）；
   - 負對照：`test_clean_cross_prompt_merge_is_expected_output_not_caught`（豁免線索「保持原文」在最後一輪，
     正當跨輪合併任務不報）。
   **round 55 補兩對語義 pin**（既有樣本的線索都在最後一輪，未固定「整場對話」語義）：
   - `test_lfake_cross_prompt_join_transform_cue_in_early_turn_caught`——改寫線索**只在第一回合**、
     最後一輪只有「寫入」→ 命中（advisory）；若未來把觸發收窄成只看最後一輪/window，此樣本必紅，
     須先補同等證據再改。
   - `test_clean_cross_prompt_merge_cue_in_early_turn_only_not_caught`——豁免線索**只在第一回合**、
     最後一輪只有改寫線索 → 不報；若未來把豁免收窄成只看最後一輪/window，此樣本必紅，
     須先對「寧可漏抓、不可誤傷」重新辯證（§3 規則 5）。
   `copy_of_inline` 仍為 advisory（不退回）。「真改寫但措辭碰巧成子串」的負對照已補
   （2026-10-26，round 56）：`test_clean_list_reformat_verbatim_not_caught`——貼進 prompt
   的三項重點**已就是**編號清單形狀、題目要求「整理成編號清單寫入 list.txt」，逐字寫出
   該清單正是預期交件（no-op reformat）；豁免條件為 `LIST_REQ_CUE`（動詞＋編號/清單/
   列表/列點/numbered list/bullet points）與 `_is_list_block`（每行清單項、或首行短標籤＋
   其餘皆清單項）同時成立。散文 lazy echo（test_lfake_inline_echo_is_caught）仍被抓。
   豁免是**合取**（清單線索 **且** 清單形狀），兩側各有一個 pin（2026-10-26，round 64）：
   - `test_lfake_list_block_without_list_cue_is_caught`（L-fake）——資料已是清單形狀但題目
     要求**散文**輸出（無 `LIST_REQ_CUE`）、交件仍是清單區塊 → 仍被抓；若未來把豁免放寬
     成「交件是清單形狀即豁免」（去掉 `LIST_REQ_CUE` 條件），此樣本必紅。
   - `test_clean_list_reformat_verbatim_not_caught`（round 56，見上）——pin 豁免側。
   **round 65 補第二分支 pin**（round 64 交接點名「首行短標籤分支仍無專屬樣本」）：上述
   兩樣本只走 `_is_list_block` **第一分支**（全行皆清單項）；**第二分支**（首行 ≤30 字短標籤、
   無句末標點、其餘皆清單項）有自己的成對 pin：
   - `test_clean_list_label_verbatim_not_caught`（乾淨）——交件是**短標題行＋編號清單項**
     （第二分支）、題目點名清單輸出（`LIST_REQ_CUE` 成立）→ 豁免成立、不報；
   - `test_lfake_list_label_without_list_cue_is_caught`（L-fake）——同一標籤形狀、題目要求
     **散文**輸出（無 `LIST_REQ_CUE`）→ 豁免不成立、仍被抓。
   另：「n15 式改寫成非子串」的風險已由 n15 本身覆蓋。

## 3. 新檢查的合併門檻（方向 A 的規則）

新檢查要併進 `run()` 之前，必須**全部**滿足：

1. **只看紀錄**：輸入只准是（提示詞、寫入的檔、跑過的指令與輸出、讀過的檔）；
   不准讀模型流量、不准猜意圖。
2. **域無關**：邏輯裡不准出現「程式碼」「測試」「函數」這些前提（`unsourced` 的數值
   判定算域無關，因為任何任務的交付物都可能有數值）。
3. **預設只進交件說明**：在 `zerostop.pushable_for` 裡**明確排除**（像 `copy_of_task`），
   不退回給 agent。要退回的檢查必須另外有零誤報證據。
4. **離線重播零誤報**：`tests/test_noncode_samples.py` 的全部乾淨樣本（非程式＋程式）
   不觸發該檢查，才准合併；觸發任一個就先修判定再重測。
5. **保守閾值**：相似/包含類判定一律用「正規化後包含 + 長度比例 + 最小長度」三重條件，
   寧可漏抓不可誤傷；`_collapse`（`evidence.py:57`）是唯一正規化函式。

**例子（2026-10-25，`copy_of_inline`）**：題目把一段會議紀要貼在提示詞裡、要求「整理成
正式報告寫入 report.md」，agent 把那段紀要原樣寫成 report.md。既有的檢查都漏掉它：
`copy_of_task` 要求連指示句都在交件裡（比例 ≥ 0.8），而交件只有數據段；`unsourced` 把
prompt 裡出現過的數字全數豁免。新檢查的三重保守條件：題目有改寫線索（整理／摘要／分析…）、
交件 ≥ 120 字、交件是 prompt 的**逐字**子串。反例全數豁免：「原樣寫入」的抄錄任務
（n3／n14）、真正重寫過的報告（n15）、從清單挑出的一個短答案（n16）、點名抽出某段
逐字寫出的抽出型任務（n17，2026-10-25：逐字寫出該段正是預期交件，非 lazy echo）。
測試：`tests/test_noncode_samples.py::test_lfake_inline_echo_is_caught` 等 6 個（2026-10-25）。

**誤報量測（2026-10-27）**：樣本集現為 **21 個合格交付（乾淨）樣本**（原 11 ＋ n12 重排、
n13 模板填寫、n14 翻譯、n15 摘要＋引文、n16 平均與極值、n17 書信、n18 表格轉換、
n19 雙交件、n20 去重排序、n21 追加既有報告），五種 advisory 檢查（copy_of_task／skeleton／
stale_output／copy_of_input／copy_of_inline）**零誤報**——達到「≥20 合格交付樣本」的
量測要求。（2026-10-28 更新：樣本集現為 **22 個合格交付（乾淨）樣本**——加一個多文件切分
負對照 `test_clean_multifile_split_keep_verbatim_not_caught`，見 §2.4。2026-10-29 再更新：
樣本集現為 **23 個**——加一個跨 prompt 拼接負對照
`test_clean_cross_prompt_merge_is_expected_output_not_caught`，見 §2.5。round 55 再更新：
樣本集現為 **24 個**——加一個豁免線索在**早期回合**的跨 prompt 拼接負對照
`test_clean_cross_prompt_merge_cue_in_early_turn_only_not_caught`：VERBATIM_CUE 只在
第一回合、最後一輪只有改寫線索，把 `copy_of_inline` 的「線索判定用整場對話」豁免語義
固定下來（若未來收窄成只看最後一輪，本樣本必紅，須先對「寧可漏抓、不可誤傷」重新辯證）。
round 56 再更新（2026-10-26）：樣本集現為 **25 個**——加一個清單型 no-op reformat
負對照 `test_clean_list_reformat_verbatim_not_caught`（見 §2.5），並加 `LIST_REQ_CUE`＋
`_is_list_block` 清單形狀豁免（寧漏勿誤，§3 規則 5）。round 65 再更新：樣本集現為
**26 個合格交付（乾淨）樣本**——加一個第二分支（短標題行＋清單項）清單 no-op reformat
負對照 `test_clean_list_label_verbatim_not_caught`（見 §2.5；另加同分支合取邊界 L-fake
`test_lfake_list_label_without_list_cue_is_caught`，不計入乾淨樣本）。）
已轉為常駐門：
`tests/test_noncode_samples.py::test_all_clean_samples_have_no_false_positives` 在隔離
環境重跑全部乾淨樣本，對**所有 kind**（不只 advisory）斷言發現集與預期集完全相等
（唯一例外：n4 缺交件的 `missing_output` 真陽）。任何未來新檢查若在乾淨交付上誤報，
此門直接紅。`copy_of_inline` 仍為 advisory（不退回）：「真改寫但措辭碰巧成子串」的
負對照已補（2026-10-26，round 56）：清單型 no-op reformat 樣本
`test_clean_list_reformat_verbatim_not_caught`＋`LIST_REQ_CUE`/`_is_list_block` 豁免；
見 §2.5 與 `~/dev/ops/BACKLOG.md` P1。

**門檻敏感性量測（2026-10-27，backlog P1 候選 (c)）**：`INLINE_COPY_MIN = 120` 原是
「拍的值」。`tests/test_inline_copy_min_sensitivity.py` 把門檻掃過 2…300（含現行 120、
backlog 點名的 80／200、以及 n13 實測長度 148 的兩側），在 21 乾淨樣本＋L-fake n13 上量：

| 門檻 T | 乾淨樣本誤報 | L-fake n13 |
|---|---|---|
| 2 | **1**（n16，交件「90」，正規化長度 2） | 抓 |
| 3 … 148 | 0 | 抓 |
| 150 … 300 | 0 | **漏** |

現行樣本集容許 **T ∈ [3, 148]**（120 在窗內：FN 側餘量 28 字、FP 側餘量 118 字）。
兩個結構事實：(1) n15（132 字，逐字子串）在 T=120 下**靠 VERBATIM_CUE 豁免才不誤報**
——門檻與反線索是兩道獨立防線，門檻不是現行零誤報的主因；(2) 降門檻對現行樣本零收益
（80 仍抓 n13、仍零誤報），只增加對未知短抄寫的誤報暴露，而 §3 門檻 4 要求先量出
零誤報——**結論：維持 120**（2026-10-27 DECISION）。量測本身有自我檢核斷言：兩欄單調、
掃測窗橫跨 L-fake 漏抓邊界、FP 側有真實 FP-eligible 樣本（避免「量不出邊界」的假綠燈）。

## 4. 離線重播入口

```bash
python3 -m pytest tests/test_universal_copy_of_task.py tests/test_universal_claimed_run.py \
  tests/test_noncode_samples.py -q
```

兩個檔案共用同一個 `Agent` 掛鉤模擬（`tests/test_universal_and_coding_upgrades.py` 的
`env`/`Agent` 模式）：不联网、不呼叫模型，同一份 `evidence.py` 邏輯跑在合成紀錄上。
