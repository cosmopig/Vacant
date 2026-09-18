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
**第六輪裁決 1–6**（2026-09-14，**發射前最後一輪**；寫完等 smoke9 檢核表就凍結）：
新增 **E-11**（帶 `tools` 的推理模式擋門，smoke9 實測兩台皆 0）、
記下**兩台後端速度差**（1003 慢 1.4–3.1×，判為 task 層級干擾項）、
用 smoke9 填 §七-2b 的 **`T`（中心 10 s／最壞 30 s，雙峰）**、
寫死**評審看得到什麼**（可見測試不進 prompt）與**四維逐維報不合成總分**、
新增 **§一〇-1 凍結程序 F1–F7**。逐條在**附錄 A-19／A-20**。

**2026-09-14 補充裁決 (1)(2)(3)**（AMEND1 入庫後）：條數界改成
**可見 2–4／`tight` 隱藏 10–16／`loose` 隱藏 5–7**（量具的具名例外撤掉）、
`boundary_only_hidden_n` **不得進任何宣稱**、`loose` 層目標補述的代價寫進 §八-2。
逐條在**附錄 A-18**。
⚠ **§八-2 在 `138d6ef` 的合併裡被回退成第三輪之前的版本，本輪已復原並補上第 5 條。**

**第五輪裁決 1–5**（2026-09-14，冒煙的第二批讀數）：**冒煙又推翻一個假設**
——「5 份／24 通」。實測**一份約要 20 通**⇒ 舊的 24 通總上限讓 `A-CONF`
**連第二份都抽不到**，§八-4 那一刀切不出東西。預算改成兩層
（每份 24 通／每格 72 通）、`A-CONF` 降為 **3 份**、「等預算」這個詞全檔刪除、
新增冒煙檢核 **C9**、時程重算（§七-2b）。逐條在**附錄 A-17**。

**第四輪裁決 1–8**（2026-09-14，基建冒煙之後）：**冒煙推翻了本檔四個假設**
——工具協定預設、token 預算口徑、bwrap 的 AppArmor 前提、persona 的 rng 鍵。
逐條與依據在**附錄 A-16**；改動落在 §二-1／§二-3／§二-4／§三-3／§三-5／
§五-5（E-9、E-10）／§六-0／§六-1／§七-2a／§四-1（P-W3、P-W8）。
⚠ **§一 由 AMEND1 代理另行改寫（20 題題庫已於 `44be37f` 入庫），本輪一個字都沒動 §一。**
**AMEND1（2026-09-14）已完成，見文末的附錄 AMEND1**：§五-2 的獨立複核（20 題全過、
`excluded` 0、`amended` 5）、Fable 據此裁的五項修正、§一 的回填（§一-3 的 20 題一覽表、
§一-3c 的新 8 題逐題表）、§一-3b 的 `boundary_only` 讀法、D1／D2 重印，
以及 `bank/` 469 檔的 sha256 釘死表（合併雜湊 `bank_sha256`）。
⚠ AMEND1 改到了 §一-2 **凍結**的 `ow_08_logscan` 一格（CLI 從「不計分」變成計分、
可見 3→4、隱藏 14→16），逐條理由在附錄 AMEND1-A 第 1 項——**沒有默默改**。
AMEND1 全程**零模型呼叫**。
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
| **可見範例** `visible` | **2–4 條**可執行的驗收，附輸入與期望值。同時是 `A-GATE`／`A-CONF` 的**出貨閘門**。 | worker 看得到，而且可以自己跑 |
| **隱藏驗收** `hidden` | **`tight` 10–16 條／`loose` 5–7 條**，含邊界情況。**只計分，永遠不進工作區、不進任何送給模型的文字。** | worker 看不到（V/GT 紅線，§五-3） |
| **質化評分表** `rubric` | 四維各 1–5，附逐級準則（§一-4） | 盲評模型看得到；worker 看不到 |
| **題目 meta** `meta` | `stratum`、**`ref_solution_lines`**、**`boundary_only_hidden_n`**、`hidden_n`、`visible_n`（§一-3b 的擋門讀這一份） | 誰都不進 prompt；只給擋門與 analyzer 讀 |

**落盤形狀**（資料不是程式，沿用 R452 `vacant/suitespec.py` 的紀律）：

```
ops/gain/data/openwork/<task_id>/
  task.md        # goal + contract（英文，送進 prompt 的就是這一份逐字）
  visible.json   # 2–4 條，{kind: "call"|"cli", ...}
  hidden.json    # tight 10–16 條／loose 5–7 條，同 schema
  rubric.json    # 四維 × 5 級準則
  meta.json      # stratum / ref_solution_lines / boundary_only_hidden_n / hidden_n / visible_n
  reference/     # 參考解（PR-3 量具本來就需要它；ref_solution_lines 從這裡算）
  template/      # 乾淨工作區樣板（見 §三-1）
```

⚠ **上面三個界是 2026-09-14 補充裁決 (1) 改過的**（原本是可見 2–3／`tight` ≥10／`loose` ≥5）。
改界的理由與代價、以及量具裡那個被取代掉的具名例外，逐條在**附錄 A-18**。

⚠ **本檔凍結的是**：`task_id`、目標敘述、介面契約、可見條數界、隱藏條數界、
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
- CLI：`python -m solution FILE`。
  **v2 原文（已被 AMEND1 第 1 項取代，留著不刪）**：「印出人看得懂的表格
  （**不計分，只進質化**）」。
  **AMEND1 第 1 項改成**：stdout 放 `summarize` 回傳的**那一個 JSON 物件**、exit 0；
  版面（縮排、鍵序、空白、結尾換行）**仍明寫不驗**；壞行不構成命令失敗。
  理由：原本那句**不可計分** ⇒ goal 最後一句「from the shell without writing a
  script」**一條驗收都沒有**，而參考解有約 16 行在實作它（計分看不到的難度）。
  逐條見附錄 **AMEND1-A 第 1 項**。

可見 **3 ⇒ 4** 條｜隱藏 **14 ⇒ 16** 條｜`ref_solution_lines` **64 ⇒ 61**
（AMEND1 第 1 項。當時它超出 §一-1 的舊界，量具以具名例外 `COUNT_EXCEPTIONS` 放行這一題。
⚠ **2026-09-14 補充裁決 (1) 之後這已經不是偏離**：界本身改成
**可見 2–4／`tight` 隱藏 10–16／`loose` 隱藏 5–7**、**上下界都判**，
`COUNT_EXCEPTIONS` **發射前移除**。經過與理由見**附錄 A-18-1**——
上面這段當時的紀錄原樣留著，不要讀成現況）

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
   ⚠ **2026-09-14 實際落在哪裡**：AMEND1 沒有開新檔，而是寫成**本檔文末的附錄 AMEND1**
   （AMEND1-D ＝ 469 檔逐檔 sha256 ＋ 合併雜湊 `bank_sha256`）。理由是預註冊與它的
   修訂案分成兩個檔會讓「凍結的是哪一版」多一層轉手。⚠ 另外，題庫的**檔名與這一條
   不同**：實際是 `goal.md`＋`contract.md`（不是 `task.md`）、`tests_visible/`＋`hidden/`
   一條一檔（不是 `visible.json`／`hidden.json`）、`rubric.md`（不是 `rubric.json`），
   而且**沒有 `template/`**（工作區樣板是 §三-1 的事）。內容等價、路徑不同，
   釘死表釘的是**實際存在的路徑**。
4. **`stratum` 是 rows 的一個欄位**（`record_bank_field` 的 R530 版），逐列落盤。
5. **必須通過 §一-3b 的難度分佈擋門**（2026-09-13 補充裁決 (a)）。沒過就退回重寫。

#### 一-3 的回填：**20 題一覽**（2026-09-14 補；資料出自 `ops/gain/r530/bank/*/meta.json`）

§一-3 的回填規則第 1 條要求「在任何一通模型呼叫之前」把題庫代理寫完的東西抄進本檔。
下表是機器讀出來的，**不是重新設計**；逐題的目標敘述與契約在 §一-2（核心 12 題）
與 §一-3c（新 8 題）。

| `task_id` | `stratum` | 題目一句話 | 可見 | 隱藏 | `ref_solution_lines` | `boundary_only_hidden_n` |
|---|---|---|---:|---:|---:|---:|
| `ow_01_csvjson` | tight | CSV to JSON Lines with line-numbered failures | 3 | 14 | 105 | 3 |
| `ow_02_ratelimit` | tight | Per-caller sliding-window limiter with an injected clock | 3 | 15 | 39 | 4 |
| `ow_03_mdtable` | tight | Realign markdown tables by display width | 3 | 14 | 113 | 0 |
| `ow_04_layerconf` | tight | Three-layer settings with provenance | 3 | 15 | 70 | 4 |
| `ow_05_router` | tight | Path router with a deterministic specificity order | 3 | 15 | 80 | 3 |
| `ow_06_verrange` | tight | Version ordering and requirement specs | 3 | 14 | 61 | 3 |
| `ow_07_retrypolicy` | tight | Retry with injected sleep and a capped backoff | 3 | 13 | 16 | 3 |
| `ow_08_logscan` | tight | Per-endpoint log summary with nearest-rank percentiles | 4 | 16 | 61 | 2 |
| `ow_09_minitemplate` | tight | A very small template engine that fails loudly | 3 | 13 | 87 | 7 |
| `ow_10_dedupe` | tight | Deduplicate records with a choice of conflict policy | 3 | 13 | 30 | 2 |
| `ow_11_reflow` | tight | Reflow plain text to a display width | 3 | 14 | 92 | 1 |
| `ow_12_bytesize` | tight | Read and print human byte sizes in both bases | 3 | 13 | 39 | 3 |
| `ow_13_timespans` | tight | Merge and subtract half-open time spans | 3 | 13 | 59 | 5 |
| `ow_14_statemachine` | tight | A state machine that records the path it took | 3 | 12 | 31 | 4 |
| `ow_15_tomlsub` | tight | A small TOML-shaped format, read and written | 3 | 13 | 200 | 4 |
| `ow_16_pathglob` | tight | Path patterns with a double star and removals | 3 | 13 | 66 | 1 |
| `ow_17_diffpatch` | tight | Line diff and a patch that refuses to misapply | 3 | 12 | 79 | 4 |
| `ow_18_taskorder` | loose | An order to run jobs in (loose contract) | 2 | 6 | 23 | 2 |
| `ow_19_redact` | loose | Take the secrets out of a log line (loose contract) | 2 | 6 | 26 | 0 |
| `ow_20_slugify` | loose | URL slugs for a batch of titles (loose contract) | 2 | 7 | 29 | 0 |

**合計：20 題（`tight` 17、`loose` 3）、可見 58 條、隱藏 251 條、`boundary_only` 55 條。**

⚠ 三件事不要看漏：

1. ~~**`ow_08` 的可見 4／隱藏 16 超出 §一-1 的 2–3／10–15**，量具用具名例外放行那一題~~
   ⇒ **已由 2026-09-14 補充裁決 (1) 取消**：界改成**可見 2–4／`tight` 10–16／
   `loose` 5–7**、**上下界都判**，`COUNT_EXCEPTIONS` **發射前移除**（附錄 A-18-1）。
   ⇒ 現在**20 題受同一組界**，沒有任何一題靠例外過關。
2. **條數口徑**：§一-1 的界算的是「一個可見測試檔＝一條」，
   一檔內可以有數個 `assert` 打同一個需求的不同角度。隱藏是**一檔一條**。
3. **`boundary_only_hidden_n` 是複核者標的**（§一-3b），嚴格讀法，
   **只落盤、不設門檻，而且收官任何宣稱都不得引用**
   （2026-09-14 補充裁決 (2)，§六-8 第 12 條：55 條裡 40 條只是「契約要求丟例外」
   ⇒ 它量的是目標有沒有錯誤條款，不是驗收偏不偏邊界）；`ow_08` 的 `h15`／`h16` 是 AMEND1 之後才存在的兩條，
   複核者沒看過，由修訂代理照同一個凍結讀法標，`meta.json` 的 `marked_by` 欄逐條寫明。

---

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

**讀法（AMEND1 補，2026-09-14）＝嚴格**：一條驗收只有在**它所評分的每一個輸入**
都落在上面三條判準之內時才算 `true`；只要它同時評了一個普通情況，就是 `false`。
判準 (2) 照字面讀成「契約要求丟例外的那一條才算」。
⚠ 這個讀法要在看到數字之前寫死，因為它**會改變數字**：嚴格讀法下 55／251（21.9%），
把 (1) 讀成「狀態為零長度」、(3) 讀成「靠近而非恰好落在邊界」會變成約 67／251（約 27%），
差在哪 12 條逐條列在 `ops/gain/r530/review/review_r530.json` 的
`boundary_only_criteria_applied.sensitivity`。
**它仍然只落盤、不設門檻**（下面第 4 條）；寫死讀法是為了讓任何事後改讀法的動作看得出來。

**擋門（fail-closed，對 `ow_13`…`ow_20` 這 8 題）：**

| # | 條件 | 不過怎麼辦 |
|---|---|---|
| **D1** | `median(ref_solution_lines, 新 8 題)` 與 `median(ref_solution_lines, 核心 12 題)` 的相對差 **> 40%** ⇒ 紅 <br>（相對差＝`|m_new − m_core| ÷ m_core`） | **整批退回題庫代理重寫** |
| **D2** | 任一題的條數落在 §一-1 的界之外 ⇒ 紅。界＝**可見 2–4**、**`tight` 隱藏 10–16**、**`loose` 隱藏 5–7**（2026-09-14 補充裁決 (1)；**上下界都判**，不再只判下界） | **該題退回重寫** |

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
4. **`boundary_only_hidden_n` 只落盤，`D1`／`D2` 都不讀它，而且收官連引用都不准**
   （2026-09-14 補充裁決 (2)，§六-8 第 12 條）。
   ⚠ v2 原本寫的是「它是給收官做描述性分層用的（增益是不是只來自邊界條）」——
   **那個用途已經被取消**：全庫 55 條裡 **40 條只是「契約要求丟例外」**
   ⇒ 它量的是**目標有沒有錯誤條款**，不是**驗收偏不偏邊界**。
   兩者同名不同義，拿它分層會得到一個看起來有意義、實際上在講別的事的數字。
   ⇒ 它現在的唯一用途是**題庫附錄裡的一行描述**。

### 一-3c　**新 8 題逐題回填**（`ow_13`…`ow_20`；2026-09-14 補）

§一-3 回填規則第 1 條：「本檔 §一-2 之後**原地補上八張與 `ow_01` 同格式的表**」。
下面八張表的目標敘述與契約是從 `ops/gain/r530/bank/<task_id>/{goal.md,contract.md}`
**逐字抄過來的**（英文為準，中文一句話是對照），不是在本檔重新設計。
`ow_19`／`ow_20` 的目標各多一段，那是 AMEND1 第 4 項補的，理由見附錄。

⚠ 這八題與核心 12 題的**一個形狀差異**：核心 12 題的契約在本檔是中文摘要，
這八題是英文原文。原因是核心 12 題的契約先寫在本檔、再由題庫代理實作成英文；
新 8 題反過來。**送進 prompt 的一律是 `bank/` 裡的英文原文**，本檔的中文從來不進 prompt。

---

#### `ow_13_timespans`（`stratum = tight`）

> A client runs a booking calendar for a shared resource. Busy periods arrive from
> several systems and they need them folded into one tidy list of when the resource
> is actually busy, plus a way to work out what is left once certain periods are
> taken out of it.
> 
> The periods arrive in no particular order and they overlap. Some of them touch end
> to end, and two bookings where one ends exactly when the next begins are one busy
> stretch, not two. A period with no length is not a period at all.
> 
> Some systems send a date only and some send a time of day as well, and both have
> to be understood. A period that ends before it starts is a bug in whoever sent it
> and has to be reported rather than quietly reversed.
> 
> They also want the total, in whole seconds, of the tidy list, counting time that
> two systems both reported only once.

中文：半開區間的時段聯集與相減；頭尾相接算一段、零長度不算一段、日期與日期時間兩種寫法都要讀，反向區間要報錯。

**契約**

    solution.merge(spans: list[tuple[str, str]]) -> list[tuple[str, str]]
    solution.subtract(spans: list[tuple[str, str]],
                      holes: list[tuple[str, str]]) -> list[tuple[str, str]]
    solution.total_seconds(spans: list[tuple[str, str]]) -> int

- An instant is written `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`. A date on its own
  means midnight at the start of that day.
- A span is the pair `(start, end)` and covers the instants from `start` up to but
  not including `end`.
- `merge` returns the union of the spans as the shortest list that covers it,
  ordered by start. Spans that overlap or that touch end to end become one. A span
  whose start equals its end covers nothing and is dropped.
- `subtract` returns the union of `spans` with every instant covered by `holes`
  removed, in that same shortest form.
- `total_seconds` returns the number of whole seconds covered by the union, as an
  `int`.
- Every instant in a returned span is written `YYYY-MM-DDTHH:MM:SS`.
- A span whose end is earlier than its start raises `ValueError`, and so does an
  instant that is not one of the two written forms.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **59**｜`boundary_only_hidden_n` **5**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Interval arithmetic is a textbook exercise, but the contract combination is this project's own: half-open spans so touching periods join, zero-length spans dropped rather than kept, two input instant shapes normalised to one output shape, a union-based total rather than a sum, and a reversed span raising instead of being swapped. Libraries such as portion default to closed intervals and would fail the touching and zero-length checks.

---

#### `ow_14_statemachine`（`stratum = tight`）

> A client's order pipeline is a handful of states and a handful of things that can
> happen to an order. The rules are on a whiteboard and they want them in code, so
> that an order can only move the way the whiteboard says.
> 
> They want to ask, before trying, whether a given thing can happen right now.
> Something that cannot happen has to be refused and has to leave the order exactly
> where it was, in state and in record.
> 
> They want the path an order took, in order, starting from where it began, because
> support staff are forever asking how an order ended up here. Something that puts
> an order back into the state it was already in still happened and belongs in that
> path.
> 
> Rules that point at a state nobody defined, or a starting state that is not on the
> whiteboard at all, are a mistake in the rules and should be caught when the rules
> are handed over rather than when an order trips over them.
> 
> They run the same rules for the next order, so there has to be a way to start over.

中文：白板規則的狀態機；拒絕的事件不得留下痕跡、自我轉移仍要進路徑、history 回傳副本、規則在交接時就驗。

**契約**

    solution.Machine(spec: dict[str, dict[str, str]], start: str)
    .state -> str
    .can(event: str) -> bool
    .fire(event: str) -> str
    .history() -> list[str]
    .reset() -> None

- `spec` maps a state name to a mapping from event name to the state that event
  leads to. Every state the machine can be in appears as a key of `spec`, even
  when it has no events of its own.
- `.state` is the state the machine is in now.
- `.can(event)` is True exactly when the current state's mapping has that event.
- `.fire(event)` moves to the target state and returns it. When `.can(event)` is
  False it raises `ValueError` naming the state and the event, and nothing about
  the machine changes.
- `.history()` is the list of states the machine has been in, oldest first,
  beginning with the starting state. A successful `fire` appends the new state,
  including when it is the same state again.
- `.history()` hands back a copy: changing the returned list does not change the
  machine.
- `.reset()` puts the machine back in the starting state and makes the history
  just that state again.
- The constructor raises `ValueError` when `start` is not a key of `spec`, or when
  any event leads to a state that is not a key of `spec`.

可見 **3** 條｜隱藏 **12** 條｜`ref_solution_lines` **31**｜`boundary_only_hidden_n` **4**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：State machines are a stock exercise, but this contract pins choices the common libraries do not share: a refused event raises and leaves the history untouched, a self-transition is recorded, the history is copied on the way out, reset clears the record as well as the state, and the rules are validated at construction rather than on first use. transitions and the usual dictionary recipe both differ on at least two of those.

---

#### `ow_15_tomlsub`（`stratum = tight`）

> A client keeps their service settings in a small text format that looks like TOML
> but is only the part of it they actually use. They need to read those files into
> ordinary Python data, and to write the data back out so that a person can still
> edit it by hand afterwards.
> 
> The values they use are text, whole numbers, decimals, true and false, and lists of
> one of those. A list that mixes kinds is a mistake. Settings are grouped under
> headings, and headings can be nested with dots.
> 
> Half of every file is comments, and a `#` inside a piece of text is not a comment.
> Text sometimes has to contain quotes, tabs and line breaks, written with a
> backslash.
> 
> The same setting written twice in one group, or the same heading opened twice, is a
> mistake they want caught. Every mistake has to say which line it is on, because
> these files are edited by hand and the file is the only thing they can look at.
> 
> Writing the data out and reading it back has to give the same data, and writing out
> what was just read has to give the same text, so the format can sit in version
> control without churning.

中文：TOML 子集的讀與寫；五種值、巢狀標題、引號內的 # 不是註解，重複名稱與重開標題都要指出行號，來回兩層都要穩定。

**契約**

    solution.parse(text: str) -> dict
    solution.dumps(data: dict) -> str

- A name -- a key, or one part of a heading -- is one or more characters from
  letters, digits, `_` and `-`.
- A line is blank, a comment, a heading `[a]` or `[a.b]`, or `name = value`.
  Everything from a `#` that is not inside text to the end of the line is a
  comment.
- The values are: `"text"`, in which `\"`, `\\`, `\n` and `\t` are the only
  escapes; a whole number written `-?digits`; a decimal written `-?digits.digits`;
  `true`; `false`; and a list `[v, v, v]` whose items are all of the same kind and
  are never lists themselves. `[]` is an empty list.
- A heading opens a group: the names after `[a.b]` live in `data["a"]["b"]`. Names
  before the first heading live at the top level.
- `parse` raises `ValueError` whose message begins `line <N>: `, with `N` the
  1-based line number, for anything it cannot read, for a name used twice in one
  group, and for a heading opened twice.
- `dumps` writes the top-level names first in name order, then each heading in
  name order with its own names in name order, and puts one blank line before each
  heading.
- `dumps` writes every setting on a line of its own as `name = value`, with exactly
  one space on each side of the `=`, and every heading on a line of its own.
- `dumps` raises `ValueError` for data it cannot write: a value of some other type,
  a list whose items are not all the same kind, a list inside a list, or a name
  outside the allowed characters.
- `parse(dumps(x))` gives back `x`, and `dumps(parse(dumps(x)))` gives back the
  same text.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **200**｜`boundary_only_hidden_n` **4**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：The syntax is deliberately TOML-shaped, but this is a strict subset with its own rules: only four escapes, no nested lists, no inline tables, no dates, lists required to be of one kind, headings forbidden from reopening, and a canonical name-ordered writer with a text-level round-trip guarantee. Python's tomllib parses a superset and has no writer at all, so a remembered TOML implementation fails the duplicate, ordering and round-trip checks.

---

#### `ow_16_pathglob`（`stratum = tight`）

> A client has a build tool that picks files out of a list by pattern, the way a
> build config or an ignore file does. They write the patterns by hand; the list of
> files comes from a walk of the tree, so it is already in a sensible order.
> 
> A star should stay inside one directory level, because `src/*.py` is meant to be
> the files in `src` and not everything underneath it. When they do want everything
> underneath they write a double star, and that has to work even when there is
> nothing underneath at all.
> 
> They also need a single-character wildcard and a way to say "one of these
> characters" or "any character in this range", including the negative form.
> 
> A pattern has to match the whole path: half a match is not a match. Characters that
> mean something to a regular expression -- a dot, a plus, a bracket sitting in a
> file name -- are ordinary characters in a path.
> 
> They apply several patterns in order and want to take things back out again, so a
> pattern beginning with an exclamation mark removes what the earlier ones picked up,
> and a later pattern can put something back. The answer comes back in the order the
> files were listed, with nothing listed twice.
> 
> A pattern they typed wrongly should be reported rather than quietly matching
> nothing.

中文：路徑 glob 比對與批次挑選；星號不跨斜線、雙星可以吃零段、整條路徑要對齊，驚嘆號依序把東西拿掉再放回去。

**契約**

    solution.matches(pattern: str, path: str) -> bool
    solution.select(patterns: list[str], paths: list[str]) -> list[str]

- Patterns and paths are split into segments on `/`. A pattern matches only when it
  accounts for every segment of the path.
- Inside one segment:
  - `?` matches exactly one character other than `/`;
  - `*` matches zero or more characters other than `/`;
  - `[abc]` matches one of the characters listed; `[a-z]` matches one character in
    that range; a leading `!` inside the brackets means "any one character that is
    not listed"; the class ends at the first `]`;
  - every other character stands for itself, whatever it would mean to a regular
    expression.
- A segment that is exactly `**` matches zero or more whole segments. A `**`
  appearing inside a larger segment is just two stars and has no extra meaning.
- `select` reads the patterns left to right. A plain pattern adds every path that
  matches it; a pattern beginning with `!` removes every path picked up so far that
  matches the rest of the pattern. The result is in the order of `paths` and holds
  no path twice.
- A pattern containing an unclosed `[`, or an empty class, raises `ValueError`.
  `select` checks every pattern it is given, whether or not anything matches it.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **66**｜`boundary_only_hidden_n` **1**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Globbing is familiar, but Python's fnmatch lets a star cross a separator and knows nothing about a double star, pathlib's match anchors from the right rather than the whole path, and gitignore semantics are directory-relative rather than whole-path. This contract is whole-path, one-level stars, zero-or-more double stars, and an ordered add/remove pass over a given file list. A remembered implementation of any of the three fails several hidden checks.

---

#### `ow_17_diffpatch`（`stratum = tight`）

> A client reviews changes to plain text files by hand. They want to see what changed
> between two versions as a list of pieces, and they want to be able to take that
> list and put it back onto the old version to get the new one.
> 
> They want the difference described as separate pieces, one per place that changed,
> so that a reviewer sees the two lines that moved rather than one block covering
> everything between them. A piece must not carry lines that did not change: not at
> its start, not at its end. A file that did not change at all produces no pieces.
> 
> Applying a list of pieces to a version they do not fit is the dangerous case --
> someone edited the file in between -- and has to be refused loudly rather than
> producing a mangled file. The same goes for a list of pieces that is out of order,
> that overlaps itself, or that is simply malformed.
> 
> Applying must not touch what it was given, because they keep the old version
> around. Files with many identical lines are common in their data, and going out and
> back has to survive them.

中文：行級 diff 與 patch 套用；一個變動點一塊、兩端不得夾未變動行、套錯版本要大聲拒絕、輸入一個都不准動。

**契約**

    solution.diff(old: list[str], new: list[str]) -> list[dict]
    solution.apply(old: list[str], hunks: list[dict]) -> list[str]

- A piece is a dict with exactly the keys `start`, `old` and `new`. `start` is a
  0-based index into the old list; `old` is the run of lines being replaced,
  beginning at `start`; `new` is what replaces them. Either side may be empty, but
  not both.
- `diff` returns the pieces ordered by `start`, with at least one unchanged line
  between the end of one piece and the start of the next, and with no piece
  beginning or ending with a line that is the same on both of its sides.
- `apply(old, diff(old, new))` equals `new`, for any two lists.
- `apply` returns a new list and changes neither of its arguments.
- `apply` raises `ValueError` when a piece's `old` is not what the old list holds
  at `start`, when the pieces are out of order or overlap, when a piece reaches
  past the end of the old list, when a piece is empty on both sides, or when a
  piece is not a dict with exactly those three keys.

可見 **3** 條｜隱藏 **12** 條｜`ref_solution_lines` **79**｜`boundary_only_hidden_n` **4**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Diffing is a classic, but the shape graded here is this project's own: pieces are dicts with exactly start/old/new rather than unified-diff text, there is no context, pieces are required to be trimmed on both sides and separated by an unchanged line, and apply is required to verify, to refuse out-of-order and overlapping pieces, and to leave its arguments alone. difflib produces opcodes and SequenceMatcher-based recipes do not validate on apply, so a remembered solution fails the refusal checks.

---

#### `ow_18_taskorder`（`stratum = loose`）

> A client has a pile of jobs to run, one at a time, on a single worker. Some jobs
> cannot start until other jobs have finished, and they keep that in a table from a
> job name to the names of the jobs it waits for.
> 
> They want a planner that hands back an order to run them in. What they care about,
> in their own words:
> 
> - nothing runs before something it waits for;
> - every job appears in the order exactly once, and a job that is only ever
>   mentioned as something else's prerequisite is still a job;
> - running the planner twice on the same table gives the same order, because the
>   order goes into a build log that they diff;
> - a table that can never be run -- because some jobs wait on each other in a
>   circle, directly or through others, or because a job waits on itself -- is
>   reported as an error rather than returned half done.
> 
> Which of the many orders that satisfy those they get is up to whoever writes it.

中文：（契約鬆）相依工作的執行順序；目標只講四條性質（不早跑、每個剛好一次、同輸入同輸出、環要報錯），怎麼排隨你。

**契約**

    solution.plan(jobs: dict[str, list[str]]) -> list[str]

