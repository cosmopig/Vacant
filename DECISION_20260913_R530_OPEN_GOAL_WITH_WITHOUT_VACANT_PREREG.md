# R530 預註冊 **v2**：目標明確、做法不指定的小型專案任務上，「用 Vacant」與「不用 Vacant」的配對比較

（**v2，2026-09-13，Fable 稽核後的裁決版，含同日兩條補充裁決 (a)(b)**。
v1 是同日 Opus 的草稿；Fable 改了什麼、為什麼改，逐條在**附錄 A**，
**v1 的取捨紀錄整段留著沒有刪**。
補充裁決 (a)＝§一-3b 的難度分佈擋門（附錄 A-13）；
補充裁決 (b)＝§五-6 的 J1／J2／J3 盲評配置（附錄 A-10a）。
**同日第三輪裁決 (1)(2)(3)**（盲評管線代理交付後）：
(1) 評審改成**跨模型**，**翻掉補充裁決 (b)**（附錄 A-10b）；
(2) 質化新增**長度共線**事前規則（附錄 A-14）；
(3) 去識別化**豁免機制追認**＋**丟格對等擋門**（附錄 A-15）。
本輪仍**零模型呼叫**；碰過 vacant-dev 的動作只有**唯讀** `ssh` 查詢
（`uname`／`df`／`du`／`ls`／`git log`／`apt-cache policy`／`curl -X GET /v1/models`），
沒有建立、修改、刪除任何檔案，沒有 `sudo`，沒有啟動任何行程。逐條見 §八-0。
⚠ 另有兩個代理正在 vacant-dev 上動手（題庫、bubblewrap 安裝驗證），
**那不是本檔做的**，本檔只登記它們的產出要落在哪裡、以及驗收條件。）

**本檔授權的東西只有**：§一 的題庫組成與凍結規則、§二 的臂與預算、§三 的工作區與
探針、§五 的稽核、§六 的判準、§七 的版本 D。發射仍由人類或 Fable 的明示指令觸發。

**編號**：`R530`。發文前掃過整個 repo（`*.md`／`*.py`／`*.json`／`*.sh`），
`R530` 零命中，`runs/` 底下沒有任何 `g_r530*`。

**它是誰的續作**：R460（harness 迴圈在**單函式**題上贏不贏 CONFORM）與
R529（同一個機制換題庫還在不在）問的都是「**已經是一題一函式**的題目」。
人類 2026-09-13 的指令換掉的是**任務的形狀**：

> 「我要你去規劃任務不能太具體，但要有明確目標，一個利用 vacant，一個不利用，
> 最後的結果必須要有公正可參考性的量化結果（產出要質化，是產出出來後你去質化
> 扶佐量化），然後去做比較。」

⇒ R530 = **開放做法的小型專案任務** × **有閘門／無閘門** × **量化主指標＋質化佐證**。

---

## 〇、這個 run **不**回答什麼（收官不准借用）

1. **不**回答「Vacant 讓模型變聰明」。兩臂同模型、同 prompt、同工具、同預算；
   唯一的差別是**交付之後發生什麼事**（§二-3）。量到的差是**閘門與回饋**的差，
   不是模型能力的差。
2. **不**回答「這套做法能推到真實工程專案」。本 run 的題是 **20 個**
   **可在單一 Python 匯入面上被程式判對錯**的小任務。
   需求編不成可執行驗收的場合，這個機制沒有免費的裁判——R440P §五-1 的前提句
   逐字適用（§八-1）。
3. **不**回答「效果量是多少」。n ≤ 20（每顆 seed；**實際 n 由 §五-2 的公平性複核
   決定，複核沒過的題在發射前剔除**）在本檔登記的檢定力之下（§四-4），
   點估計的區間寬度是 ±20–30pp 等級。**點估計不准被引用成數值宣稱。**
4. **不**回答「質化比較好」。質化評分由 12B／27B 本地模型盲評，本 repo 自己量過
   模型評審票近乎常數函數（R438／R516／R440P §三）。
   ⇒ **質化不進任何一格裁決**（§六-6），它只用來描述「贏在哪裡」。
5. **不**回答「換模型還成不成立」。三條臂共用同一顆 `gemma-4-12b-it-qat`。
6. **不**產生「Vacant 有沒有用」的總結論。本 run 只量**一個**機制
   （可見驗收閘門＋失敗原文回饋＋簽章收據）在**一種**任務形狀上的配對差。
7. **不**回答「契約鬆的任務上也成立」。§一-3 的 `loose` 層只有 **3 題**，
   它是**負向對照的方向探針**，n=3 什麼都檢定不了（§六-5 末的禁令）。

---

## 一、任務與題庫

### 一-0　為什麼不能用既有的三個題庫

`lcb2`／`lcb3`／`evalplus`／`humanevalplus` 全部是**一題一函式、題目已經把做法框死**
的形狀。人類要的是「目標明確、做法不指定」。⇒ 必須自建題庫。
自建題庫的代價寫在 §八-2（沒有外部基準可比、n 小、作者偏誤）。

### 一-1　一個題目是什麼（五件東西，缺一不可）

| 元件 | 內容 | 誰看得到 |
|---|---|---|
| **目標敘述** `goal` | 一段話，講客戶要什麼、為什麼要、以及他們踩過什麼坑。**不給步驟、不給演算法、不給資料結構。** | worker 看得到（在 `TASK.md`） |
| **介面契約** `contract` | 函式簽名／類別介面／CLI 用法；語意的**釘死點**（錯誤訊息格式、退出碼、捨入規則、排序規則……）。契約存在的理由是「兩臂的產出要能被同一套測試呼叫」，不是給提示。 | worker 看得到（在 `TASK.md`） |
| **可見範例** `visible` | **2–3 條**可執行的驗收，附輸入與期望值。同時是 `A-GATE`／`A-CONF` 的**出貨閘門**。 | worker 看得到，而且可以自己跑 |
| **隱藏驗收** `hidden` | **`tight` ≥10 條／`loose` ≥5 條**，含邊界情況。**只計分，永遠不進工作區、不進任何送給模型的文字。** | worker 看不到（V/GT 紅線，§五-3） |
| **質化評分表** `rubric` | 四維各 1–5，附逐級準則（§一-4） | 盲評模型看得到；worker 看不到 |
| **題目 meta** `meta` | `stratum`、**`ref_solution_lines`**、**`boundary_only_hidden_n`**、`hidden_n`、`visible_n`（§一-3b 的擋門讀這一份） | 誰都不進 prompt；只給擋門與 analyzer 讀 |

**落盤形狀**（資料不是程式，沿用 R452 `vacant/suitespec.py` 的紀律）：

```
ops/gain/data/openwork/<task_id>/
  task.md        # goal + contract（英文，送進 prompt 的就是這一份逐字）
  visible.json   # 2–3 條，{kind: "call"|"cli", ...}
  hidden.json    # tight ≥10 條／loose ≥5 條，同 schema
  rubric.json    # 四維 × 5 級準則
  meta.json      # stratum / ref_solution_lines / boundary_only_hidden_n / hidden_n / visible_n
  reference/     # 參考解（PR-3 量具本來就需要它；ref_solution_lines 從這裡算）
  template/      # 乾淨工作區樣板（見 §三-1）
```

⚠ **本檔凍結的是**：`task_id`、目標敘述、介面契約、可見條數、隱藏條數下界、
評分表、§一-3b 的難度分佈擋門、以及 §五-2 的公平性複核規則。
**本檔尚未凍結**：`hidden.json` 的逐條內容與各檔案的 sha256
——它們必須在**任何一通模型呼叫之前**寫完、經 §五-2 複核、
以修訂案（`DECISION_2026xxxx_R530_AMEND1_BANK_FREEZE.md`）把 sha256 釘死。
發射器與 analyzer 都逐檔比對 sha256，對不上就拒跑（`abort_bank_sha_mismatch`）。

### 一-2　核心 12 題（`stratum = tight`，**本檔逐字凍結**）

（題庫最終是 **20 題**：本節的 12 題 ＋ §一-3 的 5 題 `tight` ＋ 3 題 `loose`。
組成與凍結規則見 §一-3，最終成員由 §五-2 的複核決定，見 §一-6。）

`task.md` 的正文是英文（worker 是 `gemma-4-12b-it-qat`，本 repo 既有 prompt 全英文；
換語言會多一個與機制無關的差異）。下表每一格的第一段是英文目標敘述，
第二行是中文一句話對照（**英文為準**）。

---

#### `ow_01_csvjson`

> **Goal.** A client keeps a pile of CSV files that people edit by hand. They want
> to feed that data into another tool that only speaks JSON Lines, so they need a
> command that turns one CSV file into one JSON object per row. Their files are
> messy in the ways hand-edited files are messy: fields containing commas, fields
> containing line breaks, quotes inside quoted fields, and whole columns left
> blank. When a file is broken they want to be told which line is broken, not to
> receive a stack trace.

中文：把人手維護的 CSV 轉成 JSON Lines，壞行要指出行號而不是丟 traceback。

**契約**
- `solution.csv_to_jsonl(text: str) -> str`：回傳 JSON Lines（每行一個物件、
  最後一行有換行）。第一列是標頭。所有值皆為字串。空欄＝`""`。
  標頭重名時以**最後一個**為準。
- CLI：`python -m solution FILE`，成功時 JSONL 寫 stdout、exit 0；
  輸入不合法時 stderr 印**恰好一行** `line <N>: <reason>`、exit 2（N 從 1 起算）。
- 不合法＝欄數與標頭不一致、引號未閉合。

可見 **3** 條｜隱藏 **14** 條（含：引號內逗號／引號內換行／`""` 逃逸／CRLF／
空檔／只有標頭／標頭重名／欄數不符的行號正確性／退出碼／UTF-8 非 ASCII／
行尾換行／stdout 不得有多餘輸出／`text` 無尾換行／全空欄列）

---

#### `ow_02_ratelimit`

> **Goal.** A client's service gets hammered by bursts from the same callers. They
> want a piece of code they can put in front of it that says yes or no to each
> request, configured by "how long a window" and "how many are allowed in that
> window", counted separately per caller. When it says no, the caller wants to know
> how long to wait before trying again. Their tests must not sleep, so the notion of
> "now" has to come from outside.

中文：可設定時間窗與上限的 per-key 限流器，時鐘從外面餵，被擋時要能問還要等多久。

**契約**
- `solution.RateLimiter(window_s: float, max_events: int, clock: Callable[[], float])`
- `.allow(key: str) -> bool`（允許時要記錄這次事件）
- `.retry_after(key: str) -> float`（允許時回 `0.0`；被擋時回**還要等幾秒**才會再放行）
- `.reset(key: str | None = None) -> None`（`None` ＝全清）
- 窗是**滑動窗**：落在 `(now - window_s, now]` 內的事件才計數（左開右閉）。
- `window_s <= 0` 或 `max_events < 0` ⇒ `ValueError`。

可見 **3** 條｜隱藏 **15** 條（含：恰好在窗邊界／`max_events=0` 全擋／
多 key 互不影響／`retry_after` 隨時間遞減／未見過的 key／`reset` 單鍵與全清／
時鐘倒退／浮點邊界／連續呼叫 `allow` 不得重複計數同一次拒絕／參數檢查）

---

#### `ow_03_mdtable`

> **Goal.** A client's markdown documents are full of tables whose columns do not
> line up, and some of the cells contain Chinese and Japanese text. They want one
> pass over a whole document that makes every table's columns line up when read in
> a plain text editor, and leaves everything that is not a table exactly as it was.

中文：整份 markdown 的表格重新對齊（要處理全形寬度），非表格部分原封不動。

**契約**
- `solution.realign(text: str) -> str`
- 「對齊」＝以**顯示寬度**計算：East Asian Wide／Fullwidth 字元算 2，其餘算 1。
- 每格左右各留一個空格；每列以 `|` 開頭與結尾。
- 分隔列保留原本的對齊標記（`---`／`:---`／`---:`／`:---:`），並補到欄寬。
- 圍欄程式區塊（``` 與 ~~~）內的內容不得更動。
- 非表格行原樣輸出。行尾結構（有無尾換行）不變。

可見 **3** 條｜隱藏 **14** 條（含：CJK 寬度／四種對齊標記／`\|` 逃逸／
行內程式碼含 `|`／圍欄內的表格不動／缺頭尾 `|` 的表格／欄數不齊／空格子／
**冪等性** `realign(realign(x)) == realign(x)`／CRLF／文件無表格／表格緊鄰文字）

---

#### `ow_04_layerconf`

> **Goal.** A client's program takes settings from three places: values baked into
> the program, a settings file, and environment variables. They keep losing track
> of which one actually won, and things break when a number arrives as a string.
> They want something that hands back the final settings and can also answer, for
> any single setting, where that value came from.

中文：三層設定合併（預設／檔案／環境變數），要能回答某一項是誰給的，型別照預設值轉。

**契約**
- `solution.load(defaults: dict, file_text: str | None, env: dict) -> Config`
- `Config.get(key)`／`Config.source(key) -> "default" | "file" | "env"`／`Config.as_dict() -> dict`
- 優先序：env > file > default。
- 檔案格式：`key = value` 每行一條，`[section]` 開頭的區段使 key 變成 `section.key`；
  `#` 開頭與空行忽略。
- 環境變數：前綴 `APP_`，`__` 代表 `.`，大小寫不敏感（`APP_DB__PORT` ⇒ `db.port`）。
- 型別**照該 key 在 `defaults` 裡的型別轉**（`bool`／`int`／`float`／`str`）；
  `bool` 接受 `true/false/1/0/yes/no`（大小寫不敏感）。
- 轉不動 ⇒ `ValueError`；`defaults` 裡沒有的 key ⇒ 忽略，且不出現在 `as_dict()`。

可見 **3** 條｜隱藏 **15** 條

---

#### `ow_05_router`

> **Goal.** A client is writing a very small web framework and needs to take an
> incoming path and find which registered pattern it belongs to, pulling out the
> named pieces of the path along the way. Their problem is that a path often
> matches more than one pattern, and they want the same answer every time — the
> more specific one.

中文：路徑樣板比對器，多重命中時要每次都選「比較具體」的那一個。

**契約**
- `solution.Router()`／`.add(pattern: str, name: str) -> None`／
  `.match(path: str) -> tuple[str, dict[str, str]] | None`
- 樣板語法：字面段、`{name}`（吃一段、不得為空）、`{name:*}`（吃剩下全部，可含 `/`，
  只能出現在最後一段）。
- 具體度排序（由高到低）：字面段 > `{name}` > `{name:*}`，逐段由左至右比較；
  全同 ⇒ 段數多者優先；仍全同 ⇒ `ValueError`（重複樣板，在 `add` 時就丟）。
- **註冊順序不得影響結果。**
- 不match ⇒ `None`。路徑一律以 `/` 開頭。

可見 **3** 條｜隱藏 **15** 條

---

#### `ow_06_verrange`

> **Goal.** A client stores version strings and needs to answer two questions: given
> two versions, which is newer; and given a version and a requirement written the
> way people write requirements, does it satisfy that requirement. They have been
> burned by "1.10" sorting before "1.9" and by pre-release builds being treated as
> newer than the real thing.

中文：版本比較與範圍判定；`1.10 > 1.9`，pre-release 排在正式版之前。

**契約**
- `solution.compare(a: str, b: str) -> int`（-1／0／1）
- `solution.satisfies(version: str, spec: str) -> bool`
- 版本格式：`MAJOR.MINOR.PATCH` 後可接 `-PRERELEASE`（點分段，數字段依數值比、
  非數字段依 ASCII 比，數字段小於非數字段）。有 pre-release 者**小於**同號正式版。
- spec 語法：以 `,` 分隔的條件，全部成立才算滿足；每條是
  `>=`／`>`／`<=`／`<`／`==`／`!=` 接一個版本。
- 格式不合 ⇒ `ValueError`。

可見 **3** 條｜隱藏 **14** 條

---

#### `ow_07_retrypolicy`

> **Goal.** A client's code calls things that fail intermittently. They want a
> helper that re-runs a call a few times before giving up, backing off longer each
> time, but only for the kinds of failure that are worth retrying. Their tests must
> run instantly, so waiting has to be something they can substitute.

中文：可注入 sleep 的重試策略，只重試指定的例外類別，退避序列要可預期。

**契約**
- `solution.retry(fn, *, attempts: int, backoff_s: float, max_backoff_s: float,
  retry_on: tuple[type[BaseException], ...], sleep: Callable[[float], None]) -> Any`
- 最多呼叫 `fn` `attempts` 次；第 k 次失敗後睡
  `min(backoff_s * 2**(k-1), max_backoff_s)` 秒（k 從 1 起算）。
- **最後一次失敗之後不睡**，直接把原例外往外拋（不得包裝）。
- 不在 `retry_on` 裡的例外立刻往外拋、不重試、不睡。
- `attempts < 1` ⇒ `ValueError`。`fn` 不接參數。

可見 **3** 條｜隱藏 **13** 條

---

#### `ow_08_logscan`

> **Goal.** A client has a text log written by their own service and wants to know,
> per endpoint, how many requests there were, what share of them failed, and how
> slow the slow ones are. The log is machine-written but not clean: some lines are
> truncated or garbled, and those must not stop the run.

中文：log 彙總（每 endpoint 的筆數、錯誤率、延遲分位），壞行只計數不中斷。

**契約**
- 行格式：`<ISO8601> <METHOD> <PATH> <STATUS:int> <MS:int>`，以單一空白分隔。
- `solution.summarize(lines: Iterable[str]) -> dict`，輸出 schema 釘死：
  ```
  {"endpoints": [{"path": str, "n": int, "error_rate": float,
                  "p50_ms": int, "p95_ms": int}, ...],
   "bad_lines": int, "total": int}
  ```
- `error_rate` ＝ `status >= 500` 的比例，四捨五入到小數 4 位。
- 分位數用 **nearest-rank**：`p` 分位 ＝ 排序後第 `ceil(p/100 * n)` 個（1-indexed）。
- `endpoints` 依 `n` 由大到小排；`n` 相同時依 `path` 字典序。
- 壞行 ＝ 欄數不符、`STATUS`／`MS` 非整數、或時間戳不合 ISO8601。
- CLI：`python -m solution FILE` 印出人看得懂的表格（**不計分，只進質化**）。

可見 **3** 條｜隱藏 **14** 條

---

#### `ow_09_minitemplate`

> **Goal.** A client wants to fill values into text without pulling in a template
> library. They need placeholders that can reach into nested data, a way to repeat
> a block of text once per item in a list, and a loud failure when the text asks for
> something the data does not have — silently producing an empty string is what
> bit them last time.

