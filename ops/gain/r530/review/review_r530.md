# R530 §五-2 規格公平性複核（獨立代理，人讀版）

- 複核者：獨立代理（**不是**題庫作者），唯讀，零模型呼叫。
- 題庫路徑：`/Users/cosmopig/Documents/GitHub/Vacant/ops/gain/r530/bank/`
  （複核途中作者 worktree `agent-acf0d5b7629dc1370` 被併進主線並移除；
  依協調者說明，主線內容與 `e00f74f` 逐位元相同）。
- 規模：20 題（tight 17、loose 3）、隱藏 249 條、可見 57 條、參考解與 3 個已知壞樁 ×20。
- 機器輸出：`review_r530.json`。

## 〇、結論先講

| 項目 | 結果 |
|---|---|
| `passed` | **20 題全過** |
| `excluded` | **0 條、0 題** |
| `amended` | **5 筆**（4 筆題目層級 ＋ 1 筆 rubric 層級；**都必須在 AMEND1 之前處理**） |
| D1 難度擋門 | **綠**（裁決口徑 rel_diff=0.0149；預註冊字面口徑 0.3284，兩個都綠） |
| D2 條數擋門 | **綠** |
| 正向擋門（anchor 逐字） | **249/249 過**（我自己重跑，不只信 `gauge_r530.py`） |
| 反向擋門（目標每句困擾都有驗收） | **19/20 過；`ow_08_logscan` 失敗一句** |
| 可見／隱藏零重疊 | **過**（0 條逐字相同；11 筆 `overlap_note` 記錄） |
| `boundary_only_hidden_n` 合計 | **55 / 249（22.1%）** |

§一-6 第 6 條的停機條件（`tight` < 14 或 `loose` == 0）**沒有觸發**：
複核後 tight 17、loose 3，n_after_review = 20。

---

## 一、擋門怎麼跑的

**順序照 §五-2 擋門 0b 寫死的：先 §一-3b，再 anchor 對照表。**

### 一-1　難度擋門（§一-3b）

`ref_solution_lines` 我**重算過**（`ast.unparse(ast.parse(src))` 後數非空行，
`bad_*.py` 排除），20 題逐題與 `meta.json` 相符，沒有一題對不上。

| 量 | 值 |
|---|---|
| `median(核心 12 題)` | **67.0**（16, 30, 39, 39, 61, 64, 70, 80, 87, 92, 105, 113） |
| `median(新 tight 5 題 ow_13–17)` | **66.0**（31, 59, 66, 79, 200） |
| **相對差（裁決口徑）** | **0.0149 ⇒ D1 綠** |
| `median(新 8 題，預註冊字面口徑)` | **45.0**（23, 26, 29, 31, 59, 66, 79, 200） |
| **相對差（預註冊字面口徑）** | **0.3284 ⇒ D1 綠** |
| **D2** | tight 隱藏最小 12（ow_14、ow_17）≥10；loose 6／6／7 ≥5 ⇒ **綠**。可見 tight 3、loose 2，都在 2–3 內 |
| 退回重寫次數 | **0** |

兩個口徑我都印，因為它們**差很多**：裁決口徑 1.5%，預註冊字面口徑 32.8%——
離紅線只剩 7pp，而它之所以接近紅線，只是因為三題 loose 的參考解本來就短
（契約只釘進入點）。作者在 `TASKS_TABLE.md` 已經主動點出這件事，我核對過，屬實。

誠實邊界（必帶）：

1. 行數是難度的粗代理。ow_15 的 200 行與 ow_07 的 16 行都落在同一個中位數檢定裡，
   中位數看不見這個離散度。
2. 40% 是訂出來的，沒有外部錨。
3. **ow_08 的 64 行裡約 16 行是命令列程式碼，而沒有任何一條驗收讀它**（見下面的 `amended`）。
   代理量到的工作量包含了計分看不到的部分。
4. D1 只比新題 vs 核心題。**§八-2 第 4 條（沒有人類逐題看過這 20 題）沒有因此被解決。**

### 一-2　正向擋門（anchor 逐字）

249 條全部有 `# anchor_kind:` / `# anchor:` / `# derivation:` 三行檔頭，
我獨立重跑逐字比對（空白正規化後做子字串比對，且 `anchor_kind` 宣告的來源
必須是**實際找得到**的那一份）：**249/249 過，0 條指不回去**。