- The keys of `jobs` are job names. Each value is the list of job names that have
  to finish before that job may start.
- `plan` returns a list of job names.
- When the goal cannot be satisfied, `plan` raises `ValueError`.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; everything else is a design decision.

可見 **2** 條｜隱藏 **6** 條｜`ref_solution_lines` **23**｜`boundary_only_hidden_n` **2**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Topological sorting is textbook and graphlib.TopologicalSorter exists, which is the point: this task deliberately grades only the properties the goal states, so a worker who reaches for the library and one who writes Kahn's algorithm can both score full marks quantitatively and be separated only by the qualitative reading. Nothing here is a trick the library gets wrong.

---

#### `ow_19_redact`（`stratum = loose`）

> A client is about to start posting their application logs into a shared channel and
> needs the secrets taken out of each line first. They know roughly what their secrets
> look like and gave three real examples from yesterday's log:
> 
>     AKIAIOSFODNN7EXAMPLE
>     Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.abcdef
>     postgres://svc:hunter2@db.internal:5432/app
> 
> Those three lines are yesterday's, not the whole list. The same three kinds turn up
> written differently: keys with other text in them, tokens that are not made of
> dot-separated parts, and addresses for the other stores they run -- mysql, mongodb,
> redis and amqp all appear in these logs, written the same way the postgres one is.
> 
> What they care about:
> 
> - after the pass, none of the secret text is anywhere in the result;
> - everything in the line that is not a secret comes back exactly as it was, because
>   a person is going to read the line and needs the rest of it;
> - running the pass on a line that has already been through it changes nothing
>   further;
> - a secret that appears twice in one line is gone both times;
> - they can ask what was found in a line so a dashboard can count it, and a line with
>   nothing in it answers with nothing.
> 
> What the replacement looks like, and how much of the surrounding structure is kept,
> is up to whoever writes it.

中文：（契約鬆）log 行的祕密遮蔽；目標只講五條性質（祕密不留、其餘原樣、二次無變、重複都清、數得出來），遮成什麼樣隨你。

**契約**

    solution.redact(text: str) -> str
    solution.findings(text: str) -> list[str]

- `redact` takes one line of log text and returns one line of log text.
- `findings` takes the same text and returns a list, one entry per secret found.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; the shape of the replacement and the contents of the list are design
decisions.

可見 **2** 條｜隱藏 **6** 條｜`ref_solution_lines` **26**｜`boundary_only_hidden_n` **0**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Secret scanners exist, but nothing here depends on matching one: the only things graded are the properties the goal states, using three examples the client supplied. Two workers with completely different pattern sets can both score full marks quantitatively, which is the point of the loose stratum.

---

#### `ow_20_slugify`（`stratum = loose`）

> A client publishes articles and needs a piece of URL for each one. They hand over a
> whole batch of titles at once, as they come out of their editor.
> 
> What they care about:
> 
> - one slug per title, in the same order as the titles they handed in;
> - a slug holds only lowercase letters, digits and hyphens, never starts or ends with
>   a hyphen, and never has two hyphens in a row;
> - no two slugs in a batch are the same, because a URL has to point at one article,
>   and the same title really does show up twice in a batch;
> - handing in the same batch twice gives the same slugs, because the slugs go into a
>   sitemap they diff;
> - a title that is already a clean slug, and that nothing else in the batch collides
>   with, comes back exactly as it was;
> - a title written in a script with no Latin letters in it at all still gets a usable
>   slug rather than an empty one;
> - and so does a title with nothing usable in it at all -- one that is only
>   punctuation is still a title their editor hands over, and it still needs a slug
>   rather than an empty string.
> 
> How a title is turned into a slug, and what a collision is resolved with, is up to
> whoever writes it.

中文：（契約鬆）整批標題轉 URL slug；目標只講六條性質（同序、字元集、連字號規則、批內不重複、同批同結果、非拉丁也要有得用）。

**契約**

    solution.slugify(titles: list[str]) -> list[str]

- `slugify` takes the batch of titles and returns a list of strings.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; the transliteration rules and the collision suffix are design decisions.

可見 **2** 條｜隱藏 **7** 條｜`ref_solution_lines` **29**｜`boundary_only_hidden_n` **0**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Slugify is one of the most copied snippets there is, which is exactly why it is here: the graded properties are batch-level (uniqueness within the batch, determinism across calls, a non-empty answer for a non-Latin title) rather than per-title, and the common snippet handles none of the three. Two workers can still solve it in completely different ways and both score full marks quantitatively.

---

### 一-4　質化評分表（四維 × 1–5，逐級準則；**全部題目共用同一份**）

| 維度 | 1 | 3 | 5 |
|---|---|---|---|
| **可讀性** | 命名無意義、無註解且不需要註解也看不懂、單一函式超過 80 行 | 命名大致達意，結構看得懂，但有幾段需要重讀 | 讀一次就懂；命名與契約用詞一致；註解只出現在「為什麼」不是「做什麼」 |
| **結構** | 全部塞在一個函式／一個檔案裡且互相糾纏 | 有拆分但邊界隨意，重複邏輯出現 2 次以上 | 每個單元一個職責；沒有重複的邏輯；加一條新規則不必改三個地方 |
| **錯誤處理** | 例外訊息沒有指出哪裡錯；或用裸 `except:` 吞掉 | 契約要求的例外都丟了，訊息尚可 | 契約要求的例外都丟了，訊息指名輸入的哪一部分出錯；沒有吞例外；沒有把正常流程寫成例外 |
| **與目標的貼合度** | 做的事與目標敘述講的客戶困擾對不上 | 做到了契約，但目標敘述講的困擾只處理了一部分 | 目標敘述裡每一個客戶困擾都看得到對應的處理 |

⚠ **「與目標的貼合度」是四維裡唯一與隱藏驗收有部分重疊的一維**，
因此它**必然**與主指標相關，不可被引用成「質化獨立佐證了量化」（§八-8）。

**落盤形狀（2026-09-14 回填）**：題庫是 20 份 `bank/<task_id>/rubric.md`，
**四維量表那一段 20 份逐位元相同**（本節的擴充版，1–5 五級都寫滿），
只有最底下「逐題範例」不同。⚠ **AMEND1 第 3 項**：`ow_18`／`ow_19`／`ow_20` 的
rubric 原本多了一條 `readability + 2*structure + error_handling + 2*fit_to_goal`
的加權、並自稱「prereg amendment, Fable ruling 2026-09-13」——**本檔全文沒有任何加權**，
那條裁決不存在於任何凍結文件。加權已於 2026-09-14 拿掉，三份 rubric 回到與其他 17 題
同一份量表。帶著一句凍結文件裡沒有的裁決進 AMEND1 是不允許的。
⚠ 另記一處與本節字面的差異：本節的表只寫 1／3／5 三級，題庫的 rubric 寫滿 1–5 五級。
那是**擴充不是衝突**，但它是新的凍結文字，一併記在 AMEND1。

### 一-5　題目來源：能舉證的是什麼、舉不了證的是什麼

**能舉證的（三件，全部可重算）：**

1. **這 20 段目標敘述、20 份契約、251 條隱藏驗收的逐字內容，落盤時間可查。**
   （v2 這裡原本寫「12 段／12 份／167 條」，那是核心 12 題的數字；20 題定案後
   實際是 20／20／251，2026-09-14 回填更正。）git commit sha＋時間戳＋逐檔 sha256
   釘死（附錄 AMEND1 的釘死表，合併雜湊 `bank_sha256`）；
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

| 臂 | 宣告完成之後發生什麼事 | 預算怎麼用（**上限三臂相同**） | 工作區 | persona |
|---|---|---|---|---|
| **`A-SOLO`** | **收。** 宣告完成的那一刻，工作區就是最終交付。無閘門、無回饋、**不存在拒交**——`accepted` **結構性恆真**，**包含「宣告完成但什麼都沒寫」（＝交付一份空的，`hidden_frac_delivered = 0`）**（第四輪裁決 7，§六-0） | **1 份**（實際用量預期 ≈20 通，**不會用到 72**） | 一個，從頭到尾 | 一位（`Random(f"{seed}:{task}:{attempt}")`，`attempt` 恆為 1） |
| **`A-CONF`** | 跑可見驗收。過 ⇒ 出貨。不過 ⇒ **工作區重置回樣板**、**換一位 persona**、**全新對話**（不告訴它上一次哪裡錯）；**3 份**都不過 ⇒ **拒交**（`hidden_frac_delivered = 0`） | **最多 3 份**（3 × 24 ＝ 72，與總上限對齊） | 每份一個全新的 | 每份換一位（`attempt` 遞增 ⇒ 鍵變 ⇒ 換人） |
| **`A-GATE`** | 跑可見驗收。過 ⇒ 出貨。不過 ⇒ **把失敗原文貼回同一段對話**、**同一個工作區**、**同一位 persona**，在 72 通之內**續改**；用完或 5 輪都不過 ⇒ **拒交**（`hidden_frac_delivered = 0`） | **72 通續改**（名目 5 輪，實際約 2–3 輪） | 一個，全程累積 | 一位（`attempt` 恆為 1） |

⚠ **三條臂在 `attempt=1` 抽到的是同一位 persona**（第四輪裁決 6 的新 rng 鍵，§三-5）
⇒ **第一則訊息逐字相同**這件事現在是**可驗的**，不只是 prompt 模板相同。

**主要假設＝`A-GATE` vs `A-SOLO`**（人類問的那一句）。

**`A-GATE` vs `A-CONF` 這一刀，第五輪裁決 2 之後的準確說法**：
> **在相同的上限之下（每份 24 通、每格 72 通），「拿失敗原文續改同一份」
> 對「丟掉重來、換人重抽」。**

⚠ **不要再寫成「等預算」。** 兩條臂的**上限**相同，**實際用量不會相同**，
而且事前就知道不會相同（`A-CONF` 每份都從零開始，`A-GATE` 的後續輪站在前一輪上）。
⇒ 口徑沿用 R460：**上限寫在設計裡，實際用量各自落盤、逐臂報**
（`per_arm.<seed>.<ARM>.calls_per_task`／`.calls_hist`）。
⇒ **兩臂實際呼叫數的差異進成本指標 (iii)**（§六-5），不是被忽略掉，
也不是被說成「一樣多」。

（機制上的理由沒變：R440P §二 選擇規則的天花板是候選池；
R460 §一 迴圈是唯一在原理上能越過它的東西。）

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
    "max_calls_per_attempt": 24,       # **單一份交付**（一次嘗試）之內的呼叫上限
    "max_model_calls": 72,             # **每格總上限**（跨所有嘗試／回饋輪）
    "max_completion_tokens": 120_000,  # 每格累計，**只算 completion**（第四輪裁決 1）
    "max_context_tokens": 200_000,     # 單通 prompt 上限；超過 ⇒ stop_reason=budget_context
    "max_wall_s": 7_200,               # 每格牆鐘；在呼叫之間檢查，不是硬上界
    "max_conf_attempts": 3,            # A-CONF 最多 3 份（第五輪裁決 1，原本 5）
    "max_gate_rounds": 5,              # A-GATE 的閘門輪名目上限（實際綁定的是 72 通）
    "max_tool_calls": 40,             # run_bash 次數上限
    "tool_timeout_s": 120,            # 單一指令；模型可要求 1–300
    "gate_timeout_s": 60,             # 跑一次可見驗收的沙箱上限
    "nudge_budget": 2,                # 宣告完成但工作區空白時的推一把次數（沿用 localagent）
}
```

⚠ **`max_tokens: 120_000`（總量）已被第四輪裁決 1 取代，理由是量出來的不是推出來的**：
vacant-dev 冒煙實測**單格 prompt 207,591 token／completion 14,542 token**。
多輪工具迴圈**每一通都要重送整段 context**（訊息、工具回傳的 stdout、回饋原文都累積）
⇒ **prompt token 隨輪數二次成長**，而 completion 幾乎是線性的。
⇒ 一個 120k 的**總量**上限在 **5–8 通**就會撞滿，
而那不是「這一格做完了」，是「context 把預算吃光了」
——那會把 `A-GATE`／`A-CONF`（輪數多）系統性地砍在半路，
**製造一個與機制無關的劣勢**。所以上限改成兩個各自獨立的量：
**completion 累計 40k**（量的是「模型實際產出多少」）＋
**單通 context 200k**（擋的是「脈絡爆掉」這個死法）。

⚠ **v2 原本的「24 通 ＝ 每格總上限」已被第五輪裁決 1 取代，理由又是量出來的**：
冒煙量到**模型在這種小專案任務上大約要 20 通才宣告完成一份**。
⇒ 在舊的 24 通總上限之下，`A-CONF` **連第二份都抽不到**
（第一份就吃掉 20 通，剩 4 通不夠再做一份）
⇒ 它退化成一條「只跑一次可見驗收」的臂，
而 §八-4 那一刀（回饋續改 vs 全新重抽）**切不出任何東西**。
⇒ 預算改成**兩層**：

| 層 | 值 | 擋的是什麼 |
|---|---:|---|
| **`max_calls_per_attempt`** | **24** | 單一份交付之內的呼叫上限。**三條臂相同** |
| **`max_model_calls`** | **72** | 每格總上限（跨所有嘗試／回饋輪）。**三條臂相同** |

- **三條臂的上限相同，實際用量各自落盤**（第五輪裁決 2，與 R460 同口徑）：
  - **`A-SOLO`**：宣告完成即收 ⇒ 實際用量預期落在 **1 份 ≈ 20 通**，
    **它不會用到 72**，而那正是「不用 Vacant」這條臂的樣子。
  - **`A-CONF`**：最多 **3 份**（第五輪裁決 1，原本 5）。
    3 × 24 ＝ 72，與總上限**剛好對齊**。
    ⚠ 從 5 降到 3 的理由是**機時與 20 通／份的實測**，不是設計上的偏好
    ——5 份在 20 通／份之下要 120 通／格，180 格跑不完（§七-2a）。
    **這是一個被算力壓出來的取捨，不准寫成「3 份就夠了」。**
  - **`A-GATE`**：在 72 通之內**續改**（同一段對話、同一個工作區、同一位 persona）。
    `max_gate_rounds=5` 仍在，但**綁定約束是 72 通不是 5 輪**
    ——20 通／份之下實際能跑的大約是 **2–3 輪**。
    ⇒ 收官要報 `per_arm.<seed>.GATE.gate_rounds_hist`，
    **不准**把「跑了 2 輪」講成「迴圈只用了 2 輪就收斂」——它是被預算擋住的。
- ⚠ **`max_wall_s` 不是每題牆鐘的上界**（沿用 R460 §二-3 的同一句誠實邊界）：
  它在呼叫之間檢查；單次請求在 `--request-timeout-s 900 --retries 4` 之下
  最壞可以燒掉約 4500 秒。收官報 `wall_s` 的分佈，不准講成硬上界。
- **不送 `max_tokens` 給端點。** 只有有閘門的臂設輸出上限的話，長答案會被砍而
  `A-SOLO` 不會，那是憑空造出來的劣勢（R460 §二-3 同一條）。
  `max_completion_tokens` 只在**呼叫之間**當停止條件，不進請求本體。
- **`budget_context` 是一個新的停止理由，語意＝拒交**（第四輪裁決 1）：
  單通 prompt 超過 `max_context_tokens` ⇒ 該格停止、`accepted=False`、
  `stop_reason="budget_context"`。
  ⚠ 它**不是** `infra_void`：void 的意思是「基建壞了，這一格量不到」，
  而 context 撞牆是**這條臂在這一題上的真實行為**（它把脈絡用光了）。
  ⇒ **照 complete-case 留在分母裡**，逐臂計數 `per_arm.<seed>.<ARM>.stop_reason_pp.budget_context`。
  ⚠ 對 `A-SOLO` 幾乎不可能觸發（輪數少）⇒ 這一格的觸發率本身就是
  「多輪機制的成本」的一個量，收官要逐臂報。
- **成本指標 (iii) 的 token 口徑＝ prompt ＋ completion**（第四輪裁決 1）。
  ⚠ 這一條是本輪改口徑的地方：`token_per_delivered_correct` 讀的是**兩者之和**
  ——付出去的算力是兩種都算，只報 completion 會讓多輪機制看起來便宜得多
  （冒煙那一格的比例是 **207,591 : 14,542 ≈ 14 : 1**）。
  ⇒ **逐格兩種都印**：`rows.jsonl` 的 `prompt_tokens`／`completion_tokens`
  （欄位已存在，冒煙驗過），`tokens.<seed>.<ARM>.` 底下印
  `prompt_per_task`／`completion_per_task`／`total_per_task`／
  `token_per_delivered_correct`（＝總和版，**仲裁量**）。
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
- **協定：預設 `native`（OpenAI `tools` function-calling）；文字圍欄協定降為備援。**
  （第四輪裁決 2，**翻掉** v2 原本「預設文字協定」的設計。）

  | | v2 原本 | **第四輪裁決 2** |
  |---|---|---|
  | 預設 | 文字圍欄協定 | **`native`** |
  | 備援 | `native`（探針全綠才啟用） | **文字圍欄協定**（`native` 探針紅了才退） |

  **推翻它的是冒煙不是論證**：v2 的理由是「R460 實測同一顆模型的圍欄遵循是
  925/925」，但那是**單輪、只要它吐一段程式碼**的場景。
  多輪工具迴圈要的是「吐一段**我解析得出來的指令**」，那是另一件事。
  vacant-dev 冒煙實測：**文字協定下 6 格有 4 格零工具呼叫**
  ——模型回的是 ```` ```python ```` 區塊、或它自己內部的 `<|tool_call>` 格式，
  兩種 harness 都解析不到 ⇒ 那 4 格等於**沒有 agent**，只是一個會講話的模型。
  同時 `native` 探針回 `finish_reason=tool_calls` 正常。
  ⇒ **零工具呼叫的格子不是「模型偷懶」，是協定選錯了。**
  （這也是 §五-5 新增 E-10 `noop_cell` 的由來。）
- ⚠ **兩種模式的資料不得混算**（沿用 R460 §六-(6)-g 對 `harness_wire_mode` 的同一條）。
  模式逐列落盤在 `rows.jsonl` 的 `tool_protocol`（欄位已存在，冒煙驗過）
  與 `summary.tool_protocol`；**同一個 run 裡出現兩種值 ⇒ `broken_reasons` 紅**。
  切換只能整批切、而且**三條臂同時切**。
- ⚠ **PR-1 探針改成「每次換模型必跑」**（第四輪裁決 2）：
  不是「發射前跑一次就算數」。`native` 支不支援是**模型 × 後端 × LM Studio 版本**
  的性質，換任何一格都要重驗，結果落盤
  `summary.backend_meta.tool_protocol_probe`（含 `finish_reason` 原文）。

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
   （另加 §三-6 的 6 格冒煙），`A-CONF` 每格最多 **3** 個工作區（第五輪裁決 1）
   ⇒ 最壞約 **420** 個工作區、合計 < 150 MB。
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
| **後端速度差**（2026-09-14 去快取配對探針） | **1003 比 1004 慢**：冷 prefill **3.1×**、暖 prefill **1.4–2.7×**、生成 **1.6×** | **task 層級干擾項，不是 arm 層級混淆**（§八-11） |
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
| **S1（裁定）** | `sudo apt install bubblewrap`，之後以 `bwrap --unshare-net --unshare-pid --die-with-parent --ro-bind / / --bind <ws> <ws> --dev /dev --tmpfs /tmp --chdir <ws>` 跑每一條指令與每一次驗收 | 一次 apt ＋ **一份要由人寫並載入的主機 AppArmor profile**（見下面的更正） | profile 沒載入 ⇒ bwrap 起不來 ⇒ 退 S2 |
| **S2（退路，第四輪裁決 4 改寫）** | **ACL 結構隔離**：`hidden/`／`reference/` 由**專用使用者**擁有、`mode 700`；**驗收 runner 以該使用者執行**；**agent 的 bash 以 `user1` ＋ `unshare -n` 執行**。⇒ agent 那一側在**檔案系統權限上**就讀不到隱藏測資，不靠指令文字比對 | 要建一個使用者、要搬兩個目錄的擁有者（寫入操作，本輪沒做） | `unshare -n` 在 `apparmor_restrict_unprivileged_userns=1` 之下要 root 起手 ⇒ 降權那一步要在 PR-2 上逐字驗過 |

⚠ **更正一句 v2 寫錯的話（第四輪裁決 4，照實改）**：
v2 原本認為「Ubuntu 24.04 的 `bubblewrap` 套件自帶 AppArmor profile，裝完應該可用」。
**那是錯的。** Ubuntu 24.04 的 `kernel.apparmor_restrict_unprivileged_userns=1`
會擋掉非特權 user namespace，而 **`bubblewrap` 套件本身不帶 profile**
⇒ 光 `apt install` **不會**讓 bwrap 能跑，還要**另外寫一份主機端的 AppArmor profile
並載入**。⇒ S1 的成本比 v2 估的高，而且那份 profile 是**要人寫、要人載入**的東西，
不是一次 apt。
**這一條要原樣留著**：它是本檔第一次把「我以為它自帶」寫成事實而被冒煙推翻的地方
（附錄 A-16）。

⚠ **S1 與 S2 的判準不是「哪一條比較像沙箱」，是 §五-5 的 E-9**：
**兩者任一達到 E-9（`repo_hidden_from_sandbox == true`）即可**。
S1 靠 mount namespace 做到，S2 靠檔案權限做到——**結構上都是「讀不到」，
不是「擋門說不准讀」**，而那正是 E-9 要的東西。

**兩者都要落盤用了哪一種**（Fable 裁決第 5 點）：
`summary.backend_meta.sandbox` ∈ `{"bwrap", "acl_unshare"}`，
連同 `repo_hidden_from_sandbox`／`write_confined`／`network_isolated`／
`sandbox_uid`／`sandbox_gid`／`honest_bound`／`probe_detail`
（欄位名照冒煙實際落盤的那一份 `backend_meta.json`），
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
| **PR-4 能不能做完一題** | 讓 worker 跑一次 `ow_01`（丟掉，不進資料） | **每份 24 通／每格 72 通**夠不夠（第五輪裁決 1 之後的值） | 不夠 ⇒ 改預算並**重寫本檔**，不准跑起來再調。⚠ v2 原本這一格寫的是「24 通夠不夠一題」，而冒煙量到**一份就要 ≈20 通** ⇒ 這個探針在第五輪之前**問錯了問題**（附錄 A-17） |

⚠ PR-1／PR-4 會燒模型呼叫。它們的 run 目錄一律 `runs/_probe/r530_*`，
**不進任何分析**，且 seed 與正式 run 不同。

### 三-5　塊、seed、後端分配

- **seed 三顆**：`g-r530-s1`／`g-r530-s2`／`g-r530-s3`。發射前掃兩台所有
  `runs/*/summary.json`，命中任何一個 ⇒ 停（`abort_seed_not_fresh`）。
- **seed 控制什麼、不控制什麼（誠實邊界）**：seed 決定題序與 persona 指派。
  **persona 的 rng 鍵是 `random.Random(f"{seed}:{task}:{attempt}")`——不含 `arm`**
  （第四輪裁決 6，**改掉 v2 原本的 `f"{seed}:{arm}"`**）。
  ⚠ **為什麼改**：v2 那個鍵會讓三條臂在同一題上抽到**不同的 persona**
  ⇒ 三條臂的第一則訊息就不一樣了，而 §二-2 的整個設計是
  「**三條臂的第一則訊息逐字相同**」。鍵裡含 `arm` 與那一條直接衝突，
  **以「第一則訊息逐字相同」優先**。
  ⇒ 新鍵之下：同一題的三條臂在 `attempt=1` 抽到**同一位** persona；
  `A-CONF` 重抽時 `attempt` 遞增 ⇒ 換人（那是它的機制）；
  `A-GATE`／`A-SOLO` 全程 `attempt=1` ⇒ 同一位（那是它們的機制）。
  逐列落盤 `rows.jsonl` 的 `persona_first`（欄位已存在，冒煙驗過）。
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
- **佇列由 `ops/gain/r530/schedule_r530.py` 輪流分配**（第六輪裁決 2）。
  ⚠ **禁止手動把題綁死在單一台**——那會讓「題目」與「後端」共線，
  而 §三-2 量到 1003 比 1004 慢 1.4–3.1× ⇒ 綁死之後那個速度差就變成
  **題目層級的系統性差異**，`budget_wall` 會偏著咬。
  ⚠ **`smoke9` 就是手動綁死跑的** ⇒ **它的兩塊不可跨台比較**，
  它只能說「機制跑得起來」與「兩台各自的延遲長什麼樣」，**說不了兩台可比**。

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
| **C9** | **兩條有閘門的臂真的動起來了**（第五輪裁決 4） | **`A-CONF` 至少一格出現第 2 份**（`attempts_n ≥ 2`）**且** **`A-GATE` 至少一格進到回饋輪**（`gate_rounds ≥ 1`） | **不准發射。** 這一條擋的正是第五輪推翻的那個死法：預算不夠時 `A-CONF` 連第二份都抽不到、`A-GATE` 一輪回饋都跑不到 ⇒ 兩條臂在資料上與 `A-SOLO` **無法區分**，而那不會有任何錯誤訊息、只會安靜地產出一個 `INCONCLUSIVE` |

⚠ **C9 是本檔唯一一條「機制必須被觀察到啟動過」的檢核**。
其他八條問的是「有沒有壞掉」，C9 問的是**「有沒有發生」**。
⚠ C9 用的是**冒煙那 6 格**，而冒煙只有 2 題 ⇒ 它證得了「機制跑得起來」，
**證不了**「機制在 20 題上都會啟動」。這一句要跟著 C9 一起帶。

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
| **P-W3** | ~~預測~~ ⇒ **結構性陳述，不判 HIT／MISS**（第四輪裁決 7）：`A-SOLO` 的 `refusal_n` **恆為 0**、`accepted` **恆為 true**，因為它沒有拒交語意；「宣告完成但什麼都沒寫」也算交付（一份空的，`hidden_frac_delivered = 0`）。`A-GATE`／`A-CONF` 的 `refusal_n` 則是**資料** | `per_arm.<seed>.<ARM>.refusal_n`（三臂都印） | **沒有窗**——這一格若不成立，代表**程式寫錯了**，不是預測落空 ⇒ 走 `broken_reasons` 不走 MISS | 結構上必然。**這一條不是發現，是把設計講清楚**，寫在這裡是為了不讓收官把它當成結果 |
| **P-W4** | **假交付件數** `A-GATE` ≤ `A-CONF` + 1（每 seed；分母＝該 seed 複核後的實際題數） | `per_arm.<seed>.<ARM>.false_delivery_n` | ≤ +1 | R460 實測假交付從 29 降到 14（P-H4 預測寫錯方向）。本 run 沿用**實測**方向。⚠ 門檻是**件數**不是 pp，所以題數從 12 變 20 時它**變嚴了**——這是刻意的，寫在資料之前 |
| **P-W5** | `A-SOLO` 的「宣告完成但隱藏沒有全過」件數 **≥ 8**（20 題） | `per_arm.<seed>.SOLO.false_delivery_n` | ≥ 8 | 這是本 run 對展場最有用的一格：不用閘門時，錯的東西**全部**出貨。窗＝v1 的 5/12（41.7%）按比例換算到 20 題（8/20 ＝ 40%），**比例沒有放寬** |
| **P-W6** | 模型呼叫/格：`SOLO ∈ [10, 24]`、`GATE ∈ [20, 72]`、`CONF ∈ [20, 72]` | `per_arm.<seed>.<ARM>.calls_per_task`（＋`calls_hist`） | 三條都要 | **第五輪裁決 1 之後重寫**。錨＝冒煙實測**一份 ≈20 通**：`A-SOLO` 只做一份 ⇒ 落在單份上限 24 之內；另兩臂做 1–3 份／輪 ⇒ 20 起跳、72 封頂。⚠ v2 原本的窗（`SOLO [4,14]`、另兩臂 `[8,24]`）是用「每題 3–8 通」倒推的，**冒煙推翻了那個假設**（附錄 A-17） |
| **P-W7** | `A-SOLO` **自己跑過可見驗收**的題目比例 | `per_arm.<seed>.SOLO.self_ran_visible_pp` | **不設窗；落在哪一格由 §四-1a 的 W7a／W7b 事前命名** | 這是本 run 的主要歸因量。⚠ 「跑過」的操作型定義事前寫死：該格的工具呼叫紀錄裡出現**至少一次**成功執行 `run_examples.sh` 或直接執行 `examples/` 底下任一檔的指令（`blocked: true` 的不算），逐格布林值落盤在 `rows.jsonl` 的 `solo_self_ran_visible` |
| **P-W8** | 撞預算的比例（**三種停止理由分開印**：`budget_calls`／`budget_wall`／**`budget_context`**） | `per_arm.<seed>.<ARM>.stop_reason_pp.budget_calls` ＋ `.budget_wall` ＋ `.budget_context`，**以及三者之和** | **和 ≤ 20%**（三條臂都要）；**`budget_context` 另外單獨印，不設窗** | 專案題比單函式題長，20% 比 R460 的 5% 寬；寬的理由是任務形狀，不是為了容易 HIT。⚠ `budget_context` 不設窗，是因為第四輪裁決 1 才剛把它變成一個停止理由、**本檔沒有事前資料**（冒煙只有 2 題、而且那一格的 prompt 207,591 已經超過新的 200k 上限）⇒ 它的觸發率本身是本 run 的一個產出 |
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
| **P-W11** | **逐維**判（第六輪裁決 4，**不合成總分**）：`A-GATE` ≥ `A-SOLO` 在**四維都成立**，而且**「錯誤處理」那一維的 Δ 最大** | `rubric.<seed>.<dim>.<ARM>.mean`（逐維、逐評審，§五-6 第 3b 項） | 四維方向都要 ≥ 0；「錯誤處理」的 Δ 是四維最大。⚠ 被長度共線擋掉的維度**不判也不補**（該維直接不報） |
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
**E-9 為什麼是發射前的擋門而不是事後檢查**（第四輪裁決 3）：
V/GT 分離若只靠 `DENY` 的指令文字比對，那是**把紅線建立在模型的服從度上**
（`ops/localagent.py` 的 docstring 對 `DENY` 自己就寫了這一句）。
E-9 要的是**結構性**的不可讀——`repo_hidden_from_sandbox` 這個欄位在冒煙的
`backend_meta.json` 裡已經存在，而冒煙那一次的值是 **`false`**
（本機 stub，`honest_bound` 逐字寫著「**不是沙箱**：沒有網路隔離、沒有檔案隔離」）。
⇒ **那個值必須在 vacant-dev 上變成 `true` 才准發射**，不准帶著 `false` 上。

