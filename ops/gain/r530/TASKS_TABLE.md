# R530 題庫：20 題的目標敘述與契約（回填給預註冊 §一 的表）

⚠ **這一份不是正典，是待合併的材料。** 主工作樹那份
`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md` 由 Fable 合併，
題庫代理**沒有動過它**。本檔是 Fable 合併時要貼進 §一-2／§一-3 的內容。

實體題庫在 `ops/gain/r530/bank/<task_id>/`，六件東西一題不缺（§一-1）：
`goal.md`／`contract.md`／`tests_visible/`／`hidden/`／`rubric.md`／`meta.json`，
外加只給量具用、永不進工作區的 `reference/`（`solution.py` ＋ 三個已知壞樁）。
量具 `ops/gain/r530/gauge_r530.py --check`。

## 〇、一覽

| task_id | 層 | 可見 | 隱藏 | `ref_solution_lines` | 標題 |
|---|---|---|---|---|---|
| `ow_01_csvjson` | tight | 3 | 14 | 105 | CSV to JSON Lines with line-numbered failures |
| `ow_02_ratelimit` | tight | 3 | 15 | 39 | Per-caller sliding-window limiter with an injected clock |
| `ow_03_mdtable` | tight | 3 | 14 | 113 | Realign markdown tables by display width |
| `ow_04_layerconf` | tight | 3 | 15 | 70 | Three-layer settings with provenance |
| `ow_05_router` | tight | 3 | 15 | 80 | Path router with a deterministic specificity order |
| `ow_06_verrange` | tight | 3 | 14 | 61 | Version ordering and requirement specs |
| `ow_07_retrypolicy` | tight | 3 | 13 | 16 | Retry with injected sleep and a capped backoff |
| `ow_08_logscan` | tight | 3 | 14 | 64 | Per-endpoint log summary with nearest-rank percentiles |
| `ow_09_minitemplate` | tight | 3 | 13 | 87 | A very small template engine that fails loudly |
| `ow_10_dedupe` | tight | 3 | 13 | 30 | Deduplicate records with a choice of conflict policy |
| `ow_11_reflow` | tight | 3 | 14 | 92 | Reflow plain text to a display width |
| `ow_12_bytesize` | tight | 3 | 13 | 39 | Read and print human byte sizes in both bases |
| `ow_13_timespans` | tight | 3 | 13 | 59 | Merge and subtract half-open time spans |
| `ow_14_statemachine` | tight | 3 | 12 | 31 | A state machine that records the path it took |
| `ow_15_tomlsub` | tight | 3 | 13 | 200 | A small TOML-shaped format, read and written |
| `ow_16_pathglob` | tight | 3 | 13 | 66 | Path patterns with a double star and removals |
| `ow_17_diffpatch` | tight | 3 | 12 | 79 | Line diff and a patch that refuses to misapply |
| `ow_18_taskorder` | loose | 2 | 6 | 23 | An order to run jobs in (loose contract) |
| `ow_19_redact` | loose | 2 | 6 | 26 | Take the secrets out of a log line (loose contract) |
| `ow_20_slugify` | loose | 2 | 7 | 29 | URL slugs for a batch of titles (loose contract) |

**合計：20 題（tight 17、loose 3）、可見 57 條、隱藏 249 條。**

條數口徑（要和預註冊對齊）：預註冊 §一-2 凍結的是「可見 **3** 條」。
本題庫把它實作成**三個可見測試檔，一檔＝一條**，每檔內含數個 assert 打同一個需求的不同角度；
`meta.visible_n` 數的是檔數。loose 層是兩檔。隱藏條數＝`hidden/` 裡的檔數，**一檔一條**。

## 〇-1　難度擋門（§一-3b，發射前、零模型呼叫）

| 量 | 值 |
|---|---|
| `median(ref_solution_lines, 核心 12 題)` | 67.0 |
| `median(ref_solution_lines, 新 8 題)` | 45.0 |
| 相對差 | 0.328 |
| **D1（>40% ⇒ 紅）** | **綠** |
| **D2（tight hidden ≥10、loose ≥5）** | **綠**（新 8 題最小 hidden_n＝6，loose 三題 6／6／7）|

⚠ **給 Fable 的一句話**：D1 的「新 8 題」把 5 題 tight 與 3 題 loose 算在同一個中位數裡，
而 loose 三題的參考解**本來就短**（23／26／29 行，因為契約只釘進入點）。
只算新 tight 5 題的話中位數是 66.0、相對差 0.015。
兩個數字都落盤，判準照預註冊寫死的那一個（0.328，綠），**沒有事後換算法**。

`boundary_only_hidden_n` 逐題留 `null`：§一-3b 明寫由**不是作者的複核者**標，
作者自己標會讓那個量失去意義。

---

## 一、核心 12 題（預註冊 §一-2 已凍結；本節是逐字回填 ＋ 增補清單）

### `ow_01_csvjson`（tight）

> A client keeps a pile of CSV files that people edit by hand. They want to feed
> that data into another tool that only speaks JSON Lines, so they need a command
> that turns one CSV file into one JSON object per row.
> 
> Their files are messy in the ways hand-edited files are messy: fields containing
> commas, fields containing line breaks, quotes inside quoted fields, whole columns
> left blank, the same column name used twice, and line endings from whichever
> machine last touched the file. Some of the data is not ASCII and has to survive
> the trip unchanged.
> 
> When a file is broken they want to be told which line is broken, not to receive a
> stack trace. The command is going to be driven from a shell script, so success and
> failure have to be distinguishable without reading the output, and the converted
> data must not be polluted by chatter.

中文：把人手維護的 CSV 轉成 JSON Lines；壞行要指出行號而不是丟 traceback，退出碼要讓 shell 分得出成敗。

**契約**

## Library

    solution.csv_to_jsonl(text: str) -> str

- Returns JSON Lines: one JSON object per data row, each object on its own line,
  every line terminated by a newline, so the returned string ends with a newline.