`anchor_kind` 分佈符合 §五-2 對 loose 的預期：loose 三題 19 條裡 18 條指向 `goal.md`，
只有 `ow_18/h06` 指向契約——那正是「契約留白 ⇒ anchor 更常指到目標敘述」的形狀。

### 一-3　反向擋門（機器做不到的那一半）

我逐題把 `goal.md` 拆成「客戶困擾／必須成立的性質」的句子，再一句一句找對應驗收。
**19 題全覆蓋；`ow_08_logscan` 有一句完全沒有被量到。** 詳見第二節。

### 一-4　`boundary_only` 的判準（我實際怎麼標）

§一-3b 的三條判準寫死、不准加第四條，所以我把它讀成**最窄**的版本，並且加一條
「boundary_**only**」的解釋：**一條驗收只有在它所評分的每一個輸入都落在三條判準之內時才算 true；
只要它同時評了一個普通情況，就是 false。**

- (1) 函式操作的那個輸入本身是空的／零長度（`""`、`[]`、`{}`、`None`＝沒有檔案、零資料列）。
- (2) 該條所評的行為就是契約要求的丟例外。
- (3) 某個輸入值**恰好等於**契約點名的邊界或極值（視窗端點、進位點、最小合法值、單位階）。

結果 **55 / 249（22.1%）**。**其中 40 條是判準 (2)**——也就是說，嚴格讀法下這個量
幾乎塌縮成「這條是不是例外檢查」。

⚠ **敏感度（必須一起看）**：把 (1) 讀成「狀態為零長度」、(3) 讀成「靠近而非恰好落在邊界」，
會再多出約 12 條（ow_02 h02／h08、ow_01 h04／h13、ow_03 h09、ow_05 h09／h15、
ow_16 h03、ow_08 h04、ow_17 h06、ow_18 h06、ow_13 h13），變成約 27%。
最清楚的例子是 **ow_02 h02**：`window=5.0`、`t=4.999`，擺明是視窗端點的探針，
但 4.999 不「恰好」等於端點 ⇒ 嚴格讀法判 false，而它的孿生兄弟 h01（`t=5.0`）判 true。
**這個數字對讀法敏感。** §一-3b 已經寫死「只落盤、不設門檻」，收官不准事後拿它當判準——
我把兩個數字都留在 JSON 裡，就是為了讓任何事後改讀法的動作看得出來。

---

## 二、逐題

### `ow_01_csvjson`（tight，ref 105，hidden 14，boundary_only 3）
反向覆蓋完整：逗號、換行、雙引號、空白欄、重複表頭、CRLF、非 ASCII、行號、退出碼、
stdout 不被污染，每一句都有對應條。CLI 有 v03／h10／h11 三條在測，**是全庫唯一真的跑
`python -m solution` 的題**。`boundary_only`：h08、h09（ValueError）、h12（空輸入／只有表頭）。
h04（整列空欄）與 h13（缺結尾換行）是邊界味道很重但判準管不到的兩條，已記 note。
`overlap_note`：h01 與 v02 是同一需求的等價輸入（引號內含逗號），字面不同，不擋。

### `ow_02_ratelimit`（tight，39，15，4）
八句困擾全覆蓋（每人分開計數、等待要縮短、被拒不延後、時鐘外注、時鐘倒轉、
小數秒、單人／全體清除、建構期擋設定）。`boundary_only`：h01（事件恰好在 `now-window`）、
h03／h04（`max_events=0` 極值）、h14（ValueError）。
**兩筆值得記的重疊**：(a) v02 第一個 assert `retry_after('u')` 在任何呼叫之前 ==0.0，
就是 h08 測的「沒見過的 key」；(b) v02 的建構失敗集合與 h14 同類（`window_s=0`、`max_events<0`），
h14 只多了 `-0.5` 與 `(-1,-1)`。兩條都不是逐字相同，擋門 3 不觸發，但 h14 在可見已給的前提下**偏薄**。