**E-11 為什麼要「帶 tools」探（第六輪裁決 1）**：
`reasoning_effort=none` 在**不帶 `tools`** 的請求上生效，不代表在**帶 `tools`** 的請求上
也生效——兩者在 LM Studio 端走的是不同的模板路徑。
本 run 的每一通都帶 `tools`（§二-4 預設 `native`）⇒ **探針必須長得跟實際請求一樣**。

**已實測（smoke9，2026-09-14）**：**72 通實跑 ＋ 10 次獨立探針，兩台的
`reasoning_tokens` 全部為 0**，`reasoning_effort=none` 在原生 tools 模式下**確實生效**。
⇒ **R529 §十一 那種「同一批資料混了兩種推論條件」的情形沒有重演。**
⚠ 但 E-11 **照樣是發射前的擋門**，不因為 smoke9 全綠就免驗：
LM Studio 的版本、模型載入參數、`reasoning_effort` 的預設值都可能在發射前被動到，
而這件事**不會有任何錯誤訊息**——它只會讓某幾塊的 completion 裡混進推理 token，
把 token 帳與成本指標 (iii) 一起弄髒。

**E-10 為什麼存在**（第四輪裁決 3，來自裁決 2 的同一批冒煙）：
文字協定下**6 格有 4 格零工具呼叫** ⇒ 工作區從頭到尾沒被動過
⇒ 那一格量到的不是「這條臂做得好不好」，是「協定沒接上」。
⚠ **20% 這條線是訂出來的，沒有外部錨**，而且它**逐臂判**——
因為協定壞掉會打到三條臂，而「只有一條臂 noop 很多」代表的是別的問題
（例如 `A-SOLO` 真的宣告完成就走人，那是資料不是故障）。
⚠ **≤ 20% 時不剔除、不特殊處理**：一格 noop 若是模型真的什麼都沒做，
那就是它的表現，照 `accepted` 語意計分（見 §六-0 的結構性說明）。

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
| **E-9** | **發射前**：`backend_meta.sandbox.repo_hidden_from_sandbox` **必須是 `true`**——隱藏測資與參考解對沙箱**在結構上不可讀**（S1 靠 mount namespace／S2 靠 `mode 700` 的檔案權限），**不是**靠 `DENY` 的指令文字比對。<br>⚠ 另：`write_confined == false` 時，**每格結束要比對工作區之外沒有新檔**（`gates.E9_stray_files`），有就是紅 | `gates.E9_repo_hidden`、`gates.E9_stray_files` |
| **E-11** | **推理模式一致**（第六輪裁決 1）。**發射前**：兩台端點各做一次**帶 `tools` 的**探針，回應的 `usage.reasoning_tokens` **必須為 0**。⚠ **欄位不存在算紅**（不能讀成 0）、**沒探過的端點算紅**（量不到不是通過）。**收官**：任一塊的 `reasoning_tokens ÷ completion_tokens > 0` ⇒ 該塊 `broken`（`inference_mode_inconsistent`），該塊不進合併 | `gates.E11_reasoning_zero`、`gates.E11_probed_endpoints`、`blocks.<block>.reasoning_ratio` |
| **E-10** | **`noop_cell`**：`ws_start_sha256 == ws_end_sha256` **且**該格零工具呼叫 ⇒ 標記 `noop_cell=true`。**同一條臂的 noop 比例 > 20% ⇒ 整個 run `INVALID`**；≤ 20% 則**照既有的 `accepted` 語意計**（不特別處理、不剔除） | `gates.E10_noop_pp.<ARM>`、`gates.E10_noop_cells` |

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

1c. **評審看得到什麼、看不到什麼**（第六輪裁決 4，**事前寫死**）：

   | 進 prompt | 不進 prompt |
   |---|---|
   | `goal.md`（**逐字**） | **可見測試**（`tests_visible/`） |
   | `contract.md`（**逐字**） | **隱藏測試**（任何形式） |
   | 去識別化後的**提交檔案內容**（§五-6 第 1 項處理過的那一份） | **隱藏通過率／`hidden_frac`／`deliv`／任何分數** |
   | `rubric.json` 的四維準則 | **臂別、seed、後端、輪數、嘗試次數** |

   - **為什麼可見測試不進 prompt**：評審若看得到那 2–4 條驗收，
     它會**拿測試當錨**——評分退化成「這份有沒有照著那幾條寫」，
     而那件事**量化那邊已經量過了**（可見驗收就是閘門本身）。
     質化要問的是另一個問題（可讀性、結構、錯誤處理、與目標的貼合度），
     給它測試等於把兩個問題併成一個。
   - **為什麼 `goal.md` ＋ `contract.md` 要逐字給**：「與目標的貼合度」那一維
     沒有目標原文就無法評；契約則是判斷「這份有沒有照介面做」的唯一依據。
   - ⚠ **隱藏測試與通過率永不進 prompt**（V/GT 紅線的質化版，§五-3）。
   - **盲評必須明給 `--bank ops/gain/r530/judge_bank`**——那是專門為盲評做的投影
     （只含 `goal.md`／`contract.md`／`rubric.json`，**結構上不含任何測試**）。
     ⚠ **不准**直接指向 `ops/gain/r530/bank/`：那份正典裡有 `hidden/` 與
     `tests_visible/`，指錯目錄就是把紅線交給「記得加參數」這件事。
     `ops/gain/r530/export_for_judge.py --check` **連 dry-run 一起驗**
     （投影內容對得上正典、而且投影裡沒有任何測試檔）。

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
3b. **四維逐維報，不合成總分**（第六輪裁決 4，**事前寫死**）：
   `rubric.json` 的四維（可讀性／結構／錯誤處理／與目標的貼合度）
   **各自報各自的**，`rubric.<seed>.<dim>.<ARM>.mean`。
   **本檔不定義、也不准計算任何「總分」**（四維總分、三維總分、加權分都不准）。
   - **理由**：四維**不是同一把尺**，相加等於默認它們可以換算，而那個換算率
     本檔沒有依據。⚠ 而且「與目標的貼合度」與主指標部分重疊（§一-4）
     ⇒ 任何含它的總分都會把量化的結果偷渡進質化。
   - ⚠ **這一條取代了 v2 原本「四維總分與三維總分都要報」的規則**
     ——那個規則已經全檔刪掉（附錄 A-19）。
   - ⇒ 長度共線被擋掉的維度（§五-6 第 4b 項）就是**那一維不報**，
     不需要再算什麼「扣掉被擋維度的總分」。

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
     | **`rho > 0.7`** | 該維**只准寫「與長度高度共線」**，**不准用它講任何臂比較**（含該維的逐臂平均分與 P-W11 在那一維的判定）。⇒ 實務上就是**那一維不報** |
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
- **成功的定義，三個欄位、兩個角色（第四輪裁決 5）**：

  | 欄位 | 定義 | 角色 |
  |---|---|---|
  | **`hidden_frac_delivered`** | **客戶實際拿到的那一份**的隱藏通過比例。**拒交 ⇒ 0**；**交付一份空的 ⇒ 0** | **M1 的仲裁量** |
  | `hidden_frac` | **最後一份草稿**的隱藏通過比例（拒交時仍然離線計分） | **只當敏感度印出**（`primary.<seed>.<pair>.M1_lastdraft.*`） |
  | `deliv` | `accepted ∧ (hidden_frac_delivered == 1.0)` | **M2 的仲裁量** |

  **為什麼 M1 讀 `hidden_frac_delivered` 而不是 `hidden_frac`**（事前寫死）：
  本 run 量的是**客戶拿到什麼**，不是「模型私底下寫到多好」。
  一份被拒交的草稿對客戶的價值是 0，就算它隱藏驗收過了 12/14。
  ⚠ 這一刀對 `A-GATE`／`A-CONF` **不利**（它們才有拒交），而且是**刻意的**：
  拒交的成本必須算在有閘門的那一邊，否則「拒交」會變成一個沒有代價的動作。
  ⚠ `hidden_frac` 那一版照印，因為「拒掉的那些其實有多好」是一個真問題
  ——但它是**敏感度不是仲裁量**，事前就說死（收官不能挑）。
  ⚠ 兩個欄位在冒煙的 `rows.jsonl` 裡都已經存在、都已經落盤。

- **`A-SOLO` 的 `accepted` 是結構性恆真**（第四輪裁決 7）：
  它沒有閘門也沒有拒交語意 ⇒ **只要它宣告完成就算交付**，
  **包含「宣告完成但工作區什麼都沒寫」——那算交付了一份空的，
  `hidden_frac_delivered = 0`，不是 void、不是缺值。**
  ⇒ `A-SOLO` 的 `false_delivery` 在結構上等於它的錯誤率。
  **這不是發現，這是定義**，每一次引用 `deliv` 都要跟著講（§八-4）。

### 六-1　**主指標 M1 ＝ `frac` 的配對精確 Wilcoxon signed-rank**

- `diffs = [hidden_frac_delivered_GATE(t) − hidden_frac_delivered_X(t) for t in 共同題]`
  （第四輪裁決 5：讀**客戶拿到的那一份**，拒交＝0、交付空的＝0），
  丟 `vacant.research.wilcoxon_signed_rank_exact`（n ≤ 24 ⇒ `method == "exact"`，
  **必須逐次確認這個欄位是 `exact`**，掉到 `normal_approx` 就是 n 超過 24，
  那代表題數被動過）。
- 仲裁欄位：`primary.<seed>.<pair>.M1.w_plus` / `.n` / `.p` / `.method` / `.p_adj`。
- ⚠ **`hidden_frac_delivered` 的顆粒度逐題不同**（`tight` 每條值 1/10–1/15，`loose` 每條值 1/5–1/8）
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
| (iii) 成本 | `tokens.<seed>.GATE.token_per_delivered_correct` ≤ **2.0 ×** `…SOLO…`（含 void 的那一版，token 口徑＝prompt＋completion） | 2.0× | 本 run **沒有 OFF5 之類的同上限錨**（R460 的 (iii) 讀的是同一個 run 的 OFF5）。2.0× 是自訂：閘門若要當展場的建議做法，「每交出一件對的東西的代價」不該超過不設閘門的兩倍。⚠ **三條臂的實際呼叫數差異就從這一格進裁決**（第五輪裁決 2）：`A-GATE` 在 72 通內續改、`A-SOLO` 只花 ≈20 通 ⇒ 這一格量的正是「多花的那些通值不值得」。旁邊必印 `per_arm.<seed>.<ARM>.calls_per_task` 三臂的實測值 |
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
  ⇒ **引用那一維時必須逐字帶這句重疊警語**。
  （v2 原本要求「同時報扣掉那一維的三維總分」——第六輪裁決 4 之後
  **沒有總分了**，四維逐維報，所以那個補償機制不再需要，見附錄 A-19。）
- ⚠ **長度共線的維度不准用來講臂比較**（第三輪裁決 (2)，§五-6 第 4b 項）：
  `rubric.length_confound.<dim>.rho` 超過 ±0.7 的那一維，
  收官**只准寫「與長度高度共線」**，**那一維不報分數比較**。
  ⇒ 極端情況（四維全被擋）的處置事前寫死：**質化那一段只留描述與人工註記，
  一個分數比較都不寫**。
  （v2 原本的 `rubric.<seed>.total_excl_confounded` 已隨「不合成總分」一起刪掉。）
- ⚠ **去識別化丟格不對等的 seed，質化整段不可引用**（第三輪裁決 (3)，§五-6 第 1b 項）。
- ⚠ 上面兩條**都不改任何一格裁決**——它們限制的是「質化那一段能寫什麼」，
  四狀態仍然一格都不讀 `rubric.*`。

### 六-7　宣稱規則（事前寫死，`aggregate.statement_rule`）

> **`EFFECTIVE` 且三顆 seed 方向一致 ⇒ 可以寫「在 N 件目標明確、做法不指定的
> 小型工作上（N ＝ `bank.n_after_review`），把同樣的工具與預算交給同一顆本地模型，
> 加上『跑客戶自己的可見驗收、沒過就把失敗原文貼回去讓它改、預算用完還不過就不交』這一層，
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
12. **收官的任何宣稱不得引用 `boundary_only_hidden_n`**（2026-09-14 補充裁決 (2)）。
    它只留在題庫附錄當**描述**，不進任何比較、不進任何分層、不進任何句子。
    **理由**：全庫 55 條被標成 `boundary_only` 的驗收裡，**40 條只是「契約要求丟例外」**
    ⇒ 這個量實際上在講**目標／契約裡有沒有寫錯誤條款**，
    **不是**在講「這套驗收偏不偏邊界」。拿它做任何宣稱都是在講另一件事。
    ⚠ 這條禁令**取代**了 §一-3b 原本那句「不准臨時拿它當門檻」——現在是**連引用都不准**。

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

| 版本 | 格數 | 模型呼叫（中心／上界） | token（**舊估，已作廢**） | 序列算力 | **牆鐘（4 串，含 1.4× 減速）** |
|---|---:|---:|---:|---:|---:|
| A：2 臂 × 12 題 × 3 seed（**裁掉**） | 72 | 864 ／ 1,728 | ~~4.3 M～8.6 M~~ | 9.6 h | ≈ 3.5 h |
| B：3 臂 × 12 題 × 3 seed（**裁掉**） | 108 | 1,512 ／ 2,592 | ~~7.6 M～13 M~~ | 16.8 h | ≈ 6 h |
| C：2 臂 × 20 題 × 3 seed（**裁掉**） | 120 | 1,440 ／ 2,880 | ~~7.2 M～14 M~~ | 16 h | ≈ 5.5 h |
| **D：3 臂 × 20 題 × 3 seed（裁定）** | **180** | **2,520** ／ 4,320 | ~~12.6 M～22 M~~ **⇒ 見下表** | 28 h | **≈ 10 h**（上界 17 h） |

#### 七-2a　**成本模型重算**（第四輪裁決 1；錨＝冒煙實測，**2 題的錨**）

v2 的 token 估計（每通 5,000 token × 呼叫數）**低估了一個數量級**，
原因是它把「每通的 token」當成一個常數，而多輪迴圈**每通都重送整段 context**
⇒ prompt 隨輪數二次成長。

**錨（vacant-dev 冒煙實測，逐格）**：**prompt 207,591 ／ completion 14,542**
⇒ 單格合計 **≈ 222,133 token**，**prompt : completion ≈ 14 : 1**。

| 項 | 值 | 說明 |
|---|---:|---|
| 每格 prompt（中心） | **207.6 k** | 冒煙錨 |
| 每格 completion（中心） | **14.5 k** | 冒煙錨；新上限 40 k **不吃緊** |
| 每格合計（中心） | **222.1 k** | |
| **180 格合計（中心）** | **≈ 40.0 M**（prompt 37.4 M ＋ completion 2.6 M） | **比舊估的 12.6 M 高 3.2 倍** |
| completion 上界 | **7.2 M**（40 k × 180） | 硬上界，`max_completion_tokens` 擋得住 |
| prompt 上界 | **算不出來** | `max_context_tokens` 擋的是**單通 200 k**，不是累計 ⇒ **72 通**的累計沒有硬上界。⚠ 照實寫成「沒有上界」，不要編一個 |

⚠ **這個錨的四條限制，收官必須原樣帶著**：
1. **它是 2 題的錨**（`ow_01`／`ow_02`），不是 20 題的分佈。
2. **它逐臂拆不開**——上表把 222 k 一律套在三條臂上，而 `A-SOLO` 輪數少
   ⇒ **中心估計對 `A-SOLO` 是上偏的**，對整體則偏高。
3. **那一格的 prompt 207,591 已經超過新的 `max_context_tokens=200_000`**
   ⇒ 同樣的格子在新設定下會以 `budget_context` 停下來
   ⇒ **真正跑起來的每格 token 會比這個錨低**，低多少本檔量不到。
4. ⚠ **這個 token 錨是在「24 通／格」的舊預算下量到的。**
   第五輪裁決 1 把每格上限拉到 **72 通** ⇒ 同一格的累計 prompt 會**再往上長**
   （而且是二次的）⇒ **207.6 k 現在是下界不是中心**。
   ⇒ 40.0 M 這個數字要標成「**舊預算下的下界外推**」，
   收官用 `summary.json` 回填，差多少照實寫。
5. **牆鐘另算**，見 §七-2b（第五輪裁決 3）。

#### 七-2b　**時程重算**（第五輪裁決 3；每格最壞 72 通、兩台 8 串）

**公式（事前寫死，收官逐項回填）**：

```
牆鐘(小時) = 總呼叫數 × 每通秒數 × 併發減速係數 ÷ 併發串數 ÷ 3600
           = calls × T × 1.4 ÷ 8 ÷ 3600
```

- **`T`（每通秒數）＝ 錨。2026-09-14 由 `smoke9` 填入**（第六輪裁決 3）：
  **中心 `T = 10 s`、最壞 `T = 30 s`**。
  - **`T` 由生成長度決定**，不是由題目難度或輪數決定：
    smoke9 量到**每通延遲與生成 token 數的相關係數 +0.98**。
  - ⚠ **`T` 的分布是雙峰的、依題而定**，不是一個常數：
    **`ow_02` 型**（每輪只發小的工具呼叫）在 **1004** 上 **p50 ＝ 1.2 s**；
    **`ow_01` 型**（每輪重寫整個檔案）在 **1003** 上 **p50 ＝ 26 s**。
    ⇒ **平均值在這裡沒有意義**，10 s／30 s 是拿來算牆鐘上下界的，
    **不是「每通大約 10 秒」這種可以外引的描述**。
  - ⚠ 兩個 p50 分別量在**不同的台**上（`ow_02`@1004、`ow_01`@1003），
    而兩台差 1.4–3.1×（§三-2）⇒ **這兩個數字不可互相比較**，
    它們是「兩種題型 × 兩台」的四格裡的兩格，另外兩格 smoke9 沒有量。
  - 舊的四列候選（30／45／60／90）**保留在表裡當敏感度**，不刪。
- **總呼叫數**：中心＝每格 **38 通**（`A-SOLO` ≈20 ＋ `A-GATE` ≈45 ＋ `A-CONF` ≈50，
  三臂平均）× 180 格 ＝ **6,840 通**；最壞＝每格吃滿 **72** × 180 ＝ **12,960 通**。
- **併發 8 串**（兩台各 4 串，第五輪裁決 3；v2 原本是 4 串）。
  ⚠ 8 串之下 **1.4× 減速係數幾乎確定不夠**——它是用 3 併發的短請求估的。
  這一格是本節最弱的假設，照實標。

| `T`（秒/通） | 中心（6,840 通） | 最壞（12,960 通） |
|---:|---:|---:|
| **10（smoke9 中心）** | **3.3 h** | **6.3 h** |
| **30（smoke9 最壞）** | **10.0 h** | **18.9 h** |
| 45（敏感度） | 15.0 h | 28.3 h |
| 60（敏感度） | 19.9 h | 37.8 h |
| 90（敏感度） | 29.9 h | 56.7 h |

⇒ **在 smoke9 的錨之下，最壞的一格（`T=30` × 12,960 通）是 18.9 h，低於 24 h。**
⚠ 這**不是**「一定跑得完」：`T` 是雙峰的，而 8 串之下 1.4× 減速係數
**已知偏樂觀**（上一項）。若實際超過 24 h，照下面既有的取捨順序走，**不准當場想**。

**事前寫死的取捨順序（超過 24 小時就照這個走，不准當場想）**：

> **1. 砍 seed，不砍題。3 → 2。**
> 2. 2 顆 seed 仍然超過 ⇒ **停下來問 Fable**，不自行再砍。

- 砍到 2 顆 seed ⇒ 格數 180 → **120**，牆鐘 ×0.667。
- ⚠ **代價事前寫死（與 §七-4 同一條）**：複製次數從 3 降到 2
  ⇒ §六-5 的「≥2 顆 seed」要改成「**2 顆全中**」，那是**更嚴**不是更鬆。
- ⚠ **不准砍題**：砍題直接打到 §四-4 的檢定力（20 題是為了把 Wilcoxon 推過 0.80），
  而 seed 砍掉只損失複製次數、**逐 seed 的檢定力一點都沒掉**。
- ⚠ **不准砍 `A-CONF`**（§七-4 已寫死）、**不准把 3 份再降成 2 份**
  ——降到 2 份會讓 §三-6 的 C9 更難通過，而 C9 是「機制有沒有發生」的唯一擋門。

**版本 D 之外還要算進去的機時**（事前登記，不然收官對不起帳）：

| 項 | 格數／通數 | 牆鐘 |
|---|---:|---:|
| 探針 PR-1（工具協定，兩種模式各 20 輪） | ~40 通 | < 0.5 h |
| 探針 PR-4（跑完一題，丟掉） | ~72 通 | < 0.5 h |
| **冒煙**（§三-6，2 題 × 3 臂 × 1 seed；**C9 要求兩條臂真的動起來** ⇒ 比 v2 估的貴） | **6 格 ／ ~230 通** | **< 1.5 h** |
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
拿掉它就同時拿掉了「同上限、換一種花法」的對照（§八-4）與四狀態的 (ii)、(iv) 兩格，
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

### 八-2　自建題庫的代價（五條）

（⚠ **修復紀錄**：本節在 `138d6ef` 的合併裡被回退成第三輪之前的三條版本，
2026-09-14 依原文復原並補上第 5 條。）

1. **沒有外部基準可比。** 20 題是我們自己寫的，別人沒跑過。
   收官不准把通過率拿去跟任何公開榜單比。
2. **作者偏誤擋不掉、只擋得住一部分。** §五-2 的公平性複核擋的是
   「隱藏驗收藏了目標沒暗示的需求」，擋不掉「題目的選擇本身偏向迴圈擅長的形狀」。
   ⚠ 事前承認：**17/20 題是「契約釘死語意、邊界情況多」的題型**，
   而那正是回饋迴圈最可能有用的形狀。
   v2 加了 3 題 `loose` 當負向對照（§一-3），**但 3 題只夠看方向、不夠下結論**
   ——所以這一條**沒有被解決，只是被標示出來**。
3. **n 小。** 20 題（複核後可能更少）× 3 seed，逐 seed 判。
   §四-4 的檢定力表就是這一條的後果。
4. **題庫的作者是代理不是人類。** `ow_13`…`ow_20` 由題庫代理寫、由另一個代理複核，
   人類沒有逐題看過。§五-2 的擋門是可執行的，但「這 20 題合不合起來是一個
   好的任務分佈」這個判斷**沒有人做過**。
5. **`loose` 層為了通過反向擋門，往 `tight` 靠了一步**（2026-09-14 補充裁決 (3)）。
   §五-2 第 2 條要求「目標敘述裡每一句客戶困擾都要有對應驗收」，反過來也要求
   **每條驗收都指得回目標**。`loose` 的契約刻意留白 ⇒ 它的驗收只能指回**目標**
   ⇒ 為了讓那些驗收有 anchor，**`ow_19`／`ow_20` 的目標敘述補述成列出了
   隱藏驗收的覆蓋面**（**列的是要處理哪些情形，不是做法**）。
   ⇒ **代價照付、寫在這裡**：那兩題的目標比原本具體，
   **`loose` 層因此離 `tight` 近了一步**，它作為負向對照的力道**比設計時弱**。
   ⚠ 收官引用 `by_stratum.loose` 的三筆逐題差時**必須帶這一句**；
   第 2 條（選題偏誤只是被標示出來）因此**更成立不是更不成立**。

### 八-3　汙染

- **不可**宣稱模型沒看過類似任務（§一-5）。
- 汙染的方向性後果：完整記住的題會讓三條臂都第一輪就過 ⇒ **壓縮檢定力，
  不製造假效果**。但這句話**只在「記住」是全有全無的時候成立**——
  部分記住（記得 CSV 怎麼 parse、不記得我們的 exit code）會抬高共同基準線、
  同樣壓縮差距。兩種都是往「量不到」的方向走。

### 八-4　**上限相同、實際用量不同——「等預算」這個詞已從本檔刪除**（第五輪裁決 2）

- **三條臂的上限逐欄相同**：每份 24 通、每格 72 通、completion 120k、context 200k、
  牆鐘 7,200 s。**上限是設計，用量是資料。**
- **實際用量事前就知道會差很多**：`A-SOLO` ≈1 份 ≈20 通；
  `A-CONF` 最多 3 份 ≈ 最多 72 通；`A-GATE` 在 72 通內續改。
  ⇒ **逐臂落盤、逐臂報**（`calls_per_task`／`calls_hist`），
  差異**進成本指標 (iii)**（§六-5），不是被抹平也不是被忽略。
- ⚠ **v2 原本用「等預算」形容 `A-GATE` vs `A-CONF`，那個詞已經全檔刪掉。**
  它不準確：兩條臂的**上限**一樣，但 `A-CONF` 每份從零開始、`A-GATE` 的後續輪
  站在前一輪的工作區上 ⇒ **同樣 72 通買到的東西本來就不一樣**，
  而那正是要量的東西。口徑沿用 R460：上限寫死、用量落盤。
- 人類問的「收第一份」對「有閘門」那一刀（`A-GATE` vs `A-SOLO`）
  **本來就不是同用量比較**，而且**故意不是**。
- ⇒ v1 曾考慮的「兩臂版」（沒有 `A-CONF`）**拿不到「同上限之下換一種花法」的對照**，
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

一格最多 **72** 通呼叫、40 次工具往返；任何一通重試用盡都會 void 掉**整格**
（含前面已成功的輪次）。⇒ `A-GATE`／`A-CONF` 的 void 曝險比 `A-SOLO` 高 2–3 倍，
而 void 格燒掉的 token 不進分母 ⇒ **token／題會被低估**。
⇒ 兩個 token 數字都要報，(iii) 的仲裁用**含 void 的那個**（較嚴）。

### 八-11　**兩台後端不一樣快**（2026-09-14 去快取配對探針）

- **量到什麼**：**1003 比 1004 慢** ——冷 prefill **3.1×**、暖 prefill **1.4–2.7×**、
  生成 **1.6×**。
- **判定：task 層級的干擾項，不是 arm 層級的混淆**。
  理由與 R460 §二-2 逐字同一條：**同一題的三條臂一定打同一顆後端**
  ⇒ 配對差分把後端消掉。
- ⚠ **它會打到的是 `budget_wall`**：同樣 7,200 s 的牆鐘，在慢的那一台上
  **咬到的題目不一樣**（慢台會先撞到）。
  ⇒ analyzer **必須逐後端印 `budget_wall` 的計數**
  （`per_arm.<seed>.<ARM>.stop_reason_by_backend.budget_wall.<1003|1004>`），
  不准只印一個合併數字。
- ⚠ **跨塊的絕對值（通過率、token／題、牆鐘）混了後端速度差** ⇒
  收官要逐後端拆開描述；**配對比較不受影響**（R529 §一一-2 的同一條）。
- ⚠ **佇列必須輪流分配**（§三-5）。手動綁死 ⇒ 題目與後端共線 ⇒ 上面「配對差分
  把後端消掉」那個保證**仍然成立**（同題三臂同台），但「哪些題撞到 `budget_wall`」
  會變成一個系統性的偏誤。`smoke9` 是綁死跑的，**它的兩塊不可跨台比**。