- The first record of the input is the header. Every value in every object is a
  string. A field that is empty becomes `""`.
- When a header name repeats, the last occurrence wins.
- Quoting is the usual CSV convention: a field may be wrapped in double quotes;
  inside such a field a doubled `""` stands for one literal double quote, and
  commas and line breaks are ordinary characters.
- `"\n"` and `"\r\n"` are both accepted as line endings and neither survives into
  a parsed value.
- The input may or may not end with a final newline; that makes no difference to
  the output. A completely empty line is ignored.
- When there are no data rows the result is the empty string.
- Invalid input raises `ValueError` whose message starts with `line <N>: `, where
  `N` is the 1-based line number on which the offending record starts and the
  header is line 1. Invalid means: a record whose field count differs from the
  header, or an unclosed quote.

## Command line

    python -m solution FILE

- The file is read as UTF-8.
- On success the JSON Lines go to stdout and the exit code is 0. Nothing else is
  written to stdout.
- On invalid input exactly one line `line <N>: <reason>` is written to stderr and
  the exit code is 2. Nothing is written to stdout.

可見 **3** 條｜隱藏 **14** 條｜`ref_solution_lines` **105**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：CSV-to-JSON is a common exercise, but the graded semantics here are this project's own: last-wins on repeated header names, ValueError/stderr text pinned to `line <N>: ` with the header counted as line 1 and a quoted line break counted inside its own record, exit code 2 rather than 1, and stdout required to stay free of anything but data. A memorised generic converter does not satisfy those.

*相對預註冊 §一-2 的增補*：
- goal: added 'the same column name used twice', 'line endings from whichever machine last touched the file', 'Some of the data is not ASCII', 'success and failure have to be distinguishable without reading the output', 'must not be polluted by chatter' -- needed so that the prereg's own hidden list (repeated header / CRLF / UTF-8 / exit code / clean stdout) has a verbatim anchor, per prereg S5-2 gate 1.
- contract: library-level ValueError with the same 'line <N>: ' prefix as the CLI; blank lines ignored; empty result for zero data rows; quoting convention spelled out.

---

### `ow_02_ratelimit`（tight）

> A client's service gets hammered by bursts from the same callers. They want a
> piece of code they can put in front of it that says yes or no to each request,
> configured by how long a window is and how many calls are allowed in that window,
> counted separately per caller.
> 
> When it says no, the caller wants to know how long to wait before trying again,
> and that answer has to shrink as time passes rather than being a fixed guess.
> Being turned away repeatedly must not push the wait further out.
> 
> Their tests must not sleep, so the notion of now has to come from outside. The
> same test clock is sometimes rewound between cases, and it deals in fractions of
> a second, so neither of those may blow up.
> 
> They also want to wipe the record for one caller, or for everybody, without
> rebuilding the limiter, and they want a nonsensical configuration to fail at
> construction rather than at the first request.

中文：可設定時間窗與上限的 per-key 限流器；時鐘從外面餵，被擋時要能問還要等多久，而且那個數字要隨時間縮小。

**契約**

solution.RateLimiter(window_s: float, max_events: int, clock: Callable[[], float])
    .allow(key: str) -> bool
    .retry_after(key: str) -> float
    .reset(key: str | None = None) -> None

- `clock()` returns the current time in seconds as a float, and is the only
  source of time the limiter may use.
- The window slides: an event counts while it falls in `(now - window_s, now]`,
  left open and right closed.
- `allow(key)` returns True when the number of counted events for that key is
  below `max_events`, and records the event. A denied call records nothing, so
  being denied ten times in a row leaves the same state as being denied once.
- Events are counted per key; a key that has never been seen has no events.
- `retry_after(key)` returns `0.0` whenever the next `allow(key)` would succeed.
  Otherwise it returns `leaving + window_s - now`, where `leaving` is the
  earliest counted event that has to fall out of the window before the next call
  can be admitted. When `max_events` is 0 no wait ever helps, so `retry_after`
  returns `float("inf")`.
- `reset(key)` forgets the events of that key; `reset()` and `reset(None)` forget
  everything.
- A clock that moves backwards is not an error: events lying in the future are
  simply outside `(now - window_s, now]`.
- `window_s <= 0` or `max_events < 0` raises `ValueError` from the constructor.

可見 **3** 條｜隱藏 **15** 條｜`ref_solution_lines` **39**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Rate limiters are everywhere, but the combination graded here is this project's own: the window is left-open/right-closed so an event exactly window_s old has already left, retry_after is pinned to `leaving + window_s - now` rather than to the window length, max_events=0 returns infinity, denied calls record nothing, and a rewound clock is defined behaviour rather than an error. A remembered token-bucket implementation fails those.

*相對預註冊 §一-2 的增補*：
- goal: added 'that answer has to shrink', 'Being turned away repeatedly must not push the wait further out', 'The same test clock is sometimes rewound', 'it deals in fractions of a second', 'wipe the record for one caller, or for everybody', 'nonsensical configuration to fail at construction' -- anchors for the prereg's own hidden list (clock rewound / float boundary / repeated denial / reset / parameter checks), per prereg S5-2 gate 1.
- contract: pinned the exact retry_after formula, float('inf') for max_events=0, and the rewound-clock rule, which the prereg left open.

---

### `ow_03_mdtable`（tight）

> A client's markdown documents are full of tables whose columns do not line up,
> and some of the cells contain Chinese and Japanese text. They want one pass over
> a whole document that makes every table's columns line up when read in a plain
> text editor, and leaves everything that is not a table exactly as it was.
> 
> Their documents also contain pipe characters that are not column separators: some
> are escaped, some sit inside inline code, and some are inside fenced code blocks
> that happen to show a table. None of those may be treated as structure.
> 
> The tool is going to run in a pre-commit hook, so running it twice must produce
> the same file as running it once, and files saved on Windows must come back with
> the line endings they arrived with.
> 
> Their tables are also sloppy: some rows have more cells than the header, some
> cells are empty, and some rows are missing the pipes at the start and end. A
> document with no table in it at all must come back byte for byte.