### `ow_03_mdtable`（tight，113，14，0）
十二句困擾全覆蓋（含轉義管線、行內碼、兩種 fence、缺邊界管線、參差列、空格、
冪等、CRLF、無表格原樣）。**`boundary_only` = 0**，全庫唯一一題零邊界條——
它的困擾清單本來就沒有例外條款，契約也不要求丟任何例外。
已知壞樁：`bad_c` 是 identity 函式（「骨架」），被 1 條可見 ＋ 5 條隱藏擋下
（h01／h07／h08／h09／h13）——依指示記錄，不擋。
另記：h10（冪等）、h12（無表格）、h14（結尾換行）**沒有任何一個已知壞樁會踩到**，
量具的單邊保證涵蓋不到這三條。

### `ow_04_layerconf`（tight，70，15，4）
十一句困擾全覆蓋（三層優先序、來源查詢、型別、分節、註解、含等號的值、沒有檔案、
無關環境變數、大寫底線映射、拼錯忽略、轉不動要炸）。
`boundary_only`：h06／h07（ValueError）、h11（KeyError）、h12（`None` 與 `""` 都是沒有檔案）。

### `ow_05_router`（tight，80，15，3）
六句困擾全覆蓋。`boundary_only`：h06／h13／h14（都是 add 期的 ValueError）。
h09（`/tags/` 空 segment）、h15（catch-all 不得為空）在寬鬆讀法下會變 true，已記 note。
另記：h09、h10、h11、h12 四條**沒有已知壞樁會踩到**，是全庫最多的一題。

### `ow_06_verrange`（tight，61，14，3）
十一句困擾全覆蓋（1.10 vs 1.9、pre-release 較舊、rc.2 vs rc.1、alpha vs beta、
多一段較新、逗號分隔、空白、全部條件都要成立、看不懂就拒絕）。
`boundary_only`：h12／h13／h14（三條 ValueError）。h10 六個運算子各測兩側，
含恰好等於界線的輸入，但**同時也測了非邊界輸入** ⇒ 依「only」判 false。

### `ow_07_retrypolicy`（tight，16，13，3）
十句困擾全覆蓋。`boundary_only`：h08（`retry_on=()` 空 tuple）、h09（ValueError）、
h10（`attempts=1`＝契約 `attempts < 1` 的最小合法值）。
⚠ ref 16 行是全庫最短，但它的隱藏條數 13 條、覆蓋十個困擾——這是 D1 用行數當代理時
看不見的那種錯配（誠實邊界 1）。

### `ow_08_logscan`（tight，64，14，2）　**⚠ 唯一的反向擋門失敗**
九句困擾有對應，**第十句沒有**：

> Finally they want to eyeball a file from the shell without writing a script.

契約寫了 `python -m solution FILE`，但補了一句「Prints a table a person can read.
Nothing about its layout is checked.」，而**全庫只有 ow_01 的驗收會起 subprocess，
ow_08 一條都沒有**。參考解的 64 行裡有約 16 行在實作這個 CLI。
按 §五-2 擋門 2，這句話現在是「沒有被量到的需求」：不做的人不會掉分，做的人是在
計分之外白付難度（「留著＝在計分之外偷偷加難度」）。⇒ 進 `amended`，兩條路二選一，見第三節。
`boundary_only`：h03（p50 於 n=4 恰好 `ceil(2.0)` ＝進位點）、h05（作者點名的那條，見下）。

**作者點名的 `h05_single_sample`**：anchor「Percentiles are nearest-rank」逐字存在，
derivation（n=1 時每個百分位的 rank 都是 1）推得動，**通過**。
我把它標成 `boundary_only=true`（判準 3，樣本數的極值），但誠實講：
契約點名的是公式 `ceil(p/100*n)`，**沒有**點名 n=1，所以這是「定義域的極值」
而不是「契約字面點名的門檻」。這一條是我在整個標記過程中判準 (3) 拉得最開的一次。

### `ow_09_minitemplate`（tight，87，13，7）
十二句困擾全覆蓋。**`boundary_only` = 7／13，全庫比例最高**——但那不是題目歪掉，
是它的目標敘述自己就列了四種「模板寫壞」的困擾（未關閉、巢狀 repeat、
非 list 的 repeat、多餘的關閉標籤），錯誤路徑本來就佔一半。描述性記錄，不擋。

### `ow_10_dedupe`（tight，30，13，2）
八句困擾全覆蓋。`boundary_only`：h09（KeyError）、h10（ValueError）。
h12 是空列表 ＋ 無重複列表兩件事合成一條 ⇒ 依「only」判 false。