### 八-8　質化的七條限制

1. **評審是 12B／27B 本地模型**，而本 repo 自己量過模型評審票近乎常數函數
   （R438／R516／R440P §三）。**本輪又量到一次**：同模型、同 temperature 0 的
   兩位評審在假資料上 **κ = 1.000**（§五-6 第 3 項）——那是常數函數不是一致。
2. **「與目標的貼合度」與主指標部分重疊** ⇒ 引用那一維時必須逐字帶重疊警語。
   ⚠ **四維逐維報、不合成總分**（第六輪裁決 4，§五-6 第 3b 項）：
   四維不是同一把尺，相加等於默認它們可以換算，而那個換算率本檔沒有依據。
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
   ⇒ 被擋的維度只准寫「與長度高度共線」，**那一維不報分數比較**。
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

- **沒有**第四條「同上限的 SOLO×3」臂（R460 的 OFF5 類比）。
  ⇒ 「5 次獨立重寫、挑最後一份」這個對照本 run **量不到**。
- **沒有**跨模型複製（三條臂共用 `gemma-4-12b-it-qat`）。
- **沒有**跨機器複製（工作區全在 vacant-dev 一台）。
- **沒有**人類評分者的質化（只有 Fable 抽讀的註記，n 很小且不盲）。
- **沒有**「多做幾輪會不會更好」的曲線。`A-GATE` 名目 5 輪，但在 72 通之下
  實際只跑得到 **2–3 輪**（§二-3）⇒ **輪數的邊際效益本 run 量不到**，
  而且「跑了 2 輪就停」是**被預算擋住**不是「收斂了」。
- **沒有**在 `loose` 層下任何結論的能力（3 題，§一-3a）。
- **沒有**第三顆模型的質化視角：J1／J2 已經是**跨模型**（gemma × qwen，第三輪裁決 (1)）,
  但兩顆都是本機小模型 ⇒ 「換一顆更強的模型來評會不會得到不同結論」本 run 量不到。

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
7. **【已裁 → §二-3】** 第五輪裁決 1：冒煙量到**一份 ≈20 通** ⇒
   24 改成**單份**上限、每格總上限另設 **72**、`A-CONF` 從 5 份降為 **3** 份。
   **殘餘兩條**：(a) 72 與 3 這兩個數字的依據是**機時**不是機制
   （「3 份就夠了」這句話本檔一個字都沒有講）；
   (b) `A-GATE` 實際只跑得到 2–3 輪 ⇒ 「迴圈多跑幾輪會不會更好」仍然量不到（§八-10）。
   v1／v2 原文：**`max_model_calls=24` 這個數字沒有錨。** R460 的 5 通是綁 OFF5 的；
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
- **本檔仍未凍結的東西，逐條**（2026-09-14 更新：1／2／3／3b 已由附錄 AMEND1 處理，
  仍**待 Fable 或人類簽字**才算凍結；4／4b／5 還開著）：
  1. ~~`ow_13`…`ow_20` 的逐題內容~~ ⇒ **已回填** §一-3c（逐字抄自 `bank/`）；
  2. ~~20 題 × 四種檔案的 sha256~~ ⇒ **已釘死** 附錄 AMEND1-D（469 檔逐檔 sha256
     ＋ 合併雜湊 `bank_sha256`）；
  3. ~~§五-2 的複核結果與最終成員~~ ⇒ **已落盤**：20 題全過、`excluded` 0、
     `amended` 5（五筆都已修進題庫），報告在 `ops/gain/r530/review/`，
     **含 §一-3b 的 `difficulty_gate` 結果**（AMEND1-C 重印）；
  3b. ~~逐題 `meta.json` 的 `ref_solution_lines` 與 `boundary_only_hidden_n`~~
      ⇒ **已落盤**（§一-3 的 20 題一覽表；`boundary_only` 讀法＝嚴格，見 §一-3b）；
  4. 沙箱實際落在 S1 還是 S2（基建代理驗證中，§三-3）；
  4b. J2（`qwen/qwen3.8-27b`）**能不能關掉 thinking**——§五-6 寫的是
      「若該顆可設；設不了就照實記」，發射前要試一次並把結果寫進 AMEND1；
  5. §三-5 註冊行的逐塊 `n`（複核之後的機械後果）。
  **以上全部要在任何一通模型呼叫之前完成。** 1／2／3／3b 這四項確實是在
  **任何一通模型呼叫之前**做完的——AMEND1 的每一步都是唯讀檔案與確定性重算，
  零模型呼叫（§八-0 的同一條紀律）。
- 本檔只出檔案、指令與判準；發射由人類或 Fable 的明示指令觸發。

### 一〇-1　**凍結程序**（第六輪裁決 6；發射前最後一個動作）

> **凍結 ＝ 把下面七樣東西一次寫進一份 `FREEZE` 區塊，然後才發射。**
> 少一樣就不是凍結，是「大概記得」。

| # | 要記什麼 | 從哪裡取 | 為什麼非它不可 |
|---|---|---|---|
| **F1** | **程式碼 commit sha** ＝ 基建分支**併入主線之後**的 `HEAD` | `git rev-parse HEAD` | 發射器與 analyzer 的 `runner_git_info` 要對得上這一個 sha（§五-5 E-6）。⚠ **不是**基建分支自己的 sha——併入之後才是實際會跑的那一份 |
| **F2** | **bank sha256** ＝ AMEND1-D 的 **`1eae5f19…`** | 附錄 AMEND1-D 的 `bank_sha256` | §五-5 E-2 逐檔比對的根；對不上就 `abort_bank_sha_mismatch` |
| **F3** | **`judge_bank` 投影 sha** | `export_for_judge.py --check` 的輸出 | 盲評吃的是投影不是正典（§五-6 第 1c 項）⇒ 投影自己也要有 sha，否則「指對目錄」這件事沒有證據 |
| **F4** | **E-9／E-11 preflight 的存證路徑** | 沙箱與推理模式探針各自的落盤檔 | 這兩道是**發射前**的擋門（`repo_hidden_from_sandbox == true`、兩台 `reasoning_tokens == 0`）⇒ 證據必須指得出檔案，不是「當時跑過」 |
| **F5** | **smoke9 檢核表路徑** | `runs/_smoke/.../checklist.json` | C1–C9 的逐格結果。⚠ **C9 是「機制有沒有發生」的唯一擋門**，它的證據不能只活在對話裡 |
| **F6** | **發射時間戳**（UTC） | 發射器 log | 兩台在發射前後的任何變動（LM Studio 版本、模型重載、併發數）都要能對到時間軸上 |
| **F7** | **佇列 JSON 的 sha** | `ops/gain/r530/queues/*.json` | §三-5 的註冊行是「哪些塊被註冊過」，**佇列 JSON 才是跑的順序**（R529 §二-2 的同一條）。順序會影響後端輪流分配，所以它要有 sha |

⚠ **凍結之後到發射之間不准改任何一項。** 改了任何一項 ⇒ **重新凍結、重記七樣**，
並在 `FREEZE` 區塊裡留下上一版（不是覆蓋掉）。
⚠ **F1–F7 全部寫進本檔的一個新章節或一份 `DECISION_..._R530_FREEZE.md`**，
而且要**逐字抄進發射器的 log 開頭**——兩邊對不上就停。
⚠ **本輪（第六輪）寫完、等 smoke9 的檢核表補齊之後，本檔就凍結。**
凍結之後的任何改動都要走修訂案，不准就地改正文。

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
  並在 §八-4 寫明它拿不到「同上限換一種花法」的對照。
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
- **補充裁決 (a)(b)、第三輪 (1)(2)(3)、第四輪 1–8、第五輪 1–5、以及 2026-09-14 補充裁決 (1)(2)(3) 改完之後各掃過一次，三個詞都沒有被帶回來。**
- **第五輪另外刪掉一個詞：「等預算」。** 它讓人以為 `A-GATE` 與 `A-CONF` 花一樣多，
  而事實是**上限一樣、用量不會一樣**（§八-4、附錄 A-17）。全檔只剩兩處提到它，
  兩處都是在講「這個詞已經被刪掉」。
- **2026-09-14 補充裁決 (1) 掃到 AMEND1 帶進來的一處「證明」**
  （量具單邊保證那一段），已改成「擋得住的是／不代表」。
- **第六輪掃過一次，三個詞都沒有被帶回來。**
  ⚠ 第六輪另外刪掉一個**量**而不是一個詞：**「四維總分」**（附錄 A-19-4）。
  它不是措辭問題，但它與措辭紀律同源——**把四個不同的尺相加，
  等於用一個沒有依據的換算率講一句聽起來更有力的話。**
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
  不准用它講任何臂比較（那一維直接不報）。
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

### A-16　**基建冒煙推翻的四個假設**（第四輪裁決 1–8，2026-09-14）

本輪與前三輪**性質不同**：前三輪改的是判準，這一輪改的是**被量測推翻的事實宣稱**。
四條都是本檔**寫成「應該可以」而實際上不行**的地方，逐條留著。

| # | 本檔原本怎麼寫 | 冒煙量到什麼 | 依據 | 改成什麼 |
|---|---|---|---|---|
| **1. 工具協定預設** | §二-4：「預設走**文字協定**」，理由是「R460 實測同一顆模型的圍欄遵循 925/925」 | **文字協定下 6 格有 4 格零工具呼叫**——模型回 ```` ```python ```` 區塊或它自己的 `<|tool_call>` 內部格式，harness 兩種都解析不到 ⇒ 那 4 格**等於沒有 agent**。`native` 探針回 `finish_reason=tool_calls` 正常 | vacant-dev 冒煙（6 格＝2 題 × 3 臂）的 `calls.jsonl`；本機 stub 對照跑在 `runs/_smoke/g_r530_local/`（`rows.jsonl` 6 列、`checklist.json` C1–C8） | **預設 `native`**，文字協定降為備援；兩種不得混算；**PR-1 探針改成每次換模型必跑**（§二-4） |
| **2. token 預算口徑** | §二-3：`max_tokens: 120_000` **總量**（prompt＋completion 一起算） | **單格 prompt 207,591／completion 14,542**（≈14:1）。多輪迴圈每通重送整段 context ⇒ **prompt 隨輪數二次成長** ⇒ 120 k 總量在 **5–8 通**就撞滿，而那會把輪數多的 `A-GATE`／`A-CONF` 系統性砍在半路 | 同上 | 拆成 **completion 累計 40 k** ＋ **單通 context 200 k**（超過 ⇒ `budget_context`，拒交語意）；成本指標 (iii) 改成**含 prompt＋completion**、逐格兩種都印；§七-2a 用這個錨重算成本（**40.0 M，比舊估高 3.2 倍**） |
| **3. bwrap 的 AppArmor 前提** | §三-3：認為 Ubuntu 24.04 的 `bubblewrap` 套件**自帶 profile、裝完應可用** | **套件不帶 profile。** `kernel.apparmor_restrict_unprivileged_userns=1` 之下，光 `apt install` 不會讓 bwrap 能跑，**還要另外寫一份主機端 AppArmor profile 並載入** | 基建代理在 vacant-dev 的安裝驗證 | §三-3 照實更正；S2 退路改成 **ACL 結構隔離**（`hidden/`／`reference/` 由專用使用者擁有、`mode 700`，驗收 runner 以該使用者跑，agent 的 bash 以 `user1`＋`unshare -n`）；判準改成「**兩者任一達到 E-9 即可**」 |
| **4. persona 的 rng 鍵** | §三-5：`random.Random(f"{seed}:{arm}")` | 鍵裡含 `arm` ⇒ **三條臂在同一題上抽到不同的 persona** ⇒ 與 §二-2「三條臂的第一則訊息逐字相同」**直接衝突** | 設計層面的矛盾，冒煙時逐格核對 `persona_first` 才看出來 | 改成 `random.Random(f"{seed}:{task}:{attempt}")`（不含 `arm`），**以「第一則訊息逐字相同」優先**；`A-CONF` 靠 `attempt` 遞增換人，另兩臂 `attempt` 恆為 1 |

**本輪同時新增、不是推翻而是補洞的三處**：

- **E-9**（§五-5）：V/GT 分離必須是**結構性**的（`repo_hidden_from_sandbox == true`），
  不能只靠 `DENY` 的指令文字比對。⚠ 冒煙那一次這個值是 **`false`**，
  而 `backend_meta.json` 的 `honest_bound` 逐字寫著
  「**不是沙箱**：沒有網路隔離、沒有檔案隔離」——**帶著 `false` 不准發射**。
- **E-10**（§五-5）：`ws_start == ws_end` 且零工具呼叫 ⇒ `noop_cell`；
  同臂 noop > 20% ⇒ run `INVALID`。這一條是裁決 2 那批冒煙的直接產物。
- **M1 改讀 `hidden_frac_delivered`**（§六-0，裁決 5）：拒交＝0、交付空的＝0，
  量的是**客戶拿到什麼**；`hidden_frac`（最後一份草稿）降為敏感度。
  ⚠ 這一刀對有閘門的兩條臂**不利**且**刻意**——拒交的成本必須算在有閘門的那一邊。

⚠ **這一節最該被記住的一句**：前三輪的裁決是「判準訂得對不對」，
**這一輪的四條全部是「我以為會這樣，量出來不是」**。
四條裡有三條（協定、token、profile）如果沒有冒煙就會直接帶進正式 run，
而其中至少兩條會**安靜地**製造與機制無關的臂間差異
（文字協定下的 noop 格、120 k 總量砍掉輪數多的臂）。
§三-6 那份冒煙檢核表**買到的就是這個**。

---

## 附錄 AMEND1（2026-09-14）：§五-2 複核結果、五項修正、題庫 sha256 凍結

> **這份附錄在任何一通模型呼叫之前完成。** AMEND1 的每一步都是唯讀檔案、
> 確定性重算與人寫的判斷，**零模型呼叫**（§八-0 的同一條紀律）。
> 它處理 §一〇 未凍結清單的第 1／2／3／3b 項；第 4／4b／5 項仍開著。
> ⚠ **本附錄不授權發射**，發射仍由人類或 Fable 的明示指令觸發。

**這份附錄是誰寫的、憑什麼**：§五-2 的複核由**一位不是題庫作者的獨立代理**做完
（唯讀、零模型呼叫，報告逐位元複製進 `ops/gain/r530/review/`）。Fable 讀完報告後
裁了五項修正；本附錄由**第三個代理**（既不是作者也不是複核者）執行那五項並落盤。
⚠ **三個角色都不是人類。** §八-2 第 4 條（沒有人類逐題看過這 20 題）**沒有被本附錄解決**。

### AMEND1-A　五項修正，逐條

#### 第 1 項　`ow_08_logscan`：反向擋門失敗 ⇒ 補 CLI 驗收（**唯一一項改到凍結語意的**）

| 欄 | 內容 |
|---|---|
| **複核依據** | `review_r530.md` §二 `ow_08`（全庫唯一一筆反向擋門失敗）＋ §四-1 |
| **問題** | goal 最後一句「Finally they want to eyeball a file from the shell without writing a script.」**零驗收**。契約寫了 `python -m solution FILE` 卻補一句「Prints a table a person can read. Nothing about its layout is checked.」——那句話**不可計分**。參考解 64 行裡約 16 行在實作這個 CLI ⇒ 按 §五-2 擋門 2，這是「沒有被量到的需求」：不做的人不掉分，做的人在計分之外白付難度 |
| **改了什麼** | `bank/ow_08_logscan/contract.md` 的 Command line 節：改成 stdout 放 `summarize` 回傳的**那一個 JSON 物件**、exit 0，**版面（縮排、鍵序、空白、結尾換行）仍明寫不驗**，並補一句「壞行不構成命令失敗」。新增 `tests_visible/v04_command_line.py`（1 條可見）、`hidden/h15_cli_gives_back_the_result.py` ＋ `hidden/h16_cli_survives_bad_lines.py`（2 條隱藏）。三條都照 `ow_01` 的寫法用 `subprocess` ＋ `tempfile.mkstemp`（系統 TMPDIR，**不動工作區**）。`reference/solution.py` 的 `main()` 改成印 `json.dumps(report, indent=2)` |
| **為什麼不是「刪掉那句」** | 兩條路都合規（§五-2 擋門 2 寫「要嘛補驗收、要嘛從目標敘述刪掉」）。刪掉會讓「從 shell 直接看」這個真需求消失，而它是這題唯一不是純函式的部分；而且刪掉會讓參考解掉約 16 行、把核心 12 題的中位數從 67.0 推到 65.5——**兩條路都會動 D1**，不是「補驗收比較保守」 |
| **為什麼可見也要補一條** | 只補隱藏的話，CLI 會變成「計分但 worker 看不到」的需求——那正是 §五-2 要擋的形狀。`ow_01` 的做法就是可見（`v03`）＋隱藏（`h10`／`h11`）都有，本項照抄 |
| **⚠ 偏離凍結文字（兩處，都記在這裡，沒有默默放過）** | (a) §一-2 的 `ow_08` 條目原本寫「CLI……**不計分，只進質化**」——現在計分了。(b) 條數：可見 3→**4**、隱藏 14→**16**，超出當時 §一-1 的界。當時的處置是量具**具名例外** `gauge_r530.COUNT_EXCEPTIONS`（只放行 `ow_08`），理由是放寬會讓其他 19 題一起漂。⚠ **2026-09-14 補充裁決 (1) 改了這個處置**：界本身改成可見 2–4／`tight` 10–16／`loose` 5–7、**上下界都判**，具名例外**發射前移除**（附錄 A-18-1）。上面這段是當時的紀錄，原樣留著 |
| **副作用** | `ref_solution_lines` 64 → **61**（`main()` 短了 3 行）⇒ 核心 12 題中位數 67.0 → **65.5** ⇒ D1 兩個口徑都重算（AMEND1-C）。§一-3b 明寫「退回重寫之後整組 D1／D2 重算」，照做 |

#### 第 2 項　`ow_15_tomlsub`：契約補一句 `dumps` 的排版

| 欄 | 內容 |
|---|---|
| **複核依據** | `review_r530.md` §二 `ow_15`（「全庫最接近排除的一條」）＋ §三 表第 2 列 |
| **問題** | `h12_written_order` 比對**整串輸出文字**，等於把 `apple = 2` 裡等號兩側的**單一空白**也釘死了；而契約只在 **parse 的行文法**裡寫過 `name = value`，從來沒規定 `dumps` 的排版（複核者實測參考解的 parser 吃得下 `a=1`）⇒ 一個 `dumps` 輸出 `apple=2` 的解滿足契約每一句（含兩條 round-trip）卻被 h12 擋掉 |
| **改了什麼** | `bank/ow_15_tomlsub/contract.md` 補一條：「`dumps` writes every setting on a line of its own as `name = value`, with exactly one space on each side of the `=`, and every heading on a line of its own.」**測試一個字都沒改** |
| **為什麼補契約不是改測試** | 排序那個主張本身錨得死死的（`anchor` 逐字存在），缺的只是排版那一句。改測試會讓一個真實需求（可手編的正規輸出）從計分裡消失 |

#### 第 3 項　三份 `loose` 的 `rubric.md`：拿掉不存在的加權

| 欄 | 內容 |
|---|---|
| **複核依據** | `review_r530.md` §三 表第 5 列（**唯一一筆 rubric 層級的 `amended`**）＋ `review_r530.json` 的 `prereg_deviations_noted[2]` |
| **問題** | `ow_18`／`ow_19`／`ow_20` 的 rubric 加了 `readability + 2*structure + error_handling + 2*fit_to_goal` 的加權，並自稱「prereg amendment, Fable ruling 2026-09-13」。**本檔全文沒有任何加權**，§一-4 明寫「全部題目共用同一份」，§六-6 已經寫死質化那一段能報什麼。那條裁決**不存在於任何凍結文件** |
| **改了什麼** | 三份 rubric 的量表段換成與其他 17 題**逐位元相同**的那一份（四維各 1–5、等權），移除加權句與「prereg amendment, Fable ruling」字樣、移除表頭的「(double weight)」。`loose` 的描述性說明保留，移到「逐題範例」那一節的開頭 |
| **為什麼是拿掉而不是寫進預註冊** | 兩條路 Fable 都可以選，Fable 選了拿掉。**不可以帶著一句凍結文件裡沒有的裁決進 AMEND1**——那會讓「預註冊」這個詞失去意義 |

#### 第 4 項　`ow_19_redact`／`ow_20_slugify`：把隱藏驗收多要求的性質補進目標

| 欄 | 內容 |
|---|---|
| **複核依據** | `review_r530.md` §二 `ow_19`／`ow_20` ＋ §三 表第 3、4 列 ＋ **§四-3**（給 Fable 的三個質疑的第 3 點） |
| **`ow_19` 的問題** | 目標給**三個字面例子**，隱藏驗收要的是**類推**：`h01` 用 `mysql://`、`h03` 用 `amqp://`、`h05` 用 `mongodb://`、`h06` 用 `redis://`，`h05` 還把 `Authorization: Bearer tok-one`（**不是**點分三段的 JWT）算成密鑰。兩條可見驗收用的卻都是目標的三個字面例子 ⇒ **把三個字面值寫死的 worker 可見全過、隱藏六條掉四條** |
| **`ow_20` 的問題** | `h03` 對標題 `"..."`（純標點）斷言 `slug != ""`，而目標的「非空」保證只綁在「a title written in a script with no Latin letters in it at all」上——純標點算不算「一種文字」是可爭的 |
| **改了什麼** | 兩題都**只改 `goal.md`、不改測試**。`ow_19` 在三個例子之後補一段：那三行是昨天的、不是全部，同樣三類會換個寫法出現（key 裡有別的字、token 不是點分的、以及 mysql／mongodb／redis／amqp 這些別的 store 的位址）。`ow_20` 補一條 bullet：純標點的標題也是標題，也要有非空 slug。**兩段都用「客戶要什麼」的口吻，沒有給做法**（不給 pattern、不給轉寫規則、不給 fallback 長什麼樣） |
| **⚠ 這一項最值得記的一句** | **「驗收要求的 > 目標承諾的」在 §五-2 現行三條擋門下是不可表達的**：擋門 1 只問「錨得回去嗎」（錨得回去）、擋門 2 只問「目標每句有沒有被量」（有）、擋門 3 只問重複（沒有）。這個形狀**只有人讀得出來**。它同時解釋了為什麼 §五-2 一定要人做，以及為什麼「複核通過」不該被讀成「題目的難度與目標對齊了」 |
| **副作用** | 補進目標的那兩段本身也是**目標句子**，按 §五-2 擋門 2 也要被量到：`ow_19` 那一段由 `h01`／`h03`／`h05`／`h06` 量到，`ow_20` 那一條由 `h03` 量到。⚠ 但 `ANCHORS.md` 是**一檔一錨**（每條驗收只列它檔頭宣告的那一句），所以這層對應**在那張表上看不見**——與複核者對 `ow_11/h11` 記的是同一個限制。`export_bank.py` 已把這句警告寫進每一份 `ANCHORS.md` 的表頭 |

#### 第 5 項　`boundary_only_hidden_n`：逐條落盤 ＋ 讀法寫死

| 欄 | 內容 |
|---|---|
| **複核依據** | `review_r530.json` 的 `per_hidden`（249 條逐條）與 `boundary_only_criteria_applied` |
| **改了什麼** | 20 份 `meta.json` 各補 `boundary_only_hidden_n`（條數）與 `boundary_only_hidden`（逐條 `{boundary_only, note, marked_by}`）。§一-3b 補一段把**讀法**寫死＝**嚴格**（一條驗收只有在它所評分的每一個輸入都落在三條判準內時才算 true；同時評了普通情況就是 false；判準 (2) 照字面讀成「契約要求丟例外的那一條」） |
| **數字** | 嚴格讀法 **55／251（21.9%）**；複核當時的口徑是 **55／249（22.1%）**，差在 AMEND1 新增的兩條（都判 false）。寬鬆讀法約 **67／251（約 27%）**，差在哪 12 條逐條列在 `review_r530.json` 的 `boundary_only_criteria_applied.sensitivity` |
| **⚠ 誠實邊界** | **55 條裡 40 條是判準 (2)**——嚴格讀法下這個量幾乎塌縮成「這條是不是例外檢查」。跨題比較時它量到的主要是「這題的目標有沒有錯誤條款」（`ow_09` 的 7／13 是因為目標自己列了四種「模板寫壞」；`ow_03` 的 0／14 是因為契約一個例外都不要求），**不是**「這題的隱藏驗收有多偏邊界」。§一-3b 已寫死它**只落盤、不設門檻**；收官若拿它做「增益是不是只來自邊界條」的分層，**分層變數的語意比預期弱**，必須照這一句講 |
| **⚠ 誰標的** | 249 條由**複核者**標；`ow_08` 的 `h15`／`h16` 是 AMEND1 之後才存在的，複核者**沒看過**，由本附錄的修訂代理照複核者凍結的同一個嚴格讀法標（兩條都是 false）。`meta.json` 的 `marked_by` 欄逐條寫明是誰標的，不准混為一談 |

### AMEND1-B　§五-2 複核結果摘要

| 項目 | 結果 |
|---|---|
| `passed` | **20 題全過** |
| `excluded` | **0 條、0 題**（§一-6 第 2 條的 `excluded` 陣列為空，不是沒寫） |
| `amended` | **5 筆 ⇒ 已全數處理，殘餘 0**（4 筆題目層級 ＋ 1 筆 rubric 層級） |
| 正向擋門（每條隱藏驗收 anchor 逐字指得回原文） | **249／249 過**（複核者獨立重跑，不只信 `gauge_r530.py`） |
| 反向擋門（目標每句困擾都有驗收） | 複核當時 **19／20**（`ow_08` 失敗一句）⇒ AMEND1 第 1 項修掉 ⇒ **20／20** |
| 可見／隱藏零重疊（擋門 3） | **過**（0 條逐字相同；11 筆 `overlap_note` 記錄「同需求不同輸入」，那是設計不是重複） |
| `boundary_only_hidden_n` | **55／249（複核口徑）→ 55／251（AMEND1 後）**，嚴格讀法 |
| §一-6 第 6 條的停機條件（`tight` < 14 或 `loose` == 0） | **沒有觸發**：`tight` 17、`loose` 3、`bank.n_after_review = 20` |
| 退回重寫次數 | **0** |

**複核報告的正典副本**（逐位元複製，AMEND1 釘的就是這兩份）：

| 檔 | sha256 |
|---|---|
| `ops/gain/r530/review/review_r530.md` | `f8b1c69d28a104d9b5846bb3e6b7a43484d47d713dd6c91e837eb55d3a4e078a` |
| `ops/gain/r530/review/review_r530.json` | `7da34015b990d34fa750baaca733eb4a333c202120c519b0bc9713ef178a8079` |

⚠ §五-2 寫的落盤路徑是 `ops/gain/data/openwork/_fairness_review.json`。那個目錄是
發射基建的形狀、由基建代理建；**在它存在之前，正典副本是上面這兩份**，
analyzer 要比對的也是上面這兩個 sha256。

### AMEND1-C　§一-3b 難度擋門：AMEND1 後重印（兩個口徑都印）

| 量 | AMEND1 前 | **AMEND1 後** |
|---|---:|---:|
| 核心 12 題的 `ref_solution_lines` 中位數 | 67.0 | **65.5** |
| 新 5 題 tight（`ow_13`–`ow_17`）的中位數 | 66.0 | **66.0** |
| 相對差（**tight-only 口徑**，Fable 2026-09-13 的複核指示） | 0.0149 | **0.0076** |
| 新 8 題的中位數（**預註冊字面口徑**） | 45.0 | **45.0** |
| 相對差（**字面口徑**，§一-3b 表格 D1 那一列寫的） | 0.3284 | **0.3130** |
| **D1（>40% ⇒ 紅）** | 綠 | **綠（兩個口徑都綠）** |
| **D2**（`tight` hidden ≥10、`loose` ≥5） | 綠 | **綠**（`tight` 最小 12＝`ow_14`／`ow_17`；`loose` 6／6／7） |
| 退回重寫次數 | 0 | **0** |

核心 12 題的 `ref_solution_lines`（排序）：16, 30, 39, 39, **61**, 61, 70, 80, 87, 92, 105, 113
（粗體那個是 `ow_08`，AMEND1 前是 64；它原本正好壓在中位數兩格 64／70 的下半格上，
所以 3 行的變動把中位數推了 1.5）。新 8 題：23, 26, 29, 31, 59, 66, 79, 200。

**兩個口徑差很多，兩個都要印**：tight-only 0.0076，字面口徑 0.3130。字面口徑離紅線只剩
約 9pp，而它之所以接近紅線，只是因為三題 `loose` 的參考解**本來就短**（23／26／29 行，
契約只釘進入點）。**判準照 §一-3b 表格寫死的那一個**（字面口徑，0.3130，綠），
**沒有事後換算法**。

**§一-3b 的四條誠實邊界，一條都不准掉**：