中文：整份 markdown 的表格重新對齊（全形算兩欄）；非表格、圍欄內、逃逸與行內程式的管線一律不動，跑兩次要等於跑一次。

**契約**

solution.realign(text: str) -> str

- A column separator is a `|` that is neither preceded by a backslash nor inside a
  span delimited by backticks.
- A separator row is a row whose cells all match `:?-+:?`.
- A table is a run of consecutive lines whose first line contains a column
  separator and whose second line is a separator row; it ends at the first line
  that is blank or holds no column separator.
- Alignment is computed from display width: a character whose East Asian Width is
  Wide or Fullwidth counts as 2, every other character counts as 1.
- Every rendered row begins with `| ` and ends with ` |`, and neighbouring cells
  are joined by ` | `. Cell text is stripped of surrounding whitespace and then
  padded on the right to the column's width.
- A column's width is the widest of its non-separator cells, and never less than 3.
- A separator cell keeps the alignment markers it had -- `---`, `:---`, `---:` or
  `:---:` -- and its dashes are stretched or shortened so that the cell fills the
  column width.
- The number of columns is the largest cell count of any row in the table; shorter
  rows are padded with empty cells.
- Lines that are not part of a table are emitted unchanged, and so is every line
  inside a fenced code block opened by three backticks or three tildes.
- Each line keeps the line ending it arrived with, and the presence or absence of
  a final newline is unchanged.

可見 **3** 條｜隱藏 **14** 條｜`ref_solution_lines` **113**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Table formatters exist, but the graded semantics are this project's own: a minimum column width of 3, separator cells stretched to the column width while keeping their markers, the largest row deciding the column count, escaped pipes and backtick spans excluded from splitting by one shared scan, per-line ending preservation, and an explicit idempotence requirement. A memorised formatter written against a different convention fails those.

*相對預註冊 §一-2 的增補*：
- goal: added 'some are escaped', 'some sit inside inline code', 'inside fenced code blocks', 'running it twice must produce the same file', 'files saved on Windows', 'some rows have more cells than the header', 'some cells are empty', 'some rows are missing the pipes', 'no table in it at all' -- anchors for the prereg's own hidden list, per prereg S5-2 gate 1.
- contract: pinned the definition of a column separator, the minimum column width of 3, the largest-row column count, and per-line ending preservation, which the prereg left open.

---

### `ow_04_layerconf`（tight）

> A client's program takes settings from three places: values baked into the
> program, a settings file, and environment variables. They keep losing track of
> which one actually won, and things break when a number arrives as a string. They
> want something that hands back the final settings and can also answer, for any
> single setting, where that value came from.
> 
> Their settings file is grouped into sections and half of it is comments. Some of
> their values contain an equals sign. Sometimes there is no settings file at all.
> 
> Their deployment sets a pile of environment variables, most of which have nothing
> to do with this program, and the ones that do are spelled in capitals with
> underscores rather than in the dotted form the program uses.
> 
> A typo in a setting name should be ignored rather than quietly adding a setting
> nobody reads, and a value that cannot be turned into the right kind of thing must
> fail loudly rather than becoming a zero.

中文：三層設定合併（預設／檔案／環境變數）；要能回答某一項是誰給的，型別照預設值轉，打錯的 key 直接忽略。

**契約**

solution.load(defaults: dict, file_text: str | None, env: dict) -> Config
    Config.get(key: str) -> object
    Config.source(key: str) -> str            # "default" | "file" | "env"
    Config.as_dict() -> dict

- Precedence is env over file over default.
- `defaults` fixes both the set of keys and the type of each value. A key that is
  not in `defaults` is ignored wherever it appears and never shows up in
  `as_dict()`.
- `get` and `source` raise `KeyError` for a key that is not in `defaults`.
- File format: one `key = value` per line. A line whose first non-blank character
  is `#` is a comment and a blank line is nothing. A line of the form `[name]`
  opens a section, and every key after it becomes `name.key` until the next
  section header. A line that is neither of those and contains no `=` is ignored.
  The value is everything after the first `=`, with surrounding whitespace
  removed. `file_text` may be `None`, which means there is no file.
- Environment format: only names beginning with `APP_` are considered, and the
  name is matched without regard to case. After the prefix, `__` stands for `.`
  and the rest is lowercased, so `APP_DB__PORT` sets `db.port`.
- A value arriving from the file or the environment is converted to the type that
  key has in `defaults`: `bool`, `int`, `float` or `str`. A `bool` accepts
  `true`, `false`, `1`, `0`, `yes` and `no` without regard to case.
- A value that cannot be converted raises `ValueError`.

可見 **3** 條｜隱藏 **15** 條｜`ref_solution_lines` **70**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Layered configuration is a familiar shape, but the graded semantics are this project's own: defaults fix the key set and the types, provenance is a first-class query with three fixed labels, the env mapping is APP_ + __ + lowercase, booleans take six spellings, unknown keys are dropped rather than added, and unconvertible values raise. No library's defaults match that combination.

*相對預註冊 §一-2 的增補*：
- goal: added sections/comments, 'Some of their values contain an equals sign', 'Sometimes there is no settings file at all', 'most of which have nothing to do with this program', 'A typo in a setting name should be ignored', 'must fail loudly rather than becoming a zero' -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned KeyError from get/source, first-equals-sign splitting, lines with no '=' ignored, and that the environment prefix is matched case-insensitively.

---

### `ow_05_router`（tight）

> A client is writing a very small web framework and needs to take an incoming path
> and find which registered pattern it belongs to, pulling out the named pieces of
> the path along the way. Their problem is that a path often matches more than one
> pattern, and they want the same answer every time -- the more specific one.
> 
> The routes are registered by half a dozen modules that load in whatever order the
> importer happens to choose, so the answer must not depend on that order.
> 
> They also want a pattern that swallows the rest of the path for serving files,
> and they want a mistake in a pattern to be reported when the route is registered
> rather than on the first request that hits it.
> 
> A path that belongs to nobody has to be distinguishable from a path that matched
> with no named pieces.