### `ow_11_reflow`（tight，92，14，1）
十句困擾全覆蓋（寬字兩欄、任意位置可斷不補空格、縮排、三種 bullet 懸掛縮排、
空行保留、每個 bullet 自成一段、超長不切、寬度不合法要拒）。
`boundary_only`：只有 h10（ValueError）。

**作者點名的 `h11_whitespace_collapses`**：anchor
「runs of spaces and tabs separate words and are replaced by a single space」
逐字存在，主 assert 直接從它推得出，**通過**。
但要記兩件事：(a) 第二個迴圈（`line == line.rstrip()`）評的是**另一句契約**
（"No output line ends in a space."），不是宣告的那一句——仍然錨在契約裡，
只是 `ANCHORS.md` 一檔一錨的表格因此**描述不足**；(b) 那個迴圈在上面那個
逐字相等的 assert 之後是冗餘的，不構成額外負擔。**不排除，記 note。**

### `ow_12_bytesize`（tight，39，13，3）
十一句困擾全覆蓋。`boundary_only`：h06（1023／1024／1024²-1／1024²／1024³，
**每一個輸入都恰好落在單位階的兩側**，是全庫最乾淨的一條邊界條）、h12／h13（ValueError）。
`overlap_note`：v03 與 h13 都含空字串 `""` 這個**同一個字面輸入、同一個需求**；
h13 另外六個是新的，擋門 3 不觸發。

### `ow_13_timespans`（tight，59，13，5）
八句困擾全覆蓋。`boundary_only`：h01（首尾相接，恰好在契約的半開端點）、
h03（零長度 span）、h10／h11（ValueError）、h12（空列表）。
另記：`bad_b` 只被 3／13 條隱藏擋下，是**全庫最薄的已知壞樁格**（比 ow_03 `bad_c` 的 5／14 更薄）。

### `ow_14_statemachine`（tight，31，12，4）
九句困擾全覆蓋。`boundary_only`：h02／h08／h09（ValueError）、
h03（被拒之後狀態與紀錄不動——所評行為就是例外路徑）。
h10（死路狀態）同時評了正常轉移與拒絕 ⇒ false。

### `ow_15_tomlsub`（tight，200，13，4）　**⚠ 全庫最接近排除的一條**
十二句困擾全覆蓋。`boundary_only`：h06／h08／h09／h13（都是 ValueError）。
ref 200 行是全庫最長，但它不是新 tight 五題的中位數（66.0）——D1 不因它翻紅。

**作者點名的 `h12_written_order`**：anchor
「`dumps` writes the top-level names first in name order, then each heading in name
order with its own names in name order」逐字存在，**排序這件事錨得死死的**。
問題在別的地方：這條驗收**比對整串輸出文字**，等於把 `apple = 2` 裡
等號兩側的**單一空格**也釘死了。而契約只在 **parse 的行文法**裡寫過 `name = value`，
從來沒有規定 `dumps` 的排版；我實測參考解的 parser **吃得下 `a=1`**。
⇒ 一個 `dumps` 輸出 `apple=2` 的解，滿足契約每一句（含兩條 round-trip），仍然被 h12 擋掉。
**不排除**（排序主張本身錨得住，而且這是補一句契約就解決的事），但進 `amended`。

### `ow_16_pathglob`（tight，66，13，1）
十三句困擾全覆蓋（單層星號、雙星含零段、`?`、字元類、範圍、否定、整路徑比對、
正則元字元當字面、`!` 移除、後面的可以加回來、順序與去重、壞 pattern 要報）。
`boundary_only`：只有 h12（ValueError）。
`overlap_note`：壞 pattern `'src/[abc.py'` **逐字**同時出現在 v03 與 h12——
不同進入點（`matches` vs `select`），擋門 3 不觸發，但 h12 的第一個案例對
過得了 v03 的人接近白送。

### `ow_17_diffpatch`（tight，79，12，4）
十句困擾全覆蓋。`boundary_only`：h07／h08／h09（ValueError）、h11（空版本）。
h06（沒有變更）同時評了空 hunks 與正常清單 ⇒ false。