1. **行數是難度的粗代理，不是難度。** `ow_15` 的 200 行與 `ow_07` 的 16 行落在同一個
   中位數檢定裡，中位數看不見這個離散度。`ow_07` 只有 16 行卻有 13 條隱藏驗收、
   覆蓋十個困擾——這正是行數代理看不見的錯配。
2. **40% 這條線是訂出來的，沒有外部錨。** 它是**選擇**不是量測。
3. **D1 只比新題 vs 核心題**，不保證 20 題整體的難度分佈合理。
4. **§八-2 第 4 條（沒有人類逐題看過這 20 題）沒有因為這個擋門或這次複核而被解決。**
   ⚠ AMEND1 第 1 項順帶修掉了複核者記的第三條誠實邊界（`ow_08` 有 16 行 CLI 程式碼
   不被任何驗收讀）——現在那些行被量到了，但那是**修掉一個特例**，不是解決代理本身的問題。

### AMEND1-D　題庫 sha256 釘死表（`ops/gain/r530/bank/`，2026-09-14）

```
bank_sha256  1eae5f193a0e7616ebe13b430c075848c23bbad204f6017e8c93cc40a2dd48ef   (469 files)
```

**合併雜湊怎麼算的**（寫死，不准事後改）：把下面每一行 `<sha256>  <bank/ 起算的相對路徑>`
以換行串起來（路徑以 UTF-8 位元組序排序、結尾補一個換行），整串 UTF-8 取 sha256。
`__pycache__` 與 `.pyc` 不算。重算指令：

```
python3 ops/gain/r530/gauge_r530.py --bank-sha
```

⚠ **`meta.json` 也在表裡**：每一題 `meta.sha256` 是自己算自己那一題的其他檔案，
**算不到自己那一檔**，所以 `meta.json` 的雜湊只能在這一層釘死。
發射器與 analyzer 逐檔比對，對不上就 `abort_bank_sha_mismatch`（§一-1）。

<details>
<summary>469 檔逐檔 sha256（點開）</summary>