中文：路徑樣板比對器；多重命中時由「最左邊第一個不同的段」決定勝負，註冊順序不得影響結果，壞樣板在 add 就丟。

**契約**

solution.Router()
    .add(pattern: str, name: str) -> None
    .match(path: str) -> tuple[str, dict[str, str]] | None

- A pattern begins with `/` and is read as segments split on `/`. A segment is
  one of three things: a literal, `{name}`, or `{name:*}`.
- `{name}` matches exactly one segment, never spans a `/`, and never matches an
  empty segment.
- `{name:*}` matches the whole remainder of the path, may contain `/`, must not be
  empty, and may only appear as the last segment.
- `match` returns the name of the winning pattern together with a dict mapping
  each parameter name to the text it captured, or `None` when nothing matches. A
  pattern with no parameters returns an empty dict.
- When more than one pattern matches, specificity decides. Rank the segments
  literal, then `{name}`, then `{name:*}`, and compare the two patterns segment by
  segment from the left: the first position at which they differ picks the winner.
  If neither differs anywhere they both reach, the pattern with more segments
  wins.
- Two patterns that differ only in their parameter names are the same pattern.
  Registering the second one raises `ValueError` from `add`.
- A pattern that does not begin with `/`, a segment holding an unmatched brace or
  an empty parameter name, and a `{name:*}` that is not last all raise
  `ValueError` from `add`.
- Paths handed to `match` always begin with `/`.

可見 **3** 條｜隱藏 **15** 條｜`ref_solution_lines` **80**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Every web framework routes paths, but none of them ranks routes the way this contract does: three segment ranks compared left to right with the first difference deciding, patterns differing only in parameter names treated as the same pattern and rejected at registration, a non-empty rest-of-path capture allowed only in last position, and an empty dict required to be distinguishable from no match. A remembered framework router disagrees on at least the duplicate rule.

*相對預註冊 §一-2 的增補*：
- goal: added the import-order sentence, the rest-of-path sentence, 'reported when the route is registered', and the None-versus-empty-dict sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned what counts as malformed (no leading slash, unmatched brace, empty parameter name), that a capture must be non-empty, and that parameter names do not distinguish two patterns.

---

### `ow_06_verrange`（tight）

> A client stores version strings and needs to answer two questions: given two
> versions, which is newer; and given a version and a requirement written the way
> people write requirements, does it satisfy that requirement. They have been burned
> by "1.10" sorting before "1.9" and by pre-release builds being treated as newer
> than the real thing.
> 
> Two pre-releases of the same version also have to sort among themselves: rc.2
> comes after rc.1, alpha comes before beta, and a pre-release with more parts is
> newer than the same pre-release with fewer.
> 
> Their requirements arrive as one line holding several conditions separated by
> commas, sometimes with spaces around them, and every condition has to hold.
> 
> A version string or a requirement they cannot make sense of has to be rejected
> rather than guessed at, because a silent guess is how a bad build shipped last
> time.

中文：版本比較與範圍判定；1.10 > 1.9、pre-release 排在正式版之前、rc.10 > rc.2，讀不懂的字串一律拒收不猜。

**契約**

solution.compare(a: str, b: str) -> int        # -1, 0 or 1
    solution.satisfies(version: str, spec: str) -> bool

- A version is `MAJOR.MINOR.PATCH`, each a run of digits, optionally followed by
  `-` and a pre-release made of dot-separated identifiers drawn from letters,
  digits and hyphens. Nothing else is a version.
- `compare(a, b)` returns `-1` when `a` is older, `0` when they are the same
  version and `1` when `a` is newer. It returns exactly those three values.
- The three numbers are compared as numbers, most significant first.
- A version carrying a pre-release is older than the same version without one.
- Two pre-releases are compared identifier by identifier: an identifier made only
  of digits is compared by value, any other identifier is compared by ASCII, and
  an all-digit identifier is older than one that is not. If every shared
  identifier is equal, the pre-release with more identifiers is the newer one.
- A spec is one or more conditions separated by `,`. Surrounding whitespace on a
  condition is not part of it. Every condition has to hold for `satisfies` to
  return True.
- A condition is one of `>=`, `>`, `<=`, `<`, `==`, `!=` followed by a version.
- A version that does not fit the shape above, a spec with an empty condition, and
  a condition with an unrecognised operator all raise `ValueError`.

可見 **3** 條｜隱藏 **14** 條｜`ref_solution_lines` **61**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Version comparison resembles semver, but this contract is not semver: build metadata does not exist here, compare returns exactly -1/0/1 rather than a rich object, the spec language is a comma list of six operators with no tilde or caret, and malformed input raises rather than being coerced. A remembered semver implementation accepts strings this contract must reject.

*相對預註冊 §一-2 的增補*：
- goal: added the pre-release ordering sentence (rc.2/alpha/more parts), the comma-and-spaces sentence, and the reject-rather-than-guess sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned that an all-digit identifier is older than a textual one, that a longer pre-release with an equal prefix is newer, and what exactly raises ValueError.

---

### `ow_07_retrypolicy`（tight）

> A client's code calls things that fail intermittently. They want a helper that
> re-runs a call a few times before giving up, backing off longer each time, but
> only for the kinds of failure that are worth retrying. Their tests must run
> instantly, so waiting has to be something they can substitute.
> 
> A failure that is not worth retrying has to come straight back out, immediately,
> with no pause at all. A subclass of a listed error counts as that error.
> 
> When the last attempt fails they want the original error, not something the helper
> wrapped around it, and they do not want to sit through a pause that leads nowhere.
> 
> The delay must stop growing once it reaches a ceiling they set, because doubling
> forever is how one of their jobs slept for an hour. Asking for fewer than one
> attempt is a programming mistake and should be caught before anything is called.