中文：極小樣板引擎（巢狀取值、重複區塊、缺 key 要吵）。

**契約**
- `solution.render(template: str, data: dict) -> str`
- `{{a.b.c}}`：巢狀取值，值以 `str()` 轉字串。
- `{{#each items}} ... {{/each}}`：對 list 重複；區塊內 `{{.}}` 指當前元素，
  `{{.field}}` 指元素的欄位。不得巢狀 `each`（出現巢狀 ⇒ `ValueError`）。
- `{{! ... }}`：註解，輸出空字串。
- 取不到的 key ⇒ `KeyError`，訊息為該 key 的完整路徑字串。
- `{{` 沒有對應的 `}}` ⇒ `ValueError`。字面上的 `{{` 以 `\{{` 逃逸。

可見 **3** 條｜隱藏 **13** 條

---

#### `ow_10_dedupe`

> **Goal.** A client merges record lists that arrive from several places and the
> same thing shows up more than once. They want one list back, in the order things
> first appeared, and they want to choose what happens when two copies disagree:
> keep the first, keep the last, or take whichever fields are actually filled in.

中文：依 key 去重，保留首次出現順序，衝突策略三選一（first／last／merge）。

**契約**
- `solution.dedupe(records: list[dict], key: str | list[str],
  policy: str = "first") -> list[dict]`
- 輸出順序＝每個 key 值**第一次**出現的順序。
- `policy`：`"first"`（保留先到的）／`"last"`（保留後到的）／
  `"merge"`（逐欄取**最後一個非 `None` 且非缺席**的值）。
- `key` 是 list 時＝複合鍵，依給定順序組成 tuple。
- 有記錄缺 key 欄位 ⇒ `KeyError`；`policy` 不在三者之內 ⇒ `ValueError`。
- 不得更動輸入的 dict 物件（輸出是新的 dict）。

可見 **3** 條｜隱藏 **13** 條

---

#### `ow_11_reflow`

> **Goal.** A client writes notes in plain text and wants them wrapped to a fixed
> width for reading in a terminal. Their notes have indented blocks, bullet lists
> whose continuation lines should line up under the text and not under the bullet,
> code fenced off with backticks that must not be touched, and a lot of Chinese.

中文：純文字重排（縮排、項目符號續行對齊、圍欄不動、全形寬度）。

**契約**
- `solution.reflow(text: str, width: int) -> str`
- 寬度以**顯示寬度**計（East Asian Wide／Fullwidth 算 2）。
- 段落＝連續非空行；空行保留（連續幾個就留幾個）。
- 縮排：段落續行沿用該段**第一行**的縮排；項目符號（`- `／`* `／`N. `）的續行
  縮到符號後的第一個字下面。
- 圍欄程式區塊（```）內原樣輸出。
- 單一「字」長過 `width` 時獨佔一行、不切斷。CJK 字元可在任意兩字之間換行。
- `width <= 0` ⇒ `ValueError`。

可見 **3** 條｜隱藏 **14** 條

---

#### `ow_12_bytesize`

> **Goal.** A client's config files and log lines are full of sizes written the way
> humans write them, and elsewhere the same sizes are printed back out for humans to
> read. They keep getting bitten by the two meanings of "KB" and by numbers that
> come back out different from the way they went in.

中文：容量字串解析與反向輸出，KiB／KB 兩種進位要分清楚，來回要對得起來。

**契約**
- `solution.to_bytes(s: str) -> int`：接受 `"1.5 KiB"`、`"10MB"`、`"512"`、`"3 b"`。
  單位大小寫不敏感；`KiB/MiB/GiB/TiB` ＝ 1024 進位，`KB/MB/GB/TB` ＝ 1000 進位，
  無單位或 `B` ＝ bytes。小數容許；結果**向零截斷**成整數。
- `solution.humanize(n: int, *, binary: bool = True) -> str`：回傳
  `"<數字><空格><單位>"`，數字保留到小數 1 位（`.0` 要留），
  選最大的單位使數字 `< 進位基數`；`n < 基數` 時單位為 `B` 且不帶小數
  （例：`"512 B"`、`"1.0 KiB"`）。
- 負數、未知單位、空字串、多個單位 ⇒ `ValueError`。

可見 **3** 條｜隱藏 **13** 條

---

**核心集合計：12 題、可見 36 條、隱藏 167 條（中位數 14）。**

### 一-3　**題庫最終組成：20 題、兩層**（Fable 2026-09-13 裁決；v1 的「選配擴充」已被取代）

| 層 `stratum` | 題 | n | 這一層在問什麼 |
|---|---|---:|---|
| **`tight`** | `ow_01`…`ow_12`（§一-2）＋ `ow_13`…`ow_17`（新） | **17** | 契約把語意釘死、邊界情況多。**這是主指標的題型** |
| **`loose`** | `ow_18`／`ow_19`／`ow_20`（新） | **3** | **負向對照**：契約刻意只釘住呼叫面（簽名、回傳型別），語意留白；隱藏驗收考的是「整體設計有沒有把目標敘述講的困擾處理掉」，不是某一個邊界值 |

**為什麼要有 `loose` 層（Fable 裁決第 1 點，回應 v1 §九-4 我自己提的質疑）**：
v1 的 12 題**全部**是「契約釘死語意」的題型，而那正是回饋迴圈最擅長的形狀
——不放負向對照，收官時分不出「閘門有用」與「我們挑了對閘門有利的題」。
⚠ **代價事前寫死**：`loose` 題的隱藏驗收比較難通過 §五-2 第 1 條
（每條都要指得回目標或契約的某一句），**掉題的機率比 `tight` 高**。

**回填規則（本檔登記，內容由題庫代理產出）**：

1. `ow_13`…`ow_20` 由**題庫代理**依 §一-1 的五件東西寫完，格式與逐題明細落在它的
   `TASKS_TABLE.md`；本檔 §一-2 之後**原地補上八張與 `ow_01` 同格式的表**（目標敘述、
   契約、可見／隱藏條數、`stratum`）。
   ⚠ **回填時間點**：必須在 §五-2 複核**之前**、AMEND1 凍結**之前**、
   任何一通模型呼叫**之前**。回填只是把已寫好的東西抄進來，**不是**在本檔裡重新設計題目。
2. 作者與複核者**不得是同一個代理**（§五-2）。
3. 20 題 × **各檔案**（`task.md`／`visible.json`／`hidden.json`／`rubric.json`／
   `meta.json`／`reference/`／`template/`）的 sha256 在
   `DECISION_..._R530_AMEND1_BANK_FREEZE.md` 一起釘死。
4. **`stratum` 是 rows 的一個欄位**（`record_bank_field` 的 R530 版），逐列落盤。
5. **必須通過 §一-3b 的難度分佈擋門**（2026-09-13 補充裁決 (a)）。沒過就退回重寫。

### 一-3a　`stratum` 只做描述性拆分，**不進家族**（Fable 裁決第 1 點）

- 主指標的家族固定 4 格（§六-3），**不因為有兩層而變成 8 格**。
- 逐層的 `b_k`／`c_k`／`delta_frac` 照印（`paired.<seed>.<pair>.by_stratum.<tight|loose>.*`），
  **只當描述**：`loose` 只有 3 題，任何檢定在 n=3 上都不成立。
- ⚠ **禁句**：「在 loose 題上也成立／也不成立」。能講的只有
  「`loose` 那 3 題的逐題差是 …（逐題列出來，三筆）」。

### 一-3b　**難度分佈擋門**（2026-09-13 補充裁決 (a)；發射前、零模型呼叫）

**為什麼要有這一格**：§九-9 提的風險——那 8 題由另一個代理寫，
§一-3 的回填規則擋得住「格式不對」，擋不住「難度分佈與核心 12 題差很多」。
若新題明顯比核心題簡單，三條臂會一起撞天花板 ⇒ **檢定力被吃掉，
看起來卻像「效果變小」**。這兩件事在收官時分不開，所以要在發射前擋。

**兩個量，逐題記進 `meta.json`，定義事前寫死（不准事後改算法）：**

| 量 | 定義 | 誰算 |
|---|---|---|
| **`ref_solution_lines`** | 參考解所有 `.py` 檔，各自先做 `ast.unparse(ast.parse(src))` 正規化（去掉註解、空行、排版差異），再數**非空行**，加總 | 機器（確定性、可重跑） |
| **`boundary_only_hidden_n`** | 該題 `hidden.json` 裡被標成 `boundary_only: true` 的條數 | **§五-2 的複核者**（不是題目作者）逐條標 |

`boundary_only: true` 的判準**三選一，滿足任一即為真**（寫死，不准加第四條）：
(1) 輸入是空的／零長度；(2) 契約要求它**丟例外**；
(3) 輸入**恰好落在契約明講的邊界值上**（極值、進位點、視窗端點……）。
⚠ 判準之外的一律 `false`。標記者是複核者不是作者——**作者標自己的題會讓這個量失去意義**。

**擋門（fail-closed，對 `ow_13`…`ow_20` 這 8 題）：**

| # | 條件 | 不過怎麼辦 |
|---|---|---|
| **D1** | `median(ref_solution_lines, 新 8 題)` 與 `median(ref_solution_lines, 核心 12 題)` 的相對差 **> 40%** ⇒ 紅 <br>（相對差＝`|m_new − m_core| ÷ m_core`） | **整批退回題庫代理重寫** |
| **D2** | 任一新題 `hidden_n < 10`（`tight`）或 `< 5`（`loose`） ⇒ 紅 | **該題退回重寫** |

- 退回重寫之後**整組 D1／D2 重算**（改了一題會動到中位數）。
- ⚠ **重寫兩次仍然不過 ⇒ 停下來問 Fable**，不自行放寬（同 §一-6 第 6 條的形狀）。
- 擋門的結果（兩個中位數、相對差、逐題兩個量、紅／綠）**進 §五-2 的複核報告**
  `_fairness_review.json` 的 `difficulty_gate` 物件，並逐字抄進 AMEND1。

**這個擋門的誠實邊界（必帶）：**

1. **行數是難度的粗代理，不是難度。** 一個 12 行的解可以比 40 行的難想。
   D1 擋的是「分佈整體偏掉」這種**粗**的失衡，擋不掉逐題的難度錯配。
2. **40% 這條線是訂出來的，沒有外部錨。** 它寬到容得下 12 題自己的離散度、
   窄到擋得住「新題整批只有核心題一半長」。⚠ 它是**選擇**不是量測，收官要照實講。
3. **D1 只看新 8 題 vs 核心 12 題。** 它**不**保證 20 題整體的難度分佈是合理的
   ——§八-2 第 4 條（沒有人類逐題看過這 20 題）**沒有因為這個擋門而被解決**。
4. **`boundary_only_hidden_n` 目前只落盤、不設門檻。** 它是給收官做描述性分層用的
   （「增益是不是只來自邊界條」），事前**沒有**任何判準讀它。
   ⚠ 收官不准臨時拿它當門檻——那是看過數字之後設判準。

### 一-4　質化評分表（四維 × 1–5，逐級準則；**全部題目共用同一份**）

| 維度 | 1 | 3 | 5 |
|---|---|---|---|
| **可讀性** | 命名無意義、無註解且不需要註解也看不懂、單一函式超過 80 行 | 命名大致達意，結構看得懂，但有幾段需要重讀 | 讀一次就懂；命名與契約用詞一致；註解只出現在「為什麼」不是「做什麼」 |
| **結構** | 全部塞在一個函式／一個檔案裡且互相糾纏 | 有拆分但邊界隨意，重複邏輯出現 2 次以上 | 每個單元一個職責；沒有重複的邏輯；加一條新規則不必改三個地方 |
| **錯誤處理** | 例外訊息沒有指出哪裡錯；或用裸 `except:` 吞掉 | 契約要求的例外都丟了，訊息尚可 | 契約要求的例外都丟了，訊息指名輸入的哪一部分出錯；沒有吞例外；沒有把正常流程寫成例外 |
| **與目標的貼合度** | 做的事與目標敘述講的客戶困擾對不上 | 做到了契約，但目標敘述講的困擾只處理了一部分 | 目標敘述裡每一個客戶困擾都看得到對應的處理 |

⚠ **「與目標的貼合度」是四維裡唯一與隱藏驗收有部分重疊的一維**，
因此它**必然**與主指標相關，不可被引用成「質化獨立佐證了量化」（§八-8）。

### 一-5　題目來源：能舉證的是什麼、舉不了證的是什麼

**能舉證的（三件，全部可重算）：**

1. **這 12 段目標敘述、12 份契約、167 條隱藏驗收的逐字內容，落盤時間可查。** git commit sha＋時間戳＋逐檔 sha256 釘死；
   analyzer 與發射器都比對 sha256，對不上拒跑。
2. **隱藏驗收綁的是我們自己釘死的語意**，不是通用題目的通用解：
   `ow_01` 的 `line <N>: <reason>` 與 exit 2、`ow_05` 的具體度排序、
   `ow_08` 的 nearest-rank 定義、`ow_12` 的向零截斷與 `"512 B"` 格式……
   ⇒ **一份背下來的「CSV 轉 JSON」解，在沒讀我們的契約的情況下過不了那幾條。**
3. **發射前的反向檢索紀錄**：對每題的契約特徵字串做一次公開檢索，
   查詢字串、日期、前 N 筆結果與「為什麼都不是這一題」逐條落盤，
   走 `examples/archive_citations.py` 的三級規則（A 全文／B 僅摘要／人工核對）。
   查得到近似題**也照樣記下來**——記錄的目的不是拿到「零命中」這個結論。

**舉不了證的（必須逐字帶著，§八-3）：**

- **不可**宣稱「模型沒看過類似的任務」。CSV 轉 JSON、限流器、樣板引擎都是
  常見題型，`gemma-4-12b-it-qat` 的訓練資料裡幾乎確定有功能相近的東西。
- **這件事對本設計的影響方向是可以講清楚的**：污染抬高的是**題目層級**的基礎水準，
  而三條臂跑的是**同一題**、配對比較差分掉題目層級的東西
  ⇒ 污染是干擾項不是混淆項（沿用 R460 §二-2 的同一條理由）。
  ⚠ 但它有**一個**方向性後果不可忽略：若某題被模型完整記住，
  三條臂都會第一輪就通過 ⇒ 那一題對所有配對貢獻 0 個不一致對
  ⇒ **污染會壓縮檢定力，不會製造假效果。**

### 一-6　**最終成員由公平性複核決定**（Fable 裁決第 1 點，事前規則）

> **主指標的家族只吃通過 §五-2 公平性複核的題。**

規則逐條，**全部在發射前執行、發射後不得再動**：

1. 一題若有**任何一條**隱藏驗收指不回目標或契約的某一句，先走 §五-2 的修法
   （刪那一條、或把目標／契約改到指得回為止，改完重跑整張表）。
2. 修不動的題 ⇒ **整題在發射前剔除**，並在
   `ops/gain/data/openwork/_fairness_review.json` 的 `excluded` 陣列裡
   **記名**（`task_id`、哪一條指不回、為什麼修不動），同時逐字抄進 AMEND1。
3. 被剔除的題**不進工作區、不進任何 run、不進任何指標**——
   它不是「跑了但不算」，是**根本沒跑**。
4. ⚠ **剔除只能發生在發射之前。** 發射之後看到數字再剔題 ⇒ 本輪失敗（§六-8 第 1 條）。
5. **實際 n 逐 seed 印在 `bank.n_after_review` 與 `bank.excluded_task_ids`**，
   而且 §四-4 的檢定力表要**用實際 n 重算一次**印在 `power.recomputed_at_actual_n`
   ——事前的 n=20 那一版照留，兩個都印。
6. 若複核後 `tight` < 14 或 `loose` == 0 ⇒ **停下來問 Fable**，不自行發射
   （前者是檢定力掉太多，後者是負向對照整層消失，兩件事都改變了本檔的設計）。

---

## 二、臂與預算

### 二-1　三條臂（**三臂定案**。v1 的「兩臂版」已被裁掉，取捨紀錄留在附錄 A-2）

| 臂 | 全名 | 宣告完成之後發生什麼事 | 工作區 | persona |
|---|---|---|---|---|
| **`A-SOLO`** | 不用 Vacant | **收。** 宣告完成的那一刻，工作區就是最終交付。無閘門、無回饋、**不存在拒交** | 一個，從頭到尾 | 一位 |
| **`A-CONF`** | 用 Vacant，但只有閘門＋重抽 | 跑可見驗收。過 ⇒ 出貨。不過 ⇒ **工作區重置回樣板**、**換一位 persona**、**全新對話**（不告訴它上一次哪裡錯），最多 5 次嘗試；5 次都不過 ⇒ **拒交** | 每次嘗試一個全新的 | 每次嘗試換一位 |
| **`A-GATE`** | 用 Vacant（本 run 的主要假設） | 跑可見驗收。過 ⇒ 出貨。不過 ⇒ **把失敗原文貼回同一段對話**、**同一個工作區**、**同一位 persona**，最多 5 個閘門輪；5 輪都不過 ⇒ **拒交** | 一個，全程累積 | 一位 |

**主要假設＝`A-GATE` vs `A-SOLO`**（人類問的那一句）。
**`A-GATE` vs `A-CONF`** 是把「閘門本身」與「回饋迴圈」切開的那一刀
（R440P §二：選擇規則的天花板是候選池；R460 §一：迴圈是唯一在原理上能越過它的東西）。

### 二-2　**三條臂的 prompt 逐字相同**（鐵律 1／KS-1）

- system prompt、`TASK.md`、工具說明、工具 schema、`DENY` 清單——**逐字相同**。
- 差異**只有兩件**：(a) 宣告完成之後會不會有一則新的 user 訊息進來；
  (b) 那則訊息的內容是可見驗收的失敗原文（`A-GATE`）還是根本不存在（`A-SOLO`）；
  `A-CONF` 則是整段對話重開。
- **worker 事前不知道自己在哪一條臂。** 三條臂的第一則訊息完全一樣。
- 回饋模板沿用 `ops/gain/harness_arms.py` 的 `FEEDBACK_TEMPLATE`（:509）與
  `truncate_message`（:530，頭 1000 ＋尾 1000 字元）的語意，
  只換 `{block}` 的渲染（§二-5）。
- 所有新增的 prompt／回饋常數都要過 `vacant.memory.assert_ks1_clean`
  的 **import 時**斷言（沿用 `harness_arms.py:1144-1149` 的形狀）——
  寫出「你有責任／會被懲罰／有人在看」類措辭，模組就 import 不進來、run 起不來。

### 二-3　預算（**寫死成模組常數，不是 CLI 旋鈕**；三條臂同一份）

```python
OPENWORK_BUDGET = {
    "max_model_calls": 24,      # 每題每臂的模型呼叫總數上限（跨所有嘗試／輪次）
    "max_tokens": 120_000,      # 同上，累計
    "max_wall_s": 2_400,        # 在呼叫之間檢查，不是每題牆鐘的硬上界
    "max_gate_rounds": 5,       # A-GATE 的閘門輪上限／A-CONF 的嘗試上限
    "max_tool_calls": 40,       # run_bash 次數上限
    "tool_timeout_s": 120,      # 單一指令；模型可要求 1–300
    "gate_timeout_s": 60,       # 跑一次可見驗收的沙箱上限
    "nudge_budget": 2,          # 宣告完成但工作區空白時的推一把次數（沿用 localagent）
}
```

- **`max_model_calls=24` 三條臂共用同一個數字，這是本設計的骨幹。**
  `A-SOLO` 不會用完（預期 6–12 通，§四 P-W6），`A-GATE`／`A-CONF` 會用比較多。
  ⇒ **`A-GATE` vs `A-SOLO` 不是等預算比較**，而且**故意不是**：人類問的就是
  「收第一份」對「有閘門」。等預算那一刀由 `A-GATE` vs `A-CONF` 負責
  （兩者共用 24 通與 5 輪上限，§六-2）。這一段要原樣進收官（§八-4）。
- ⚠ **`max_wall_s` 不是每題牆鐘的上界**（沿用 R460 §二-3 的同一句誠實邊界）：
  它在呼叫之間檢查；單次請求在 `--request-timeout-s 900 --retries 4` 之下
  最壞可以燒掉約 4500 秒。收官報 `wall_s` 的分佈，不准講成硬上界。
- **不送 `max_tokens` 給端點。** 只有有閘門的臂設輸出上限的話，長答案會被砍而
  `A-SOLO` 不會，那是憑空造出來的劣勢（R460 §二-3 同一條）。
- `temperature` 三臂同值，事前釘死（`0.3`，沿用 `ops/localagent.py:153` 既有值），
  落盤在 `summary.request_policy`。

### 二-4　工具面（一個工具，沿用 `ops/localagent.py`）

- **`run_bash(command, timeout_s)` 一個工具**（`ops/localagent.py:67-87`）。
  理由逐字沿用該檔 docstring：12B 級模型工具越多越容易選錯，而讀檔、寫檔、
  跑指令、跑測試全都能經過 shell；附帶好處是每個動作都以**可重跑的指令**落盤。
- `DENY`（`ops/localagent.py:51-65`）**加碼**三條 R530 專用擋門：
  1. 任何跳出工作區的路徑（`..`／絕對路徑指到工作區之外）⇒ 擋；
  2. 任何可能觸網的指令（`curl`／`wget`／`pip`／`nc`／`ssh`／`git clone|fetch|pull|push`）⇒ 擋；
  3. 讀取 `hidden`／`rubric` 字樣路徑 ⇒ 擋，**並記成 V/GT 事件**（§五-3）。
  擋下來的指令**照樣落盤**（`blocked: true`），因為「模型試圖做什麼」比
  「模型做成了什麼」更值得留著看。
- **協定**：預設走**文字協定**（模型在圍欄區塊裡寫指令，harness 解析），
  不是 OpenAI 原生 `tools`。理由見 §三-4 的探針——
  `gemma-4-12b-it-qat` 在 LM Studio 上支不支援 function calling
  **本檔沒有量過**，而 R460 實測同一顆模型的圍欄遵循是 925/925。
  原生 `tools` 只有在發射前探針全綠時才啟用，而且**三條臂同時切換**，
  模式落盤在 `summary.tool_protocol`，兩種模式的資料**不得混算**
  （沿用 R460 §六-(6)-g 對 `harness_wire_mode` 的同一條）。

### 二-5　閘門的回饋長什麼樣（`A-GATE` 專用；`A-CONF` 一個字都不給）

可見驗收失敗時貼回去的 `{block}` 五種之一，**逐字模板事前凍結**：

| kind | 內容 |
|---|---|
| `assert` | `case <i>: <call or argv> got=<repr> want=<repr>` |
| `exception` | `case <i>: <ExcType>: <str(exc)>`（只給 `str(exc)`，不給 traceback 內部路徑） |
| `timeout` | `case <i>: the check did not finish within 60 seconds.` |
| `import` | `the module 'solution' could not be imported: <ExcType>: <str(exc)>` |
| `nofile` | `no file named solution.py or package named solution/ was found.` |

- **只給可見驗收的結果。** 隱藏驗收的存在、條數、內容一律不進回饋。
- 訊息長度走 `truncate_message`（頭 1000 ＋尾 1000），全文以 sha256 落盤。
- ⚠ **可見驗收的輸入與期望值本來就在工作區裡**（`examples/` 目錄），
  worker 可以自己讀、自己跑。這是設計要的（R460 §八-1 的同一件事），
  展場文案必須講（§八-5）。

---

## 三、工作區與後端

### 三-0　先回答人類那一句：**兩台還是一台分兩個工作區**

> 「去 linux 你看看是抓兩台還是找一台分兩個一模一樣的乾淨工作區」

**答案：工作區全部在一台（vacant-dev），兩台是兩顆推論後端。**

理由三條，都可驗：

1. **工作區放兩台 ⇒ 機器變成臂層級的混淆項。** 兩台的 CPU、磁碟、Python 版本、
   負載都不同，而沙箱逾時是計分路徑的一部分（R529 §一一-13 量過「同一題在不同塊
   之間判不一樣，第一個要查的是沙箱不是模型」）。放同一台，這個干擾項直接消失。
2. **工作區很小。** 樣板目錄約 10–30 KB；20 題 × 3 臂 × 3 seed ＝ **180 格**
   （另加 §三-6 的 6 格冒煙），`A-CONF` 每格最多 5 個工作區
   ⇒ 最壞約 660 個工作區、合計 < 200 MB。
   vacant-dev 剩 14 GB（§三-2 實測）⇒ 不是限制。
   ⚠ 這與「每格開一個 git worktree」完全不同：那台的 `Vacant` repo 是 2.1 GB
   （`runs/` 占 1.9 GB），worktree 路線 5–6 個就撐爆。**本設計不開 worktree。**
3. **兩台真正該拿來做的是推論。** 1003（`100.119.113.56:1234`）與
   1004（`100.86.226.21:1234`）各有一顆 `gemma-4-12b-it-qat`，
   兩邊 gguf 逐位元相同、`reasoning_effort=none`。
   **同一題的三條臂走同一台**（後端因此永遠是 task 層級的干擾項，
   不是 arm 層級的混淆項——R460 §二-2 的同一條，本 run 逐字沿用），
   題目在兩台之間輪流。

### 三-1　乾淨且逐位元相同的工作區

```
ops/gain/data/openwork/<task_id>/template/
  TASK.md          # goal + contract（唯讀給 worker 看的那一份）
  examples/        # 2–3 條可見驗收（可執行）
  run_examples.sh  # 一行：跑可見驗收並印結果（worker 可自己跑）
  .gitignore