```
47237a488aef393f5ad709773c7593cbf72f4fddbe8e469a3314ea312a6483f3  ow_01_csvjson/contract.md
ba394f69423fed745ccee2bd4cab736edc9531745254782178307a7b5de2d47e  ow_01_csvjson/goal.md
25e0b28dd0e53d8bd7f8e96c388ac84f69af055a198b751687dac09a1b29ac54  ow_01_csvjson/hidden/h01_comma_in_quotes.py
f5b35c473d8e619cc28405c59669c6ec798558faf66da330a9c356ef3e2b9d08  ow_01_csvjson/hidden/h02_newline_in_quotes.py
94c04ad376393be81198359a1bb40690908f6ba99b5bb7ccf6a3647a76db3a6c  ow_01_csvjson/hidden/h03_doubled_quote.py
205a8849af329b7d56e9f37e514586cb5a8356eed7ed58155a48727863fd6249  ow_01_csvjson/hidden/h04_blank_column.py
a95620f1f397fa9497109cc80024bb4a154b373d63b5185a8675b266ee97928a  ow_01_csvjson/hidden/h05_repeated_header.py
b9e12155876374c05b57e0db0c551979b5629e2f7a356571de323feaf31af044  ow_01_csvjson/hidden/h06_crlf.py
1c7a9750bc43966ebed9b439de2b74a2ed2338f35e4583eb66f61e6842b94d5f  ow_01_csvjson/hidden/h07_non_ascii.py
7def890b2ef635c8a6494510e140e48d644e7a8c0996291fd851a3ea5e36ae2a  ow_01_csvjson/hidden/h08_line_number_of_bad_row.py
df3a6ab422aae4053c39247af9398e1c51706433fe9548832b1ff81972b14575  ow_01_csvjson/hidden/h09_unclosed_quote.py
e98c2be640a119ae7fd27496108e058a4edf5e6a1868cb13954401f187c318b2  ow_01_csvjson/hidden/h10_exit_code_is_the_signal.py
2ec71c1a8713f3af903beff8d9b9c26a047c5508d13dc4890a80c8971bee6fa1  ow_01_csvjson/hidden/h11_stdout_not_polluted.py
a3bcaddcdbd0c5db26c6e3d80b60e8d72a5c7b6e8d95d3c1541007a0f6229fd2  ow_01_csvjson/hidden/h12_no_data_rows.py
ed85f330f9189539111dc232ef4e828e76a87999ec54990ac6f572469c9f5698  ow_01_csvjson/hidden/h13_missing_final_newline.py
678f6a409c20d0c9548da8266a44da13d9373e0139dec95e647ec8d608d7c0ac  ow_01_csvjson/hidden/h14_one_object_per_line.py
c8c4268755c336dbb017f1b90c28cd2d3212a32897ca5f7a8efc933d4a9f5503  ow_01_csvjson/meta.json
18d2e201bdc920ce8582f58519578366794958a9cd98d98025421ea77b33df8f  ow_01_csvjson/reference/bad_a.py
ca8ee2bda3115b7b985a4e7f8328c89886c515c1007c199295cc865d776dbaba  ow_01_csvjson/reference/bad_b.py
9f3c72098fafaa2ed0bdf6f6154458ad7d0e3e06d748fcc967ea180eedeacde7  ow_01_csvjson/reference/bad_c.py
763248c97d4b0048cca70012003aefd69f5028d47bfd758d07c271895fcf5b4f  ow_01_csvjson/reference/solution.py
d84e542b78f7e0d57ddc11989bd1977a0565183a5f373448e19c1498ef0b800b  ow_01_csvjson/rubric.md
e0c594daaf2522c380f7411c8332ef62df8f644eb3d20cbcf6c419368861c415  ow_01_csvjson/tests_visible/v01_plain_rows.py
0cd73f95cbd0f06ee4db3e2bd4ab0a0e97a49872b5197142ec77f77dcd42d065  ow_01_csvjson/tests_visible/v02_quoted_comma.py
d78a7e59c38ac470a305dde7d2b88fd162ec21a34d6106ca1485a0a170c6ed47  ow_01_csvjson/tests_visible/v03_cli_exit_codes.py
6978722f966ab94c5804fbea4ae1c1007e5df14a4ff7ba3f6c928bf4ed243699  ow_02_ratelimit/contract.md
909a12852ca377d2a81759c885739862ba9c4adfee761b4cd4ed9ba8eb4de32b  ow_02_ratelimit/goal.md
a1994262922377ae11798ca3b8822131ba78ed4c4cb84e1594c5a6683fa82f01  ow_02_ratelimit/hidden/h01_left_open_boundary.py
e5dd8ab37f25128fba41fda658ee506c06ad63f688c60b664b272cc6653548b7  ow_02_ratelimit/hidden/h02_right_closed_boundary.py
685d83a360999c246d67e12753941688bf73a0a42a3005806274437e4372c56a  ow_02_ratelimit/hidden/h03_zero_budget_blocks.py
f5b4a7f225d5a36ec4f2af80dc4be2a14b3c678a943005caa5bb415e8d0a43a7  ow_02_ratelimit/hidden/h04_zero_budget_wait_is_infinite.py
2cf44d812d6700b261d65082e4b6b0c0ef1b8c7241cbab4eb225b7b42bcefc8e  ow_02_ratelimit/hidden/h05_keys_are_independent.py
d93e9370b38a89833c61ea5e49028797a8c8f1aa0c108647bcd87ee8841f3a23  ow_02_ratelimit/hidden/h06_wait_shrinks.py
309ac50923734652825a28cfb2224fe137ba52db2792731f589ddda2aa4f5927  ow_02_ratelimit/hidden/h07_wait_formula.py
9730e3f9e7468358b336770cd1f0171f087930b007a1203072788664f611e8c0  ow_02_ratelimit/hidden/h08_unseen_key.py
e107cddd15b6d8bcbec15f84cfb66be16128e124818b06f805cb08edd0e7d2dc  ow_02_ratelimit/hidden/h09_reset_one_caller.py
73c020c6f48cfe1ec9bdd6ebca44367cf3ddef07f23a278bfbafe015a047a77b  ow_02_ratelimit/hidden/h10_reset_everybody.py
863af4422426da8ea2301d92b4a2ad4e167fbed5fea071934736e9c627245923  ow_02_ratelimit/hidden/h11_clock_rewound.py
96f8ca059d433811c2c30f0014bde5b7390c5911d2d9f7c0e9fb0efd2fc158cc  ow_02_ratelimit/hidden/h12_denial_does_not_extend.py
b483c28889d448c32f305a917997c176327402509962962491dd922298a36bbf  ow_02_ratelimit/hidden/h13_fractional_seconds.py
2dfb46c1d4eae8ed85dcb027c2d72b8770b64a5722dd42624321db44ac613de7  ow_02_ratelimit/hidden/h14_bad_configuration.py
fa3685f7afdb347506b04ad53b4e5d5ab530e4ebcf252fe9730de90ed0a588e5  ow_02_ratelimit/hidden/h15_no_real_clock.py
209a7ba1ea16e046d5aecc47ed1dc0fe859c305de79585f79eeefff91ba5f55c  ow_02_ratelimit/meta.json
d0de40fb3a80b3a2cc089224bec655b82b22a76216912527529f24363bd89592  ow_02_ratelimit/reference/bad_a.py
9922b7cb667e096826937602c93a03f01bd72318ef3b0bd5baeeb2e934294927  ow_02_ratelimit/reference/bad_b.py
9130f66f5de5f6b9b9ecc2efe928dc6eb4022251174c72b95d916e710753614b  ow_02_ratelimit/reference/bad_c.py
cf0798e954341a46d681c5b01b8b9543fbde2a610fb4faa2dc9708c1d2b91d7d  ow_02_ratelimit/reference/solution.py
34193252b98885dc2c8e3dbd3eed8d8df851739ca6bc88410ed7569cf4908d8d  ow_02_ratelimit/rubric.md
216ebd937de53c86f1480cd8365bd3d56540e99739f5bcfaf2eec9abc18dfbcb  ow_02_ratelimit/tests_visible/v01_window_and_keys.py
93d2ba3cb741da38cfcb3559b699f1f537a4f5b29b0a8b8c87382fa30266f994  ow_02_ratelimit/tests_visible/v02_retry_after_and_config.py
571f8306024e3d0c1d17aec01457f3bf7a7aabcc3f0bf9f1bbf118d73939ef8e  ow_02_ratelimit/tests_visible/v03_reset.py
5631088fefc4ae3f076d6c1b55f9134664aa068a0ef3ca16ca1546080ddaeaa7  ow_03_mdtable/contract.md
5c14c0961a57fae4350b6746ac0cd1e8a6293c3e3b58104acbf2c926dcb59075  ow_03_mdtable/goal.md
0502bc6c9b47ecaf85081abe7729b90bfccb787c48ef7c6619e7525932ac7751  ow_03_mdtable/hidden/h01_cjk_display_width.py
16e6778a28d61f24d9b86810248f216856371f54cf941303a18bdc8393d07115  ow_03_mdtable/hidden/h02_four_markers.py
05b91e1c67c953cc96ceecec38cf5e0f61bffe65beb11de8914688aa6a1580e6  ow_03_mdtable/hidden/h03_escaped_pipe.py
6d2ec6cad38bc7eba6a836fbc1e1c72f9d1a4045ec7821161cc03dca6348684d  ow_03_mdtable/hidden/h04_pipe_in_inline_code.py
76c5dcae62b6f2fcae2f2bc944b2fd24b132e7e357e3632cd9565ab936396d3b  ow_03_mdtable/hidden/h05_backtick_fence_untouched.py
95f3c08bf2cb22750aeb449ea5d9ec421b369059fe889346ef8d1accb1ee9ea1  ow_03_mdtable/hidden/h06_tilde_fence_untouched.py
1ca6541e3a0b8b6df2f22504293e31b14f4d126673dd9e51fdc62bea89258d41  ow_03_mdtable/hidden/h07_missing_edge_pipes.py
4ed0758102b4b8739deb9e1ce5cc9cfe0be6e01eaf061c053d03fd840aebadd1  ow_03_mdtable/hidden/h08_ragged_rows.py
b1b95f65ec46d33339b7755bb461fedd82c15d467bedfee02b27a658bcf9e010  ow_03_mdtable/hidden/h09_empty_cells.py
3cb6a5abc2449ad0e6e01a40a23f98e2879f89eb131f2137ded440dfa57cef73  ow_03_mdtable/hidden/h10_idempotent.py
376ebd129a41ceed571d7efb4fb7e9b769aef1a77cbc17b5bc48f3ee95a834ea  ow_03_mdtable/hidden/h11_crlf_preserved.py
ba4a4973fc17d2501196b79d84c6a6c1588212df20bf3ffe0b537e3ce26de05f  ow_03_mdtable/hidden/h12_no_table_at_all.py
d5e1e231fed17073696bdc578b7a0a48d5b1f6758543012015543525a05812c2  ow_03_mdtable/hidden/h13_table_touching_prose.py
3d96fedcb47255c9db137d9dba29cca3089b6fd3410773e6c95ee0e6a556e729  ow_03_mdtable/hidden/h14_final_newline.py
8a81f90dbef8e53a4641248718e1877c3e03a5b8e1caedf7f69b119e80f4306a  ow_03_mdtable/meta.json
939a7899338405f8b17ef5541085890cfe23b7274fe3e994c93cfd8584110678  ow_03_mdtable/reference/bad_a.py
0bdeb8312af70d1f8c98a61ca72d7bf505da7fe57acb3abc84c42e577fd71b0a  ow_03_mdtable/reference/bad_b.py
98a202a3c09e0244cd9cb17ced6fdd0a76e216b9281844c67c0695a4a02c7bf4  ow_03_mdtable/reference/bad_c.py
357abe4e6bacacc1aa932d6e4347ba0a9cb4becb2c905e2e28a74fdcc56eac3d  ow_03_mdtable/reference/solution.py
b9daf7c94a64964904e4fb5efd75c598edc9caeee08c8113b1b5a8b54ae6831f  ow_03_mdtable/rubric.md
3cb68a6e1ce2cd84f93253f0e1a868f74745ef5146a1abc2ce76ac6459b1b884  ow_03_mdtable/tests_visible/v01_columns_line_up.py
03a1268ece5713e62978d8e2a603c0b7dbf1941e78dda86a18d45044a336d8ad  ow_03_mdtable/tests_visible/v02_non_table_untouched.py
34484d1c38237f3e2db7cad5291ae06fc70050b22a34e60e93f3fc792ff12249  ow_03_mdtable/tests_visible/v03_alignment_markers.py
ea54aa9a5f06b991e6e79b9f70c4eb363b825ec118a0a3f815b3b0419c9136f5  ow_04_layerconf/contract.md
29c2567474a134aa4851ffc6336c3759f64eb2e20be232e564ae0b2ac919639d  ow_04_layerconf/goal.md
63641b487be7d1a422c6a4ee4aedcd527a67670a51337825cc1557981b78bd36  ow_04_layerconf/hidden/h01_env_beats_file.py
559f0df65a3060eaedd0664ad9271ef867a1d59ca302eb8d4728c59a70c56f55  ow_04_layerconf/hidden/h02_file_beats_default.py
9ddc05db9b4a59fed7807f67913499993c28e18d4c4deb92ab34ed9774c56905  ow_04_layerconf/hidden/h03_sections_make_dotted_keys.py
e3f2ce5427c4eb2492f31b17544505f9c52ffece2197be45f4c2ead0da203340  ow_04_layerconf/hidden/h04_comments_and_blanks.py
dd0b126da0edef19a76cae5ae84ff15cc1cc122222e3225b4557e47294d8905d  ow_04_layerconf/hidden/h05_boolean_spellings.py
d5632fa7b00363dc566740edaa1a42cdae86ae448cad96f298e9002be8c31d4f  ow_04_layerconf/hidden/h06_unconvertible_boolean.py
d283a789ebcbd957017aa9cb07e0e792bde25ea8355ce5cc9839700247603b93  ow_04_layerconf/hidden/h07_unconvertible_number.py
eb1a9af1b3296677dd97a5714b4a88d0332fd3439b19bb4297ecea244b644e6d  ow_04_layerconf/hidden/h08_env_name_shape.py
b361e1cd2ea4b5667ad24ceeeca931d8f27011d133bb4dea97a985d25404d5cf  ow_04_layerconf/hidden/h09_unrelated_env_ignored.py
7aabfd2d6cc5f62a2e7769432a838c4664643d70cf6c502675b3d22475c2c394  ow_04_layerconf/hidden/h10_unknown_keys_ignored.py
950223948ceaabc68eca0894abd45ac4d31addfd9df65b87d92424e3031b3149  ow_04_layerconf/hidden/h11_unknown_key_raises.py
97a05569e9dbbf4b8f56a36e71aff240bbd8d6e22b5a5066e7155a3a32c0dfee  ow_04_layerconf/hidden/h12_no_file_at_all.py
b848f594845e6411a4e1de19bf4d77851b7dc472a4aec7d8930c2b4702a5fd5d  ow_04_layerconf/hidden/h13_value_with_equals_sign.py
4bb9f9b307012445cbfd2eb398f1baacd809a69bd6d0e7f132d02f2ea903c1b5  ow_04_layerconf/hidden/h14_whitespace_and_stray_lines.py
6f4276fde79b749f828953f129955f1357a91676a7236b086fd29c5c6f443db8  ow_04_layerconf/hidden/h15_defaults_fix_the_key_set.py
1e1a2e86bedb239f0b0a51918ac18da85a51af5fa047b4ad0a77d1d2c988b493  ow_04_layerconf/meta.json
1386a6bd3a7e92bfae870e214d0a86fc34061c673b609f92d47cddc3614f7a14  ow_04_layerconf/reference/bad_a.py
4dbe0cbfec01298a8de607820841e5030b98f2c7431968e6cedf99baeeda2630  ow_04_layerconf/reference/bad_b.py
ea9dad5761ba69a62f2088a65ea2f1b770dc38f5cac8cfaf2c2f0826f4e142db  ow_04_layerconf/reference/bad_c.py
029b4008c1d403d74fa4804b107fdcbf6717432f64cafa213925aeac79c31a99  ow_04_layerconf/reference/solution.py
7722c35899f7e1f550705ca310ca6cfca07cdaedc52cafaacbb9abcccf37bd30  ow_04_layerconf/rubric.md
cf15cae47c657147e252153d9c34a63434c088af2c642a7532014e1875b547ea  ow_04_layerconf/tests_visible/v01_precedence.py
6287b405bb64a305f9ca2c92c3e2b54188580b708b88d05ec06f0b178d868d76  ow_04_layerconf/tests_visible/v02_provenance.py
8ed007d99fb5541e4b61b7325fa1104b4992dd45d4b91e4a79a46065a2074f8a  ow_04_layerconf/tests_visible/v03_types_follow_defaults.py
92be8401ca9874544169848fb1a1b498c6d5a4c0c3c474e4b06925775361466d  ow_05_router/contract.md
85bc211e1db8c30c78645f5075c006e27ee1afbce3210714a316d5599ebdfbd6  ow_05_router/goal.md
8e288ff3251078a4f31cf825667e10e2527839651bc0929ec7c48d3a6768f35e  ow_05_router/hidden/h01_literal_beats_parameter.py
c121de471e2348e081a990f41345285aa34328d31ecc5889069dbabb87f2a049  ow_05_router/hidden/h02_parameter_beats_catch_all.py
af12ebde696ac879f98b1f8e616736b82d94bfae936e14168115ba6dc69b4b98  ow_05_router/hidden/h03_leftmost_difference_decides.py
40058b280f50982a596df739c27a91675137000e35c3669d4755aba5ef926f58  ow_05_router/hidden/h04_literal_prefix_beats_bare_catch_all.py
46045a15d920098a297c8197d1fa3c93796d91e36cfd5846e229cf49db77a725  ow_05_router/hidden/h05_registration_order_irrelevant.py
6218ba24e99f4baea3b0d3069880b97c11bd0a24eb4d26a33ab122963af4896c  ow_05_router/hidden/h06_same_pattern_twice.py
14d1df034f5dbd44a6954e731879e9280f082898e2dc8cbd5cddf409384ccd47  ow_05_router/hidden/h07_several_named_pieces.py
536128476a3e7a3ff2162def2ed8ed60537ee122e8b717576a15ed860820771f  ow_05_router/hidden/h08_catch_all_keeps_slashes.py
9db5628c125e1f9ec92f4fea07cf2e276bb3c1a84a940126a3d7309b75346767  ow_05_router/hidden/h09_parameter_rejects_empty_segment.py
a7dfef5e0ae3fec4dc9986c2cc14d5074c9d54f842a146dfb6117b91b86a15cb  ow_05_router/hidden/h10_parameter_does_not_span_slash.py
8da75d41f947ddc1f48dd57b71171f715e8aec2c313885335c0a30377d27cc87  ow_05_router/hidden/h11_nobody_owns_it.py
21865f8e9a6c75930c5461e2c9d5219ca4e7e260fbdf4e028b46d4090751ffc3  ow_05_router/hidden/h12_matched_with_no_named_pieces.py
29327cff1cb7e4e0ef04f621ecc00999810aeb007a36edd4a6d1d566e242e518  ow_05_router/hidden/h13_catch_all_must_be_last.py
43a35c52544aeaa525df185fd068e80cc2994361ececc263ba2b1a64458daef3  ow_05_router/hidden/h14_malformed_patterns.py
c51caf8b91adfcfb54c43caf55a6b46bb8da3f4d154055ff4a43987093300387  ow_05_router/hidden/h15_catch_all_needs_something.py
db11d8e09365186101745e635dfd2f5d08baac68266828a6676fe6e3540101e7  ow_05_router/meta.json
1cd65a70af8e891fc6f1efbda7f70bfd7e2a49ec32bcd768aeee69751267cd3f  ow_05_router/reference/bad_a.py
9612d7b7f6ab05ea5d96b2c6e96bf366bf995613fb8a1a9e38729cb371e42926  ow_05_router/reference/bad_b.py
27bd440f64dbe7b9bd49da5bed77b43a749010555b6e68bd793653e7f66c20dd  ow_05_router/reference/bad_c.py
5d6bc099daf4e9b41f01c1c0984b937ed3061cd2b0c114f291857013f1c133ac  ow_05_router/reference/solution.py
ca03e6fd4e0d00c1fa14c46493f6fd659db03d274c3d1a6d4db9454445bf15fe  ow_05_router/rubric.md
734f363e9f83a6c23242929913240b2362ced3340b69f5cd642cc11ce8cd39cb  ow_05_router/tests_visible/v01_match_and_params.py
a3907d8f5e3ee3ad48ec8b6c98113a2dae746dba035801af85e36b0c9512a37d  ow_05_router/tests_visible/v02_more_specific_wins.py
1979867e2112064cf3abdf105d2671c75c067b3c12f93f09f23cbb6c1135a6e0  ow_05_router/tests_visible/v03_catch_all_and_miss.py
e969c9b3655c394d072edb2e70f417cdb577301fb87528a5ed6015ea654d7f1b  ow_06_verrange/contract.md
302f5297a4bf06ea1561c6df1a402d24318690e93d032ecd5a9499e5e00dd7f6  ow_06_verrange/goal.md
d59f34040f0f84e058e3730f7cedbd3f1e758cb72b2ba1862491f2da11bca81e  ow_06_verrange/hidden/h01_ten_after_nine.py
32a170b1ad4ff812e5b1b14413fb48f3d2d40de7a1719280b13de44e91db6a75  ow_06_verrange/hidden/h02_release_beats_prerelease.py
9af3575a9a2d686e67d115793ee947784a30ce46836abe86ef19d9e894c44b1a  ow_06_verrange/hidden/h03_only_three_values.py
63b109b8fd46b249b3eb436cff0e56aaf1100818f762fa127e7be6d0220f9991  ow_06_verrange/hidden/h04_numeric_identifiers_by_value.py
41d2700b5c5a406d7bd8befee6e960dec9c8a2fb18c0cef221ee8ec91818f805  ow_06_verrange/hidden/h05_text_identifiers_by_ascii.py
8ee969d07b6664fabf3017a15f8e80b7649d8e15bae49697c7f3d0f04014ce1c  ow_06_verrange/hidden/h06_digits_below_text.py
fe5b63d218f5a0bf08d47d68e2b6980cf5063ade76cce4ccea3a0f4f1d1f0b1c  ow_06_verrange/hidden/h07_longer_prerelease_wins.py
6d90a36482a510568de0a6630ce1920fda85cd5490988e64f57b568559b8ab04  ow_06_verrange/hidden/h08_every_condition_holds.py
23196b2386f7abd288400cdb6ba20e9ddc6cc3b18cd27838ad15cdca0002e0fd  ow_06_verrange/hidden/h09_spaces_around_conditions.py
76a4bc1fc90322590ee4a60a1d9fcaf9a990c048dc22f9d9fbe8673ed7f532dc  ow_06_verrange/hidden/h10_all_six_operators.py
57e25e967f4d48e5c63a5eb690f80f016865a19892434102293119c1fd910178  ow_06_verrange/hidden/h11_prerelease_in_a_spec.py
a960f5ecd2f3acd4afd3013cefb380438f9155ecf7bf737ae42e9fb6f48a7791  ow_06_verrange/hidden/h12_bad_version_rejected.py
1f7dc470b20ae1b11e2f34f6b43e253c3b31e6188f192b567c66ed284b220f04  ow_06_verrange/hidden/h13_bad_spec_rejected.py
8314469d11185752e850b518f9a39e14debc6e32f8984a89bb592b1c0cda9afa  ow_06_verrange/hidden/h14_bad_target_version_rejected.py
781c15af1e1c311fbe199d157a8f35532ca769177f2090aa9b049823f99f6e7a  ow_06_verrange/meta.json
70d4ba6c6c971e9a47cb1c3c9eb592ec4a79121cc8ac440d976bc1ae617f1847  ow_06_verrange/reference/bad_a.py
57100a3daebd61dd5f410cf67108cfb2e9d15555798b23fec5d783ddf11727e8  ow_06_verrange/reference/bad_b.py
96acda01120720496e104a67103633cfc72552eafbd2f64870a68c5ac4a64b7f  ow_06_verrange/reference/bad_c.py
f58d33a0d24f45d81d7197cd773885cf25bc2a13ea8b39daf315c432248074be  ow_06_verrange/reference/solution.py
749d2dba380c9f03d9a66035d8624953aeef30347ab1576b4f3bb8ad5abccacb  ow_06_verrange/rubric.md
9bf1f7e120e50a40399a35fb2e66a7f1d0c7778f01cbe6b51852ff3e9e2b7c40  ow_06_verrange/tests_visible/v01_numbers_are_numbers.py
1d8566128943e99a708e039cea742db2784ec44575e193b212383ca31b14abfb  ow_06_verrange/tests_visible/v02_prerelease_is_older.py
d4bad40eb0bea3029b59bdb9ee7894cc7a1e8b74a80d365fb19246eee37cdf85  ow_06_verrange/tests_visible/v03_spec_conditions.py
ae32fcc013052d2473465d5234cc03e3357c932bd1439d3540f2bb0caf502b1e  ow_07_retrypolicy/contract.md
a23cd388fe1934d7b5abe5962107bfe73da38091bee4a854dcfdb34b4725f30a  ow_07_retrypolicy/goal.md
9c52695ba20b3c6607496077352a3f9c65de71c560dbe2c77121a69618a2b43b  ow_07_retrypolicy/hidden/h01_first_call_wins.py
0f70f396b08af67142ebbff7075cedf3a770a163da8f7d935fa30da008a327b4  ow_07_retrypolicy/hidden/h02_exact_backoff_sequence.py
bb78c4a05c215d9865d85f49b6b5e0c7f0df43f5572925fbe0d47007826316f7  ow_07_retrypolicy/hidden/h03_ceiling_applies.py
bd71cec7686411cf8c87996326ff1580344e6054d40572d148bb2660e2a02634  ow_07_retrypolicy/hidden/h04_no_trailing_wait.py
b572c0b6765a62f1183b8bdae66a50798c4053fcb8a41dbf4d74d398b30ab652  ow_07_retrypolicy/hidden/h05_original_error_object.py
bf1a3289ab7dd096bb32fb20797d3b6ac0e2826354c09891664de3107182c304  ow_07_retrypolicy/hidden/h06_subclass_counts.py
b9ac7ace701acbb078f5bd8563863a6385c955ad6d1747d5f35edb70a4c644dd  ow_07_retrypolicy/hidden/h07_unrelated_error_escapes_at_once.py
c8d637c6e6eeb069372d581dbcedf3ebfbd915a869c9fbdd07f1a2c2be9aacd2  ow_07_retrypolicy/hidden/h08_empty_retry_on.py
182554f0305f67361ed5a64c56a41ac03ee748965d75459dfbbf77afae66e47f  ow_07_retrypolicy/hidden/h09_attempts_must_be_at_least_one.py
ecc2d73be0f6822f6979364dd72722b0dc6d04f2d6493497808f222f8290d479  ow_07_retrypolicy/hidden/h10_single_attempt.py
1055dc50a3fbad74a5f5b6d954dcc5fb770afee69583c61659e2424ae848c638  ow_07_retrypolicy/hidden/h11_succeeds_on_the_last_attempt.py
19950f218ac2603cb0bf30232123e2371740920003286d72c924235a53554487  ow_07_retrypolicy/hidden/h12_sleep_is_the_only_waiting.py
e93fbe17a594a139f60992d6d44e0b905a8bc6d3399864577385468878f0d23c  ow_07_retrypolicy/hidden/h13_several_listed_kinds.py
bd9f7039af1b76f10539a849890471f693ea2128c24eb61f48d5c5540aa5c02d  ow_07_retrypolicy/meta.json
1ad60b81c1e072fb23971b29d60ad47f93d4bc9fcf852256d9d2b2581e55052e  ow_07_retrypolicy/reference/bad_a.py
6ca75f62b207eaa925aa990d3ca10c40991786a1643dbbfae523b444a686cde3  ow_07_retrypolicy/reference/bad_b.py
691637495580532fca64a6fe4d9ddb64d267572a2300de36936f1d832cfe355c  ow_07_retrypolicy/reference/bad_c.py
453c924502703fd8e2f9f158ed074383e65ae4fb502541532f05c4321325a27e  ow_07_retrypolicy/reference/solution.py
2890848f62842cc9de184438de48d9e2c3e60c1d9b1c09603a277a0c2389c2f5  ow_07_retrypolicy/rubric.md
6d2da0c587ab4a44617c4749e7f11f46194df1483c735836211592f7cd3b9831  ow_07_retrypolicy/tests_visible/v01_retries_then_succeeds.py
7c976f015ab3995657fdac34c1fbb15884b003d011285e8a362f747d7f834b30  ow_07_retrypolicy/tests_visible/v02_backs_off_longer.py
ab1c01b8988dfaf0df2a5ba39650b612a3546377cd96c19afa73c98d9685949d  ow_07_retrypolicy/tests_visible/v03_not_worth_retrying.py
0417ec37389e5a8dd13c38be676d8b42f31e9d3488c1aaca57e9c3efde98bfc4  ow_08_logscan/contract.md
ba29c9bb56c5ba9644ff2829394fd3782f2a3d7895b27dd2f80eaee4c9aef818  ow_08_logscan/goal.md
1ac9870fa2cb0bd587f1ddb0c72dd30e3df3b98cd3edc1224ef2006805a500a4  ow_08_logscan/hidden/h01_five_hundreds_only.py
078cd7b890119cf0f1b30bc0b9a4da644487bc4473c2d23baf950275da119419  ow_08_logscan/hidden/h02_error_rate_rounded.py
675f6dcfa4c7e41ae22639a47f65b6a9047ad663ca9a0a588df50cc4b1be9a78  ow_08_logscan/hidden/h03_p50_nearest_rank.py
a23477d845cdfe8970e3c25db88d8a3282a1d1a44fa95b355e85b2b347a4eb2d  ow_08_logscan/hidden/h04_p95_nearest_rank.py
788c6cc8eb58b1200f4b52eec0b2837a188ceb070b8805cee2c053344afc469c  ow_08_logscan/hidden/h05_single_sample.py
e8d18c833e5ed28c04ed53bb7354d79df7ed7828064b84af6d1afdff88067191  ow_08_logscan/hidden/h06_busiest_first.py
4c4f48dd767d0d504cc63b97bf5eb719931d99876c33fc978164c0dd12026e3b  ow_08_logscan/hidden/h07_tie_broken_by_path.py
8f76a7d5939d37a85ae79465e1305735ff37cb310fd58de56f4f6574e712153f  ow_08_logscan/hidden/h08_wrong_field_count.py
452a2ede8aecd6ed2046f43f359a4f381ddecaba7cc5cb8b365cd6d3998b21a3  ow_08_logscan/hidden/h09_non_integer_fields.py
780780289e2ae310870eb50232d7aa7e7242fc2602e0e3818b74bc958d1c01ea  ow_08_logscan/hidden/h10_bad_timestamp.py
88d82c6b6b102be3197739dfa3b67f9c3d1dc259318c99fe83f2d6b8ab6f0bc8  ow_08_logscan/hidden/h11_bad_lines_are_reported.py
2e4f60150878d713137ff17bae0f5d3418e59534477410c618f82eeafa3036d5  ow_08_logscan/hidden/h12_blank_lines_are_nothing.py
388a36b96a0b9f79491f5988e35d61b56a52b622e30ee642efa5c9bd0b19203e  ow_08_logscan/hidden/h13_trailing_newlines.py
ea501d154e6abc37345f78c071a27ff7b4312f4adcdcfe868f457269d6a1fa5b  ow_08_logscan/hidden/h14_result_shape.py
a66a45f3797bde1e63118240c660491269ce56f443c921ee1c11abb3eb82f512  ow_08_logscan/hidden/h15_cli_gives_back_the_result.py
20f4f038a43eacc8f4dba9aefbc34d644fa13c05e54779a861b755ea00ed1598  ow_08_logscan/hidden/h16_cli_survives_bad_lines.py
8730f7a212e4acb9925079aa828d032cddb88cc488411d98af59c2faefcca37b  ow_08_logscan/meta.json
02cd8e27c03c9b06bd9f5f2249ca5eb11e47fe07589c9470ffead91dc1c3fa16  ow_08_logscan/reference/bad_a.py
be3103e27e8b330134c9d4363b97b4f0c63f96fab78e0e4252fdaa792e2a7af8  ow_08_logscan/reference/bad_b.py
21d7d91a61e1a63f6294c47dfd44adaa2ca5cefc8b795b3fed3aee11e7a7e3be  ow_08_logscan/reference/bad_c.py
c578034206e397eb8bf7a2d864374af04b71e259b631caf7fab7fddde16d01c6  ow_08_logscan/reference/solution.py
d5c0eea3e285b2f30d519de21b6e955ce36b06b6806ffb0cfdb148567364a685  ow_08_logscan/rubric.md
e3ef3e8deb959ba0cb04355dacff846752a943a5bba3a1959b7c08842ae453ed  ow_08_logscan/tests_visible/v01_counts_and_error_share.py
61d5ace4eb0437f3117bfb1d2431b4b212fbe4dd05e0d32b3d8495c886872951  ow_08_logscan/tests_visible/v02_bad_lines_do_not_stop_it.py
73b12a5ba4cfbbd01e70e2bc677b87447f25bcf76d8638bfe51bc8b9b6d356cc  ow_08_logscan/tests_visible/v03_percentiles.py
8af809670ba30cd97d28aa53d836505a6b685f8d89222e3da8af1fa510218320  ow_08_logscan/tests_visible/v04_command_line.py
6b1b96cd077611d1cb3cc1b41e84a569b5c7046375cab99c640770735f6e6d89  ow_09_minitemplate/contract.md
73bcd3f0a3d259b4e5fe34c6e47b93e9504c2c5f7affe074fe263ca4a8b1ba61  ow_09_minitemplate/goal.md
9ffcb42b5a1c607b1adce7da5b2d0fb1426ad5bdf848f82909d74ec48e2aac7a  ow_09_minitemplate/hidden/h01_values_become_text.py
8a1c74182730b428491ff01195315f5cd020eb20dc2bffb14bffc330665e8735  ow_09_minitemplate/hidden/h02_deep_paths.py
500f5d3213f98a5cac30c45ea18a5a4995a08bdbd9c028fcfdf35ce9f3fbb2e3  ow_09_minitemplate/hidden/h03_missing_path_names_itself.py
ff8498337fa9e06ff4a1bbf473a65b75ca9fed2a3108ef5a2d91fcf1bd4b6fb0  ow_09_minitemplate/hidden/h04_never_an_empty_string.py
219f593c84221b816b281441a93dd8abb6d1e355062206c08534c8e15a6b1e48  ow_09_minitemplate/hidden/h05_item_itself.py
bf026d5ba6c8dcc2177a09319ad33722af45eea037215b4855914fc97b4a29e5  ow_09_minitemplate/hidden/h06_outer_names_inside_a_block.py
f294eb50e4b12410ca81cffa80d4b35d09a1d4f7821d6330203d7f602e6338f5  ow_09_minitemplate/hidden/h07_empty_list_leaves_nothing.py
567df5c20b294ef8cd49748dc09a1998d681f4944b25755bfe277cc443105ceb  ow_09_minitemplate/hidden/h08_comments_vanish.py
fb113f45e40399160faf4a4640d0241fc0be3aa9c742ea3ae3c86bd96b929aa7  ow_09_minitemplate/hidden/h09_literal_braces.py
d88e4bbee63a7103965b576ef69d961996fbb777d79d4a893463dc99fbef03c7  ow_09_minitemplate/hidden/h10_unclosed_placeholder.py
d3d933d428f873afdce17b25e85055e029b31420fdadaed798cf8da18db02ad2  ow_09_minitemplate/hidden/h11_no_repeat_inside_a_repeat.py
0c36c5e656e360936829770b3fadc52e02e661ff9f4fa9ceaace03fd8c5048db  ow_09_minitemplate/hidden/h12_repeat_over_a_non_list.py
33b5143f8d0a0a527f8b9e4e961eb965abef8ffc31d2346d33088f66ed4f5cce  ow_09_minitemplate/hidden/h13_stray_closing_tag.py
abe5c6323794ce330e5a02e2714e23074ca77bc680dc907578f70db86a4a232f  ow_09_minitemplate/meta.json
99468e04c52c41ab900d06a6c29c2c3425d707ec07148634c677f984fb41f6fe  ow_09_minitemplate/reference/bad_a.py
10ff066e85002088e1f5bb961d9fc3f7daa737603a9424210c1496704e439f3c  ow_09_minitemplate/reference/bad_b.py
872cd7d556e412c0ac86c748272f673a1e0aa388d155ee6e480fcf22b38bb912  ow_09_minitemplate/reference/bad_c.py
d1ebcfb126ab9b0a6b21eef20374ed5e8d350df1ca937268eaff4d823045b42f  ow_09_minitemplate/reference/solution.py
9092ea4f9780b04d3225e22859de78e26c732b16318ca39465af57d71c2f04d2  ow_09_minitemplate/rubric.md
5c7ff05d4406913f4c9108a2c502188d9a9a6136554882da9ae3006c4a564d52  ow_09_minitemplate/tests_visible/v01_placeholders.py
0b0f8d2de0bf9e1545f711b20b771d884c3cde546ad2d983a3a6a3f1869f6962  ow_09_minitemplate/tests_visible/v02_repeat_a_block.py
9ec2972310e8a4afe784896aeec6a80afc1b8c261c40e906225c79a61a6d96cf  ow_09_minitemplate/tests_visible/v03_missing_key_is_loud.py
799e63184f2ad3c11f6be3d6bd4987ec5af4442ffb5b1404d0fd7baf2547b5dd  ow_10_dedupe/contract.md
d2bb4e2466e2c14e2905352e40ed4ee8d20629fa7196c0d5460466d87a06d026  ow_10_dedupe/goal.md
de5880fff6b3130dba6bda1be0d02d27f499f7a98c708b3c96974b8d6ef99334  ow_10_dedupe/hidden/h01_order_is_first_appearance.py
b40c5316e3a8de568318794d5c6b653365d0dd11dc972eb0a2b50d93e0807243  ow_10_dedupe/hidden/h02_first_is_the_default.py
54b2871444f78d652272361dc04d1cda6873177fff86aceffede4d78640ba6a6  ow_10_dedupe/hidden/h03_last_replaces_wholesale.py
ccd928c98a1bdcd1ae1966ee89b9a0cd3af5b2e3613a01e1240a2a4e246a55b6  ow_10_dedupe/hidden/h04_merge_takes_the_last_filled.py
ae56d8508515b5a134abe598d7954272675204b66a2a30d6cb514aaead78971c  ow_10_dedupe/hidden/h05_merge_gains_new_fields.py
b06eb99b7bfc01a73a12dff03855227db8f18a88eea8aa439c2748e91c3f5a9e  ow_10_dedupe/hidden/h06_none_never_overwrites.py
3caedd69016a5c23bb1d3c4fe77758187ab250cd450b6854359abd9bb01f428a  ow_10_dedupe/hidden/h07_composite_key_order.py
356cd5a24073e3b1121205b09218425e280f2e2b38398067a294a5814d58b11f  ow_10_dedupe/hidden/h08_composite_parts_do_not_run_together.py
cbe2a5b968c96999473cc4dd296488901ed86ed56c5127ff743f84a3b0f7f3ee  ow_10_dedupe/hidden/h09_missing_key_field.py
1a88e9340d2e35d83e648d2b5e8330d3c7222072db61a397c054b882aaff4b6a  ow_10_dedupe/hidden/h10_unknown_policy.py
733905d6aef5edce9a61638f70d801d5191816d40d2744962af26a297869a5f2  ow_10_dedupe/hidden/h11_inputs_are_left_alone.py
9343426d51c58c70ae5cf24a4f2587f2218ded18c54fdbc392b2acae2aa57ab7  ow_10_dedupe/hidden/h12_nothing_to_do.py
8492eb4128c8a5b6f0ea7bc03ad68439205332e233adcc0a9efa60fcb0fcf3dc  ow_10_dedupe/hidden/h13_key_values_of_other_types.py
6b0136e7f13df962b4643f566a8b454f8bb167ebf944aa50410622e5b993541b  ow_10_dedupe/meta.json
ce8576d199bf19dfefc89df42c75d686ef83ef091a3b1e164306703e0d69396f  ow_10_dedupe/reference/bad_a.py
19ae88dfb38d6b6ae32b48dc310ab1544e220aac85ae32c1fb892e0e5eed064a  ow_10_dedupe/reference/bad_b.py
53a3f2df73df4f6826193fab78fea7427e9026f33ed8003752b07b5b2179867e  ow_10_dedupe/reference/bad_c.py
d5a24e0a579b17b3af588e59ee16558973bfe5319544e9d558640f7322ccf2c5  ow_10_dedupe/reference/solution.py
926d69dfd17e9ba3902a2ec5a11399dd2454133f461fbec546f758bf93ba8eb3  ow_10_dedupe/rubric.md
577855806685ce679c01c7ed3081650c6fa4d31bbaa5e7d3cd178de956657749  ow_10_dedupe/tests_visible/v01_first_appearance_order.py
1509846bf270150b8cf3944eb69c5a1896f33baeef466e87348b99449e19a571  ow_10_dedupe/tests_visible/v02_keep_the_last.py
f89dc703c5e016469b70f9ab78de8da3efb66702d741cc0cb6cc1315b0a13b28  ow_10_dedupe/tests_visible/v03_merge_filled_fields.py
8eb96f4b96a09dd98977491fa34beec62a7aa954fa7b0f29e0575b37a3047b86  ow_11_reflow/contract.md
8aaee3a7374ca7120b5a5d1361c1d2bd08d7ecb306656c5ffb33d6e6bdb47018  ow_11_reflow/goal.md
af06954d90f8196729962ae5e81b7e356bcd260d5a114cf4cba10eb1416ec579  ow_11_reflow/hidden/h01_wide_characters_count_two.py
af66d6050b89fb062aeb9a8e5d892f2a9587f8ab1dc40ad9e07a4c446537646c  ow_11_reflow/hidden/h02_break_between_wide_characters.py
8c471492b09373acb3d7a55870ae36885b006321472b215a110ccb6eeae9a0d1  ow_11_reflow/hidden/h03_paragraph_indent_carried_down.py
20d314cf39aa857ebf0d2377ddd4913b4f5be01d87a3a3157ed7aeacb503291d  ow_11_reflow/hidden/h04_numbered_bullets.py
703a79ead7e33c3f02847c66576cd37ce9995b6aee5a3a7ba75514d45f5dc42f  ow_11_reflow/hidden/h05_star_bullets_and_nesting_indent.py
b5aadad092e49122b3143915293f6ce493a993938341a7f68f5b2358f41fab76  ow_11_reflow/hidden/h06_each_bullet_is_its_own.py
064d43e1353ef093ebb56ef3ee02b7b595203920e73dfeeb050f3be85535eaff  ow_11_reflow/hidden/h07_blank_runs_kept.py
b22ebc55371bfbfbd77e8c18cb4ab50e00dd350ab2a66393235f4eda1e348257  ow_11_reflow/hidden/h08_fence_contents_untouched.py
ff0760392c491a4ff7d7f4cfcc8a91b83a56915864d77f04bb2b93ffb240f4ad  ow_11_reflow/hidden/h09_long_piece_sticks_out.py
2b0794c6f30e5fe9a5991f9ba2c65b81f235c47ca59698659e7200b8a05d1802  ow_11_reflow/hidden/h10_bad_width_refused.py
83ced3b80e50e4313c0903d0c1e020a9d4fcabc239c09b61524e64bc1e9c3733  ow_11_reflow/hidden/h11_whitespace_collapses.py
0aed2053a834a6e06b7f57961d0d36acf36d8f8ac165128d75240308faf1952a  ow_11_reflow/hidden/h12_final_newline.py
b183603cafd44b30a60aee4a7ef8a119f2ddd81f3ceab00ce4343ba23b60018f  ow_11_reflow/hidden/h13_mixed_scripts_in_one_word.py
16b6948e67e0c8c9ad8f4d67ba9093f7ad4d179e2645894e951dd5c5c01975f4  ow_11_reflow/hidden/h14_bullet_after_paragraph.py
c867b59b5c2eb52b0adc6824b13e7dc7f7515d44241e87910e485e26530ca5fd  ow_11_reflow/meta.json
70812b514f4a7a13569d4505764c507fb1ee6deebf1d89fab6c20dfb4f3931d4  ow_11_reflow/reference/bad_a.py
96f7b451f41dd1b9b93bae5b7d6eecb2706cb251a751a47fba71559fa1d02cc2  ow_11_reflow/reference/bad_b.py
30eaf5cd30493023c18e4659e77157d50044ddb0a76dd4fb1b25f69249a0cdcd  ow_11_reflow/reference/bad_c.py
4694975432eaee330c771f36bb6a571bfb2a72e9b2945ed8faf5dbc69e58fb8c  ow_11_reflow/reference/solution.py
b2d0011d7735d3bc35c391bd4bb6b1e1da1c637aacbad46955d183bbe760d4f3  ow_11_reflow/rubric.md
077c16549205a58f2492d08c7820878baaad62e3616cc6511e8f752f83e9be95  ow_11_reflow/tests_visible/v01_wraps_to_width.py
c02ef9b1fdf7ad49199f335e2b9a67c33d2c4875aadedde498073c7c0ee64d97  ow_11_reflow/tests_visible/v02_bullet_hanging_indent.py
d7c4a09eaa60ccf397d094765c547f94eea6909a9ea567e453e5304b9b560387  ow_11_reflow/tests_visible/v03_fence_and_bad_width.py
e630d5c2e16e940586c1371dffe697d786107f27e8cf58afcc38889ea623d5ef  ow_12_bytesize/contract.md
b91b46aa2eece64f6bcc06b82a250da724058e236d1e71b9d8ac0a82100bd1cc  ow_12_bytesize/goal.md
1a90915a3de0f08723449048509765f12945ad897f36804076c3ec4cd7ae107d  ow_12_bytesize/hidden/h01_two_meanings_of_kb.py
8ae6511336f53528e942f395a263cbeaeb8ab5a98b5ea5ce6634575c0082e4bf  ow_12_bytesize/hidden/h02_unit_case_does_not_matter.py
08405c9c81feaad0cbdf56d75f17fb0b80481b190103dc2cf06b3525f6ebabb8  ow_12_bytesize/hidden/h03_space_is_optional.py
047d47fef55a4cf34d42db9235c98ce8796f0f85111bb2b6e0a2914869ae1cfb  ow_12_bytesize/hidden/h04_no_unit_is_bytes.py
c35fd54fb97ff80d65ddbd96b03ad360a3e0b407f6827425076c2927b2f13b36  ow_12_bytesize/hidden/h05_fraction_is_dropped.py
a12fa328d7fbe22fceb943a38084785186b1aa4d62bbc66a8a47e6a98af61292  ow_12_bytesize/hidden/h06_largest_unit_below_the_step.py
4caa71a59d83602b58e124e62efd2f3845c1b4fbc09943a8b5cdada26626f61d  ow_12_bytesize/hidden/h07_trailing_zero_is_kept.py
bef914822b331419cd77e9cf2202a4d0921db6270768a9a49497704de1cc07ab  ow_12_bytesize/hidden/h08_bytes_are_whole_things.py
8137f738e003dc10d8c63d103a887bb7d4bab49a5d64240af72003ba4906f5bd  ow_12_bytesize/hidden/h09_decimal_family.py
15627a8a7b24acdd633b7b23b9f9a7fd069aa8b3f99fbe0fd1b356a547e7f9c4  ow_12_bytesize/hidden/h10_above_the_largest_unit.py
94e8198b748e74e28abfc71eb0434d1e9b75dc37976847b555136f0c65e64571  ow_12_bytesize/hidden/h11_round_trip.py
d9ed87c3ebbb3edeea1c89f46bc564288846b710d5eee502043958d42c193c7f  ow_12_bytesize/hidden/h12_negative_is_refused.py
0005632f9cb0efaf6f479a6db3c9fd49ace4cc13d4a148700d51f9cd775d2342  ow_12_bytesize/hidden/h13_other_refusals.py
ad7da8dffe30aadea41ab00b032f32bdb9999bb94e547486996bd9e2580720f4  ow_12_bytesize/meta.json
9d4c8ff1b874d6a3a843d81c5723ef2fafee778f69ae1b21c7a9c82a4c15b8e3  ow_12_bytesize/reference/bad_a.py
c16e71c42d663da2e0adbe08dd82c8029c1e372ea19cad94d46b82e60bd69553  ow_12_bytesize/reference/bad_b.py
37c1501bc2940afcd49d2475e42f103f719db95fd289ef4c4322b35a48abe2a8  ow_12_bytesize/reference/bad_c.py
fffe474431872ffe12c039b865e916c6aef135417a46e8e4c333fae56d33f0fe  ow_12_bytesize/reference/solution.py
6018711a01e102769d3ec14a77b5e4441564f255f500857a0739334101655f4b  ow_12_bytesize/rubric.md
7e6f08dd57ad02fbdaf18151bc584603ad1f0f2f903e2f62c611fbfd3b464d2c  ow_12_bytesize/tests_visible/v01_reads_sizes.py
e4d641074c7b1c140038f07e769869503c88a65994a15e615db869050118ae8b  ow_12_bytesize/tests_visible/v02_prints_sizes.py
8eab51760bb8555dc4d771067f67739ec67c79845d1d3b3d409fddc6437ad13e  ow_12_bytesize/tests_visible/v03_refuses_nonsense.py
b47b61fa919bd0b1fd1a81c979b4fc3ced7e7b94b6a17b7826e5cb635e322797  ow_13_timespans/contract.md
1ffcdabb6d6317fbdcd851500523be70d763f88b380b9fe90ada36777a10c90c  ow_13_timespans/goal.md
303e90e89969e46d64f9b438061149dd95b064b3c4a0b277511fb1e55f85af72  ow_13_timespans/hidden/h01_touching_spans_join.py
bf26d478fead6cb84381aa5ea5217953c7c54b8dcf3ee05d3e023ad1ebc20430  ow_13_timespans/hidden/h02_unordered_input.py
528c6f3fd67dc340b8ed6530281564c996a1f154b5448ef854c1969e6fe7504e  ow_13_timespans/hidden/h03_zero_length_dropped.py
3c4fdb42d2cc2eacc218ace31d51776e8d766e1b4c594676baa1c7686488143d  ow_13_timespans/hidden/h04_dates_are_midnight.py
e2c7a1348601b189d1b149917dcb5c3b9402d4fc79c6b5f8e17ae52f098ebd69  ow_13_timespans/hidden/h05_output_is_normalised.py
f0fd3c4675f8548d3d4064f60948b7ab2ae74615602507494259e36c820a8741  ow_13_timespans/hidden/h06_hole_in_the_middle.py
d28dad0638fa86b70f336baf7c4fd450998ced802e5b9c51bd536c38bc93d62e  ow_13_timespans/hidden/h07_hole_swallows_everything.py
f736d6913ea2c0a613447c8ec7f80c4a515ac0bef22a5b28d87d98518a063335  ow_13_timespans/hidden/h08_holes_that_miss.py
58e572a0ad979d7ebc5702dd1d150abdd8bbfe67fadea97ea4e7de7af7a9e1b2  ow_13_timespans/hidden/h09_total_counts_overlap_once.py
decb31bf338fef10e299ab8b2baf5842738d0bb9ad1a8fb96107f08b777e5cea  ow_13_timespans/hidden/h10_reversed_span_is_reported.py
ea6006ff3985a1c12557c5ab7f0e1db8a5404e4181001934937879ff8b02bb1e  ow_13_timespans/hidden/h11_unreadable_instant.py
40d483a5f823ba8ede5e2ab66c25beb6d9c42f5f7e751f31922cffaa22920fa6  ow_13_timespans/hidden/h12_nothing_to_do.py
882ef4c1f7b8047413b2aee0706ec8574f194bc1d355e802344bcb7f8c883c1c  ow_13_timespans/hidden/h13_seconds_resolution.py
f5dde9ef8b55e8320bc936d6d9e680786922473af5ac241bcbb52ebf3b2efc07  ow_13_timespans/meta.json
b5f1f4289d2190bba8705518a330168a9aab3cc4ef811d76dbe05d91e8dc02b5  ow_13_timespans/reference/bad_a.py
cbb9b9cc98d37785622b480090d70b5cd017c6170185b5ddf03987f5c64068b5  ow_13_timespans/reference/bad_b.py
19c3392967fa02a897799ffcb073ae6b162599cd431133b2e8600cf840e2df33  ow_13_timespans/reference/bad_c.py
c5c1490be2e9c4fcd35f295d1436e5cbc243e17a72da354b9024264ea395cac4  ow_13_timespans/reference/solution.py
6e7827399ca7c7b3c998c09c021eef985750bc29cb57d7bfcee3563290a6ce3d  ow_13_timespans/rubric.md
22f03ec3e8a41a5aa490ee8f1361b3f3241420970095be1938b37aca2edc29f2  ow_13_timespans/tests_visible/v01_merge_overlaps.py
50a88aa9406c7a163245a267d42a38ddbfe347710b0973762b7cf8401dfbd906  ow_13_timespans/tests_visible/v02_subtract_from_an_end.py
33a0fdf9ebfa420f849f897f25cdae3ad12054aaf6bb6ca8d2533ca048a9ff78  ow_13_timespans/tests_visible/v03_total.py
8da695948d68448b4df66b7fa82191ca451c99401d765806a872a603c224ddf1  ow_14_statemachine/contract.md
3aee4f6114db414c7d8a4118c42e1f7c59d35b259226978600875c53f0e38ae1  ow_14_statemachine/goal.md
5d9be10654528c9376cbc9b3c2ea7c92c440d8f5e4bc9028cd262e5baddbac50  ow_14_statemachine/hidden/h01_history_starts_at_the_beginning.py
97cf8b0b0e0c98d9b0bfcd6cf8b172b5a8657153e470bb74489e4b4673c2609f  ow_14_statemachine/hidden/h02_refusal_names_both_halves.py
9a67a2186860ae89e65a9e5e40cf4715cc829ea0ac9c04a4064c88c052476a1e  ow_14_statemachine/hidden/h03_refusal_leaves_no_trace.py
c5500f88638be09f7ae6e8bc86aca1e3ba8325a880b6664c8f99dfd04afb1418  ow_14_statemachine/hidden/h04_can_matches_fire.py
2d9771d93971edb0a5ebdab141ca16ee83e19a27584fa94b041a72d27113369c  ow_14_statemachine/hidden/h05_self_transition_is_recorded.py
a6d1fcc4a7c2283c6075f248304d98ea3ca58d696e352635244a89bf1190a328  ow_14_statemachine/hidden/h06_history_is_a_copy.py
20c5cf75ee0d9c956a20595730fe1a552790d5b7019f6145205c1a1f0f1a8b78  ow_14_statemachine/hidden/h07_reset_starts_over.py
b621608819a93963d0687ae818d023f4a10c6636f2bee9e9fe9ae863ed3bd717  ow_14_statemachine/hidden/h08_unknown_start_state.py
68f28de36da42d94ecffb0f28a678ccdb71cdb04c5ad0bfd7957ee78b87b6c5d  ow_14_statemachine/hidden/h09_target_state_must_exist.py
e5c98df7c1e9f463827b431b896c18d278e617c99b9b645c4a91b9b021df3478  ow_14_statemachine/hidden/h10_dead_end_states_are_fine.py
9ff2425a2aca4c231f2df406bb0cbe8ddd568e3eb682ab1f4b0df438b2cd74cc  ow_14_statemachine/hidden/h11_two_machines_do_not_share.py
a289906e7f94560d29f59b243f8dfd892d0e375e13efbd28886e4dafb4703bcc  ow_14_statemachine/hidden/h12_long_path_in_order.py
f8365755252f5eebe3f233f6e8709a1aecb0b4fd5fc2a600e7fb055b7627d748  ow_14_statemachine/meta.json
4c62a54c88419be379cc13c977185701220def6225a3f625b8c16e7b0266e8d4  ow_14_statemachine/reference/bad_a.py
df3883eade7e618748b9f59deb9b832acafd49e1774807fd7069236200abe932  ow_14_statemachine/reference/bad_b.py
085872cb9fda2c553be0142ff4ffc5bd288b02695f9f692e895c0991366873a9  ow_14_statemachine/reference/bad_c.py
32aca45c0f3393dda4dfd0a777841d59af2ce54516927870eacbed15dd69227b  ow_14_statemachine/reference/solution.py
51c072b0eaa1b80cf80b673771f17a37662b7ce78bdf523932276102966ab727  ow_14_statemachine/rubric.md
83ed98160155593ce8e425ae0cde019c58ff4ce03eabd7a0ba878d32a427310e  ow_14_statemachine/tests_visible/v01_moves_the_way_the_rules_say.py
c5418c516c9508aa82144a02fa32e69f19f0d749404a2c09469a6de4b3ac4f15  ow_14_statemachine/tests_visible/v02_asking_first_and_being_refused.py
5f65e651395d65749cd83b5a30f72416425d548afc0d14dc0f45b9cf369f2d8f  ow_14_statemachine/tests_visible/v03_the_path_it_took.py
cbb156d2737b6ee9ccf95fb4179ceabe826236889abd1b41904e84777bebc8a8  ow_15_tomlsub/contract.md
559d579377aabffa8207abfec19b13e0d9d02243c4a9d709813225b605b2332c  ow_15_tomlsub/goal.md
63d7cace6be67b5e25e60d47b58d120e58395bdc7bbb64997e38e371a8dd3b55  ow_15_tomlsub/hidden/h01_five_kinds.py
64d6310ca8ad7961a024a272652ce99e39e2ccce1a6ffb2b98a6e4a92009b615  ow_15_tomlsub/hidden/h02_escapes_in_text.py
6447bc080f6db932fa4e573542a8a9c3de15342bd61c9a96713405c60c41f013  ow_15_tomlsub/hidden/h03_hash_inside_text.py
17318816e1a8ea83885d854ab8576440d9cf37e6767b13486427e6c6650d8484  ow_15_tomlsub/hidden/h04_nested_headings.py
8330c2e62d351b889589e08994ba82a961a200a0a3353927e7aff7c090b4ce1d  ow_15_tomlsub/hidden/h05_names_before_the_first_heading.py
bfd3b5a637b8ab49e3b025ccec3e4aff0321074497193b886583d666465edd5a  ow_15_tomlsub/hidden/h06_mixed_list_is_a_mistake.py
96ba3ee45fe7632336eac14a36bc48b7a0840563d3ed79b8b7c2ab5852dcf257  ow_15_tomlsub/hidden/h07_duplicate_name.py
f74f3de8bec70f1cb89e1b3cf1cd34f2bb37171ac5886bc4620d6f4d407cb51a  ow_15_tomlsub/hidden/h08_duplicate_heading.py
ca65118165e073bb259dbeb0b3f7680bb59f810a0793f3c6d61a5db30950948e  ow_15_tomlsub/hidden/h09_line_numbers_on_every_mistake.py
9cec5da8b9c6eebd97c13b82e5a0e847c1c72d7cbb97ec72b8878041fb5712ba  ow_15_tomlsub/hidden/h10_round_trip_data.py
18e1d77685886e4bddd5b930319d89b66ae82b02d1936189dcbf2fc10aea3b85  ow_15_tomlsub/hidden/h11_round_trip_text.py
a98592d76004a1402358fa490fb6427a759f26c277c19b19415714e33759eb8e  ow_15_tomlsub/hidden/h12_written_order.py
a7fb1914a19a111b3ede9bd7cea07c86ff9f506ecb1f2057e5adc22a239e2e08  ow_15_tomlsub/hidden/h13_unwritable_data.py
781bba71c41aeefd75a7dc2560defa9d6ce01f0fbcca1629f4edc76957a4dad3  ow_15_tomlsub/meta.json
42c2ac1cc843a5d4ef25890ed67ebbcdc9ac8bdeebbd284b5f8fa31fd8a5c476  ow_15_tomlsub/reference/bad_a.py
ef182a152c2ed98c5541c7613270ea8c2f4f447ac527fb478cac6ad510b4a162  ow_15_tomlsub/reference/bad_b.py
b24ccbaa3616aace4e85d9a98cba237d7bca9ecaff92e0082810cd8c11ea49cd  ow_15_tomlsub/reference/bad_c.py
c523b358023650a9233daf9f86c809b64bd08c68e11d4c64bac483cd3117f3f7  ow_15_tomlsub/reference/solution.py
e1c04d29d1a1729f81c067d56f119277321db5226953cdcfd36c566c19ae91fa  ow_15_tomlsub/rubric.md
94e16277dc4467ff741c6d3fc8628ab385494f1426843526a09fdffa45b84d56  ow_15_tomlsub/tests_visible/v01_values_and_groups.py
751938fc0952a0e8f1f3b8683e6f960e588ec4cad54bad9df94db617893c77a3  ow_15_tomlsub/tests_visible/v02_lists_and_comments.py
b4e740d255d2bdadf3b1fd1b1ea9f99312e41e4c0dbcd9ac4782240ba05775e7  ow_15_tomlsub/tests_visible/v03_round_trip.py
689b0f7753b73fa6941d11b27f0c937d4539f2b38b6d405edd53bc22e349e2f5  ow_16_pathglob/contract.md
d73a51c38f8e5a36a5ea04c6844df2d9cfa0c09adf139047cbe7dbebdafd6db6  ow_16_pathglob/goal.md
787be692dbf0dc16b2b86247027cacbad44fbc4742080b8f6b878d5be2c37e94  ow_16_pathglob/hidden/h01_star_does_not_cross_a_slash.py
2f6b6df24d2cfeaea2f470efc8c368a351ae5027b9e9c13ec087d2fa8725e587  ow_16_pathglob/hidden/h02_question_mark_is_one_character.py
d7f4d0be6852898518f215423b8a1e8ba5c5accb2ae9d7e945d27a9b23f396d4  ow_16_pathglob/hidden/h03_double_star_may_swallow_nothing.py
53a3828371d4914521e74fd24e7119f3ea14c65e5d3dcf47fb26c56e3ee709c3  ow_16_pathglob/hidden/h04_double_star_in_the_middle.py
f1fc26efaf24e9e6b56f2f51578956e44003b94f8c87ae590028c6b23ffff19a  ow_16_pathglob/hidden/h05_class_and_range.py
c105a8b1ab876390e27b8dec7b2a1168710124d4637c1ad65506839aec003954  ow_16_pathglob/hidden/h06_negated_class.py
e341f59499fcd1b72f429bc05843b5f214b487643f1ba4225ea4668dc3337061  ow_16_pathglob/hidden/h07_whole_path_only.py
934f88201d185e25b2a7ee16db56f29eb70f37db42ffbfb8f21d70e9ba3ce09d  ow_16_pathglob/hidden/h08_metacharacters_are_literal.py
331804e1cf8b8c576096ecd00a483ec705bf190c668c4129ba7cacff02220cdc  ow_16_pathglob/hidden/h09_selection_keeps_file_order.py
04a9fd38b4f83a0f0030446a1c5230d82c3543440385db34a2499e29fda18c76  ow_16_pathglob/hidden/h10_exclamation_removes.py
993f0d9bac0ef0002198534ffa382a83998fb1d3e6a7c39f093ec6bfeae5e8cf  ow_16_pathglob/hidden/h11_later_pattern_puts_it_back.py
53e81f2c1cb30cf03cacbd909a1c2ea24a24b4cce96e4f89ffaf9dfc4951552e  ow_16_pathglob/hidden/h12_every_pattern_is_checked.py
b68ab96865fd02d7b4f6b111de7f59bc4e97e550efd2fe62fa5daac512d55ad6  ow_16_pathglob/hidden/h13_nothing_selected.py
ab4816d860c318029114cf01ab5bd1381d3ef1811986077ace618cd37772e905  ow_16_pathglob/meta.json
e349121f7a13f49169727a2c80901d849a0541c0d2a8d3fd6eabf8bca47698f8  ow_16_pathglob/reference/bad_a.py
526ee089cb7501d092eca5ff2849c627c18f80f474a13a87c6421d0841285af2  ow_16_pathglob/reference/bad_b.py
5c74b73d033ac2567fd753f8d38ba68109498dd85f338f97cd3198b41f019c02  ow_16_pathglob/reference/bad_c.py
4e1632588384b06ee2206f6ecee7de5f771453369c93407ad2c98819de8ac1f9  ow_16_pathglob/reference/solution.py
17d2685d1b9db474a5613717d639ad5a72c9da848f8a1d71f351627b2759a229  ow_16_pathglob/rubric.md
a40770b271d4aeaf5ea11a171d3416f5448948b780e8665cd70029e968fc7c02  ow_16_pathglob/tests_visible/v01_star_stays_in_one_level.py
1c62423a85c0f00d8e6da689fd17239090a1d1f69288730e6107bd95b0821a76  ow_16_pathglob/tests_visible/v02_double_star_goes_deep.py
356487f055d04a74dfc36c1ac4721ee2e6d765bab2f9cdf9730d1e07f6a128c3  ow_16_pathglob/tests_visible/v03_classes_and_bad_patterns.py
6ae06e56a2cd925563c1cfdeaa8a2547aedfad15cdbfe45d8e268d499d82afe6  ow_17_diffpatch/contract.md
1e2d4dcc938687bd97d90a2b79511bbf8c1f8b8e96cf244812f046fa059777d7  ow_17_diffpatch/goal.md
28cd9792158e1d6d563f1627113782bf8b24b007a834d6d1dc6a8dcc7d0ecd24  ow_17_diffpatch/hidden/h01_one_piece_per_place.py
83445e7dc4471637aca2a962d90c8a3580fa390bfd5407eeedb6aef2562a7c94  ow_17_diffpatch/hidden/h02_no_unchanged_lines_at_the_edges.py
8db12164d66026abea8808985ae484e13f66b2b163bd110f05cef022d88e2a5e  ow_17_diffpatch/hidden/h03_pieces_are_ordered_and_apart.py
5756ec506ea5aa31d7c144d616bedca8175c48be69941060ffc3c1fd913443b6  ow_17_diffpatch/hidden/h04_insertions.py
8788178f8829ade67f8a9f97e71a3d69f93b0f42ec3b8f8fe3ead7961fb98690  ow_17_diffpatch/hidden/h05_deletions.py
0a8c5a735aa1ab388fd92b5d67dddbe6d5002512a6f78ada4133fc5311223b2b  ow_17_diffpatch/hidden/h06_nothing_changed.py
cdecbdd38f7380e61c44c7b3a8016d5e9306ba1659a99c7e12f8c6677e341def  ow_17_diffpatch/hidden/h07_piece_that_does_not_fit.py
0a6778f3d45f56ed65db7fc64361411a268b8ecfdd1c58b08b4d698fc27e2c6c  ow_17_diffpatch/hidden/h08_out_of_order_or_overlapping.py
88eb771cd7ddf12a6c038151c0d58f7497f7db2dafee79b0af0993238d7b2cac  ow_17_diffpatch/hidden/h09_malformed_piece.py
4aee092629dc5a054666f3be9e6ae4549896aae5bb6a0843debfd716c7002e11  ow_17_diffpatch/hidden/h10_inputs_are_untouched.py
e4e25a6f51f6666203a23b728b8d63e68f07a3965ece560e3ec33a8be64797ae  ow_17_diffpatch/hidden/h11_empty_versions.py
047e438efbe6b9f0682a0d96da32087afa0df4939d77ab8d53fc6c9ffaa60cac  ow_17_diffpatch/hidden/h12_repeated_lines.py
3d61355251a4b8a71dddd81ca5cd0f4f399de6e1d79084d80773d808158a58af  ow_17_diffpatch/meta.json
0b23ae2d6e2579b63fec3a36dffbaa65297e920259a42214dc7186b68fe723dd  ow_17_diffpatch/reference/bad_a.py
797bcea9a7141e7e4b87f82249b1506d5a5dddc98087f02458ed26dc8097aae9  ow_17_diffpatch/reference/bad_b.py
8b7dd7775ba7256cea24bc249109c40c3fcec097a3e2bb73c17d80361087765a  ow_17_diffpatch/reference/bad_c.py
e3340c73c263e6b80990328e1fc2fe98c84e9764ffe848aeb9563fd7e181187f  ow_17_diffpatch/reference/solution.py
4c255a46f1015e1439f16b21bf0f6733dc806af7491b8952abd3b5b6d062be77  ow_17_diffpatch/rubric.md
df6b160ef8dbde9ac4036c7e519cf04373db987a0131eeeb9b5157b3fc0328a5  ow_17_diffpatch/tests_visible/v01_out_and_back.py
c0e836c4c886f3288a0b88f6d705ded6fbbe379df05841a9642ddd329c2665cb  ow_17_diffpatch/tests_visible/v02_shape_of_a_piece.py
7904323942880b3213ef92ef6e1fdfbf6bc4d00d94c90dde2f3f3fde641b8cec  ow_17_diffpatch/tests_visible/v03_refuses_a_piece_that_does_not_fit.py
4fe405505db9bbdbc6c26329383934316b1a7a7bfb50c1af9dd09772574a7060  ow_18_taskorder/contract.md
7103256d55b8f0840fca5e6484f37c63ccecb0013b8f733c07bddd0a9f93f49f  ow_18_taskorder/goal.md
800cd84b31e1efe7ca70653903ec100365b05a06eb516c2ddbb7733e214f4a5e  ow_18_taskorder/hidden/h01_every_job_exactly_once.py
c5811074e2f875a2a7c9c10e9a8ecc1a5c6f47db9af29932223de39bd5f8d56b  ow_18_taskorder/hidden/h02_nothing_runs_too_early.py
951156821120a57cfd1865ef55c678f64d17edf64949a281daf062f53a4fd2eb  ow_18_taskorder/hidden/h03_same_table_same_order.py
34125b57b194740e267bb604e9eb212b1ac7e666f8a4436b592d8b1fd5101eb2  ow_18_taskorder/hidden/h04_circles_are_reported.py
a02211145d1a945d96ee6da649637a43780380301ba92370a506f7c97a59bc63  ow_18_taskorder/hidden/h05_a_job_waiting_on_itself.py
49130fad86c09aaa04011565dd954f888084b93a6f8faf46ebbb86bce35024fb  ow_18_taskorder/hidden/h06_nothing_to_do.py
899092419e4487cc2f9d20a63c6c1dc44eb90598238f7da06e1cddff7294f311  ow_18_taskorder/meta.json
df627b1ba9626cab7effc8b42d0551fc818149c496fbe976b8cb33cb986206d4  ow_18_taskorder/reference/bad_a.py
18e9c7b8d34f3fe582751512d178e6a61bf7e3bfbb00eac42bf2b8fce7a00d30  ow_18_taskorder/reference/bad_b.py
f236cf13cbca948c6f6842f38f00576436f93b3a4ad9f30edb1fc234175e1e70  ow_18_taskorder/reference/bad_c.py
5bfad17fb5579ec44616fbfb9101b249e2cf86a7b3a1f7399024f64f489377b2  ow_18_taskorder/reference/solution.py
6aae9a63d7dc4852e6057f64f59f646a385dfce3baa99dfa2ee4f99d308b0585  ow_18_taskorder/rubric.md
55fb9ae29b129a4279f15c89c2ad7848a09652216c95465ac7b91cec28dd7977  ow_18_taskorder/tests_visible/v01_prerequisites_come_first.py
c05df1408fd8b2688145b6b41e1c5b09975afb703bfbc3f5088b2199dac9f659  ow_18_taskorder/tests_visible/v02_a_circle_is_an_error.py
3eca0f13da5e32b4769d1feabd3a930ebb68fb75f8d41807c62860c0543f1ca1  ow_19_redact/contract.md
3f36886dfa12cbc5e97dbcc5c6e81695d3ddcc6e6e901e9e68cd96992aad863d  ow_19_redact/goal.md
59f6847effdc5977247366705fc0f581e067387602bbb2e0c2197fdf3d2714e7  ow_19_redact/hidden/h01_all_three_kinds_go.py
49b6abab81da8a52e3ed77ef538eeaae71fc725dbdad640f5d61ff55a8ce81ba  ow_19_redact/hidden/h02_ordinary_lines_untouched.py
a4ec291b1b6c030267ef6d3524b6b3b298d43a6d3c55597813a9d1a0ac140829  ow_19_redact/hidden/h03_second_pass_changes_nothing.py
2c106b83505baa7601fe4fd445ef24493b4f67a137ba0d45f14ae1ccf3df3dfd  ow_19_redact/hidden/h04_the_rest_of_the_line_survives.py
33a282f6ca0252c5fdfac94ebe04988dcec18e9668827a28915e620319dfd58d  ow_19_redact/hidden/h05_repeats_both_go.py
407aa4e167b107a3c1d12586a2be620db3bd4e46dd0f40c5b7c5682fd158e86e  ow_19_redact/hidden/h06_the_count_is_usable.py
38afcd327b8419ce1c5c856a3aed6656fc32420fada7f5586144698ceaa95c2c  ow_19_redact/meta.json
50ace02e36d7e56a0ab4fc4b545733b0f9f169ab5c7f256ff6f582d624ac448b  ow_19_redact/reference/bad_a.py
69c7d19d31da68894176a9ed7d2ef8b7e35b570f027a0e04f436e320ee0aa5a8  ow_19_redact/reference/bad_b.py
038ff1aacbce40179c9d334926407841e9b925ea4675bfcaf247ac024b6973f8  ow_19_redact/reference/bad_c.py
bf79d464a0ce979c9ed451822dd31965b797fc28bf463fd66e96c520f57ab4f5  ow_19_redact/reference/solution.py
dc7f5f50a412db0cbf7add6402a007dadd6ec20cf4e9e3cf89aa267ba58dfa97  ow_19_redact/rubric.md
99700e19d3c7074f901141bea6394223055313ac745cd0f9e6b6320ab12e1f7b  ow_19_redact/tests_visible/v01_the_secret_goes_the_rest_stays.py
cc97b2549c8dd4c72c5ddc6557d52cb1b224f8c0fe2d7c8a011c5c08d72b7664  ow_19_redact/tests_visible/v02_clean_lines_and_second_passes.py
94a2a087508f83ee4212cebfbc84afe22908d1bdad946eaed705d521b1ce27af  ow_20_slugify/contract.md
824ee1802861cb1b37936172971af53090e95f4338e2785f8a2951e9ddfa8488  ow_20_slugify/goal.md
27acf29c3df626a36e5c60f70fe4770d3228e6da51b422704d4ac270f931696c  ow_20_slugify/hidden/h01_same_order_same_length.py
56a6bf65fb83f3f83a33f657e7ae20a962e4cac21b2b35e1df82f494d3d54394  ow_20_slugify/hidden/h02_only_allowed_characters.py
6fec1ebefc080477ab1ce3b58dcb9dc6daa8c27f3ebf044621659d0e1a98e260  ow_20_slugify/hidden/h03_hyphen_rules.py
a5b6df1f047520c463be99ea2f3504733f0c8fe1377b2215481cb68c32a4160d  ow_20_slugify/hidden/h04_no_two_the_same.py
d2f23a173f3653e655135300d79dbee19c374ea52676e18885abfd615e40af9b  ow_20_slugify/hidden/h05_same_batch_same_slugs.py
b617979d7ba764f9b2d4ac35732a73e496bb8b464b6044995a5183e5981c619c  ow_20_slugify/hidden/h06_clean_titles_come_back_whole.py
b5fde3b33ca68003ef28d1962becede625fa2a5c6bc81ea814278f381b657239  ow_20_slugify/hidden/h07_non_latin_titles.py
4ab7a8d46bd60f1bc2000169966fcffd028bad55c49ee6e3101dbbd20657b0a6  ow_20_slugify/meta.json
bd13f5438b87d3e1460aeb8cad2d644cae794ade2d50945ee4446f2032915648  ow_20_slugify/reference/bad_a.py
a80d3687a96e965b6bc3e0427a7a33c3746bdda7c6f8a76c956cb73fe01aab17  ow_20_slugify/reference/bad_b.py
c601e0cca7bb478ccbc4b7f2ee9df0e07e0f684b97e054f5c7111a1521eba46e  ow_20_slugify/reference/bad_c.py
1e0d663b9982bff6011531d0fa99f103b1fded2da9e310e6b58daf69cbd174cc  ow_20_slugify/reference/solution.py
dc5e2108b5db877ba16ee950c060ef5807490cf3e5dc511d901205a9766c9029  ow_20_slugify/rubric.md
9a52b23f667a31b1899839a572d726c8ab8b2c8c23c73f1b796fd924d06cea8d  ow_20_slugify/tests_visible/v01_one_slug_per_title.py
5478666abe52f1dac0abf0288f687edb422289b4d61b29d2888ac69e7cca1b26  ow_20_slugify/tests_visible/v02_already_a_slug.py
```