中文：可注入 sleep 的重試策略；退避序列釘死、最後一次失敗不睡、原例外不包裝、不在清單裡的例外立刻往外拋。

**契約**

solution.retry(fn, *, attempts: int, backoff_s: float, max_backoff_s: float,
                   retry_on: tuple[type[BaseException], ...],
                   sleep: Callable[[float], None]) -> Any

- `fn` takes no arguments. `retry` returns the value of the first call that
  returns.
- `fn` is called at most `attempts` times.
- After the k-th failure, counting from 1, the helper waits
  `min(backoff_s * 2 ** (k - 1), max_backoff_s)` seconds by calling `sleep` with
  that number.
- After the final failure there is no wait; the exception `fn` raised is raised
  onward, the same object, not wrapped in anything.
- An exception that is not an instance of any type in `retry_on` is raised onward
  at once: no further call, no wait. An empty `retry_on` therefore retries
  nothing.
- `attempts < 1` raises `ValueError` before `fn` is called.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **16**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Retry helpers are common, but the graded semantics here are this project's own: the delay sequence is pinned to min(backoff_s * 2**(k-1), max_backoff_s) with the first wait undoubled, there is deliberately no wait after the final failure, the original exception object must survive unwrapped, an empty retry_on must retry nothing, and the attempts check must fire before the first call. Libraries such as tenacity differ on at least the trailing-sleep and wrapping points.

*相對預註冊 §一-2 的增補*：
- goal: added 'come straight back out, immediately, with no pause at all', 'A subclass of a listed error counts', 'not something the helper wrapped', 'a pause that leads nowhere', the ceiling sentence and the attempts sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned that retry returns the first successful value and that an empty retry_on retries nothing.

---

### `ow_08_logscan`（tight）

> A client has a text log written by their own service and wants to know, per
> endpoint, how many requests there were, what share of them failed, and how slow
> the slow ones are. The log is machine-written but not clean: some lines are
> truncated or garbled, and those must not stop the run.
> 
> Failed means the server's own fault, the five-hundreds; a client sending a bad
> request is not a failure of theirs. Their idea of slow is the ordinary middle and
> the unlucky tail.
> 
> They want the busiest endpoints at the top, and when two are equally busy they
> want the order to be the same every time they run it.
> 
> They also want to know how many lines were unusable, because a sudden jump in that
> number is their signal that something upstream changed. Blank lines are just noise
> from the rotation script and should not count as anything at all.
> 
> Finally they want to eyeball a file from the shell without writing a script.

中文：log 彙總（每 endpoint 筆數、五百錯誤率、nearest-rank 分位）；壞行只計數不中斷，空行完全不算。

**契約**

## Library

    solution.summarize(lines: Iterable[str]) -> dict

A log line is `<ISO8601> <METHOD> <PATH> <STATUS> <MS>`, the five fields separated
by one space each. Any trailing newline is not part of the line.

The result has exactly this shape:

    {"endpoints": [{"path": str, "n": int, "error_rate": float,
                    "p50_ms": int, "p95_ms": int}, ...],
     "bad_lines": int, "total": int}

- `error_rate` is the share of that endpoint's requests whose status is 500 or
  more, rounded to four decimal places.
- Percentiles are nearest-rank: the p-th percentile of n sorted values is the one
  at 1-based position `ceil(p / 100 * n)`.
- `endpoints` is ordered by `n` from large to small, and endpoints with the same
  `n` are ordered by `path` in ordinary string order.
- A line is bad when it does not have exactly five fields, when `STATUS` or `MS` is
  not a run of digits with an optional leading `-`, or when the timestamp is not
  ISO8601. A timestamp counts as ISO8601 when
  `datetime.datetime.fromisoformat` accepts it, after a trailing `Z` has been
  replaced by `+00:00`.
- `total` counts every line that was looked at, good and bad together. A line that
  is empty or only whitespace is not looked at: it is neither good nor bad and is
  not in `total`.
- `bad_lines` counts the bad ones. A bad line never stops the run.

## Command line

    python -m solution FILE

Prints a table a person can read. Nothing about its layout is checked.

可見 **3** 條｜隱藏 **14** 條｜`ref_solution_lines` **64**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Log summarising is a stock exercise, but the graded semantics are this project's own: the output schema is pinned key by key, percentiles are nearest-rank rather than the interpolated default of numpy or statistics, the error share is five-hundreds only and rounded to four places, ties are broken by path, blank lines are excluded from the total while bad lines are counted in it. A memorised summariser disagrees on the percentile definition alone.

*相對預註冊 §一-2 的增補*：
- goal: added the five-hundreds sentence, the busiest-first and stable-tie sentences, the unusable-lines sentence, and the blank-lines sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned what counts as an ISO8601 timestamp (fromisoformat after Z substitution), the integer field shape, that total includes bad lines, and that blank lines are outside the count.

---

### `ow_09_minitemplate`（tight）

> A client wants to fill values into text without pulling in a template library.
> They need placeholders that can reach into nested data, a way to repeat a block of
> text once per item in a list, and a loud failure when the text asks for something
> the data does not have -- silently producing an empty string is what bit them last
> time.
> 
> Inside a repeated block they need both the item itself and its fields, and they
> still need to reach the values that live outside the block. An empty list should
> leave nothing behind.
> 
> They want to be able to leave a note in the template that does not appear in the
> output, and their templates sometimes have to print two literal braces, so there
> has to be a way to say that too.
> 
> A template that is malformed -- a placeholder that is never closed, a repeat
> inside a repeat, a repeat over something that is not a list, a closing repeat with
> nothing to close -- is a mistake in the template and must be reported as one,
> rather than rendered as best it can.

中文：極小樣板引擎（巢狀取值、重複區塊、註解、逃逸）；缺 key 要丟 KeyError 而不是靜靜給空字串。

**契約**