### `ow_18_taskorder`（loose，23，6，2）
五條 goal bullet 逐條對上 h01–h05。
⚠ **loose 層最重要的公平性性質成立**：沒有任何一條隱藏驗收釘死「哪一個合法順序」——
h03 只要求**同一份表兩次呼叫給同一個答案**，h01／h02 只要求集合與偏序。
這正是 §一-3「Which of the many orders ... is up to whoever writes it」要的形狀。
唯一要記的是 **h06 是三題 loose 裡唯一錨到契約而不是目標的一條**：
`plan({}) == []` 目標沒有明講，但它由「every job appears exactly once」＋
「plan returns a list of job names」推得出來，**通過**，記 note。
`boundary_only`：h04／h05（ValueError）。

### `ow_19_redact`（loose，26，6，0）
五條 goal bullet 逐條對上 h01–h06。**但它是三題 loose 裡風險最高的一題**：
目標給的是**三個字面例子**（`AKIAIOSFODNN7EXAMPLE`、`Authorization: Bearer eyJ...`、
`postgres://svc:hunter2@...`），而隱藏驗收要求的是**類推**——
h01 用 `mysql://`、h03 用 `amqp://`、h05 用 `mongodb://`、h06 用 `redis://`；
h05 更把 `Authorization: Bearer tok-one`（**不是**點分三段的 JWT）也算成密鑰。
而兩條可見驗收用的都是目標的字面例子 ⇒ **一個把三個字面值寫死的 worker，
看得到的全過，看不到的六條裡掉四條。** 目標只用一個「roughly」暗示要類推。
⇒ 不排除（anchor 逐字都在，「none of the secret text is anywhere in the result」
也確實是目標明講的性質），但進 `amended`：補一句話把類推說出來。
`boundary_only` = 0。

### `ow_20_slugify`（loose，29，7，0）
六條 goal bullet 逐條對上 h01–h07，含批次層級的三個性質
（同批不重複、同批可重現、非拉丁字母也要拿得到 slug）。
⚠ 一處要記：**h03 對標題 `"..."`（純標點）斷言 `slug != ""`**，
而目標的「非空」保證是綁在「a title written in a script with no Latin letters in it
at all」上的，純標點是不是「一種文字」是可爭的。其餘三個 hyphen 斷言錨得住。
⇒ 進 `amended`（改目標一句，或把那個 assert 拿掉；建議前者）。
`boundary_only` = 0。

---

## 三、`amended`（五筆，全部必須在 AMEND1 之前處理；我不改題庫）

| # | 題 | 要處理什麼 | 建議 |
|---|---|---|---|
| 1 | `ow_08_logscan` | **反向擋門失敗**：goal 最後一句（shell 直接看檔）零驗收 | (a) 加一條隱藏驗收只驗 `python -m solution FILE` 的 exit 0 ＋ stdout 非空、檔案不存在時 exit 非 0（版面仍不驗）；或 (b) 從 goal.md 刪掉那句、從 contract.md 刪掉整個 Command line 節。**不准原樣留著。** |
| 2 | `ow_15_tomlsub` | `h12` 釘死 `dumps` 的等號空白，契約沒規定 | (a) 契約補一句：「`dumps` writes each setting as `name = value`, with one space on each side of the `=`, and each heading on a line of its own.」；或 (b) 把 h12 改成比對順序而非字面行。建議 (a)。 |
| 3 | `ow_19_redact` | 隱藏驗收要求類推（四種 DSN scheme、非 JWT 形狀的 token），目標只說「roughly」 | goal.md 補一句：「The three lines above are shapes, not literals: the same kinds turn up with other key text, other token text, and other database schemes.」 |
| 4 | `ow_20_slugify` | `h03` 對純標點標題要求非空 slug，目標的非空保證只綁在非拉丁字母標題上 | goal bullet 改成「a title with nothing usable in it -- another script, or only punctuation -- still gets a non-empty slug」；或拿掉那個 assert。建議前者。 |
| 5 | `ow_18/19/20` 的 `rubric.md` | **rubric 層級，不是驗收層級**：三份 loose rubric 加了預註冊沒有的加權 `readability + 2*structure + error_handling + 2*fit_to_goal`，並自稱「prereg amendment, Fable ruling 2026-09-13」 | 預註冊 §一-4 明寫「全部題目共用同一份」，全文沒有任何加權；§六-6 已經寫死質化那一段能報什麼。**要嘛 Fable 在 AMEND1 之前把加權正式寫進預註冊，要嘛三份 rubric 拿掉它。** 不可以帶著一句「凍結文件裡沒有的裁決」進 AMEND1。 |

