# 通用任務（非程式）：現有檢查的分類與新檢查規則

> 對應 ASSIGNMENT 方向 A（「通用任務：程式以外也有用」）與 BACKLOG P1 第 1 項。
> 本頁只整理**現有的**證據檢查（`vacant_network/trace/evidence.py`），並定下新檢查的合併門檻。
> 沒有這裡沒寫的保證；每一行都可以用對應的測試離線重播。

## 1. 現有發現（finding）分類

`run()`（`evidence.py`）目前會產生 **11 種 kind**（2026-10-25 對照原始碼盤點：
`missing_output`、`invalid_output`、`failed_step`、`test_claim`、`unsourced`、`unread`、
`copy_of_task`、`skeleton`、`stale_output`、`copy_of_input`、`copy_of_inline`；
前 6 種可退回給 agent，後 5 種被 `zerostop.pushable_for` 明確排除、只進交件說明）。
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
| `copy_of_inline`（2026-10-25 新增，**僅建議**） | **是** | 交付檔（正規化後）是 prompt 的逐字子串（≥ 120 字）、且題目要求改寫（整理／摘要／分析／重排…） | 抄錄任務（「原樣寫入」，VERBATIM_CUE）、複製任務（COPY_CUE）、抽出型任務（「抽出／摘出／extract…某段寫入」，EXTRACT_CUE，2026-10-25 n17）豁免；短答案（< 120 字）不報；交件＝整段 prompt 由 `copy_of_task` 報（比例 1.0），不重複。見 §3 例子；120 的敏感性實測見 `tests/test_inline_copy_min_sensitivity.py`（2026-10-27） |

**結論：** `missing_output`、`invalid_output/empty`、`unsourced`、`unread` 對非程式任務
直接可用且可退回；`copy_of_task`、`skeleton`、`stale_output`、`copy_of_input`、`copy_of_inline`
五種域無關但預設只進交件說明（不退回）；`syntax/stub/test_claim/failed_step/empty_filter/contract_shape`
的前提是「有程式碼/表格可跑」，對純文件任務大多不會觸發（不會擋，但也不會幫上忙）。

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
量測要求。已轉為常駐門：
`tests/test_noncode_samples.py::test_all_clean_samples_have_no_false_positives` 在隔離
環境重跑全部乾淨樣本，對**所有 kind**（不只 advisory）斷言發現集與預期集完全相等
（唯一例外：n4 缺交件的 `missing_output` 真陽）。任何未來新檢查若在乾淨交付上誤報，
此門直接紅。`copy_of_inline` 仍為 advisory（不退回）：「真改寫但措辭碰巧成子串」的
負對照仍未補（見 `~/dev/ops/BACKLOG.md` P1 候選）。

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
python3 -m pytest tests/test_universal_copy_of_task.py tests/test_noncode_samples.py -q
```

兩個檔案共用同一個 `Agent` 掛鉤模擬（`tests/test_universal_and_coding_upgrades.py` 的
`env`/`Agent` 模式）：不联网、不呼叫模型，同一份 `evidence.py` 邏輯跑在合成紀錄上。