solution.render(template: str, data: dict) -> str

- `{{name}}` is replaced by the value `name` holds in `data`, converted with
  `str()`. `{{a.b.c}}` walks into nested dictionaries. Whitespace just inside the
  braces is not part of the name.
- `{{#each items}} ... {{/each}}` renders what is between the tags once per element
  of the list `items`. Inside the block, `{{.}}` is the element itself and
  `{{.field}}` is a field of it; names that do not begin with `.` are still looked
  up in `data`.
- `{{! anything }}` is a comment and renders as nothing.
- `\{{` renders as a literal `{{` and starts no placeholder.
- A name the data does not have raises `KeyError` whose single argument is the
  placeholder's name exactly as it was written.
- `ValueError` is raised for: a `{{` with no `}}` after it; an empty placeholder; a
  `{{#each}}` inside another `{{#each}}`; a `{{#each}}` that is never closed; a
  `{{/each}}` with no `{{#each}}` open; a `{{#each}}` over something that is not a
  list; and `{{.}}` or `{{.field}}` outside any block.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **87**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：The tag spelling is borrowed from Mustache-like engines on purpose, but the graded semantics are the opposite of theirs: a missing key must raise rather than render empty, nesting an each block is forbidden rather than supported, an each over a non-list is an error rather than an iteration, and the escape is a backslash rather than a triple brace. A memorised Mustache implementation fails most of these hidden checks.

*相對預註冊 §一-2 的增補*：
- goal: added the outer-names sentence, the empty-list sentence, the comment sentence, the literal-braces sentence and the four malformed-template cases -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned the KeyError argument as the placeholder name as written, whitespace trimming inside braces, and the complete list of ValueError cases.

---

### `ow_10_dedupe`（tight）

> A client merges record lists that arrive from several places and the same thing
> shows up more than once. They want one list back, in the order things first
> appeared, and they want to choose what happens when two copies disagree: keep the
> first, keep the last, or take whichever fields are actually filled in. A field
> that is present but empty of meaning counts as not filled in.
> 
> Sometimes one field is not enough to say that two records are the same thing, so
> they need to be able to name several, and two records that agree on only one of
> them are not the same thing.
> 
> A record that does not carry the field they are keying on is a data problem they
> want to hear about, not something to skip quietly. Asking for a way of resolving
> disagreements that does not exist is a programming mistake and should say so.
> 
> They pass the same lists on to other code afterwards, so nothing they handed in
> may come back changed.

中文：依 key 去重並保留首次出現順序；衝突策略三選一，None 算「沒填」，缺 key 要吵，輸入的 dict 一個都不准動。

**契約**

solution.dedupe(records: list[dict], key: str | list[str],
                    policy: str = "first") -> list[dict]

- The result holds one record per distinct key value, in the order each key value
  first appeared in `records`.
- `key` is a field name, or a list of field names making a composite key whose
  parts are compared in the order given.
- `policy` is one of:
  - `"first"` -- the earliest copy's values are kept;
  - `"last"` -- the latest copy's values are kept;
  - `"merge"` -- field by field, the value of the last copy that both has the
    field and whose value is not `None`.
- The default is `"first"`.
- A record that has no such field raises `KeyError` whose argument is the name of
  the missing field.
- A `policy` outside those three raises `ValueError`.
- No dictionary passed in is modified, and every dictionary in the result is a new
  object, not one of the inputs.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **30**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Deduplication is a stock operation, but this contract pins choices no library shares: three named policies with merge defined as last-non-None per field, composite keys compared part by part rather than as a joined string, a missing key field raising KeyError rather than being skipped, and a hard requirement that no input dictionary is aliased or mutated. pandas drop_duplicates and the usual set-based recipe both fail several of these.

*相對預註冊 §一-2 的增補*：
- goal: added 'empty of meaning counts as not filled in', the composite-key sentences, the loud-KeyError sentence, the bad-policy sentence and the do-not-mutate sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned that 'last' replaces the record wholesale, that the KeyError argument is the field name, and that result dictionaries are new objects.

---

### `ow_11_reflow`（tight）

> A client writes notes in plain text and wants them wrapped to a fixed width for
> reading in a terminal. Their notes have indented blocks, bullet lists whose
> continuation lines should line up under the text and not under the bullet, code
> fenced off with backticks that must not be touched, and a lot of Chinese.
> 
> Chinese takes two columns per character in their terminal, and unlike English it
> can be broken between any two characters without a space appearing at the break.
> 
> Blank lines are how they separate thoughts, so however many there were is however
> many they want back. Each bullet in a list is its own thought and must not be
> glued onto the one above it.
> 
> Now and then a note contains something with no spaces in it that is simply longer
> than the width -- a URL, a long path -- and they would rather it stick out than be
> chopped in half. A width that makes no sense should be refused.

中文：純文字重排（顯示寬度、縮排、項目符號續行、圍欄不動）；中文可在任意兩字之間斷行，過長的字寧可凸出去。

**契約**

solution.reflow(text: str, width: int) -> str

- Width is display width: a character whose East Asian Width is Wide or Fullwidth
  counts as 2, every other character counts as 1.
- A blank line is a line holding nothing but whitespace. It is emitted as an empty
  line, and a run of blank lines keeps its length.
- A paragraph is a run of consecutive non-blank lines. A line whose first non-blank
  characters are a bullet marker -- `- `, `* `, or digits followed by `. ` --
  starts a new paragraph.
- Within a paragraph, runs of spaces and tabs separate words and are replaced by a
  single space.
- The first line of a paragraph keeps the indentation it had. Continuation lines
  repeat that indentation, except in a bullet paragraph, where they are indented to
  the first character after the marker.
- Lines are filled greedily up to `width` columns, counting the indentation.
- A break may fall between any two characters when at least one of them is wide,
  and no space is inserted at such a break.
- A piece that does not fit even on a line of its own is not split: it takes a line
  of its own and overflows it.