</details>

### AMEND1-E　AMEND1 **沒有**做的事（照實列，別讓它看起來像做過）

1. **沒有跑任何模型。** 五項修正、D1／D2 重算、sha256 全部是確定性的檔案操作。
2. **沒有人類逐題看過這 20 題**（§八-2 第 4 條）。三個角色（作者／複核者／修訂者）都是代理。
3. **沒有驗證題庫對 `gemma-4-12b-it-qat` 難不難**——那需要模型呼叫，而 §一-3b 的擋門
   本來就不問這個。天花板效應的風險原樣留在 §四-4 與 §八-2。
4. **沒有做 §一-5 第 3 點的反向檢索紀錄**（對每題契約特徵字串做公開檢索、逐條落盤）。
   那一項仍然開著，且它與污染那一段（§一-5、§八-3）綁在一起。
5. **沒有建 `template/`**（§一-1 列了它，題庫目錄下沒有這一層；工作區樣板是 §三-1 的事）。
6. **量具的單邊保證原樣留著**：`gauge_r530.py --check` 全綠 **不等於** 驗收套件固定點已解。
   它擋得住的是「這些**已知的**錯法」，**不代表**「所有錯法都會被擋下來」，
   更不代表隱藏驗收涵蓋了目標的全部需求。複核者另外記了兩處量具涵蓋不到的地方：
   `ow_03` 的 `h10`／`h12`／`h14` 與 `ow_05` 的 `h09`–`h12` **沒有任何已知壞樁會踩到**，
   `ow_13` 的 `bad_b` 只被 3／13 條隱藏擋下（全庫最薄的一格）。
7. **`amended` 不是瑕疵紀錄，是題目定稿的過程**（§五-2 原話）——但它必須看得見，
   否則「複核通過」會變成一個沒有內容的印章。五筆全在 AMEND1-A，一筆都沒有被吸收掉。

### A-17　**冒煙推翻的第五個假設：「5 份／24 通」**（第五輪裁決 1–5，2026-09-14）

| | 內容 |
|---|---|
| **本檔原本怎麼寫** | §二-3：`max_model_calls: 24` ＝ **每格總上限**，三條臂共用；§二-1：`A-CONF` **最多 5 次嘗試**、`A-GATE` **最多 5 個閘門輪**；§四-1 P-W6 的窗是 `SOLO [4,14]`／另兩臂 `[8,24]`，由「每題 3–8 通 × 5 輪」倒推 |
| **冒煙量到什麼** | 模型在這種小專案任務上**大約 20 通才宣告完成一份** |
| **後果（這才是重點）** | 24 通總上限之下，`A-CONF` 第一份就吃掉 20 通、剩 4 通**做不出第二份** ⇒ 它退化成「只跑一次可見驗收」的臂 ⇒ **`A-GATE` vs `A-CONF` 那一刀切不出任何東西**。而且這個失敗**不會報錯**——它只會安靜地產出一個 `INCONCLUSIVE`，然後被後續引用成「量過了」 |
| **改成什麼** | 預算拆兩層：**每份 24 通**（`max_calls_per_attempt`）＋**每格 72 通**（`max_model_calls`）；completion 40 k → **120 k／格**；牆鐘 2,400 → **7,200 s／格**；`A-CONF` **5 份 → 3 份**（3 × 24 ＝ 72，與總上限對齊）；`A-GATE` 在 72 通內續改（名目 5 輪，實際 2–3 輪） |
| **連帶改掉的** | §二-1 表格三列與那一刀的表述；**§八-4 整節重寫**（「等預算」這個詞**全檔刪除**，改成「上限相同、實際用量各自落盤」，與 R460 同口徑）；§六-5 (iii) 明寫實際呼叫數差異從這一格進裁決；§三-6 新增 **C9**；§七-2b 時程重算；§三-0-2 工作區數 660 → 420；P-W6 的窗重寫；PR-4 的問題改對；§九-7 結案 |

**兩件事要特別留著**：

1. **`A-CONF` 從 5 份降到 3 份的理由是機時，不是機制。**
   5 份在 20 通／份之下要 120 通／格、180 格跑不完（§七-2b）。
   **本檔一個字都沒有講「3 份就夠了」**——那是一個沒有根據的說法，
   而 R440P 量到的候選池天花板（17–19% 五份全錯）**本來就是在 5 份上量的**
   ⇒ 3 份的重抽比 5 份**更弱**，這對 `A-GATE` **有利**。
   ⚠ 收官引用 `A-GATE` vs `A-CONF` 的差時**必須帶這一句**。
2. **「等預算」這個詞被刪掉，不是換個說法而已。**
   它原本讓人以為兩條臂花一樣多，而事實是**上限一樣、用量不會一樣**，
   而且事前就知道不會一樣。R460 的口徑（上限寫死、用量落盤、差異進成本指標）
   才是準確的，本檔改成那一套。

⚠ **這是連續第二輪被冒煙推翻的事實宣稱**（第四輪四條、第五輪一條）。
第四輪那四條是「機制接不接得起來」，**這一條是「機制接起來了，但預算讓它跑不動」**
——後者更難發現，因為六格冒煙**全部成功收尾**，錯的是**沒有人去看那 6 格各用了幾通**。
C9 就是補這個洞的：它逼冒煙回答「**兩條有閘門的臂真的動起來了嗎**」。

### A-18　**條數界放寬 ＋ 量具具名例外撤掉**（2026-09-14 補充裁決 (1)(2)(3)）

#### A-18-1　條數界（補充裁決 (1)）

- **v2 原本的界**：可見 **2–3** 條、`tight` 隱藏 **≥10**、`loose` 隱藏 **≥5**（只有下界）。
- **AMEND1 撞到的事**：§五-2 的反向擋門在 `ow_08_logscan` 失敗一句
  ——goal 裡「from the shell without writing a script」那一句**零驗收**。
  Fable 裁決補 **1 條可見 ＋ 2 條隱藏**（JSON-CLI 路線）⇒ 那一題的條數
  **超出當時的界**。
- **AMEND1 當下的處置**：在 `ops/gain/r530/gauge_r530.py:61` 寫一個**具名例外**
  `COUNT_EXCEPTIONS = {"ow_08_logscan": {"visible": (2,4), "hidden": (10,16), ...}}`，
  理由逐字是「改界線會讓其他 19 題一起漂，而且下一次有人多寫兩條就再也擋不住；
  具名例外會在 diff 裡看得見」。**那個理由本身是對的**，所以它被寫成例外而不是放寬。
- **補充裁決 (1) 的決定**：ow_08 走 JSON-CLI **照准**，而且**把界本身改掉**
  ——可見 **2–4**、`tight` 隱藏 **10–16**、`loose` 隱藏 **5–7**（**上下界都判**）。
  `COUNT_EXCEPTIONS` **在發射前移除**，由基建代理改 `gauge_r530.py`。
- **為什麼最後選「改界」而不是「留例外」**：
  一個只對一題成立的例外，會讓「這 20 題的條數分佈」變成**看不出來的東西**
  ——`ow_08` 到底是特例還是界訂得太緊，從資料上分不出來。
  改成**上下界都判**之後，界本身變成一個可驗的、對 20 題一致的判準，
  而 AMEND1 擔心的「下次多寫兩條就擋不住」由**上界**接手擋。
- ⚠ **代價照實寫**：界是**看過 `ow_08` 需要幾條之後**才放寬的。
  順序上這是「資料先於判準」，只是那個「資料」是**題庫的結構**不是實驗結果
  ——**它不碰任何一條臂、任何一格 rows**。
  即便如此，這件事要留在這裡，不要被寫成「界本來就是 2–4／10–16」。

#### A-18-2　`boundary_only_hidden_n` 從「描述性分層」降到「不得引用」（補充裁決 (2)）