```

- 建立方式：`cp -a <template>/. <cell_dir>/` 然後 `git init -q && git add -A &&
  git -c user.name=… -c user.email=… commit -q -m template`
  （**空 git 起點**，事後可 `git diff` 出 worker 到底動了什麼）。
- **起始狀態 sha256 落盤**：對 `{relpath: sha256}` 排序後取 Merkle 根，
  寫進 `rows.jsonl` 的 `workspace_start_sha256`。
  **180 格（最壞 660 個工作區）的這個值必須全部相同**——不同的處置見 §五-5 E-1
  （單格 void 並記名、≥2 格 `INVALID`）。
- **結束狀態也取一次**（`workspace_end_sha256`），連同工作區 tar.gz
  （`runs/<name>/ws/<task>_<arm>_<attempt>.tar.gz`）一起落盤。質化盲評與
  獨立重算都吃這一份。
- ⚠ `cp -a` 保留 mtime ⇒ Merkle 根只取**內容**不取 mtime，
  否則同一份樣板在不同時間複製會得到不同的值。

### 三-2　vacant-dev 的實測條件（2026-09-13，唯讀）

| 項 | 實測 | 對本 run 的意義 |
|---|---|---|
| OS | Ubuntu 24.04.4 LTS，kernel 6.8.0-137 | — |
| CPU／RAM | 8 vCPU（i9-12900K）、7.7 GiB RAM、swap 4 G 已用 2.8 G、loadavg 0.00 | 併發上限的依據（§七） |
| 磁碟 | `/` 與 `$HOME` 同一個 LV，38 G 總量、**剩 14 G**；`/dev/shm` 只剩 1.1 G | 工作區沒問題；**不要開 worktree** |
| Python | `/usr/bin/python3` **3.12.3**；**沒有任何 venv** | 隱藏驗收與沙箱只能用標準庫 |
| pip／venv | **都沒有**（`python3-venv`、`python3-pip` 皆未安裝） | ⇒ **不得依賴 pytest** |
| pytest | **沒有** | 驗收 runner 必須自寫（`unittest` 或沿用 `ops/run_tests_nopytest.py` 的形狀） |
| 沙箱 | `bwrap`／`firejail`／`docker`／`podman`／`nsjail` **全缺**；`unshare` 有，但 AppArmor 的 `kernel.apparmor_restrict_unprivileged_userns=1` 擋掉非特權 userns（實測 `write failed /proc/self/uid_map`） | **§三-3 的阻斷項** |
| sudo | `(ALL) NOPASSWD: ALL` | 補裝工具做得到，但那是**寫入操作**，本輪沒做 |
| `bubblewrap` | apt 可裝（noble-updates `0.9.0-1ubuntu0.1`） | §三-3 的建議路線 |
| ulimit -n | **1024** | 併發 4 串以內安全 |
| 後端 | 1003 `:1234` HTTP 200 / 3 ms；1004 `:1234` HTTP 200 / 31 ms；hub `:8765` 200 / 67 ms | 兩台都活著，**直連不走 hub** |
| 迴圈 | `~/vacant/STOP` 存在（0 bytes，09-05） | 24 小時迴圈目前是停的 |
| repo | `~/vacant/Vacant`（分支 `feat/v2-four-stages`，HEAD `34bb1a4`），工作樹**不乾淨** | 發射前要對帳（§五-5 E-6） |

### 三-3　沙箱：現況跑不了。**裁定 S1（bubblewrap），S2 是退路**，兩者都要在 PR-2 上驗過

worker 會在工作區裡跑它自己寫的指令，隱藏驗收也要在同一台跑。
`vacant/checks.py` 那顆沙箱（`_cpu_limits` RLIMIT_CPU/DATA/AS 128 MiB、
`python -I`、環境變數只留 `PATH/HOME/TMPDIR`、`killpg` 收尾、AST import 白名單）
是**單一程式碼字串**的沙箱，**跑不了一個目錄**，而且它對網路的隔離是間接的
（`socket` 不在白名單裡），對「模型自己寫的任意 bash」不成立。

**Fable 2026-09-13 裁決：走 S1（bubblewrap）。** 基建代理正在 vacant-dev 上安裝與驗證；
**S2 是退路（fallback），不是備選方案。**

| 路線 | 做法 | 代價 | 風險 |
|---|---|---|---|
| **S1（裁定）** | `sudo apt install bubblewrap`，之後以 `bwrap --unshare-net --unshare-pid --die-with-parent --ro-bind / / --bind <ws> <ws> --dev /dev --tmpfs /tmp --chdir <ws>` 跑每一條指令與每一次驗收 | 一次 apt（需網路，已驗 archive 可達）；要驗 Ubuntu 24.04 的 AppArmor 是否放行 bwrap 的 userns | 裝完不放行 ⇒ 退 S2 |
| **S2（退路）** | **專用的無特權使用者**（新建 `r530run`；**不是 `nobody`**——那是系統共用身分，拿它跑會與別的服務共享 uid）＋ `sudo unshare -n setpriv --reuid=r530run --regid=r530run --clear-groups`（root 起手開無網路命名空間、立刻降權）＋ `timeout` ＋ `RLIMIT_*` ＋ cwd 鎖在工作區 | 要建一個使用者（寫入操作，本輪沒做） | 起手是 root ⇒ 降權那一步若寫錯就是以 root 跑模型寫的碼。**這條路徑要在 PR-2 上逐字驗過**，不准「理論上可以」就上 |

**兩者都要落盤用了哪一種**（Fable 裁決第 5 點）：
`summary.backend_meta.sandbox` ∈ `{"bwrap", "setpriv_unshare"}`，
連同 `bwrap --version` 或 `util-linux` 版本、以及**實際執行的那一行命令模板**，
逐塊落盤。⇒ 收官引用任何沙箱相關的數字時，都指得出它是在哪一種隔離下量到的。
⚠ **六塊必須全部用同一種**（併進 `gates.E8_arm_symmetry` 驗），
中途換沙箱等於換實驗條件。

⚠ **不管走哪一條，這件事都要照實講**：`vacant/checks.py` 的 docstring 自己寫著
它是**應用層加固，不是對惡意程式碼的 OS 沙箱**。本 run 跑的是自家模型寫的程式碼，
威脅模型是「意外」不是「攻擊」，但**這一句不准在收官時被刪掉**。

### 三-4　發射前的四個探針（**零實驗資料、但要燒少量 token**，全綠才准發射）

| 探針 | 問什麼 | 全綠的意思 | 紅了怎麼辦 |
|---|---|---|---|
| **PR-1 工具協定** | `gemma-4-12b-it-qat` 在 LM Studio 上能不能跑多輪工具迴圈（原生 `tools` 與文字協定各試 20 輪） | 兩種模式各自的成功率與格式遵循率 | 原生 `tools` 不通 ⇒ **只用文字協定**（不是阻斷項） |
| **PR-2 沙箱** | S1 或 S2 在 vacant-dev 上能不能跑完一份參考解的可見＋隱藏驗收 | 兩條路線至少一條可用 | 都不行 ⇒ **阻斷發射** |
| **PR-3 量具（雙向）** | 對 12（或 20）題**逐題**驗：參考解要全過、每個已知壞樁都要被擋，可見與隱藏各驗一次 | `coverage_visible_n == coverage_n == n_tasks` | 任一題不滿 ⇒ **阻斷發射**（量不到不是通過，沿用 `vacant/suitegauge.py` 的單邊保證紀律） |
| **PR-4 能不能做完一題** | 讓 worker 跑一次 `ow_01`（丟掉，不進資料） | 24 通預算夠不夠一題 | 不夠 ⇒ 改預算並**重寫本檔**，不准跑起來再調 |

⚠ PR-1／PR-4 會燒模型呼叫。它們的 run 目錄一律 `runs/_probe/r530_*`，
**不進任何分析**，且 seed 與正式 run 不同。

### 三-5　塊、seed、後端分配

- **seed 三顆**：`g-r530-s1`／`g-r530-s2`／`g-r530-s3`。發射前掃兩台所有
  `runs/*/summary.json`，命中任何一個 ⇒ 停（`abort_seed_not_fresh`）。
- **seed 控制什麼、不控制什麼（誠實邊界）**：seed 決定題序與 persona 指派
  （`random.Random(f"{seed}:{arm}")`，沿用 `gain_run.py` 的形狀）。
  **它不會讓模型取樣變確定**——LM Studio 端沒有被本 run 釘住的取樣種子。
  ⇒ 三顆 seed ＝ **同一批題目的三次隨機重複**，不是三個獨立樣本（§六-5、§八-6）。
- **塊**：一顆 seed 切兩塊（題目 index 奇數／偶數），共 **6 塊**、每塊 10 題。
  ```
  R530_BLOCK: g_r530_ow_s1_odd   tasks=odd  n=10 seed=g-r530-s1 endpoint=1003
  R530_BLOCK: g_r530_ow_s1_even  tasks=even n=10 seed=g-r530-s1 endpoint=1004
  R530_BLOCK: g_r530_ow_s2_odd   tasks=odd  n=10 seed=g-r530-s2 endpoint=1004
  R530_BLOCK: g_r530_ow_s2_even  tasks=even n=10 seed=g-r530-s2 endpoint=1003
  R530_BLOCK: g_r530_ow_s3_odd   tasks=odd  n=10 seed=g-r530-s3 endpoint=1003
  R530_BLOCK: g_r530_ow_s3_even  tasks=even n=10 seed=g-r530-s3 endpoint=1004
  ```
  ⚠ `n=10` 是**複核前**的數字。§一-6 剔掉題之後兩塊會不等長，
  註冊行的 `n` 由 AMEND1 逐塊改寫（**改在發射前，而且是複核的機械後果，不是選擇**）。
  ⚠ 奇偶切分要讓 **`loose` 那 3 題不落在同一塊**（`ow_18`／`ow_19`／`ow_20`
  ＝偶／奇／偶）——否則某一塊掛掉時負向對照層會整層消失。
  **整組**逐字比對（不是逐項），沿用 R529 §二-2 的理由。
- **臂在塊內交錯**（`for task: for arm:`，round278 起的既有紀律）⇒
  同一題的三條臂**一定**打同一顆後端、落在同一個行程、同一段時間。
  中斷在任何時刻都留下三臂格數相等的可分析資料。

### 三-6　**冒煙：正式發射前必跑，逐格核對**（Fable 裁決第 6 點）

**規格**：**2 題 × 3 臂 × 1 顆 smoke seed ＝ 6 格**。

- 題：`ow_01`（`tight`）＋**一題 `loose`**——兩層各一，因為兩層的失敗形狀不同。
- seed：`g-r530-smoke`（**與三顆正式 seed 都不同**，同樣要過新鮮度掃描）。
- 輸出：`runs/_smoke/g_r530_smoke/`。
  ⚠ **`runs/_smoke/` 永不進證據**：不進 `runs/INDEX`、不進任何 analyzer、
  不進任何配對、不進 token 帳、不進質化。它的用途只有下面這張表。
- **不合格就不准發射**，而且修完要**重跑整份冒煙**（不是只補那一格）。

**逐格檢核表**（六格都要，落盤成 `runs/_smoke/checklist.json`）：

| # | 核對什麼 | 合格條件 | 不合格代表什麼 |
|---|---|---|---|
| **C1** | 模型呼叫數 | `calls_used` ≤ `max_model_calls`，且與 `calls.jsonl` 的筆數逐一對得上 | 預算會計沒接上 ⇒ token／成本帳全部不可信 |
| **C2** | 宣告完成的輪次 | `declared_done_turn` 有值；三條臂在同一題上的第一次宣告都偵測得到（值不必相同） | 偵測不到「宣告完成」⇒ `A-SOLO` 根本停不下來 |
| **C3** | 可見驗收結果 | 逐條落盤（pass／fail、`got`／`want`）；**`A-SOLO` 那格也要跑**（只記分、不當閘門、不回饋） | 沒有 `A-SOLO` 的可見結果 ⇒ P-W7／W7a／W7b 量不出來 |
| **C4** | 隱藏驗收結果 | 逐條落盤；`frac` 與 `deliv` 都算得出來；**條數與 `hidden.json` 相符** | 條數對不上 ⇒ 分母錯，主指標整個歪掉 |
| **C5** | 樹雜湊前後 | `workspace_start_sha256` 六格全同且等於樣板；`workspace_end_sha256` 有值且**至少一格與起點不同** | 起點不同 ⇒ E-1 紅；終點全同 ⇒ 工作區根本沒被寫入 |
| **C6** | 收據條數與驗鏈 | `openwork_verdict` 數 == 該格 row 數；`openwork_attempt` 數 ≥ verdict 數；`verify_run_receipts` 回 `OK`（不是 `UNVERIFIABLE`） | 見 §五-5 E-5 |
| **C7** | 沙箱身分 | `backend_meta.sandbox` 六格相同，且與 §三-3 裁定的那一種相符 | 中途換沙箱 ⇒ 換了實驗條件 |
| **C8** | V/GT | `--scope r530` 零未豁免命中；`DENY` 第 3 條零命中 | 隱藏驗收外洩 |

---

## 四、事前預測（P-W1…P-W13 ＋ 歸因結果 W7a／W7b）——**先寫死，收官逐條判 HIT／MISS**

仲裁量一律取 `ops/gain/analyze_r530.py --run <六塊> --json` 輸出的欄位，
**欄位名逐字寫在第三欄**（判準要指名它讀哪個 key，不准靠「工具印了什麼字串」）。
逐條分 seed 判，**三顆 seed 分開，不併 n**（§六-5）。

### 四-1　量化

| # | 預測 | 仲裁欄位 | 窗 | 錨／理由 |
|---|---|---|---|---|
| **P-W1** | `A-GATE` 的隱藏通過比例 > `A-SOLO`，三顆 seed 皆然 | `paired.<seed>.GATE_vs_SOLO.delta_frac` | **> 0**（三顆都要） | 閘門至少把「宣告完成但連可見範例都不過」那一類擋掉 |
| **P-W2** | `A-GATE` 的隱藏通過比例 > `A-CONF`，**至少兩顆 seed** | `paired.<seed>.GATE_vs_CONF.delta_frac` | **> 0**（≥2/3） | R460 在單函式題上量到 +13.33pp；專案題的失敗面更多樣 ⇒ 回饋能帶的資訊更多。**但只要求 2/3，因為 n≈20 的逐 seed 噪音仍然大** |
| **P-W3** | **`A-SOLO` 的拒交件數 ＝ 0**，而 `A-GATE`／`A-CONF` > 0 | `per_arm.<seed>.<ARM>.refusal_n` | SOLO ＝ 0；另兩臂 ≥ 1（三顆 seed 至少各有一臂 ≥1） | 結構上必然（SOLO 沒有拒交語意）。**這一條不是發現，是把設計講清楚**，寫在這裡是為了不讓收官把它當成結果 |
| **P-W4** | **假交付件數** `A-GATE` ≤ `A-CONF` + 1（每 seed；分母＝該 seed 複核後的實際題數） | `per_arm.<seed>.<ARM>.false_delivery_n` | ≤ +1 | R460 實測假交付從 29 降到 14（P-H4 預測寫錯方向）。本 run 沿用**實測**方向。⚠ 門檻是**件數**不是 pp，所以題數從 12 變 20 時它**變嚴了**——這是刻意的，寫在資料之前 |
| **P-W5** | `A-SOLO` 的「宣告完成但隱藏沒有全過」件數 **≥ 8**（20 題） | `per_arm.<seed>.SOLO.false_delivery_n` | ≥ 8 | 這是本 run 對展場最有用的一格：不用閘門時，錯的東西**全部**出貨。窗＝v1 的 5/12（41.7%）按比例換算到 20 題（8/20 ＝ 40%），**比例沒有放寬** |
| **P-W6** | 模型呼叫/題：`SOLO ∈ [4, 14]`、`GATE ∈ [8, 24]`、`CONF ∈ [8, 24]` | `per_arm.<seed>.<ARM>.calls_per_task` | 三條都要 | 24 通上限；SOLO 沒有續命機制 |
| **P-W7** | `A-SOLO` **自己跑過可見驗收**的題目比例 | `per_arm.<seed>.SOLO.self_ran_visible_pp` | **不設窗；落在哪一格由 §四-1a 的 W7a／W7b 事前命名** | 這是本 run 的主要歸因量。⚠ 「跑過」的操作型定義事前寫死：該格的工具呼叫紀錄裡出現**至少一次**成功執行 `run_examples.sh` 或直接執行 `examples/` 底下任一檔的指令（`blocked: true` 的不算），逐格布林值落盤在 `rows.jsonl` 的 `solo_self_ran_visible` |
| **P-W8** | 撞牆鐘／撞呼叫上限的比例 | `per_arm.<seed>.<ARM>.stop_reason_pp.budget_*` | **≤ 20%**（三條都要） | 專案題比單函式題長，20% 比 R460 的 5% 寬；寬的理由是任務形狀，不是為了容易 HIT |
| **P-W9** | 每塊 `infra_void / processed ≤ 10%` | 逐塊 `summary.json` | ≤ 10% | 多輪工具迴圈的 void 曝險比單函式高（§八-7）。⚠ §五-5 E-5 的「驗鏈失敗 ⇒ 該格 void」也算進這個分子 |
| **P-W10** | 三條臂的 `workspace_start_sha256` **全部相同**且等於樣板 | `gates.E1_workspace_identical` | 必須 `true` | 不同就不是同一個起點（處置見 §五-5 E-1） |

### 四-1a　**歸因結果 W7a／W7b：事前命名，收官只准照落在哪一格講**（Fable 裁決第 3 點）

P-W7 量到的 `per_arm.<seed>.SOLO.self_ran_visible_pp`（三顆 seed 取**中位數**，
欄位 `attribution.solo_self_ran_visible_pp_median`）落在哪一格，
**事前就把該講的話寫死**：

| 結果 | 觸發條件 | 收官**必須**照這一句講 |
|---|---|---|
| **W7a** | `attribution.solo_self_ran_visible_pp_median` **< 30%** | 「`A-SOLO` 在多數題目上**根本沒有自己跑過**客戶給的可見驗收（中位數 N%）。⇒ 本 run 量到的增益，**主要歸給『被要求驗證』這件事本身**，而不是回饋迴圈的內容。這與 R460 在單函式題上量到的『迴圈效果』**不是同一個東西**，兩者不可互引。」 |
| **W7b** | `attribution.solo_self_ran_visible_pp_median` **≥ 30%** | 「`A-SOLO` 在相當比例的題目上**自己跑過**可見驗收（中位數 N%）卻仍然落後。⇒ 本 run 量到的增益，**主要歸給閘門的拒交語意與修訂迴圈**，而不是『被要求驗證』。這一格與 R460 的迴圈效果同型，但仍然是不同任務形狀上的獨立量測。」 |

- **30% 這條線是事前訂的，理由寫在這裡**：低於三成 ⇒ 多數格子裡
  `A-SOLO` 與 `A-GATE` 的差**包含**「有沒有跑過驗收」這個一階差異，
  歸因不得只講迴圈；三成以上 ⇒ 那個一階差異在多數格子裡不存在，
  差異必須另有來源。**這條線不是門檻，不進四狀態**（§六-5 一格都不讀它）。
- ⚠ **收官不准「事後選」**：不准因為 W7a 的句子比較不好看就改讀別的欄位、
  不准改中位數為平均數、不准分 seed 挑一顆講。**三顆 seed 的值要全部印出來**
  （`attribution.solo_self_ran_visible_pp_by_seed`），中位數只是仲裁量。
- ⚠ 兩個句子**都是本 run 可以接受的結果**。W7a **不是**壞消息：
  「多數人不會主動驗自己的東西」正是 Vacant 這一層要處理的事
  （R440P §四的拒交閘門價值），只是它與「迴圈把錯的改對」是兩件事。

### 四-2　質化（**事前寫，但不進裁決**）

| # | 預測 | 仲裁欄位 | 窗 |
|---|---|---|---|
| **P-W11** | 四維總分 `A-GATE` ≥ `A-SOLO`，而且**「錯誤處理」那一維的差最大** | `rubric.<seed>.<dim>.<ARM>.mean` | 方向為主；「錯誤處理」的 Δ 是四維最大 |
| **P-W12** | **兩位跨模型盲評（J1 gemma × J2 qwen）的評審間一致性會低**：四維的**線性加權 Cohen's κ** **< 0.50** | `rubric.irr.kappa_<dim>`（主）／`rubric.irr.alpha_<dim>`（Krippendorff α, ordinal，併印）。**J3 不進這一條** | **< 0.50**（這是預測它不好，不是門檻） |
| **P-W13** | **至少一維會被判長度共線**（`max|rho| > 0.7`），而且**最可能是 readability** | `rubric.length_confound.<dim>.rho` | **≥1 維超標**；並事前登記「readability 是最可能的那一維」 |

P-W12 的理由要寫在前面：本 repo 自己量過模型評審票近乎常數函數
（R438／R516；R440P §三：評審 recall 3/21、3/13）。
**事前就預期質化量具很鈍**，收官不准把低一致性講成「資料壞掉」，
也不准把高一致性講成「盲評是可靠的量具」——n≈20 的 κ 本身就很吵。
（Fable 裁決第 7 點：κ 是主要報告量，α 併印；**≥2 分的分歧逐案列進收官附錄**，見 §五-6。
2026-09-13 **第三輪裁決 (1)**：J1＝gemma@1003、J2＝qwen@1004（跨模型）
⇒ κ 量的是**兩顆不同模型**的一致性；thinking 版降成選配的 J3，只做描述。
補充裁決 (b) 的「同模型」設計已被翻掉，理由＝同模型 temperature 0 在假資料上
量到 κ=1.000，是常數函數不是一致。）
P-W13 的理由：`A-GATE` 的產出天生比較長（多輪修訂留下的防呆與特判），
而「長的看起來比較用心」是質化評分最常見的假訊號。
⚠ P-W13 **HIT 不是壞消息**——它正是 §五-6 第 4b 項那個擋門存在的理由；
**MISS 才要多看一眼**（可能代表分數根本沒有在動）。

### 四-3　**過擬合可見驗收：方向與最可能翻車的地方，事前講清楚**

- 每題只有 **2–3 條**可見驗收，隱藏 ≥10 條 ⇒ 可見佔真需求的比例**比 MBPP+ 低**、
  與 LCB v2（2–4 條可見）相當。⇒ 過擬合空間**結構性地大**。
- 若 P-W4 要翻車（`A-GATE` 的假交付高於 `A-CONF`），事前預期會出現在
  **隱藏條數最多、可見條數佔比最低**的三題：`ow_02`（15）、`ow_04`（15）、`ow_05`（15），
  **以及 `loose` 那三題**（契約留白 ⇒ 可見驗收離真需求更遠 ⇒ 朝可見改的空間最大）。
  這一句寫在資料之前，收官不准反過來說「本來就預期那幾題會過擬合」。
- ⚠ `loose` 層只有 3 題 ⇒ 上面那句是**方向的事前登記**，不是可檢定的預測（§一-3a）。
- ⚠ **`A-GATE` 的回饋逐字包含可見驗收的 `got=`／`want=`**（§二-5）
  ⇒ 它比 `A-SOLO` 多看到的東西是**真的**，這不是偏誤而是機制本身，
  但展場文案必須講（§八-5）。

### 四-4　檢定力——**先講結論：McNemar 在這個 n 上不能當主指標；20 題是為了把 Wilcoxon 推過 0.80**

本機實跑（`vacant.research.mcnemar_power`，2026-09-13）：

| n | 大效果 `p_disc=.40 ψ=.85` | 中大 `.35/.80` | 中 `.30/.75` | 小 `.30/.667` |
|---:|---:|---:|---:|---:|
| 12 | 0.119 | 0.052 | 0.019 | 0.009 |
| 16 | 0.256 | 0.127 | 0.055 | 0.026 |
| 20 | 0.384 | 0.208 | 0.099 | 0.046 |
| 40 | 0.793 | 0.542 | 0.307 | 0.134 |

（α=0.05；n=12 時「b=6、c=0」才剛好 p=0.031 ⇒ 12 題裡要有**一半**是
單向不一致對才可能過。n=20 時最少也要 b=6、c=0。）

⇒ **精確 McNemar 在 n=12 或 n=20 上，對本 run 而言不是可用的主指標。**
⇒ Fable 裁決第 1 點選版本 D（20 題）的理由就在這張表與下一張表之間的落差，
不是「資料比較好看」。

**替代方案（本檔採用）：主指標改成逐題「隱藏驗收通過條數比例」的配對
精確 Wilcoxon signed-rank**（`vacant.research.wilcoxon_signed_rank_exact`，
n ≤ 24 走 2^n 全枚舉，是精確的）。本機蒙地卡羅（4000 次重複、
逐題通過比例取自 `{1.0, 1.0, .93, .86, .79, .71, .64, .5, .36, .21}`、
迴圈對未滿分題以機率 `p` 加 `Δ`、另有 8% 機率倒退 7pp）：

| 情境 | n=12 α=.05 | n=12 α=.025 | n=20 α=.05 | n=20 α=.025 |
|---|---:|---:|---:|---:|
| 強（75% 的未滿分題 +35pp） | Wilcoxon **0.682** ／ McNemar 0.083 | 0.470 ／ 0.028 | **0.968** ／ 0.478 | 0.926 ／ 0.291 |
| 中（55% +25pp） | **0.318** ／ 0.005 | 0.146 ／ 0.001 | **0.807** ／ 0.069 | 0.677 ／ 0.021 |
| 弱（35% +15pp） | 0.059 ／ 0.000 | 0.015 ／ 0.000 | **0.353** ／ 0.000 | 0.204 ／ 0.000 |

**⇒ 事前說死五件事：**

1. **主指標是比例（M1），不是全過（M2）。** M2 照印、照判、進四狀態的**點估計**
   那一格，但它**不是**顯著性的仲裁量。
2. **本 run 定案跑 20 題**（Fable 裁決第 1 點）。20 題在強／中兩種情境下
   Wilcoxon 都 ≥ 0.80（α=.05），這是選版本 D 的全部理由。
3. **12 題版被裁掉的理由留在這裡**：中等效果下只有 0.32 ⇒ 有三分之二的機會白跑，
   而那會產生一個 `INCONCLUSIVE`，之後被引用成「量過了」。
4. ⚠ **實際 n 會小於 20**（§一-6 的複核剔除）。
   **收官必須用實際 n 重算一次這兩張表**，印在 `power.recomputed_at_actual_n`，
   事前這一版照留、兩個都印。若實際 n 掉到 14 以下 ⇒ §一-6 第 6 條，停下來問 Fable。
   ⚠ 分層之後 `tight`≈17、`loose`=3 —— **逐層的檢定力不要算**，
   n=3 沒有可算的東西（§一-3a）。
5. 上表的模擬**不是**本 run 的效果量預測——它是「若效果長這樣，量不量得到」。
   通過比例的分佈是**我編的**，真值未知。這一句要跟著表一起被引用。

---

## 五、量具與稽核

### 五-1　驗收 runner（**vacant-dev 沒有 pytest，必須自寫**）

- 隱藏／可見驗收是**資料**（`visible.json`／`hidden.json`），
  runner 只跑自己渲染出來的碼——沿用 `vacant/suitespec.py`（R452）的紀律：
  有狀態測試／雜湊黑名單／擬態三種攻擊在資料形狀下**不可表達**。
- 兩種 case shape（本 run 新增第三種 dialect，`suitespec` 的
  `DIALECTS = ("mbpp","lcb")` 涵蓋不到）：
  ```
  {"kind":"call", "target":"csv_to_jsonl", "args":[...], "kwargs":{...},
   "expected":<literal>, "raises":"ValueError"|null, "match":"eq"|"set"|"approx"}
  {"kind":"cli",  "argv":[...], "stdin":"...", "files":{...},
   "expect_stdout":"...", "expect_stderr_re":"...", "expect_exit":0}
  ```
  兩種都只吃 `ast.literal_eval` 收得下的字面值（`validate` 沿用 `suitespec.py:517`）。
- **`vacant/suitegauge.py` 的單邊保證逐字適用**：擋得住已知壞解 ≠ 涵蓋真需求。
  不准讀成「驗收套件固定點已解」。

### 五-2　**規格公平性複核**（發射前，獨立代理，零模型呼叫以外的資料）

一位**不是題目作者**的代理，對每一題產出一張對照表：

| 欄 | 內容 |
|---|---|
| `hidden_id` | 隱藏驗收編號 |
| `anchor_kind` | `goal` / `contract` |
| `anchor_quote` | **逐字引用**目標敘述或契約裡的哪一句 |
| `derivation` | 一句話說明「從那一句怎麼推到這一條」 |

**擋門（三條，全部 fail-closed）：**

0. **這張表決定題庫的最終成員**（Fable 裁決第 1 點）。沒通過的題在發射前剔除、
   記名、不進任何指標——逐條規則寫在 **§一-6**，兩節是同一件事的兩半。
0b. **複核者同時要做 §一-3b 的兩件事**：逐條標 `boundary_only`、
   跑一次 D1／D2 擋門。**順序寫死**：先跑 §一-3b（不過就退回重寫，
   根本還輪不到看 anchor），過了才做下面的 anchor 對照表。
1. **每一條隱藏驗收都要有 anchor。** 指不到 ⇒ 該條**刪掉**，或把目標／契約
   改到指得到為止（改完要重跑整張表）。
2. **反向也要查**：目標敘述裡的每一句「客戶困擾」至少要有一條隱藏驗收對應。
   對不到 ⇒ 那句話是**沒有被量到的需求**，要嘛補驗收、要嘛從目標敘述刪掉
   （留著＝在計分之外偷偷加難度）。
3. **可見驗收不得與任一條隱藏驗收逐字相同**（`args`／`expected` 全同）。
   相同 ⇒ 那一條隱藏驗收是白送的，要換掉。
   ⚠ 但可見與隱藏**可以測同一個需求的不同輸入**——那是設計，不是重複。

複核結果落盤 `ops/gain/data/openwork/_fairness_review.json`，
sha256 進 AMEND1；analyzer 比對不上就拒跑。
檔案裡要有三個陣列 ＋ 一個物件，**四個都不准空著不寫**：
`passed`（進題庫的 `task_id`）、`excluded`（剔除的，逐題附理由）、
`amended`（改過目標／契約才過的，附改了哪一句）、
**`difficulty_gate`**（§一-3b 的擋門結果：兩個中位數、相對差、D1／D2 紅綠、
逐題的 `ref_solution_lines` 與 `boundary_only_hidden_n`、退回重寫過幾次）。
⚠ **`boundary_only` 的逐條標記由複核者做**（§一-3b），不是題目作者，
所以它天然落在這份報告裡而不是 `hidden.json` 的作者欄。
⚠ `amended` 不是瑕疵紀錄，是**題目定稿的過程**——但它必須看得見，
否則「複核通過」會變成一個沒有內容的印章。
⚠ **`loose` 層的複核要特別記**：契約留白 ⇒ anchor 更常指到**目標敘述**而不是契約。
那是設計要的，不是複核放水；但逐題要寫清楚指到哪一句（§一-3 的代價那一段）。

### 五-3　V/GT 紅線與**動態稽核**（多輪工作區版）

既有的 `ops/gain/harness_vgt_audit.py` **擋不住這個實驗的洩漏面**，
理由逐條（不是猜的，是讀過那支的結構）：

| 既有能力 | R530 需要的 | 差在哪 |
|---|---|---|
| 逐筆掃 `calls.jsonl` 的 `messages`／`prompt`，按 `system`／`user`／`assistant` 歸戶；`split_flattened` 能還原 flatten 過的多輪 | 同左 | **可直接沿用** |
| needle 來源＝`task["hidden_check"]["code"]` 解析成 `lcb`／`mbpp` 兩種字面形狀，認不出來就 `SystemExit` 不亂猜 | needle 來源改成 `hidden.json` 的 `args`／`expected`／`expect_stdout` 字面值 | **要加第三種 dialect**；不加就會撞 `hidden_only_needles` 的 `SystemExit` |
| role 分類只有 `system`／`user`／`assistant` | 多一個 **`tool`** role：工具回傳的 stdout 也是模型讀到的文字 | **缺** |
| 沒有「模型從檔案讀到什麼」的概念 | worker 可以 `cat` 工作區任何檔案 ⇒ **檔案內容是洩漏通道** | **缺** |

⇒ 本 run 的 V/GT 稽核要做三件事（`--scope r530`）：

1. **隱藏驗收永遠不在工作區裡**（結構性保證）：`hidden.json` 從不被複製進
   `<cell_dir>`，驗收在工作區被**凍結並 tar 之後**、在另一個目錄跑。
2. **掃 `calls.jsonl` 的四種 role**（含 `tool`），對每一條
   `hidden \ visible` 的 `repr(args)`／`repr(expected)` 找 needle。
3. **掃工作區結束狀態的所有檔案內容**：worker 寫出來的檔案若含隱藏驗收的
   字面值，那要嘛是洩漏、要嘛是它猜對了——**兩者分不開**，所以規則是
   **只記錄不判定**，並逐題列進收官報告（`vgt.workspace_needle_hits`）。
   ⚠ 這一條是**已知的量具弱點**，不是漏洞被補起來了：
   「它自己想到同一個邊界情況」與「它看到了」在字面比對下同形。
4. **`DENY` 的第 3 條**（讀 `hidden`／`rubric` 路徑）命中要記成
   `vgt.deny_hidden_read_n`，任一次命中 ⇒ 逐案人工看過才准結算。

**豁免機制**沿用既有的 `needle_excuse`／`redact_harness_text`／`EXCUSE_RULES`：
harness 自己寫的字（回饋模板、可見驗收原文）要被排除，而且**豁免要落盤**，
不是靜靜地遮掉。

### 五-4　收據鏈（多輪工作區版）

- 記錄型別新增兩種（`etype` 是自由字串，既有 `Logbook` 不必改）：
  `openwork_attempt`（每一個閘門輪／每一次重抽嘗試一筆）、
  `openwork_verdict`（每格一筆）。
- ⚠ **`vacant/logbook.py:34` 的 `MAX_PAYLOAD_BYTES = 64 KiB` 是硬限制**，
  而一輪工作區記錄（指令、完整 stdout/stderr、檔案 diff）很容易超過。
  ⇒ **簽 digest，全文進 `calls.jsonl`**——沿用 `harness_arms._append_turn`
  （:1132）把 `fail_message` 換成 `fail_message_full_sha256` 的同一手法。
- **新增一樣既有機制沒有的東西：工作區樹雜湊**（`{relpath: sha256}` 排序後的
  Merkle 根）逐輪簽進鏈。沒有它，收據只佐證「模型說了什麼」，
  佐證不了「工作區當時長什麼樣」。
- 驗證沿用 `ops/gain/replay/verify_run_receipts.py` 的**三值裁決**
  `OK` / `BROKEN` / `UNVERIFIABLE`（不准塌成兩值）與數量對帳
  （verdict 數 == 該臂 row 數、`attempt` 數 ≥ verdict 數）。
- ⚠ **誠實邊界逐字沿用 `gain_run.py:686-689`**：金鑰是一次性匿名身分，
  這條鏈能說的是「事後沒有被改過」，**不是**「由某個已知的人簽的」。

### 五-5　效力前提 E-1…E-8（**不是預測，是「這份資料算不算數」的擋門**）

任一條紅 ⇒ 狀態 `INVALID`，**先修或先揭露，不准先判**。
⚠ **E-1 與 E-5 是唯二有「單格降級」路徑的擋門**（Fable 裁決第 4 點）：
一格壞掉不代表整份資料壞掉，但**兩格就代表機制本身不可靠**，那時候
「哪幾格壞了」不再是個案而是系統性問題。
⚠ 被 void 掉的格子**照 complete-case 規則退出配對**（該題的三條臂只要有一條 void，
那一題就退出**所有**涉及該臂的配對），並計進 P-W9 的 void 率。
⚠ **`gates.E*_offending_cells` 一律逐格記名**（`seed`／`task_id`／`arm`／`attempt`）。
「有幾格壞掉」不准只報一個數字。

| # | 擋門 | 仲裁欄位 |
|---|---|---|
| **E-1** | 所有工作區起點雜湊相同**且等於樣板**。⚠ 處置與 E-5 相同（Fable 裁決第 4 點）：**單一格**不一致 ⇒ **該格 void（不計）並記名**；**≥2 格** ⇒ 整個 run `INVALID` | `gates.E1_workspace_identical`、`gates.E1_offending_cells` |
| **E-2** | 題庫四種檔案的 sha256 與 AMEND1 逐字相符 | `gates.E2_bank_sha_match` |
| **E-3** | PR-3 雙向量具全綠（參考解全過、壞樁全擋、可見覆蓋 == 題數） | `gates.E3_instrument` |
| **E-4** | V/GT 稽核無未豁免命中（§五-3 第 2 項）；第 3、4 項有命中時已逐案人工看過 | `gates.E4_vgt` |
| **E-5** | 收據鏈逐格驗證。**單一格**回 `BROKEN` 或 `UNVERIFIABLE` ⇒ **該格 void（不計）並記名**；**≥2 格** ⇒ 整個 run `INVALID`（Fable 裁決第 4 點） | `gates.E5_receipts`、`gates.E5_offending_cells`、`gates.E5_void_n` |
| **E-6** | 六塊的 `runner_git_info` 指到同一個 commit，且 `dirty == false` | `gates.E6_runner_git` |
| **E-7** | 六塊齊全、`topology.blocks_n == 6`、每題的三臂在同一顆後端 | `gates.E7_topology` |
| **E-8** | 三條臂的 `tool_protocol` 與 `request_policy` 逐欄相同 | `gates.E8_arm_symmetry` |

### 五-6　質化盲評管線（**repo 裡目前不存在，要新建**）

repo 裡**沒有**任何「模型在不知道臂別的情況下評分」的東西
（既有的 `blind` 都是指「預測寫在看到答案之前」；`multiway.py:102` 的
`hide_reputation` 是最接近的結構先例）。本 run 要新建，規格如下：

1. **去識別化**（確定性、可重跑）：
   - 工作區 tar 解開 → 目錄改名 `submission_<sha256[:8]>`；
   - 刪 `.git/`（含所有 commit 訊息）、刪 `TASK.md`、刪 `examples/`；
   - 檔案 mtime 一律歸零；
   - **掃「洩漏臂別的字串」**（事前凍結的清單：`acceptance`、`gate`、
     `attempt`、`retry`、`round 2`、`the tests said`、`失敗原文`…）——
     命中就**整包退出質化**並計數 `rubric.deident_dropped_n`。
     ⚠ 這不是把它遮掉：遮掉會改變被評的東西。

1a. **豁免機制（2026-09-13 第三輪裁決 (3)，追認盲評管線代理的實作）**：

   掃描清單裡的字樣有一種**合法**的出現方式——**題目自己的凍結文字**。
   worker 常常把 `TASK.md` 或可見驗收裡的句子抄進自己的註解、docstring、README，
   而那些字是**題目給的、三條臂都拿得到**，不帶任何臂別資訊。

   | 情形 | 處置 |
   |---|---|
   | 字樣**逐字出現在該題的 `task.md`／`visible.json`／`rubric.json`** 裡 | **豁免**（不丟格），但**逐筆落盤** `rubric.deident_excuses[]`（`task_id`、`arm`、命中的字樣、豁免依據指到哪一份凍結檔的哪一行） |
   | **臂名**（`SOLO`／`CONF`／`GATE`／`A-SOLO`…） | **永不豁免** |
   | **`.vacant`** | **永不豁免** |
   | **`r530`**（任何大小寫） | **永不豁免** |
   | **路徑含 `hidden` 或 `rubric`** | **永不豁免**（這一條同時是 §五-3 的 V/GT 訊號） |

   ⚠ 豁免**必須落盤**，不是靜靜地放過去——沿用 §五-3 既有的
   `needle_excuse`／`EXCUSE_RULES` 同一條紀律：**遮掉什麼、放過什麼，都要看得見**。
   ⚠ 「永不豁免」那四列**不看它出現在哪裡**：就算題目自己的文字裡有，也照樣丟格。
   那四個字樣本來就不該出現在題目裡，出現了就是題庫有問題，不是提交有問題。

1b. **丟格對等擋門（2026-09-13 第三輪裁決 (3)，事前規則）**：

   去識別化丟格**本身可能有臂別偏誤**——`A-GATE` 的產出比較可能寫出
   「the tests said …」這種句子 ⇒ 它被丟掉的格子比較多 ⇒ **剩下來被評的那些
   `A-GATE` 提交是倖存者**，而倖存者偏誤會往哪個方向走，本 run 量不到。

   | 條件 | 處置 |
   |---|---|
   | **同一顆 seed 內，逐臂丟格數的最大值與最小值相差 ≥ 2** | **該 seed 的質化段標「不可引用（去識別化丟格不對等）」**，只印丟格表（`rubric.<seed>.dropped_by_arm`），**分數、κ、逐維平均一律不印、不引用** |
   | **三顆 seed 全部不可引用** | **質化整段只留丟格表**——沒有質化結論，而且要逐字寫「本 run 的質化段因為去識別化丟格不對等而作廢」 |
   | 其餘 | 照常，但 `dropped_by_arm` **仍然要印** |

   ⚠ 仲裁欄位 `rubric.<seed>.dropped_by_arm.{SOLO,CONF,GATE}` 與
   `rubric.<seed>.qualitative_citable`（布林）。
   ⚠ **「≥2」是件數不是比例**：20 題之下差 2 格就是差 10%，而質化的 n 本來就小。
   ⚠ 這一條**不影響量化**——丟格只發生在質化管線，`rows.jsonl` 與所有主指標
   一格都不動。

2. **順序隨機**：每位評審看到的提交順序由評審自己的 seed 決定。
3. **兩位計入 κ 的評審 J1／J2：跨模型**（2026-09-13 第三輪裁決 (1)；
   **翻掉**補充裁決 (b) 的「同模型」設計，理由在下面第一顆項目符號）。

   | 評審 | 模型 | 後端 | 推理 | temperature | seed | 進 κ 主表 |
   |---|---|---|---|---|---|---|
   | **J1** | **`gemma-4-12b-it-qat`** | **1003** | `reasoning_effort=none` | **0** | `g-r530-j1` | **是** |
   | **J2** | **`qwen/qwen3.8-27b`** | **1004**（**run 收完、gemma 卸載後才載入**） | 非 thinking（**若該顆可設**；設不了就照實記） | **0** | `g-r530-j2` | **是** |
   | **J3（選配）** | `gemma-4-12b-it-qat` | 1003 | **thinking** | 0 | `g-r530-j3` | **否** |

   - **為什麼從「同模型」翻成「跨模型」**——盲評管線代理交付後量到的東西，
     不是推理出來的：**同一顆模型、同樣 temperature 0 的兩位評審，
     在假資料上 κ = 1.000**。那不是「一致」，那是**常數函數**
     ——兩次取樣根本沒有獨立性可言，κ 這個數字在那個配置下量不到東西
     （與 R438／R516／R440P §三「評審票近乎常數函數」是同一個病）。
   - **第二個理由：worker 自己就是 `gemma-4-12b-it-qat`。**
     用同家族的模型當唯一的評審，等於讓同一顆模型評自己的產出風格
     ⇒ **需要一個非同家族的第二視角**，那就是 J2。
   - ⇒ **κ 的意義改寫成這一句，逐字寫死**：
     > **「κ 量的是：兩顆不同的模型，對同一份提交給出的分數有多一致。」**
     它**不是**「重現性」（那是被翻掉的舊設計量的東西），
     也**不是**「這把尺有多準」——κ 高只代表兩顆模型看法接近，不代表看得對。
     這一句每次引用 κ 都要帶（§八-8）。
   - ⚠ **J1 與 worker 同一顆模型，這是本設計已知的不對稱**：
     J1 可能對 gemma 風格的產出有系統性偏好，J2 沒有這個問題。
     ⇒ **κ 低的時候分不開**「兩顆模型看法本來就不同」與「J1 有家族偏好」。
     ⇒ 收官必須**逐位分開報**每一維的平均分（`rubric.<seed>.<dim>.<ARM>.mean_by_grader`），
     不准只報兩位平均之後的值。
   - ⚠ **排程硬約束（VRAM）**：1004 上的 `gemma-4-12b-it-qat` 與
     `qwen/qwen3.8-27b` **不能同時載入**（本 repo 既有教訓：gemma 被 qwen 佔掉 VRAM 而死）。
     ⇒ **質化盲評整段必須排在正式 run（含任何補跑）全部收完之後**，
     由人類或發射者確認 1004 已卸載 gemma 再載 qwen。
     ⇒ 質化**不能**與 run 併行，這一點進 §七-2 的時程。
   - **J3 是選配的第二視角**（gemma 開 thinking），**只做描述、不進 κ 主表、不進任何裁決**。
     它的用途只有一個：看「同一顆模型開了推理之後會不會系統性地給不同的分」。
     落盤在 `rubric.j3.*`（與 `rubric.irr.*` **不同的命名空間**，免得被誤讀成主表的一部分）。
     ⚠ **J3 跑不跑都可以**（機時不夠就不跑，那不是缺資料）；跑了就要照實印，
     **不准**因為 J3 的方向比較好看就拿它取代 J1 或 J2。
   - `rubric.graders[]` 逐位記 `model`／`endpoint`／`reasoning_effort`／`temperature`／
     `seed`／`in_kappa`，**temperature 一律 0 且一律落盤**
     （設不了 `reasoning_effort` 的那一顆，要把「設不了」這件事本身記下來）。
   - 三位評審看到的提交順序各自由自己的 seed 決定（第 2 項）。
   - ⚠ **κ = 1.000 那個發現本身要進收官報告**（`rubric.irr.note_same_model_kappa_1000`）：
     它是本輪唯一一個「量具在假資料上就已經壞掉」的紀錄，
     刪掉它等於讓後來的人不知道這裡曾經差點用錯配置。
4. **一致性**：**線性加權 Cohen's κ 逐維算**（主要報告量，**只用 J1 × J2**），
   Krippendorff α（ordinal）併印。
   **≥2 分的分歧逐案列進收官附錄**（`rubric.disagreements`：`task_id`（去識別後的
   代號）、維度、J1／J2 的分數、兩段評語原文）——那張清單比 κ 這個數字有用得多。
   ⚠ J3 若有跑，它與 J1／J2 的 ≥2 分分歧**另外列一張表**（`rubric.j3_disagreements`），
   **不併進上面那一張**。
4b. **長度共線檢查**（2026-09-13 第三輪裁決 (2)，**事前規則**）：

   質化分數最常見的假訊號是「長的看起來比較用心」。而 `A-GATE` 的產出
   **天生比較長**（修過好幾輪、多了防呆與特判，§五-6 末的已知弱點）
   ⇒ 若某一維的分數其實在量長度，那一維拿來比較臂就是在量
   「哪一臂寫得多」而不是「哪一臂寫得好」。

   - **量什麼**：`rubric.length_confound.<dim>.rho`
     ＝ 該維的分數與**提交長度**的 **Spearman 秩相關**。
   - **提交長度的定義事前寫死**：去識別化之後、**評審實際看得到的所有檔案**
     內容合計的**非空白字元數**（`len("".join(text.split()))`），
     逐份落盤 `rubric.submission_chars`。
     （另印行數版 `rubric.submission_lines` 當穩健性參考，**不進判準**。）
   - **怎麼算**：逐 seed × 逐維 × 逐評審各算一次；
     判準取 **`max(|rho_J1|, |rho_J2|)` 在三顆 seed 上的最大值**（fail-closed
     ——任何一位評審、任何一顆 seed 上共線就算共線）。
     實作**重用既有的** `ops/gain/r497_segment_composition.py:123` 的 `spearman`
     （含 tie 處理與課本值自檢，§七-3 W8 不必重寫一份）。
   - **門檻與處置（逐維獨立判）**：

     | 條件 | 處置 |
     |---|---|
     | **`rho > 0.7`** | 該維**只准寫「與長度高度共線」**，**不准用它講任何臂比較**（含逐維平均分、四維總分裡的那一格、P-W11 的判定） |
     | `rho < −0.7` | **同樣處置**（⚠ 這一格是我加的，不在裁決原文裡：負向共線同樣代表那一維在講長度。標出來讓 Fable 確認） |
     | 其餘 | 照常引用，但 `rho` **仍然要印在該維旁邊** |

   - ⚠ **「readability 特別容易中」是事前預期**（裁決原文點名它），
     但門檻**四維一律相同**，不是只擋 readability。
   - ⚠ 被擋掉的維度**不是資料壞掉**，它是一個結論：
     「這把尺在這一維上量的是長度」。收官要照實這樣寫。
   - ⚠ 這一格**不進四狀態**（§六-6），它只決定質化那一段哪些話可以寫。

5. **Fable 人工抽讀**：每題每臂抽 1 份（20 題 × 3 臂 ＝ **60 份**），寫質化註記。
   **這一份是給人讀的，不進任何統計。**
   ⚠ 抽樣要**涵蓋 `loose` 那 3 題**（3 題 × 3 臂 ＝ 9 份全讀）——
   量化那邊對 `loose` 什麼都不能說（§一-3a），人工註記是那一層唯一的產出。

⚠ **盲評的已知弱點，事前寫死**：`A-GATE` 的產出天生更可能帶有
「修過好幾輪」的痕跡（多餘的防呆、針對某個 case 的特判）。
去識別化擋得掉**字串**，擋不掉**風格**。
⇒ **盲評不是「評審不知道臂別」，只是「評審沒有被明說」。** 這一句不准被簡化掉。

---

## 六、決策規則（**在任何 r530 資料之前寫死**）

前提：E-1…E-8 全綠。任一紅 ⇒ `INVALID`，**不准先判**。

### 六-0　配對的基本口徑

- **主指標的題目集合 ＝ §五-2 複核通過的那一批**（Fable 裁決第 1 點）。
  被剔除的題根本沒跑，所以它不是「排除」也不是「遺漏值」——
  分母裡從一開始就沒有它。`bank.n_after_review` 與 `bank.excluded_task_ids`
  在每一份報表的最上面印一次。
- **`stratum`（`tight`／`loose`）只做描述性拆分，不進家族、不改任何裁決**（§一-3a）。
- **配對單位＝`task_id`，分 seed 判，不跨 seed 配對。**
- 分母＝**complete case**：`n_common = |rows[A].task_id ∩ rows[B].task_id|`，**逐對印**。
  （void 的格子不寫 row，沿用 `gain_run.py:1922-1932`。）
- **成功的兩個定義，兩個都要印**：
  - `frac` ＝ 隱藏驗收**通過條數 ÷ 總條數**（0..1，逐題）；
  - `deliv` ＝ `accepted ∧ (frac == 1.0)`（R667 凍結口徑的 R530 版：出貨且全過）。
  ⚠ `A-SOLO` 的 `accepted` **恆為 true**（沒有拒交語意）——這件事在每一次引用
  `deliv` 的時候都要跟著講（§八-4）。

### 六-1　**主指標 M1 ＝ `frac` 的配對精確 Wilcoxon signed-rank**

- `diffs = [frac_GATE(t) − frac_X(t) for t in 共同題]`，
  丟 `vacant.research.wilcoxon_signed_rank_exact`（n ≤ 24 ⇒ `method == "exact"`，
  **必須逐次確認這個欄位是 `exact`**，掉到 `normal_approx` 就是 n 超過 24，
  那代表題數被動過）。
- 仲裁欄位：`primary.<seed>.<pair>.M1.w_plus` / `.n` / `.p` / `.method` / `.p_adj`。
- ⚠ **`frac` 的顆粒度逐題不同**（`tight` 每條值 1/10–1/15，`loose` 每條值 1/5–1/8）
  ⇒ 同樣「差一條」在 `loose` 題上會產生**比較大的 `|diff|`**，而 Wilcoxon 排的就是
  `|diff|` 的秩 ⇒ **`loose` 那 3 題在主指標裡的權重天生偏高**。
  這件事寫在資料之前；緩解只有一個且是描述性的：`primary.*.M1` 旁邊必印
  **把 3 題 `loose` 拿掉重算一次**的敏感度值（`primary.<seed>.<pair>.M1_tight_only.*`）。
  ⚠ **仲裁量仍然是含 `loose` 的那一個**（20 題全用），`M1_tight_only` 只是必報的次要量
  ——事前就說死哪一個是仲裁量，收官才不能挑（R460 §三-C 的同一條紀律）。

### 六-2　**次主指標 M2 ＝ `deliv` 的精確 McNemar**

- `b`／`c`／`n_discordant`／`p = vacant.research.mcnemar_exact(b, c)`。
- 仲裁欄位 `primary.<seed>.<pair>.M2.*`。
- ⚠ **M2 在 n≈20 的檢定力是 0.000–0.48（§四-4），中等效果下只有 0.069。**
  它進四狀態的**點估計**那一格，**不是**顯著性的仲裁量。
  收官不准寫「M2 不顯著 ⇒ 沒有效果」。

### 六-3　家族與 Holm

- **家族 ＝ 4**（`{GATE_vs_SOLO, GATE_vs_CONF} × {M1, M2}`），
  **在每一顆 seed 內各跑一次 Holm**，α=0.05。
- **家族只吃 §五-2 複核通過的題**（Fable 裁決第 1 點）。
- 仲裁欄位 `holm.<seed>.<pair>.<metric>.p_adj`、`holm.family_size`（**必須等於 4**）。
- ⚠ 家族固定 4。**不准**因為某一格「反正一定不顯著」就抽掉再重算。
- ⚠ **`stratum` 不進家族**：家族**不會**因為分成 `tight`／`loose` 兩層而變成 8 格。
  逐層的數字是描述性的（§一-3a），**不算 p、不進 Holm**。
- （v1 的「兩臂版家族 ＝ 2」已隨兩臂版一起被裁掉，紀錄留在附錄 A-2。）
- **三顆 seed 不併 Holm、不併 n。** 理由：三顆 seed 跑的是**同一批 12 題**
  ⇒ 題目層級的效果在三顆之間是完全相關的（R460R §六-2 的同一條）。
  合併會讓型一錯誤率超過名目值。

### 六-4　區間

- M1：配對 bootstrap percentile 區間（`vacant.research.boot_ci`，
  `n_boot=10000`、`seed=530` 事前釘死）。
  > 每次引用必須逐字附上：**「n≈20 的 bootstrap 區間很粗；區間未做多重比較調整；
  > 仲裁以 analyzer 為準」**
- M2：未調整的 95% Clopper–Pearson 條件區間
  （`ops/gain/replay/paired_ci.py::diff_ci`，與 R460／R529 同一支）。
  > 逐字附上：**「區間未做多重比較調整；仲裁以 analyzer 為準」**

### 六-5　**R530 四狀態**（本研究自訂、在資料之前凍結；**不得與 R460／R529 的同名狀態互引**）

先判逐 seed 的旗標，再判整體。

**逐 seed 旗標**（`decision.<seed>.*`）：

| 條件 | 判什麼 | 門檻 | 門檻的理由（不是抄 R460） |
|---|---|---|---|
| (i) 點估計 | `delta_frac_vs_solo` ≥ **+0.08**；`delta_frac_vs_conf` ≥ **+0.05**；`delta_deliv_pp_vs_solo` ≥ **+20.0**；`delta_deliv_pp_vs_conf` ≥ **+12.0** | 見右 | **+0.08**：隱藏驗收中位數 14 條 ⇒ 0.08 × 14 ≈ **多過一條驗收**。那是展場能當場指給觀眾看的最小單位（「同一份工作，多過了一條你自己寫的驗收」）。**⚠ 題數從 12 變 20 之後這個語意不變**（Fable 裁決第 2 點）：門檻綁的是**每題的隱藏條數中位數**，不是題數；n 變大只改變檢定力，不改變「多過一條」這個換算。**⚠ 但那個中位數本身會動**——核心 12 題是 14，加進新 8 題（含 `loose` 的 ≥5 條）之後會變。⇒ analyzer 必須印 `bank.hidden_n_median_actual`，收官**用實際中位數**重述這一句（例如中位數變 12 就寫「0.08 × 12 ≈ 多過一條」）。**門檻 `+0.08` 不動、也不准因為中位數變了就改**——動的只有那句話裡的乘數。**+20.0pp**：把 0.08 換算到「全部通過」那個連言尺度上的算術示意（平均比例 0.80→0.88，在條目中度相關時大致對應全過 0.30→0.50）——**是示意不是量測**。對 `A-CONF` 的兩格取一半：R440P 實測**重抽本身**只買到 +4.5–5.4pp，回饋迴圈要值得它多背的脈絡成本，至少要再買到同一個量級 ⇒ `+0.05`／`+12.0pp` |
| (ii) 顯著性 | `holm.<seed>.GATE_vs_SOLO.M1.p_adj < 0.05` **且** `holm.<seed>.GATE_vs_CONF.M1.p_adj < 0.05` | — | 只讀 **M1**，理由見 §四-4 |
| (iii) 成本 | `tokens.<seed>.GATE.token_per_delivered_correct` ≤ **2.0 ×** `…SOLO…`（含 void 的那一版） | 2.0× | 本 run **沒有 OFF5 之類的等預算錨**（R460 的 (iii) 讀的是同一個 run 的 OFF5）。2.0× 是自訂：閘門若要當展場的建議做法，「每交出一件對的東西的代價」不該超過不設閘門的兩倍 |
| (iv) 假交付 | `per_arm.<seed>.GATE.false_delivery_n` ≤ `per_arm.<seed>.CONF.false_delivery_n` + **1** | +1 題 | n≈20 之下百分比會跳 5pp 一格 ⇒ 用**件數**寫門檻比用 pp 誠實。⚠ 件數門檻在題數變多時**變嚴**（+1/20 比 +1/12 嚴），這是刻意的 |

**整體狀態**（`decision.overall`，照順序判，先命中者為準）：

| 狀態 | 條件 |
|---|---|
| **`INVALID`** | E-1…E-8 任一紅 |
| **`EFFECTIVE`** | (i)(ii)(iii)(iv) 四條在 **≥2 顆 seed** 上同時成立，**且**三顆 seed 的 `delta_frac_vs_solo` 與 `delta_frac_vs_conf` **沒有任何一顆為負** |
| **`COSTLY_BUT_REAL`** | (ii) 的 `GATE_vs_CONF` 那一半在 ≥2 顆 seed 成立，但 (i)(iii)(iv) 任一不成立 |
| **`RULED_OUT`** | `paired.<seed>.GATE_vs_CONF.M2.ci95_hi_pp` < **+12.0** 在 ≥2 顆 seed 成立 |
| **`INCONCLUSIVE`** | 其餘 |

⚠ **`RULED_OUT` 在 n≈20 上仍然很難觸發**（CP 條件區間寬到多半蓋過 +12pp）。
這是設計的已知代價，寫在資料之前：**本 run 多半排除不掉 ≥12pp 的增益**，
收官不准把 `INCONCLUSIVE` 講成「排除了」。

⚠ **`loose` 層不進上面任何一格。** 那三題的逐題差照印（`by_stratum.loose`），
但四狀態的四條旗標**一格都不讀它**。收官能講的只有
「契約鬆的那三題，逐題的差分別是 …」——**不准**寫成「在契約鬆的任務上也／不成立」。

### 六-6　**質化不改裁決**（事前寫死）

- 四狀態的四條旗標**沒有一條讀 `rubric.*`**。
- 質化能做的只有兩件：(a) 描述「贏在哪一維」；(b) 當量化與質化**方向相反**時，
  在裁決書裡逐字寫出來並各報各的數字——**不准挑一個當結論**。
- ⚠ 「與目標的貼合度」那一維與主指標部分重疊（§一-4 的警語）
  ⇒ 引用四維總分時必須同時報**扣掉那一維**的三維總分。
- ⚠ **長度共線的維度不准用來講臂比較**（第三輪裁決 (2)，§五-6 第 4b 項）：
  `rubric.length_confound.<dim>.rho` 超過 ±0.7 的那一維，
  收官**只准寫「與長度高度共線」**，
  而且**四維總分必須同時報「扣掉所有被擋維度」的版本**
  （`rubric.<seed>.total_excl_confounded`）。
  ⇒ 極端情況（四維全被擋）的處置事前寫死：**質化那一段只留描述與人工註記，
  一個分數比較都不寫**。
- ⚠ **去識別化丟格不對等的 seed，質化整段不可引用**（第三輪裁決 (3)，§五-6 第 1b 項）。
- ⚠ 上面兩條**都不改任何一格裁決**——它們限制的是「質化那一段能寫什麼」，
  四狀態仍然一格都不讀 `rubric.*`。

### 六-7　宣稱規則（事前寫死，`aggregate.statement_rule`）

> **`EFFECTIVE` 且三顆 seed 方向一致 ⇒ 可以寫「在 N 件目標明確、做法不指定的
> 小型工作上（N ＝ `bank.n_after_review`），把同樣的工具與預算交給同一顆本地模型，
> 加上『跑客戶自己的可見驗收、沒過就把失敗原文貼回去讓它改、五輪沒過就不交』這一層，
> 比收下第一份交付平均多通過 M 條客戶自己寫的驗收（逐 seed 列出點估計與區間）」；
> `EFFECTIVE` 但方向不是 3/3 ⇒ 必須逐 seed 列出並指名哪一顆反向；
> 其餘狀態 ⇒ 逐 seed 照實列，不准寫「多數支持」。**

**任何一句往外講的交付成效，都必須把 §八-1 的 R440P 前提句附在同一段裡**
（Fable 裁決第 8 點）——不是放在附錄、不是放在下一頁。
`aggregate.statement` 這個欄位**自己就帶著那兩段前提句**，analyzer 每次都印。

判到哪一句就逐字印在 `aggregate.statement`。

**同時必須帶的，還有 §四-1a 的歸因句**（W7a 或 W7b 二選一，照落在哪一格）
——少了它，「多通過 M 條」會被讀成「迴圈把錯的改對了 M 條」，
而那在 W7a 的情況下是錯的。

### 六-8　事前寫死的禁令（違反＝本輪失敗）

1. 看到數字之後改窗、改仲裁欄位、改分母、改家族、改狀態定義 ⇒ 一律不准。
2. **不准併三顆 seed 的 n**，也不准把三顆 seed 當三次獨立複製去算合併 p。
3. **不准跨題比較點估計**（12 題的難度差很大，`ow_05` 與 `ow_10` 不可比）。
4. **不准**在 `INCONCLUSIVE` 的情況下寫「等價」「打平」「閘門沒用」。
5. **不准**用質化分數支持任何一格裁決（§六-6）。
6. **不准**把 `A-SOLO` 的 `false_delivery` 與 `A-GATE`／`A-CONF` 的直接相比
   而不講「SOLO 沒有拒交語意」——那是結構差不是量測差。
7. **不准**把兩種 `tool_protocol` 的資料混算（§二-4）；兩種 `sandbox` 同理（§三-3）。
8. **不准**把 §四-4 的模擬表講成本 run 的效果量預測。
9. **不准**把 `stratum` 拿去算 p、進 Holm、或拿 `loose` 的三題下任何結論（§一-3a）。
10. **不准**在發射之後剔題。剔題只發生在 §五-2／§一-6，而且在發射前（§一-6 第 4 條）。
11. **不准**事後選 W7a／W7b 的講法，也不准改它的仲裁欄位或統計量（§四-1a）。

---

## 七、預算與時程（**Fable 2026-09-13 裁定：版本 D**）

### 七-1　共同的估計依據

- 呼叫延遲：R460 在同一顆 `gemma-4-12b-it-qat` 上實測**成功**呼叫
  p50 20.7 s、p90 90.5 s、max 504.9 s。工作區任務的單通輸出比單函式短
  （一次只寫一個檔或跑一個指令），但輪數多 ⇒ 取**每通 40 s** 當中心估計。
- 併發：兩顆後端各 **2 串**＝4 串。R460 量到三併發會讓長生成變慢但**沒有量過倍率**
  ⇒ 本檔用 **1.4× 減速**當中心估計，並照實標成**估計不是量測**。
- 沙箱與閘門時間：每次可見驗收 < 5 s（本地、純標準庫），可忽略。

### 七-2　四個版本的數字

| 版本 | 格數 | 模型呼叫（中心／上界） | token（中心／上界） | 序列算力 | **牆鐘（4 串，含 1.4× 減速）** |
|---|---:|---:|---:|---:|---:|
| A：2 臂 × 12 題 × 3 seed（**裁掉**） | 72 | 864 ／ 1,728 | 4.3 M ／ 8.6 M | 9.6 h | ≈ 3.5 h |
| B：3 臂 × 12 題 × 3 seed（**裁掉**） | 108 | 1,512 ／ 2,592 | 7.6 M ／ 13 M | 16.8 h | ≈ 6 h |
| C：2 臂 × 20 題 × 3 seed（**裁掉**） | 120 | 1,440 ／ 2,880 | 7.2 M ／ 14 M | 16 h | ≈ 5.5 h |
| **D：3 臂 × 20 題 × 3 seed（裁定）** | **180** | **2,520** ／ 4,320 | **12.6 M** ／ 22 M | 28 h | **≈ 10 h**（上界 17 h） |

**版本 D 之外還要算進去的機時**（事前登記，不然收官對不起帳）：

| 項 | 格數／通數 | 牆鐘 |
|---|---:|---:|
| 探針 PR-1（工具協定，兩種模式各 20 輪） | ~40 通 | < 0.5 h |
| 探針 PR-4（跑完一題，丟掉） | ~24 通 | < 0.5 h |
| **冒煙**（§三-6，2 題 × 3 臂 × 1 seed） | **6 格 ／ ~84 通** | **< 1 h** |
| 質化盲評 J1＋J2（2 位 × 180 份去識別化提交） | ~360 通（短） | ~1 h |
| 質化盲評 J3（**選配**，gemma thinking） | ~180 通 | ~0.5–1 h |
| **合計（正式 run 之外）** | **~510 通** | **~3 h** |

⚠ 探針與冒煙的呼叫**不進實驗 token 帳**（它們的 run 目錄是 `runs/_probe/`
與 `runs/_smoke/`），但**要進機時帳**——收官報「這件事花了多少算力」時
不准只報正式 run 那一格。

⚠ **質化盲評不能與正式 run 併行**（第三輪裁決 (1) 的 VRAM 約束，§五-6 第 3 項）：
J2 要在 1004 上載 `qwen/qwen3.8-27b`，而那台在 run 期間載的是 `gemma-4-12b-it-qat`，
兩顆**不能同時載入**。⇒ 時程是**串接**不是重疊：
`探針 → 冒煙 → 正式 run（≈10 h）→ 1004 卸 gemma 載 qwen → 質化（≈1–2 h）`。
⚠ **換模型這個動作由人類或發射者執行並確認**，本檔不授權任何代理去動 1004 的載入狀態。

（中心估計的組成：SOLO 8 通、GATE 16 通、CONF 18 通／題；每通 5,000 token。
上界＝三臂都吃滿 24 通。**每一格都是估計**，收官要拿 `summary.json` 回填並寫出差異。）

### 七-3　建置工作量（發射前必須寫完的東西）

| # | 要建什麼 | 從哪裡拿 | 估計 |
|---|---|---|---|
| **W1** | `ops/gain/openwork_arms.py`：工作區生命週期（`cp -a` → git init → 跑 → tar → 雜湊）＋三條臂的迴圈 | `ops/localagent.py`（工具迴圈、`DENY`、JSONL）＋`harness_arms.py`（預算、停止理由、截斷、回饋模板、KS-1 斷言） | **2 代理輪** |
| **W2** | 驗收 runner ＋ 第三種 dialect（`call`／`cli`）＋ 雙向量具（PR-3） | `vacant/suitespec.py` 的資料紀律、`vacant/suitegauge.py` 的判準 | **1.5 輪** |
| **W3** | **題庫**：12（或 20）題 × `task.md`／`visible.json`／`hidden.json`／`rubric.json`／`template/` | 無，全新 | **3 輪**（最大的一塊） |
| **W4** | 公平性複核代理 ＋ `_fairness_review.json` | 無 | **0.5 輪** |
| **W5** | `harness_vgt_audit.py --scope r530`：加 `tool` role、加第三種 needle 來源、加工作區檔案掃描 | 既有架構可沿用 | **1 輪** |
| **W6** | 收據：兩種新 `etype`、digest-only payload、**工作區樹雜湊**、驗證器 | `logbook.py`＋`replay/verify_run_receipts.py` | **0.5 輪** |
| **W7** | 沙箱 S1／S2 ＋ PR-1…PR-4 探針 | `vacant/checks.py` 的 rlimit／killpg 形狀 | **1 輪** |
| **W8** | 盲評管線（去識別化＋**豁免落盤**＋**丟格對等擋門**、跨模型兩位評審、κ／α、**長度共線 `rho`**） | 盲評本身：無（`multiway.py:102` 只是結構先例）。**Spearman 直接重用 `ops/gain/r497_segment_composition.py:123`**（含 tie 處理與課本值自檢，不要再寫一份） | **1.5 輪**（第三輪裁決加了三件事） |
| **W9** | `ops/gain/analyze_r530.py` ＋ `tests/test_r530_*.py`（逐條驗仲裁欄位存在、驗發射器擋門真的會擋） | `analyze_r460.py`／`analyze_r529.py` | **1.5 輪** |
| | **合計** | | **≈ 12 代理輪**（Opus／Sonnet 混），約 **3–4 個工作天** |

⚠ **W3 是唯一不能外包給「照著做」的一塊**：目標敘述要「不太具體但明確」，
隱藏驗收要「從目標＋契約推得出來」。這兩件事互相拉扯，是本設計最可能出錯的地方。

### 七-4　裁定與退路

**Fable 2026-09-13 裁定版本 D（3 臂 × 20 題 × 3 seed）。**
理由只有一條：§四-4 的檢定力表。12 題版在中等效果下只有 0.32，
意思是**有三分之二的機會白跑**，而那會產出一個之後被引用成「量過了」的
`INCONCLUSIVE`。

**若機時中途不夠，退路事前寫死：砍 seed 不砍題。**
20 題 × 2 seed 的每一顆 seed 仍有 0.81 的檢定力；12 題 × 3 seed 的每一顆只有 0.32。
⚠ 砍 seed 的代價是複製次數變少 ⇒ §六-5 的「≥2 顆 seed」要改成「**2 顆全中**」，
而那是**更嚴**不是更鬆。**這件事要在動手砍之前決定並寫成修訂案，
不是看到數字之後。**
⚠ 另一條退路**不存在**：不准中途把 `A-CONF` 拿掉來省機時。
拿掉它就同時拿掉了等預算的對照（§八-4）與四狀態的 (ii)、(iv) 兩格，
那不是同一個實驗。

---

## 八、誠實邊界（收官必須原樣帶著，一條都不准掉）

### 八-0　本輪對 vacant-dev 做過的事，逐條

唯讀 `ssh` 查詢：`uname -a`、`cat /etc/os-release`、`df -h`、`du -sh`、`free -h`、
`nproc`、`ls`、`git -C … rev-parse/log/status`、`which`、`apt-cache policy`、
`id nobody`、`ulimit -a`、`ps`、`cat /proc/sys/kernel/*`、
以及對三個端點各一次 `curl -X GET /v1/models`。
**沒有** `sudo`、**沒有**建立／修改／刪除任何檔案、**沒有** `kill`／`pkill`、
**沒有**碰 `STOP` 檔、**沒有**啟動任何行程、**零模型呼叫**。

### 八-1　**R440P 前提句（必帶，一個字不准改）**

> R440P 量到 **17–19% 的題目五份候選全錯**——**選擇規則**（重抽、投票）打不破這個
> 候選池天花板，因為它只能在錯的候選裡挑；**修訂迴圈**在原理上可以，因為它改變
> 候選本身。本 run 量的是後者在**專案形狀的任務**上有沒有兌現，
> 而不是「有閘門的那一臂比較聰明」。
>
> **可執行驗收的前提**：整件事建立在「需求可以被編譯成可執行的驗收測資」。
> 需求跑不起來的場合，這個機制沒有免費的裁判，會退化成「問一個模型」，
> 而那正是本 repo 量出來很差的東西。

### 八-2　自建題庫的代價（三條）

1. **沒有外部基準可比。** 12 題是我們自己寫的，別人沒跑過。
   收官不准把通過率拿去跟任何公開榜單比。
2. **作者偏誤擋不掉、只擋得住一部分。** §五-2 的公平性複核擋的是
   「隱藏驗收藏了目標沒暗示的需求」，擋不掉「題目的選擇本身偏向迴圈擅長的形狀」。
   ⚠ 事前承認：**12 題全部是「契約釘死語意、邊界情況多」的題型**，
   而那正是回饋迴圈最可能有用的形狀。這是**選題偏誤**，不是量測。
3. **n 小。** 12（或 20）題 × 3 seed，逐 seed 判。§四-4 的檢定力表就是這一條的後果。

### 八-3　汙染

- **不可**宣稱模型沒看過類似任務（§一-5）。
- 汙染的方向性後果：完整記住的題會讓三條臂都第一輪就過 ⇒ **壓縮檢定力，
  不製造假效果**。但這句話**只在「記住」是全有全無的時候成立**——
  部分記住（記得 CSV 怎麼 parse、不記得我們的 exit code）會抬高共同基準線、
  同樣壓縮差距。兩種都是往「量不到」的方向走。

### 八-4　**`A-GATE` vs `A-SOLO` 不是等預算比較，而且是故意的**

- `A-SOLO` 預期用 6–12 通，`A-GATE` 預期用 8–24 通。
- 人類問的就是「收第一份」對「有閘門」，所以這一刀**必須**不等預算。
- 等預算那一刀由 **`A-GATE` vs `A-CONF`** 負責（同樣 24 通上限、同樣 5 輪上限）。
  ⇒ v1 曾考慮的「兩臂版」（沒有 `A-CONF`）**拿不到等預算的對照**，
  它能回答的只有「有閘門比沒閘門好嗎」，回答不了「好在閘門還是好在多花」。
  這是它被裁掉的理由（附錄 A-2），也是 §七-4「不准中途拿掉 `A-CONF`」的理由。
- `A-SOLO` 的 `accepted` 恆為 true ⇒ 它的 `false_delivery` 在結構上等於它的錯誤率。
  **這不是發現，這是定義。** 每次引用都要帶。

### 八-5　可見驗收的內容會進 worker 的視野——而且**三條臂都會**

- `examples/` 在**每一個**工作區裡，三條臂都可以自己讀、自己跑。
- `A-GATE` 多拿到的是**失敗當下的 `got=`／`want=`**（§二-5），
  那三個欄位全部來自可見驗收。
- ⇒ **展場文案必須講**「模型看得到那幾條驗收的輸入與期望值」，
  不准只說「把錯誤貼回去」讓人以為它是憑空修對的。
- ⇒ 動態稽核的對象是 `hidden \ visible`，不是「所有驗收」（§五-3）。

### 八-6　seed 不是決定論

三顆 seed 決定題序與 persona 指派，**不決定模型取樣**。
⇒ 三顆 seed ＝ 同一批題目的三次隨機重複，**不是三個獨立樣本**，
也**不是**「換了資料再做一次」。R529 §一一-1 的同一條精神。

### 八-7　多輪工具迴圈的 void 曝險比單函式高

一題最多 24 通呼叫、40 次工具往返；任何一通重試用盡都會 void 掉**整格**
（含前面已成功的輪次）。⇒ `A-GATE`／`A-CONF` 的 void 曝險比 `A-SOLO` 高 2–3 倍，
而 void 格燒掉的 token 不進分母 ⇒ **token／題會被低估**。
⇒ 兩個 token 數字都要報，(iii) 的仲裁用**含 void 的那個**（較嚴）。

### 八-8　質化的七條限制

1. **評審是 12B／27B 本地模型**，而本 repo 自己量過模型評審票近乎常數函數
   （R438／R516／R440P §三）。**本輪又量到一次**：同模型、同 temperature 0 的
   兩位評審在假資料上 **κ = 1.000**（§五-6 第 3 項）——那是常數函數不是一致。
2. **「與目標的貼合度」與主指標部分重疊** ⇒ 四維總分與三維總分都要報。
3. **去識別化擋得掉字串，擋不掉風格**（§五-6）。
   ⇒ 「盲評」在本 run 的意思是「評審沒有被明說」，不是「評審不可能知道」。
4. **κ 量的不是「這把尺有多準」。** 第三輪裁決 (1) 之後 J1／J2 是**兩顆不同的模型**
   ⇒ κ 量的是**兩顆模型的看法有多接近**，不是效度。
   ⇒ **κ 高不代表評分可信**（兩顆模型可以一起偏同一個方向，例如一起偏好長的）；
   **κ 低也不代表資料壞掉**（兩顆不同的模型看法不同是正常的）。
   ⇒ **κ 在本 run 只能當「這張質化表有多穩」的粗指標，不能當證據。**
   每次引用都要帶 §五-6 第 3 項那句逐字定義。
5. **J1 與 worker 同一顆模型（`gemma-4-12b-it-qat`），J2 不是。**
   J1 可能對自己家族的產出風格有偏好 ⇒ κ 低的時候**分不開**
   「兩顆模型看法不同」與「J1 有家族偏好」。
   ⇒ 逐維平均分必須**逐位評審分開報**（`mean_by_grader`），不准只報平均之後的值。
6. **長度共線**（§五-6 第 4b 項）：`A-GATE` 的產出天生比較長，
   而分數與長度的 Spearman 若超過 ±0.7，那一維量的是長度不是品質。
   ⇒ 被擋的維度只准寫「與長度高度共線」；四維總分要同時報扣掉被擋維度的版本。
7. **去識別化丟格可能有臂別偏誤**（§五-6 第 1b 項）：
   `A-GATE` 比較可能寫出「the tests said …」這種句子 ⇒ 它被丟掉的格子比較多
   ⇒ 剩下來被評的是**倖存者**，而倖存者偏誤往哪個方向走，本 run 量不到。
   擋門只擋「丟格不對等到不能引用」，**擋不掉**「丟格對等但仍然有偏誤」這種情形。

### 八-9　沙箱

- 裁定走 S1（bubblewrap）。**若實際落到 S2**，起手是 `sudo`、靠 `setpriv` 降權——
  降權那一步寫錯就是以 root 跑模型寫的碼 ⇒ PR-2 必須逐字驗過那一行。
- 不論哪一種，`backend_meta.sandbox` 都要落盤，收官引用時要指名（§三-3）。
- `vacant/checks.py` 的 docstring 自己寫著它是**應用層加固，不是 OS 沙箱**。
  本 run 的威脅模型是「意外」不是「攻擊」，但這一句不准刪。
- 沙箱在負載下會飄（R529 §一一-13）：閘門與計分共用同一顆沙箱，
  四串連跑數小時。收官若出現「同一題在不同 seed 之間判不一樣」，
  **第一個要查的是沙箱不是模型**。

### 八-10　本 run 沒有做的事（照實列，別讓它看起來像做過）

- **沒有**第四條「等預算的 SOLO×5」臂（R460 的 OFF5 類比）。
  ⇒ 「5 次獨立重寫、挑最後一份」這個對照本 run **量不到**。
- **沒有**跨模型複製（三條臂共用 `gemma-4-12b-it-qat`）。
- **沒有**跨機器複製（工作區全在 vacant-dev 一台）。
- **沒有**人類評分者的質化（只有 Fable 抽讀的註記，n 很小且不盲）。
- **沒有**「多做幾輪會不會更好」的曲線（閘門輪固定上限 5）。
- **沒有**在 `loose` 層下任何結論的能力（3 題，§一-3a）。
- **沒有**兩位評審用不同模型的設計（刻意的，§五-6 第 3 項）
  ⇒ 「換一顆模型來評會不會得到不同結論」本 run 量不到。

---

## 九、質疑清單（v1 提出 → v2 標示哪些已裁、哪些還開著）

**v1 的八點原文整段留著沒有刪**，每一點前面加上 v2 的處置。
⚠ 標成「已裁」的意思是**裁決寫進正文了**，不是「問題消失了」——
第 1、4、5 點的殘餘風險分別留在 §四-1a 末、§八-2 第 2 條、§五-4 末。



1. **【已裁 → §四-1a】** Fable 裁決第 3 點：事前命名 W7a／W7b 兩個歸因結果，
   收官只准照落在哪一格講。**殘餘**：30% 這條線是本檔自訂的，沒有外部錨。
   v1 原文：**`A-SOLO` 到底是不是一條誠實的對照臂。**
   它有工具、可以自己跑 `examples/`，卻沒有任何東西**要求**它跑。
   若 P-W7 量到它幾乎都沒跑，那 `A-GATE` 的增益有一大半是
   「被強迫看一眼」而不是「有迴圈」——**這仍然是 Vacant 的價值主張**，
   但它與 R460 量的東西不是同一個東西，宣稱時不可互引。
   反過來若它幾乎都跑了而還是輸，那才是 R460 意義下的迴圈效果。
   **問題是：要不要事前就把這兩種結果分開命名，免得收官時挑一個講。**
2. **【已裁 → §七-4】** Fable 裁定版本 D（20 題），並把「砍 seed 不砍題」寫成
   事前退路。**殘餘**：複核剔題之後實際 n 可能掉回 17 以下（§一-6 第 6 條）。
   v1 原文：**n=12 該不該直接否決這個設計。** §四-4 的表擺在這裡：
   中等效果下 12 題版有三分之二的機會白跑。
   Fable 可以合理地裁「不准跑 12 題版」。
   若裁「跑」，理由不該是「先看看」——**「先看看」會產生一個
   `INCONCLUSIVE`，而那個結果會被後續引用成「量過了」。**
3. **【已裁 → §六-1／§六-5】** Fable 裁決第 2 點：M1＝Wilcoxon、M2＝McNemar 照准，
   四狀態的 (i) 仍然把 M2 的**點估計**當擋門。**殘餘**：那個擋門是本檔自訂的。
   v1 原文：**主指標從 McNemar 改成 Wilcoxon 是不是就地放寬。**
   我的理由是檢定力（§四-4），而且兩個指標都印、都判。
   但**換指標換到檢定力比較高的那一個**，形狀上與「看到數字之後改分母」
   只差一個時間點。Fable 該問的是：如果 M1 過而 M2 不過，收官准講什麼？
   （本檔 §六-5 的答案是「(i) 的四個點估計門檻要同時過」，
   也就是 M2 的**點估計**仍然是擋門——但這是我自己設計的擋門，不是共識。）
4. **【已裁 → §一-3】** Fable 裁決第 1 點：加 3 題 `loose` 負向對照層，
   `stratum` 只做描述性拆分。**殘餘**：3 題只夠看方向，§八-2 第 2 條
   那個選題偏誤**沒有被解決，只是被標示出來**。
   v1 原文：**12 題全是「契約釘死語意」的題型（§八-2 第 2 點）。**
   那正是回饋迴圈最擅長的形狀。
   Fable 該問：要不要塞 2–3 題**刻意做成契約鬆、隱藏驗收考整體設計**的題
   當負向對照？代價是那幾題的公平性複核會很難通過（§五-2 第 1 條）。
5. **【已裁 → §五-5 E-1／E-5 ＋ §三-6】** Fable 裁決第 4、6 點：
   單格壞掉 ⇒ 該格 void 並記名，≥2 格 ⇒ 整個 run `INVALID`；
   並且加了一份發射前必跑的冒煙檢核表（C1–C8），C5／C6 就是核對這兩件事。
   **殘餘**：冒煙只有 6 格，它驗的是「機制接得起來」不是「機制在 180 格上穩定」。
   v1 原文：**工作區樹雜湊 ＋ 收據 ＝ 新的承重件，而它一次真跑都沒驗過。**
   §五-4 要新增 `openwork_attempt`／`openwork_verdict` 與 Merkle 根。
   R529 §一一-12 剛剛才記過同一種風險（「牙齒在合成案例上驗過，
   但沒有在一次真跑上驗過」）。Fable 該問：第一塊收完時要逐條核對什麼，
   以及**收據壞掉算不算 E-5 紅到整個 run `INVALID`**（本檔目前寫的是算）。

**還開著的三個（v2 沒有動到，仍然需要裁決或至少需要被看過）：**

6. **【仍開著】`A-CONF` 的「工作區重置」是不是把它做得太弱了。**
   重抽時整個工作區回到樣板，等於前一次的所有工作都丟掉。
   真實世界的重抽通常會保留某些東西。做太弱 ⇒ `A-GATE` 贏得太容易。
   （我選重置的理由是「不重置就會有資訊從上一次流過來，那就不是重抽了」，
   但那是我的判斷不是量測。）
7. **【仍開著】`max_model_calls=24` 這個數字沒有錨。** R460 的 5 通是綁 OFF5 的；
   24 是我從「每題 3–8 通 × 5 輪」倒推的，PR-4 探針才會知道夠不夠。
   若 PR-4 顯示不夠，改預算就要重寫本檔（§三-4 已寫死這一條）。
8. **【仍開著】`token_per_delivered_correct ≤ 2.0×` 的 2.0 也沒有錨**（§六-5 (iii)）。
   它是我自己訂的展場口徑，不是從任何實測來的。

**v2 新增的兩個（Fable 的裁決本身帶進來的）——兩個都已由 2026-09-13 補充裁決處理：**

9. **【已裁 → §一-3b】** 補充裁決 (a)：加了發射前的難度分佈擋門
   （`ref_solution_lines` 與 `boundary_only_hidden_n` 逐題記進 `meta.json`；
   D1 中位數相對差 > 40% 或 D2 隱藏條數不足 ⇒ 退回題庫代理重寫；
   結果進 §五-2 的複核報告）。
   **殘餘三條，寫在 §一-3b 的誠實邊界裡**：行數是難度的粗代理；40% 沒有外部錨；
   D1 只比「新 8 題 vs 核心 12 題」，**沒有**解決 §八-2 第 4 條
   （沒有人類逐題看過這 20 題）。
   v1／v2 原文：**題庫有一半是另一個代理寫的，而本檔在它寫完之前就凍結了規則。**
   §一-3 的回填規則擋得住「格式不對」，擋不住「那 8 題的難度分佈與核心 12 題差很多」。
   ⚠ 具體的風險：若 `ow_13`…`ow_17` 明顯比 `ow_01`…`ow_12` 簡單，
   三條臂會一起撞天花板 ⇒ 檢定力被吃掉而看起來像「效果變小」。
   **建議的擋法**（本檔還沒寫成擋門，等裁決）：回填時要求題庫代理逐題附
   「參考解寫起來大約幾行」與「隱藏驗收裡有幾條是純邊界」，
   與核心 12 題放在同一張表上目視對照。
10. **【已裁兩次 → §五-6】** 補充裁決 (b) 先照這個保留意見改成「同模型、
   兩邊 `none`」；**第三輪裁決 (1) 又把它翻掉**，改成**跨模型**
   （J1＝gemma@1003、J2＝qwen@1004），理由是盲評管線代理交付後量到
   **同模型 temperature 0 的兩位評審在假資料上 κ=1.000**（常數函數不是一致），
   而且 worker 本身就是 gemma、需要非同家族的第二視角。
   **殘餘兩條**：(a) κ 量的仍然不是效度（§八-8 第 4 條）；
   (b) **J1 與 worker 同家族**是新帶進來的不對稱（§八-8 第 5 條）。
   v2 原文：**兩位評審同模型、其中一位開 thinking**（§五-6 第 3 項）。
   這讓 κ 這個數字的意思變成「同一顆模型在兩種推理設定下有多一致」，
   而不是「兩個獨立視角有多一致」。
   ⚠ 我照裁決寫了，但**這一點我認為值得再看一眼**：
   若目的是「第二視角」，開 thinking 是對的；若目的是「量盲評的可靠度」，
   它把要量的東西換掉了。

---

## 一〇、這份預註冊自己的邊界

- 本檔 **v2** 由 Opus 在 2026-09-13 依 Fable 同日的八條裁決改寫，v1 是同日的草稿。
  **不授權發射。**
- **最需要被再看一眼的四處**：§六-5 的四個點估計門檻（全部是自訂的）、
  §四-4 換主指標那一步、§二-1 `A-CONF` 的重置規則（§九-6）、
  以及 **§六-1 的 `frac` 顆粒度**（補充裁決 (a) 的副作用：`loose` 允許 5 條隱藏驗收
  ⇒ 它在 Wilcoxon 的秩上權重偏高，附錄 A-13 末）。
  §九-9／§九-10 已由兩條補充裁決處理，殘餘各自寫在原地。
- **本檔仍未凍結的東西，逐條**：
  1. `ow_13`…`ow_20` 的逐題內容（題庫代理產出中，§一-3 的回填規則已凍結）；
  2. 20 題 × 四種檔案的 sha256（AMEND1）；
  3. §五-2 的複核結果與最終成員（AMEND1），**含 §一-3b 的 `difficulty_gate` 結果**；
  3b. 逐題 `meta.json` 的 `ref_solution_lines` 與 `boundary_only_hidden_n`
      （前者要等參考解寫完，後者要等複核者標完）；
  4. 沙箱實際落在 S1 還是 S2（基建代理驗證中，§三-3）；
  4b. J2（`qwen/qwen3.8-27b`）**能不能關掉 thinking**——§五-6 寫的是
      「若該顆可設；設不了就照實記」，發射前要試一次並把結果寫進 AMEND1；
  5. §三-5 註冊行的逐塊 `n`（複核之後的機械後果）。
  **以上五項全部要在任何一通模型呼叫之前完成。**
- 本檔只出檔案、指令與判準；發射由人類或 Fable 的明示指令觸發。

---

## 附錄 A：v1 → v2，Fable 改了什麼（**v1 的取捨紀錄整段留著**）

（v1＝2026-09-13 Opus 草稿；v2＝同日 Fable 稽核後的裁決版。
下面每一條都寫「v1 原本怎麼取捨」，不是只寫新的規則——
把舊的取捨刪掉，等於讓後來的人看不出這裡曾經有過一個選擇。）

### A-1　題庫：12 題 → **20 題、兩層**（裁決第 1 點）

- **v1 的取捨**：核心 12 題凍結，另外 8 題寫成「選配擴充」，
  由 §七 的版本選擇決定要不要做。理由是「預註冊裡放 8 個沒寫完的題目是個洞」。
- **v2**：20 題定案，組成改成 `tight` 17 ＋ `loose` 3。
  那個「洞」改用**回填規則＋複核擋門**堵（§一-3 的四條、§一-6 的六條），
  而不是用「選配」迴避。
- **同時解決了 v1 §九-4 自己提的質疑**：v1 的 12 題全是契約釘死題型，
  沒有負向對照。

### A-2　臂：三臂／兩臂二選一 → **三臂定案**（裁決第 1 點的後果）

- **v1 的取捨**：把兩臂版當成省機時的選項列進 §七，
  並在 §八-4 寫明它拿不到等預算的對照。
- **v2**：兩臂版裁掉。§七-4 進一步寫死「不准中途拿掉 `A-CONF` 來省機時」
  ——因為那會同時拿掉四狀態的 (ii) 與 (iv) 兩格。

### A-3　主指標成員：全部的題 → **只吃複核通過的題**（裁決第 1 點）

- **v1 的取捨**：§五-2 的複核只寫「指不到就刪那一條或改目標」，
  **沒有寫「整題剔除」這條路**，也沒有寫剔除之後 n 怎麼辦。
- **v2**：§一-6 六條規則 ＋ §五-2 的三個陣列（`passed`／`excluded`／`amended`）
  ＋ §四-4 第 4 點的「用實際 n 重算檢定力」。
- ⚠ 這一條是 v1 真正的漏洞不是取捨：**v1 讓「複核沒過」變成一個沒有出口的狀態**。

### A-4　`stratum` 的地位（裁決第 1 點）

- v1 沒有分層概念。v2 加了 `tight`／`loose`，並且**立刻把它擋在家族之外**
  （§一-3a、§六-3、§六-8 第 9 條）——分層在這裡買到的是**描述**不是檢定力。

### A-5　門檻：**照准，但補一句語意不變的說明**（裁決第 2 點）

- 四狀態的六個數字（+0.08／+0.05／+20.0／+12.0／2.0×／+1 件）**一個字都沒改**。
- 補的那一句在 §六-5 (i)：題數從 12 變 20 之後 `+0.08` 的語意不變，
  因為它綁的是**每題隱藏條數的中位數（14）**不是題數。
- ⚠ 但 (iv) 的「+1 件」語意**確實變了**：分母從 12 變 20 ⇒ 門檻**變嚴**。
  v2 把這件事寫在原地，沒有藉機放寬成 `+2`。

### A-6　歸因：P-W7「不設窗」 → **W7a／W7b 事前命名**（裁決第 3 點）

- **v1 的取捨**：P-W7 寫成「兩種結論都成立，事前不挑」。
  那句話讀起來誠實，實際上留下一個洞——**收官時仍然要選一句話講**，
  而選的時候已經看過數字了。
- **v2**：30% 這條線 ＋ 兩段逐字寫死的結論句 ＋ 三顆 seed 全印的禁令。

### A-7　E-1／E-5：全紅 → **單格降級、兩格 INVALID**（裁決第 4 點）

- **v1 的取捨**：收據鏈只要有一格不是 `OK` 就整個 run `INVALID`。
  理由是「量不到不是通過」。
- **v2**：保留那條紀律的精神，但把**個案**與**系統性問題**分開
  ——一格壞掉是個案（void 並記名），兩格就是機制本身不可靠。
  ⚠ 代價寫在 §五-5：被 void 的格子會照 complete-case 退出配對，
  所以「降級」不是免費的，它吃分母。

### A-8　沙箱：S1／S2 待選 → **裁定 S1、S2 為退路**（裁決第 5 點）

- v1 把兩條路線並列並標「S1（建議）」。v2 裁定 S1，
  並把 S2 的身分從「不裝東西的備選」改成「fallback」，
  同時把 v1 的 `nobody` 換成**專用使用者 `r530run`**（`nobody` 是系統共用身分），
  加上 `unshare -n`，並要求 `backend_meta.sandbox` 逐塊落盤。

### A-9　冒煙：v1 沒有 → **§三-6 的 C1–C8**（裁決第 6 點）

- v1 只有四個發射前探針（PR-1…PR-4），**沒有端到端的冒煙**。
  PR-4 是「跑一題看預算夠不夠」，它不核對收據、不核對樹雜湊、不核對隱藏條數。
- v2 補上 6 格冒煙與八項逐格檢核，並寫死「`runs/_smoke/` 永不進證據」。

### A-10　質化：兩顆 seed → **同模型／不同後端／其一開 thinking**（裁決第 7 點）
### A-10a　→ **再改：J1／J2 都 `none`，thinking 降成選配 J3**（補充裁決 (b)）

- **v1 的取捨**：`qwen/qwen3.8-27b` 兩顆不同 seed，並寫「若有第三顆模型，
  第二位改成不同模型（更好）」。
- **v2 第一版（裁決第 7 點）**：改成同模型、不同後端、不同 seed，1003 那位可開 thinking，
  而且必須落盤。一致性的主要報告量從 Krippendorff α 改成**線性加權 Cohen's κ**
  （α 併印），並要求 ≥2 分的分歧逐案列進收官附錄。
- **v2 第二版（補充裁決 (b)，照 §九-10 的保留意見）**：J1／J2 **兩邊都
  `reasoning_effort=none`**；thinking 版降成**選配的 J3**，只做描述、不進 κ 主表。
  κ 的意義寫成一句逐字定義放進 §五-6，並在 §八-8 新增第 4 條
  （κ 量的是重現性不是效度）。
- ⚠ **這一條是 v2 內部自己翻過一次的**：兩個版本都留著，
  因為「為什麼第一版不夠好」本身就是判斷的一部分。

### A-10b　→ **再翻一次：跨模型 J1 gemma／J2 qwen**（第三輪裁決 (1)）

- **A-10a 的取捨**：同模型、兩邊 `reasoning_effort=none`、只差 seed 與後端。
  當時的理由是「換模型會讓不一致混進兩個來源」，而且 §八-8 已經寫了
  「κ 量的是重現性不是效度」。**那個理由本身沒有錯，錯的是它假設重現性量得到。**
- **推翻它的是一個量測不是一個論證**：盲評管線代理交付後，
  同模型、同 temperature 0 的兩位評審在假資料上 **κ = 1.000**。
  ⇒ 那個配置下兩次取樣沒有獨立性，κ 不是「很一致」而是**常數函數**
  ——與 R438／R516／R440P §三 抓到的是同一個病。
- **第二個理由是設計上的**：worker 自己就是 `gemma-4-12b-it-qat`，
  同家族的評審等於讓同一顆模型評自己的風格 ⇒ 需要非同家族的第二視角。
- **v2 因此變成**：J1＝gemma@1003（`none`）、J2＝qwen@1004（run 收完、
  gemma 卸載後才載入）、J3 選配＝gemma thinking（不進 κ）；
  三位 temperature 一律 0 且落盤；κ 的逐字定義改寫成
  「**兩顆不同的模型，對同一份提交給出的分數有多一致**」。
- **代價，兩條，都寫進 §八-8**：(a) κ 仍然不是效度；
  (b) **J1 與 worker 同家族**是這一版新帶進來的不對稱 ⇒ 逐維分數必須逐位評審分開報。
- **順帶的排程約束**：1004 不能同時載 gemma 與 qwen ⇒ 質化**不能與 run 併行**，
  時程改成串接（§七-2）。
- ⚠ **這一條是 v2 內部翻過兩次的**（A-10 → A-10a → A-10b），三個版本都留著。
  第二次翻的觸發是**假資料上的量測**，不是誰講贏誰——這件事本身值得留紀錄。

### A-11　措辭（裁決第 8 點）

- 全文再掃一次「信任／證明／顯著（統計脈絡外）」：
  「信任」**零命中**；「顯著」全部落在統計脈絡（`p_adj`／「顯著性的仲裁量」／
  「不顯著不等於沒有效果」）；
  「證明」在 v1 §一-5 有四處，v2 已改成「舉證／可重算／佐證」，現在**零命中**。
- **補充裁決 (a)(b) 與第三輪裁決 (1)(2)(3) 改完之後各掃過一次，三個詞都沒有被帶回來。**
- ⚠ 第三輪裁決帶進一個新的措辭風險並已處理：κ 很容易被寫成「兩位評審一致 ⇒ 評分可信」，那是把一致性講成效度。
  §五-6 第 3 項的逐字定義與 §八-8 第 4 條就是為了擋這一句。
- **交付成效必帶前提句**：§六-7 從「判到哪一句講哪一句」加成
  「`aggregate.statement` 自己就帶著 R440P 前提句與 W7a／W7b 歸因句」，
  而且逐字寫明**不准放附錄、不准放下一頁**。

### A-12　v1 完整保留、v2 一個字沒動的部分

§一-2（核心 12 題逐題）、§一-4（評分表）、§一-5（題目來源能舉證什麼）、
§二-2…§二-5（KS-1、預算常數、工具面、回饋模板）、
§三-0…§三-2（工作區與實測條件）、§三-4（四個探針）、§四-3（過擬合方向）、
§五-1／§五-3／§五-4（驗收 runner、V/GT、收據）、§六-2／§六-4（M2、區間）、
§六-6（質化不改裁決）、§七-1…§七-3（估計依據、建置工作量）、
§八-1／§八-3／§八-5／§八-6／§八-7。

⚠ **補充裁決 (a)(b) 與第三輪裁決 (1)(2)(3) 之後從這張清單移出去的六處**
（本來是「一個字沒動」，現在動了）：
§一-1（`meta`／`reference`／條數下界分層）、§六-1（`frac` 顆粒度與 `M1_tight_only`）、
§六-5 (i)（實際中位數）、**§五-6（整節重寫了三次：J1／J2／J3 跨模型、
豁免與丟格對等、長度共線）**、**§六-6（加兩條質化引用限制）**、
**§八-8（從三條變七條）**。

### A-13　難度分佈擋門：v2 只寫成「建議」 → **寫成擋門**（補充裁決 (a)）

- **v2 第一版的取捨**：§九-9 把風險寫出來，並提了一個「建議的擋法」，
  但逐字寫著「本檔還沒寫成擋門，等裁決」。
  理由是：那需要一個難度的量，而我當時沒有一個不會被挑剔的量。
- **補充裁決 (a)**：定了兩個量（`ref_solution_lines` 正規化後行數、
  複核者標的 `boundary_only_hidden_n`）與兩條 fail-closed 的線（D1 40%／D2 條數下界），
  寫成 §一-3b，結果進 §五-2 的複核報告。
- **順帶改到的三處**：§一-1（`hidden` 條數下界分層成 `tight` ≥10／`loose` ≥5、
  新增 `meta.json` 與 `reference/`）、§六-5 (i)（中位數會動 ⇒ 用實際中位數重述那句話，
  **門檻不動**）、§六-1（`frac` 顆粒度逐題不同 ⇒ 必報 `M1_tight_only` 敏感度值，
  **但仲裁量仍是含 `loose` 的那一個**）。
- ⚠ **§六-1 那一處是本次補充裁決的副作用，不是裁決內容**：
  `loose` 允許 5 條隱藏驗收 ⇒ 它在 Wilcoxon 的秩上權重偏高。
  這件事在 v2 第一版沒被發現，是寫 (a) 的時候才看出來的，所以特別標出來。

### A-14　質化新增「長度共線」事前規則（第三輪裁決 (2)）

- **v2 之前沒有這一格。** §五-6 末只寫了「`A-GATE` 的產出天生更可能帶有
  修過好幾輪的痕跡」，但**沒有把它變成可執行的判準**——那句話擋不住任何事。
- **第三輪裁決 (2)** 把它變成量：`rubric.length_confound.<dim>.rho`
  ＝ 該維分數與提交長度的 Spearman；`|rho| > 0.7` 的維度**只准寫「與長度高度共線」**，
  不准用它講任何臂比較；四維總分要同時報扣掉被擋維度的版本。
- **本檔加的兩處（標出來讓 Fable 確認）**：
  (a) 裁決原文寫 `rho > 0.7`，本檔實作成 **`|rho| > 0.7`**（負向共線同樣處置）；
  (b) 新增預測 **P-W13**「至少一維會被判共線，最可能是 readability」，
  並寫明 **HIT 不是壞消息、MISS 才要多看一眼**。
- 實作**重用** `ops/gain/r497_segment_composition.py:123` 的 `spearman`，不重寫。

### A-15　去識別化：豁免機制**追認** ＋ 丟格對等擋門（第三輪裁決 (3)）

- **v2 之前的取捨**：§五-6 第 1 項只寫「命中就整包退出質化並計數」，
  並註明「不是把它遮掉」。**沒有寫豁免**，也沒有寫「丟格本身可能有偏誤」。
- **裁決 (3) 做了兩件事**：
  1. **追認**盲評管線代理已經實作的豁免——字樣出現在題目自己的凍結文字
     （`task.md`／`visible.json`／`rubric.json`）裡就豁免，**但逐筆落盤**
     （`rubric.deident_excuses[]`，沿用 §五-3 `needle_excuse` 的同一條紀律）；
     **臂名／`.vacant`／`r530`／路徑含 `hidden` 或 `rubric` 永不豁免**，
     且那四列**不看它出現在哪裡**。
  2. **新增**丟格對等擋門：同一顆 seed 內逐臂丟格數相差 **≥2** ⇒
     該 seed 的質化段標「不可引用（去識別化丟格不對等）」，只印丟格表；
     三顆 seed 都不可引用 ⇒ **質化整段只留丟格表**。
- **為什麼需要第 2 件**：`A-GATE` 比較可能寫出「the tests said …」這種句子
  ⇒ 它被丟掉的格子比較多 ⇒ 剩下被評的是**倖存者**。
  這個擋門擋的是「不對等到不能引用」，**擋不掉**「對等但仍然有偏誤」（§八-8 第 7 條）。
- ⚠ 這一條**完全不影響量化**：丟格只發生在質化管線，`rows.jsonl` 一格不動。