- No output line ends in a space.
- Everything inside a fenced code block opened and closed by three backticks is
  emitted unchanged, and so are the fence lines themselves.
- The presence or absence of a final newline is unchanged.
- `width <= 0` raises `ValueError`.

可見 **3** 條｜隱藏 **14** 條｜`ref_solution_lines` **92**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：textwrap exists, but it counts characters rather than columns, has no notion of a wide character being its own breakable piece, hangs nothing under a bullet marker, knows nothing about fenced blocks, and collapses blank runs. This contract requires all five, so a wrapper recalled from textwrap's behaviour fails the hidden checks.

*相對預註冊 §一-2 的增補*：
- goal: added the two-columns sentence, the break-between-characters sentence, the blank-run sentence, the each-bullet sentence, the long-run sentence and the bad-width sentence -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned greedy filling, that no output line ends in a space, the whitespace-collapse rule, and the final-newline rule.

---

### `ow_12_bytesize`（tight）

> A client's config files and log lines are full of sizes written the way humans
> write them, and elsewhere the same sizes are printed back out for humans to read.
> They keep getting bitten by the two meanings of "KB" and by numbers that come back
> out different from the way they went in.
> 
> People write the unit in whatever case they feel like, and sometimes leave a space
> before it and sometimes not. A size with no unit at all is a count of bytes.
> 
> They want the printed form to keep one decimal place even when it is a round
> number, except for plain bytes, which are whole things and should look like it.
> Sizes larger than the biggest unit they use should still print, rather than
> falling back to a bare byte count.
> 
> A fractional byte count is not a thing, so the fraction is dropped rather than
> rounded up. Anything they cannot read has to be refused rather than guessed at: an
> empty setting, a unit nobody has heard of, two units in one string, a negative
> size.

中文：容量字串解析與反向輸出；KiB／KB 兩種進位分清楚，小數向零截斷，印出來固定一位小數但純位元組不帶小數。

**契約**

solution.to_bytes(s: str) -> int
    solution.humanize(n: int, *, binary: bool = True) -> str

- `to_bytes` reads strings such as `"1.5 KiB"`, `"10MB"`, `"512"` and `"3 b"`.
  Surrounding whitespace is ignored, and any amount of whitespace may sit between
  the number and the unit, including none.
- The number is one or more digits with at most one dot and at least one digit
  after it if the dot is there. Nothing else is a number.
- Units are matched without regard to case. `KiB`, `MiB`, `GiB` and `TiB` step by
  1024; `KB`, `MB`, `GB` and `TB` step by 1000; `B` or no unit at all means bytes.
- The result is the number multiplied by the unit's step, with the fraction
  dropped -- truncated toward zero, never rounded up.
- `humanize` returns the number, one space, and the unit. It uses the 1024 units
  when `binary` is true and the 1000 units otherwise.
- The unit chosen is the largest one that leaves the number below the step, except
  that `TiB` and `TB` are the largest units there are: above them the number simply
  keeps growing.
- The number is printed to one decimal place, keeping a trailing `.0`. When the
  size is below one step it is printed as a whole number of bytes with the unit
  `B`, so `512` gives `"512 B"` and `1024` gives `"1.0 KiB"`.
- `ValueError` is raised for an empty string, a string that is not a number
  followed by an optional unit, an unrecognised unit, more than one unit, and a
  negative size given to either function.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **39**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Size formatting is a stock snippet, but the graded semantics here are this project's own: truncation toward zero rather than rounding, exactly one decimal place with the trailing zero kept, a decimal-free integer form below one step, TiB/TB as hard ceilings that then overflow numerically, and an explicit refusal list. The common humanize recipes round and drop trailing zeros, so they fail these checks.

*相對預註冊 §一-2 的增補*：
- goal: added the case sentence, the optional-space sentence, the no-unit sentence, the trailing-.0 sentence, the above-the-largest-unit sentence, the drop-the-fraction sentence and the refusal list -- anchors for the prereg's hidden list, per prereg S5-2 gate 1.
- contract: pinned the number grammar (no exponent notation), that TiB/TB are the largest units, and that a negative size is refused by both functions.

*已知量具弱點*：to_bytes is checked only on values whose product is exact in binary floating point; a Decimal-based and a float-based implementation can differ in the last unit on inputs such as '0.7 KB', and that difference is deliberately not graded.

---

---

## 二、擴充集：新 5 題 tight（§一-3）

### `ow_13_timespans`（tight）

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

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **59**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Interval arithmetic is a textbook exercise, but the contract combination is this project's own: half-open spans so touching periods join, zero-length spans dropped rather than kept, two input instant shapes normalised to one output shape, a union-based total rather than a sum, and a reversed span raising instead of being swapped. Libraries such as portion default to closed intervals and would fail the touching and zero-length checks.

*題型分散說明*：Chosen to be unlike the frozen twelve: this is the only task about ordered arithmetic over intervals.

---

### `ow_14_statemachine`（tight）

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

可見 **3** 條｜隱藏 **12** 條｜`ref_solution_lines` **31**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：State machines are a stock exercise, but this contract pins choices the common libraries do not share: a refused event raises and leaves the history untouched, a self-transition is recorded, the history is copied on the way out, reset clears the record as well as the state, and the rules are validated at construction rather than on first use. transitions and the usual dictionary recipe both differ on at least two of those.

*題型分散說明*：Chosen to be unlike the frozen twelve: the only task whose subject is a stateful object whose past is part of the contract.

---

### `ow_15_tomlsub`（tight）

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
- `dumps` raises `ValueError` for data it cannot write: a value of some other type,
  a list whose items are not all the same kind, a list inside a list, or a name
  outside the allowed characters.
- `parse(dumps(x))` gives back `x`, and `dumps(parse(dumps(x)))` gives back the
  same text.

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **200**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：The syntax is deliberately TOML-shaped, but this is a strict subset with its own rules: only four escapes, no nested lists, no inline tables, no dates, lists required to be of one kind, headings forbidden from reopening, and a canonical name-ordered writer with a text-level round-trip guarantee. Python's tomllib parses a superset and has no writer at all, so a remembered TOML implementation fails the duplicate, ordering and round-trip checks.