---

## 四、Fable 該質疑的三點

### 1. `ow_08` 那句 CLI，是「補驗收」還是「刪句子」——這兩條路不等價，而且會動到 D1

補驗收會讓 ow_08 多一條隱藏條（14→15），刪句子會讓參考解掉約 16 行（64→48）。
**後者會動到核心 12 題的中位數**：67.0 → **65.5**（因為 64 原本就壓在中位數那兩格
64／70 的下半格上），連帶把兩個 D1 相對差改成 0.0076（裁決口徑）與 0.313（字面口徑）。
兩個仍然是綠，但數字變了。§一-3b 明寫「退回重寫之後整組 D1／D2 重算」，
所以無論選哪條，**D1／D2 都要重跑一次並重新抄進 AMEND1**。
我的建議是 (a) 補驗收：它讓量表與目標一致，而且不動行數分佈；
但這是 Fable 的裁決不是我的。

### 2. `boundary_only_hidden_n` 這個量，在嚴格讀法下有 73% 只是在數「例外檢查」

55 條裡 40 條是判準 (2)。ow_09 的 7／13 不是因為題目歪，是因為它的目標敘述
本來就列了四種「模板寫壞」；ow_03 的 0／14 不是因為它沒有邊界，是因為它的契約
一個例外都不要求。⇒ **這個量在跨題比較上量到的主要是「這題的目標有沒有錯誤條款」，
不是「這題的隱藏驗收有多偏邊界」。**
再加上 §一-3b 說它只落盤不設門檻，收官若真的拿它做「增益是不是只來自邊界條」的分層，
**分層變數的語意會比預期弱**。我把嚴格值（55 條，22.1%）與寬鬆讀法的估計（約 67 條，27%）都留在 JSON，
並在 `sensitivity` 欄位逐條列出差在哪 12 條——請在 AMEND1 就把要用哪一個讀法講死，
不要留到看過數字之後。

### 3. loose 層的「代價」確實兌現了，但兌現的方向和預註冊預期的**相反**

§一-3 事前寫死的代價是「loose 題的隱藏驗收比較難通過 §五-2 第 1 條，掉題機率比 tight 高」。
實際跑下來：**loose 三題的 19 條 anchor 一條都沒指不回去**，一題都沒掉。
真正出問題的是另一個方向——`ow_19` 與 `ow_20` 的隱藏驗收**要求得比目標明講的多**
（四種 DSN scheme、非 JWT 的 token、純標點標題也要有非空 slug）。
§五-2 的三條擋門都抓不到這種形狀：擋門 1 只問「錨得回去嗎」（錨得回去），
擋門 2 只問「目標的每句話有沒有被量」（有），擋門 3 只問重複（沒有）。
**「驗收要求的 > 目標承諾的」在現行三條擋門下是不可表達的**，只有人讀得出來。
這件事值得在 AMEND1 的誠實邊界裡寫一句——它同時解釋了為什麼 §五-2 一定要人做，
以及為什麼「複核通過」不該被讀成「題目的難度與目標對齊了」。

---

## 五、我沒有做的事（照實列）

- 沒有跑任何模型，沒有碰 vacant-dev，沒有改任何 repo 檔案。
  `gauge_r530.py --check` 與已知壞樁矩陣是在 scratchpad 的**副本**上跑的。
- 沒有驗證 `meta.json` 的 sha256 清單以外的東西；`gauge_r530.py --check` 說它們全對，
  我沒有重算每一個 sha256（我只重算了 `ref_solution_lines`）。
- 沒有評估「這 20 題對 `gemma-4-12b-it-qat` 來說難不難」——那需要模型呼叫，
  而且 §一-3b 的擋門本來就不問這個。
- 沒有檢查 `template/`（預註冊 §一-1 列了它，但目前題庫目錄下沒有這一層；
  工作區樣板見 §三-1，不在本次複核範圍）。
- **單邊保證照抄**：擋得住已知壞解 ≠ 涵蓋真需求。本複核的正向擋門只證明每條驗收
  錨得回原文，不證明驗收涵蓋了目標的全部需求；反向擋門是我一句一句讀出來的，
  是人的判斷，不是可重跑的量具。