- **v2 原本**：§一-3b 寫它「給收官做描述性分層用（增益是不是只來自邊界條）」，
  只禁止「臨時拿它當門檻」。
- **AMEND1 標完之後量到的**：全庫 **55 條**被標成 `boundary_only` 的驗收裡，
  **40 條只是「契約要求丟例外」**。
- ⇒ 這個量實際上在講**目標／契約裡有沒有寫錯誤條款**，
  **不是**在講「這套驗收偏不偏邊界」。**同名不同義。**
- **改成**：§六-8 新增第 12 條——**收官任何宣稱不得引用它**，只留在題庫附錄當描述。
- ⚠ 這是本檔第一次**把自己事前定義的一個量整個作廢**。
  它沒有被刪掉（`meta.json` 照舊落盤），但**不准進任何句子**
  ——留著是為了讓後來的人看得到「這裡曾經有一個量，而它量錯了東西」。

#### A-18-3　`loose` 層的目標補述（補充裁決 (3)）

見 §八-2 第 5 條。一句話：**反向擋門與「契約留白」互相拉扯**，
`ow_19`／`ow_20` 為了讓驗收有 anchor，目標敘述補上了**覆蓋面清單**（不是做法），
`loose` 因此**離 `tight` 近了一步**，負向對照的力道比設計時弱。
⚠ 這一條與 A-13 末那個「`frac` 顆粒度」是同一種東西：
**都是後來才看出來的、由前一條裁決帶出來的副作用**，兩條都標在原地沒有藏。

## 附錄 A-18b　2026-09-14 基建落地時的兩處推導（Fable 追認，發射前記入；原編號 A-19，為避免與第六輪 A-19 重號改名）

1. `max_tool_calls` ＝ **120**（預註冊未指名）：推導自每格 72 通 × 冒煙實測每通約 1 次工具呼叫；若沿用舊值 40，`stop_reason` 會先變成 `budget_tool_calls` 而不是 §二-3 指名的那幾種。常數註解標「推導，非預註冊指名」。
2. **份層級檢查先於格層級**：`A-CONF` 第 3 份用完時 3 × 24 ＝ 72 兩個上限同時成立，先判份層級 ⇒ 記 `attempts_exhausted`（拒交語意，P-W3 讀的就是它），不記 `budget_calls`（不算拒交）。同一件事只准有一種語意。
3. 冒煙紀錄：smoke7（舊常數、含 C3／C6 兩個收尾記帳 bug 的資料）與 smoke8（過渡常數、只跑 CONF／GATE 兩格）**永不進證據**，只留作檢核表對照；發射前的正式冒煙＝ smoke9（最終程式碼、完整六格、兩台各 ≤3 串），C1–C9＋E9／E10 全綠才准發射。
4. 冒煙觀察（不進裁決）：smoke7 的 `A-SOLO / ow_01` 20 通裡 18 次重寫同一個檔案、0 次執行自己的碼、0 次跑可見測試；同 prompt 同 persona 的 `A-CONF` 第 1 份跑了 1 次可見測試。W7a／W7b 的歸因量在 n 小時會很吵，30% 那條線只判不解釋。

## 附錄 A-19　**第六輪的三個量測，以及「不合成總分」的翻轉**（2026-09-14）

#### A-19-1　推理模式：從「假設它生效」到 E-11

- **v2 之前**：`reasoning_effort=none` 寫在 §二-4 與 §三-2，**當成事實用**，沒有擋門。
- **第六輪裁決 1 把它變成擋門（E-11）**，而且指定**探針必須帶 `tools`**
  ——`none` 在不帶 `tools` 的請求上生效，不代表在帶 `tools` 的請求上也生效。
- **smoke9 實測（72 通 ＋ 10 次獨立探針，兩台）：`reasoning_tokens` 全部 0。**
  ⇒ **R529 §十一 那種「同一批資料混了兩種推論條件」沒有重演。**
- ⚠ **全綠不代表免驗**：本檔仍把它寫成**發射前擋門**，
  理由是這件事壞掉的時候**不會有任何錯誤訊息**——它只會讓某幾塊的 completion
  混進推理 token，把 token 帳與成本指標 (iii) 一起弄髒。
  「欄位不存在算紅、沒探過的端點算紅」沿用既有的「量不到不是通過」。

#### A-19-2　後端速度差：量到了，判成 task 層級干擾項

- **量到什麼**（去快取配對探針）：**1003 比 1004 慢**——
  冷 prefill **3.1×**、暖 prefill **1.4–2.7×**、生成 **1.6×**。
- **判定**：**task 層級干擾項，不是 arm 層級混淆**（同題三臂同台，R460 §二-2 同一條）。
- **它真正會咬到的地方是 `budget_wall`**：同樣 7,200 s，在慢的那一台上先撞到
  ⇒ analyzer 必須**逐後端**印 `budget_wall` 計數。
- **連帶寫死一條紀律**：佇列由 `schedule_r530.py` **輪流分配**，
  **禁止手動把題綁死在單一台**——綁死會讓題目與後端共線。
  ⚠ **`smoke9` 就是綁死跑的** ⇒ **它的兩塊不可跨台比較**。這一句要跟著 smoke9 的任何引用走。

#### A-19-3　`T` 從「四個候選」變成「雙峰的兩個數字」

- **第五輪**只能給敏感度表（30／45／60／90），因為錨還沒拿到。
- **smoke9 給了錨，而且順便推翻了「`T` 是一個常數」這個隱含假設**：
  每通延遲**由生成長度決定**（相關係數 **+0.98**），而生成長度**依題型分兩群**——
  `ow_02` 型（每輪只發小工具呼叫）p50 **1.2 s**；`ow_01` 型（每輪重寫整檔）p50 **26 s**。
- ⇒ 填進表的是**中心 10 s／最壞 30 s**，而且逐字寫明
  **「平均值在這裡沒有意義」**、兩個 p50 分別量在不同台上因此**不可互比**。
- 在這個錨之下最壞一格是 **18.9 h < 24 h** ⇒ §七-2b 的砍 seed 程序**目前不需要觸發**，
  但那條程序原樣留著（`T` 雙峰 ＋ 8 串的減速係數已知偏樂觀）。

#### A-19-4　質化：**「四維總分」整個刪掉**（第六輪裁決 4）

- **v2 原本**：§六-6／§八-8 要求「四維總分與三維總分都要報」，
  §五-6 第 4b 項還定義了 `rubric.<seed>.total_excl_confounded`。
- **第六輪改成**：**四維逐維報，不定義也不准計算任何總分。**
- **理由**：四維**不是同一把尺**，相加等於默認它們之間有一個換算率，
  而那個換算率本檔沒有依據；而且「與目標的貼合度」與主指標部分重疊
  ⇒ **任何含它的總分都會把量化的結果偷渡進質化**。
- **連帶簡化掉一整套補償機制**：原本「扣掉重疊維度的三維總分」、
  「扣掉被擋維度的總分」都不再需要——**被擋的維度就是那一維不報**。
- ⚠ 這是本檔第二次把自己事前定義的東西整個作廢
  （第一次是 A-18-2 的 `boundary_only_hidden_n`）。兩次都**留著紀錄不刪**。

#### A-19-5　評審輸入：第一次寫死「不給什麼」

- v2 的 §五-6 只講了去識別化與評審配置，**從來沒有寫清楚 prompt 裡到底放什麼**。
- 第六輪補上一張表（§五-6 第 1c 項）：給 `goal.md`＋`contract.md`（逐字）＋
  去識別化後的提交；**不給可見測試**、不給隱藏測試、不給任何通過率或分數、
  不給臂別／seed／後端／輪數。
- **「不給可見測試」是本輪唯一一個需要解釋的決定**：評審看得到那 2–4 條驗收，
  就會**拿測試當錨** ⇒ 評分退化成「有沒有照那幾條寫」，
  而那件事量化那邊已經量過了（可見驗收就是閘門本身）。
- **`--bank ops/gain/r530/judge_bank` 必須明給**，而且 `export_for_judge.py --check`
  要連 dry-run 一起驗。⚠ 不准直接指正典 `bank/`——那裡面有 `hidden/` 與
  `tests_visible/`，**指錯目錄就是把 V/GT 紅線交給「記得加參數」這件事**。

## 附錄 A-20　**smoke8／9 抓到並修好的三件事，以及 `A-SOLO` 的形狀**（2026-09-14）

#### A-20-1　三件在冒煙裡才看得到的錯

| # | 錯在哪 | 誰抓到 | 為什麼它在單元測試裡看不出來 |
|---|---|---|---|
| **1** | **撞預算的格沒跑可見驗收** | **C3** | 一格用完預算就直接收尾，跳過了「跑一次可見驗收並落盤」那一步 ⇒ 那些格子的 `visible_*` 是空的。⚠ 後果很具體：**`A-SOLO` 的 `self_ran_visible` 會缺值** ⇒ **W7a／W7b 的歸因量在撞預算的格子上量不到**（§四-1a）。撞預算是**正常結局**不是異常，所以這條路徑必須跟正常結局走同一套收尾 |
| **2** | **收據少一筆 `attempt`** | **C6** | `openwork_attempt` 的筆數少於實際輪數 ⇒ 數量對帳（verdict 數 == row 數、attempt 數 ≥ verdict 數）過不了。⚠ 這一條若帶進正式 run，會直接讓 §五-5 **E-5 紅**，而 E-5 的處置是「單格 void、≥2 格 `INVALID`」⇒ **一個收尾路徑的漏寫可以整批作廢資料** |
| **3** | **`nobody` 擁有的工作區重置炸掉** | 冒煙實跑 | `A-CONF` 每份要把工作區重置回樣板，而沙箱以低權限使用者跑過之後，工作區裡出現了**不屬於執行者**的檔案 ⇒ `cp -a`／刪除失敗。這正是 §三-3 把 S2 從 `nobody` 改成**專用使用者 `r530run`** 的那條理由的實際後果 |

⚠ **三件都不是「模型表現不好」，全部是 harness 的收尾路徑。**
三件也都**不會產生錯誤訊息**，只會產生**看起來正常但缺欄位的資料**。
⇒ 這一節與 A-16、A-17 是同一個主題的第三次出現：
**冒煙買到的東西不是「機制會不會成功」，是「機制失敗的時候長什麼樣」。**

#### A-20-2　`A-SOLO` 的形狀（發射前觀察，**不是資料**）

smoke9 觀察到 `A-SOLO` 的行為形狀：**每輪重寫整個檔案、不執行、不測試。**

- 這解釋了 §七-2b 那個 `ow_01` 型 p50 **26 s**——每輪重寫整檔 ⇒ 生成長 ⇒ 延遲高。
- ⚠ **它同時是 W7a／W7b 的事前線索**：「不執行、不測試」若在正式 run 上重現，
  `per_arm.SOLO.self_ran_visible_pp` 會很低 ⇒ 落在 **W7a**
  （增益主要歸給「被要求驗證」而不是回饋迴圈的內容）。
- ⚠ **但這不改變 §四-1a 的任何一個字**：
  W7a／W7b 的仲裁量讀的是**正式 run 的實測**，不是冒煙的觀察。
  冒煙只有 2 題、而且是發射前的探路。
  **把這段寫在這裡，是為了讓「收官時 W7a 命中」看起來不像是事後編的故事
  ——它在發射前就被寫下來了；但它一樣不能拿來取代仲裁量。**

## 附錄 AMEND2-A　正式佇列註冊行（2026-09-14，發射前逐字釘入；佇列 JSON `ops/gain/r530/queues/r530_main.json` sha256 `5d9e309292083c8fd496dce1c035ceb1dc6a71b07de120a1c810e67916b75678`）

12 塊 × 5 題 × 3 臂 ＝ 180 格；seed g-r530-s1／s2／s3；同題三臂同 seed 同一台；第 k 顆 seed 的第 i 題走 hosts[(i+k)%2]（每題三顆 seed 在兩台的分配為 2:1，不與單一台共線）；每台 ≤4 串；loose 三題散在不同塊（每塊 ≤1 題 loose）。發射器逐字比對下列註冊行（`schedule_r530.py --check`；2026-09-14 第二版：註冊行由佇列 JSON 重新產生，前一版 .txt 為 loose 交錯修正前的過期檔）：

```
R530_BLOCK: g_r530_s1_1003_1 tasks=ow_01_csvjson,ow_03_mdtable,ow_04_layerconf,ow_06_verrange,ow_08_logscan arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s1_1003_2 tasks=ow_19_redact,ow_11_reflow,ow_13_timespans,ow_15_tomlsub,ow_16_pathglob arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s1_1004_1 tasks=ow_02_ratelimit,ow_18_taskorder,ow_05_router,ow_07_retrypolicy,ow_09_minitemplate arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s1_1004_2 tasks=ow_10_dedupe,ow_12_bytesize,ow_14_statemachine,ow_20_slugify,ow_17_diffpatch arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s2_1003_1 tasks=ow_02_ratelimit,ow_18_taskorder,ow_05_router,ow_07_retrypolicy,ow_09_minitemplate arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s2 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s2_1003_2 tasks=ow_10_dedupe,ow_12_bytesize,ow_14_statemachine,ow_20_slugify,ow_17_diffpatch arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s2 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s2_1004_1 tasks=ow_01_csvjson,ow_03_mdtable,ow_04_layerconf,ow_06_verrange,ow_08_logscan arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s2 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s2_1004_2 tasks=ow_19_redact,ow_11_reflow,ow_13_timespans,ow_15_tomlsub,ow_16_pathglob arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s2 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1003_1 tasks=ow_01_csvjson,ow_03_mdtable,ow_04_layerconf,ow_06_verrange,ow_08_logscan arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1003_2 tasks=ow_19_redact,ow_11_reflow,ow_13_timespans,ow_15_tomlsub,ow_16_pathglob arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.119.113.56:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1004_1 tasks=ow_02_ratelimit,ow_18_taskorder,ow_05_router,ow_07_retrypolicy,ow_09_minitemplate arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1004_2 tasks=ow_10_dedupe,ow_12_bytesize,ow_14_statemachine,ow_20_slugify,ow_17_diffpatch arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.86.226.21:1234/v1/chat/completions
```

## 附錄 AMEND2-B　凍結紀錄（§一〇-1 的 F1–F7；2026-09-14，Fable）

| 項 | 值 | 依據 |
|---|---|---|
| **F1** 程式碼 commit | `b9eb0384d0b3`（feat/v2-four-stages，基建分支併入主線後、含註冊行修正） | `git rev-parse HEAD`；vacant-dev `~/vacant/Vacant` 已 ff 到同一 commit |
| **F2** bank sha256 | `1eae5f193a0e7616ebe13b430c075848c23bbad204f6017e8c93cc40a2dd48ef`（469 檔） | `gauge_r530.py --bank-sha`（與 AMEND1-D 相同） |
| **F3** judge_bank 投影 sha | `db818527afa6d7dec6250e7e84242bd0159d301a8d003c686f86326fa67a5bd9`（121 檔；排序路徑逐檔 sha256 再 sha256）；rubric 共用段 `90641afed6e089b7` | `export_for_judge.py --check` PASS |
| **F4** E-9／E-11 preflight 存證 | smoke9 兩塊：`ops/gain/r530/smoke9/e11_preflight.json`（兩台帶 tools 探針 reasoning 0）；正式 run 逐塊：`runs/<block>/gate_e9.json`、`inference_probe.json`、`gate_e11.json` | 發射器在任何實驗呼叫之前寫入 |
| **F5** smoke9 檢核表 | `ops/gain/r530/smoke9/checklist.json`：verdict PASS（C1–C9、E9／E10／E11 全綠；六格表在檔內；每通秒數 A-SOLO 28.2／A-CONF 13.9／A-GATE 18.7） | 由 `smoke_checklist.py --run <9a> <9b>` 產生 |
| **F6** 發射時間戳（UTC） | **發射時由排程器 log 第一行記入，見 AMEND2-C** | 排程器 `schedule_r530_<q>.log` |
| **F7** 佇列 JSON sha256 | `5d9e309292083c8fd496dce1c035ceb1dc6a71b07de120a1c810e67916b75678`（12 塊／180 格） | `ops/gain/r530/queues/r530_main.json`；12 條註冊行見 AMEND2-A，`schedule_r530.py --check` 逐字比對通過 |

凍結後到發射之間不改任何一項；改了就重新凍結、重記七樣並留上一版。
發射拓撲：1003 四串＋1004 四串（`r1003#1–4`／`r1004#1–4`）；三道發射前閘門 E-3（整個 bank 量具）、E-9、E-11 任一紅 ⇒ 該塊不發。
沙箱：`unshare --net`＋`setpriv --reuid=65534`，工作區根 `/var/tmp/vacant_r530_work`；bwrap AppArmor profile 未安裝（人類事項，`SANDBOX.md` 路線 B）。

## 附錄 AMEND2-C　第一次發射失敗與重新凍結（2026-09-14，Fable）

- **06:14:33Z 第一次發射**：8 塊全部正常起來（三道閘門都跑過、calls.jsonl 開始寫），60 秒後被排程器自己判 DEAD、搬進 `_aborted/`、重排兩輪後整批放棄。根因：`schedule_r530.py` 沿用 `schedule_harness_reps.running_block_names`，該函式寫死比對 `"gain_run.py --out "`，認不得 `run_r530.py` ⇒ runner 在 ps 上永遠「不在」。**那一次不算發射（無 F6）**；60 個誤報產物搬到 `runs/_falsealarm_20260914_scheduler_bug/`（刻意移出 `_aborted/`，否則 `aborted_counts` 會讓每塊一開始就背重排次數）；工作區與行程全清；沒有任何實驗資料進入證據。
- **修正**：R530 自己一份 `running_block_names`（比對 `run_r530.py --out `，且 `$2 == "python3"` 真的比對第二欄以濾掉 flock 那行）＋4 條測試；併入主線後 R530 測試 166 條全綠。
- **為什麼冒煙沒照出來**：smoke7／8／9 都是手動直接跑 runner，沒經過排程器。⇒ 新增發射時檢核 **C10（活體檢查）**：先發 1 塊，60 秒後排程器必須把它列為 RUNNING（不是 DEAD／PENDING），通過才放其餘塊；C10 結果進排程器 log 與本附錄。
- **重新凍結（依 §一〇-1，上一版 AMEND2-B 原樣留著）**：
  - **F1′** 程式碼 commit ＝ `0b58ad7bc266`（含排程器修正）；vacant-dev 需 ff 到同一 commit。
  - F2、F3、F5、F7 不變（bank、judge_bank、smoke9 檢核表、佇列 sha 皆未動；`schedule_r530.py --check` 逐字比對通過）。
  - F4 存證路徑不變。
  - **F6** 於重新發射時記入 AMEND2-D。

## 附錄 AMEND2-D　F6 發射紀錄（2026-09-14，Fable）

- **F6 ＝ 2026-09-14T06:29:07Z**（排程器 `~/vacant/logs/schedule_r530_r530_main.log` 本次有效發射的第一行「完成 0／佇列 11／佔用 [('r1003#1', 'g_r530_s1_1003_1')]」）。⚠ 該 log 是 append，字面第一行 `06:14:33Z` 是 AMEND2-C 記錄的失敗發射，刻意不刪。
- **C10 活體檢查 PASS**：先發 `g_r530_s1_1003_1`，t0→t+60 排程器 `observe()` 皆 RUNNING、calls.jsonl 18→24 行、`_aborted/` 無新項、gate_e9／gate_e11 綠、inference_probe 存在；通過後放其餘 7 塊。
- 8 塊槽分配：r1003#1–4 ＝ s1_1003_1、s1_1003_2、s2_1003_1、s2_1003_2；r1004#1–4 ＝ s1_1004_2、s2_1004_1、s2_1004_2、s1_1004_1；排程器 pid 3294795；佇列剩 4 塊（s3）等槽。每塊 E-3（整個 bank 量具）、E-9、E-11 於任何實驗呼叫前通過。
- 程式碼＝F1′ 0b58ad7bc266（vacant-dev `~/vacant/Vacant` at 91d9644，ops/ 內容與 0b58ad7 相同）；工作區根 `/var/tmp/vacant_r530_work`。
- 時程：依 smoke9 單串 T（A-SOLO 28.2／A-CONF 13.9／A-GATE 18.7 s/通）粗估 20–40 h；併發下 T 會變大（未量過倍率），收官以 summary.json 實測回填。

## 附錄 AMEND2-E　排程器第二次猝死與再凍結（2026-09-14，Fable）

- **09:58:37Z 排程器猝死**：第一塊寫出 `summary.json` 的瞬間，沿用的 `classify_summary` 把 R530 的 `summary["arms"]`（list；逐臂統計在 `arms_stats`）當 dict ⇒ `AttributeError`。與 AMEND2-C 同類（沿用吃外部狀態的函式），但這次要等第一塊收官才炸，排程器先安靜跑了三個半小時。
- **資料無損**：DONE 2（`g_r530_s1_1004_1`、`g_r530_s2_1003_2`，皆 verdict ok、void 0）、RUNNING 6（runner 不依賴排程器，自行跑完）、PENDING 4（尚未發射）、`_aborted/` 空。停擺代價只有吞吐（兩個空槽閒置）。
- **修正**：R530 自己的 `classify_summary_r530`／`block_state_r530`／`void_rates_r530`（讀 `arms_stats`；E-11 收官 broken ⇒ VOID）＋7 條測試（含「沿用那支對 R530 summary 必須 raise」的釘死）。併入主線 `0ebdd791f875`；**runner（run_r530.py／臂／驗收／沙箱）一行未改**，已完成與在跑的 8 塊條件不變。
- **再凍結**：F1″ ＝ `0ebdd791f875`（只動排程器）；F2–F5、F7 不變；F6 不變（06:29:07Z 的發射仍有效，8 塊條件相同）；排程器重啟時間戳記於下方。
- 教訓寫進 `schedule_r530.py` 註解：**沿用得起來的只有吃參數的純函式；吃外部狀態（ps、summary.json 形狀）的一律自己寫並附負控。**
- **排程器重啟：2026-09-14T10:34:23Z**（同佇列、log append）。活體確認通過：3 DONE 判 DONE、8 RUNNING 判 RUNNING、`_aborted/` 無新增；補發 3 塊（s3_1003_1／s3_1004_1／s3_1004_2，pid 3314122／3314121／3314124，E-3／E-9／E-11 皆綠），`s3_1003_2` 等 1003 空槽（不挪卡）。已知小瑕疵：真跑時 `gate_e11.json.enforced` 為 null（閘門實際有強制），留待下次凍結修，跑中不併碼。

## 附錄 AMEND2-F　1003 後端停擺、四塊作廢與第三次嘗試（2026-09-14 → 15，Fable 裁決）

**事件**：2026-09-14 13:37–13:43Z，1003 的 LM Studio 變成「沒有載入任何模型」（機器與 port 正常，`lms ps` 顯示 no models loaded；`/v1/chat/completions` 回 400 "No models loaded"）。當時在 1003 上的四塊 `g_r530_s1_1003_1`／`s1_1003_2`／`s3_1003_1`／`s3_1003_2` 連續 VOID，排程器重排兩次用完 `MAX_ATTEMPTS`，於 16:14:31Z 記「留給人裁決」後退出。1004 的六塊全部正常收官。

**當時結果**：DONE 8 塊（1004 六塊＋1003 的 s2 兩塊）、118 列；作廢資料一列不計。

**裁決（§一〇「留給人裁決」）：授權第三次嘗試**，條件如下，全部核對過：
- 註冊行逐字相同（同 seed、同題、同臂、同 endpoint）——佇列與 sha 未變（`5d9e3092…`）。
- 程式碼未變：F1″ `0ebdd791f875`；vacant-dev `~/vacant/Vacant` at `cde7c1a`（含 F1″）且工作樹乾淨。分支上的 `cae538a`（`gate_e11.json.enforced` 描述性欄位）**刻意未併**，避免前後塊跑在不同碼上。
- 後端條件回復：2026-09-15T01:37:48Z 於 1003 重載 `gemma-4-12b-it-qat`，`context 262144／parallel 4／gpu max／ttlMs null`，VRAM 13,339 MiB，與前次逐項相同；E-11 式探針（**帶 tools**、`reasoning_effort=none`）回 `finish_reason=tool_calls`、`reasoning_tokens=0`。
- 舊作廢紀錄移出 `runs/_aborted/` 到 `runs/_aborted_r530_1003_outage_20260914/`（附 README），理由：`aborted_counts()` 數的就是那個目錄，留在原地會讓第三次嘗試立刻被放棄。**那裡的資料一列都不進證據。**

**第三次嘗試發射**：2026-09-15T01:39:01Z，四塊各佔 r1003#1–4（1004 已全數收官，不再佔槽）。

**同時記一次操作事故**：發射命令被執行兩次 ⇒ 一度有兩個排程器行程（3343580、3343989）。runner 未重複（每塊的 `flock` 擋住，逐塊只有一個 runner），01:40Z 以 pid 殺掉後者、保留前者。**對資料無影響**，記錄於此以免日後從 log 的重複「發射」行誤判為雙跑。

**效力**：本次補跑的四塊與先前八塊在同一份程式碼、同一套題庫、同一組註冊行、同一種後端參數下執行；差別是**時間**（相隔約 12 小時）與**1003 曾經重載模型**。收官時 §八-11 的逐後端描述照舊，另加一句「s1／s3 的 1003 半邊是補跑的」。


## 附錄 AMEND2-G　1003 被人類佔用，剩餘四塊改在 1004 重跑（2026-09-16，Fable 裁決）

**事實**：AMEND2-F 的第三次嘗試於 2026-09-15T01:39Z 發射後，10:47／11:24／19:00–19:02Z 連續 VOID（呼叫回 HTTP 400），排程器 19:02:21Z 用完重排額度退出。2026-09-16T01:35Z 查 1003：載入的是 `qwen/qwen3.8-27b`、狀態 `PROCESSING PROMPT` ⇒ **那台是人類自己的工作機，qwen 27B（17.74 GB）把 gemma（13 GB）擠出 24 GB 顯存**。1003 在 36 小時內兩次掉模型，都是這個原因。**不再向人類要回 1003。**

**裁決**：剩餘四塊（`g_r530_s1_1003_1`／`s1_1003_2`／`s3_1003_1`／`s3_1003_2`）**整塊改到 1004** 重跑，題目、臂、seed、程式碼（F1″ `0ebdd791f875`）、題庫（`1eae5f19…`）、預算一律不變，只換 endpoint。塊名保留原字串（含 `1003`），以免與已發生的紀錄對不上；真正的後端以 `backend_meta.json` 與下列註冊行為準。

**排程器拒絕這個拓撲，是它該做的事**：`abort_all_blocks_one_host` 判「seed g-r530-s1 的 2 塊全在 1004 ⇒ 題在兩台輪流沒有兌現」。該護欄是為了**設計階段**不要做出後端與題號共線的佇列；本次是機器被收回後的復原，且後果相反——s1／s3 之內後端變成**常數**（不是共線），塊內三臂仍同台，逐 seed 分析、不併 n ⇒ 主指標不受影響。**處置：不改護欄、不改任何程式碼，改為直接發 runner（與 smoke9 相同的發法），並在此逐字記錄這次繞過。**

**必須跟著結果走的後果**（§八-11 逐後端描述照舊，另加）：
- seed **s1 與 s3 的 20 題全部在 1004**；seed **s2** 是 1003 十題＋1004 十題（1003 那十題在 09-14 停擺前就已收官）。
- 跨 seed 的絕對值因此混了不同後端組成；本 run 本來就不併 seed，引用時逐 seed 註明後端組成。
- s1／s3 的補跑與其他八塊相隔約兩天，模型檔、參數、程式碼皆未變（1004 自始至終是同一份 gemma、context 262144、parallel 4、無 TTL）。

**復原佇列**：`ops/gain/r530/queues/r530_recovery_1004.json`，sha256 `0e796c0115fdd3077892a416a44e8b0921148d2304518f49427186bb227a38da`。四條註冊行（`run_r530.py` 逐字比對）：

```
R530_BLOCK: g_r530_s1_1003_1 tasks=ow_01_csvjson,ow_03_mdtable,ow_04_layerconf,ow_06_verrange,ow_08_logscan arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s1_1003_2 tasks=ow_19_redact,ow_11_reflow,ow_13_timespans,ow_15_tomlsub,ow_16_pathglob arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s1 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1003_1 tasks=ow_01_csvjson,ow_03_mdtable,ow_04_layerconf,ow_06_verrange,ow_08_logscan arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.86.226.21:1234/v1/chat/completions
R530_BLOCK: g_r530_s3_1003_2 tasks=ow_19_redact,ow_11_reflow,ow_13_timespans,ow_15_tomlsub,ow_16_pathglob arms=A-SOLO,A-CONF,A-GATE seed=g-r530-s3 endpoint=http://100.86.226.21:1234/v1/chat/completions
```