*題型分散說明*：Chosen to be unlike ow_04_layerconf: that task is about layering and provenance over an ini-like file, this one is about literal typing, nesting, line-numbered errors and a canonical writer.

---

### `ow_16_pathglob`（tight）

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

可見 **3** 條｜隱藏 **13** 條｜`ref_solution_lines` **66**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Globbing is familiar, but Python's fnmatch lets a star cross a separator and knows nothing about a double star, pathlib's match anchors from the right rather than the whole path, and gitignore semantics are directory-relative rather than whole-path. This contract is whole-path, one-level stars, zero-or-more double stars, and an ordered add/remove pass over a given file list. A remembered implementation of any of the three fails several hidden checks.

*題型分散說明*：Chosen to be unlike ow_05_router: that task ranks competing patterns by specificity and extracts named pieces; this one is set selection with wildcards and negation, and never ranks anything.

---

### `ow_17_diffpatch`（tight）

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

可見 **3** 條｜隱藏 **12** 條｜`ref_solution_lines` **79**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Diffing is a classic, but the shape graded here is this project's own: pieces are dicts with exactly start/old/new rather than unified-diff text, there is no context, pieces are required to be trimmed on both sides and separated by an unchanged line, and apply is required to verify, to refuse out-of-order and overlapping pieces, and to leave its arguments alone. difflib produces opcodes and SequenceMatcher-based recipes do not validate on apply, so a remembered solution fails the refusal checks.

*題型分散說明*：Chosen to be unlike the frozen twelve: the only task with a two-way invariant (out and back) between a producer and a consumer written by the same worker.

---

---

## 三、負向對照層：3 題 loose（Fable 裁決 2026-09-13）

這三題的契約**只給進入點與回傳型別**，目標敘述改成「用途 ＋ 幾條必須成立的性質」，
隱藏驗收只考目標明講的性質。質化評分表另有一份 loose 版：
`structure` 與 `fit_to_goal` **雙倍權重**，因為這一層存在的理由就是看設計合不合理。

### `ow_18_taskorder`（loose）

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

可見 **2** 條｜隱藏 **6** 條｜`ref_solution_lines` **23**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Topological sorting is textbook and graphlib.TopologicalSorter exists, which is the point: this task deliberately grades only the properties the goal states, so a worker who reaches for the library and one who writes Kahn's algorithm can both score full marks quantitatively and be separated only by the qualitative reading. Nothing here is a trick the library gets wrong.

*loose 層說明*：The contract fixes the entry point, the argument shape and the return type only. Every hidden check tests a property the goal states in words; nothing about the chosen order among the valid ones is graded.

---

### `ow_19_redact`（loose）

> A client is about to start posting their application logs into a shared channel and
> needs the secrets taken out of each line first. They know roughly what their secrets
> look like and gave three real examples from yesterday's log:
> 
>     AKIAIOSFODNN7EXAMPLE
>     Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.abcdef
>     postgres://svc:hunter2@db.internal:5432/app
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

可見 **2** 條｜隱藏 **6** 條｜`ref_solution_lines` **26**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Secret scanners exist, but nothing here depends on matching one: the only things graded are the properties the goal states, using three examples the client supplied. Two workers with completely different pattern sets can both score full marks quantitatively, which is the point of the loose stratum.

*loose 層說明*：The contract fixes two entry points and their return types only. The mask text, the contents of the findings list and the pattern set are all design decisions and none of them is graded.

*已知量具弱點*：The hidden checks use fresh instances of the three shapes the goal names. A worker who matches those three shapes exactly will pass; a worker who writes a broader scanner will also pass. The checks cannot distinguish a general solution from a narrow one, and no claim of generality may be made from them.

---

### `ow_20_slugify`（loose）

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
>   slug rather than an empty one.
> 
> How a title is turned into a slug, and what a collision is resolved with, is up to
> whoever writes it.

中文：（契約鬆）整批標題轉 URL slug；目標只講六條性質（同序、字元集、連字號規則、批內不重複、同批同結果、非拉丁也要有得用）。

**契約**

solution.slugify(titles: list[str]) -> list[str]

- `slugify` takes the batch of titles and returns a list of strings.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; the transliteration rules and the collision suffix are design decisions.

可見 **2** 條｜隱藏 **7** 條｜`ref_solution_lines` **29**｜`origin: authored 2026-09-13`

*為什麼不是現成題*：Slugify is one of the most copied snippets there is, which is exactly why it is here: the graded properties are batch-level (uniqueness within the batch, determinism across calls, a non-empty answer for a non-Latin title) rather than per-title, and the common snippet handles none of the three. Two workers can still solve it in completely different ways and both score full marks quantitatively.

*loose 層說明*：The contract fixes the entry point and the return type only. The transliteration rule, the collision suffix and the fallback for a non-Latin title are design decisions and none of them is graded directly.

---

## 四、還沒做、必須由別人做的事

1. **§五-2 的公平性複核**（複核者不得是作者）。本量具只驗到
   「每一條隱藏驗收的 `# anchor:` 在 `goal.md`／`contract.md` 裡逐字找得到」，
   **驗不到反向那一條**（目標裡每句客戶困擾都要有驗收對應），也驗不到覆蓋的完備性。
2. **`boundary_only_hidden_n` 逐條標記**（同上，複核者做）。
3. **AMEND1 的 sha256 釘死**：`meta.json` 已逐檔落 sha256，但那是自己算自己的；
   釘進修訂案、由發射器與 analyzer 比對，是 Fable 那一步。
4. **ow_01／ow_02 有兩個版本**：基建代理的 worktree 已各寫過一版示範題，措辭與本庫不同。
   兩邊都跑得起來，但**不能同時存在**，要 Fable 指定留哪一份。
