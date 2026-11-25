# NOTE 2026-11-25 — 契約路徑的三種回饋模式在程式題上的實際行為

範圍：`vacant do --contract … --feedback-mode {none,generic,localized}`，程式碼版本 rc6-final（`release/0.9.2-prep` `b1ca9b1ff`，wheel `a575c661…`）。
依據：讀程式碼（`vacant_network/adapters/run.py` 的 `do()`、`adapters/hook.py`、`trace/stopcheck.py`），以及一次用假 agent、不接模型的試跑（L-fake）。
這份只記事實，不做建議。

## L-fake 怎麼跑的

- 題目：polyglot_py 的 `pg_proverb`，工作區照原樣複製；任務提示用題目自己的 `instruction.txt`。
- 契約：機械產生。
  - 繳付物是 `proverb.py`；`proverb_test.py` 釘成契約輸入。
  - 一條 `command` 主張：先把釘住的測試檔複製進成果副本，再跑 `python3 -m unittest -q proverb_test`。
  - `attempts.max` 是 3，每次嘗試的上限 600 秒。
- 假 agent：每次都寫同一個錯的 `proverb.py`（少了最後一句 "And all for the want of a …"），並把收到的提示逐字存下。
- 三種模式各跑一次，每次都用完 3 次嘗試，裁決都是 reject。
- 程式與逐字提示：[`ops/redo/results/rfh4_lfake/`](../../ops/redo/results/rfh4_lfake/)。
  - `code/trial.py` 用 rc6-final 的 venv 以 `python -I` 執行。
  - `prompts/<模式>/prompt_<n>.txt` 是第 n 次嘗試收到的提示。
- 第一次試跑時測試檔沒有釘成輸入：`command` 在只含繳付物的成果副本裡執行，找不到測試模組。上面的提示來自修正後的那一次。

## 三種模式實際差在哪裡

| | none | generic | localized |
|---|---|---|---|
| 第 2、3 次的工作區 | 新的乾淨工作區（`run.py` 的 `ws{i}`），上一次的檔不留 | 同一個工作區，接著上一次的檔 | 同一個工作區，接著上一次的檔 |
| 第 2、3 次的提示 | 只有原提示 | 原提示＋驗收摘要（`hookpolicy.feedback_text`） | 原提示＋追緝文字（`stopcheck.localize` 的 text）；沒有追緝文字時退回 generic |
| 工作階段內的 stop 掛鉤回饋（契約路徑預設掛掛鉤） | 關（`hook.py`：`VACANT_FEEDBACK_MODE == "none"` 時不做） | 開，用驗收摘要 | 開，用追緝 |

所以 none 和另兩種同時差三件事：提示、工作區是否接續、工作階段內退回。generic 和 localized 之間只差回饋的種類。

## L-fake 第 2 次嘗試收到的文字

第 3 次與第 2 次相同；localized 第 3 次只是在每條後面多了 `(still open)`。

- none（102 位元組）：只有原提示。
- generic（876 位元組）：原提示後面接驗收摘要。內容依序是：
  - 失敗的測試名稱；
  - traceback 指到 `proverb_test.py` 第 79 行；
  - `AssertionError: Lists differ: [] != ['And all for the want of a horseshoe nail.']`；
  - 截在 `'And all fo`；
  - 結尾一句 `Run \`vacant check\` to re-check before finishing.`
- localized（865 位元組）：原提示後面接兩條，每條的內容是：
  - `tests: FAIL — proverb_test.py:79 says "self.assertEqual("`（第二條是 `:29`）；
  - `check says:`，接著是截短的測試輸出，到失敗測試名稱的一半就斷掉；
  - `the same value is in proverb_test.py line 19 (the given input)`。
  
  localized 的文字裡沒有 `AssertionError` 那一行。

## localized 在程式題上為什麼退化

- 追緝的比對對象，是「成果裡的值」對照「契約輸入裡的值」：
  - `blame_results` 找成果裡哪個檔、哪一行寫了什麼，再查同樣的值出現在哪個輸入、第一次出現在第幾步。
  - 設計上適用的是資料型主張：成果（報告）裡的數值或引文要能對回輸入。例如 `csv_total` 會照輸入重算報告裡的總數，回饋就能寫成「`report.md:1 says "999"`，expected 60」。
  - 見 `tests/test_trace_do.py`。
- 單檔解答加 unittest 的題目，主張是「一個指令的結束碼」，成果裡沒有可以對照輸入的值。
  - 追緝拿測試輸出裡的字串去比對，結果把「位置」指進受保護的測試檔（`proverb_test.py:79`）。
  - 它又在測試檔的另一行找到同樣的字串，寫成「the given input」。
  - 每條都附上截短的測試輸出，結果字數和 generic 差不多，卻少了斷言的期望值。
- 但書：假 agent 沒有載掛鉤，所以病歷裡沒有工具步驟。真的 pi 會載掛鉤，回饋可能多一句「第幾步第一次出現」，但比對對象不變。

## 契約路徑的其他事實

- **不寫回專案**：交件留在 `$VACANT_WORK` 的 run 目錄，要 `vacant release` 才會出去；`vacant do` 結束時只印出工作區路徑。
  - `--in-place` 會直接在專案裡改，但這時 `none` 模式被拒絕（`feedback_mode=none re-draws from a clean workspace; not with --in-place`）。
- **交的是最後一次嘗試**。零設定重開與 harness R3 的規則不同：交第一個通過的；都沒過，交原件測試過最多的。
- **時限**：
  - 契約路徑沒有「單次」與「總共」之分（`--attempt-timeout` 只用在無契約時），`--timeout` 是每次嘗試的上限。
  - 一次嘗試提早結束，剩下的時間不會給下一次。
  - 逾時的嘗試照樣用工作區當時的內容驗收，算一次嘗試。
- **重試條件**：只有必要主張是 FAIL 才重試；主張是 UNKNOWN（例如驗收指令自己逾時）就停。
- **成果與判定**：
  - 成果只含繳付物。
  - 測試檔要釘成契約輸入，`command` 執行時才會複製進成果副本，所以 agent 改了工作區裡的測試檔，影響不到判定。
  - 每次嘗試都由 `flow.submit` 簽進任務帳本。
- **加固與實測**：
  - rc5／rc6 的改動與五輪對抗審查集中在零設定重開（`restart.py`）。
  - `docs/KNOWN_LIMITS_0.9.2.md` 的條目沒有一條是關於契約路徑的。
  - 測試檔裡直接測契約路徑 `do` 的有 11 個，測 restart 的有 18 個。
  - 契約路徑從沒用真模型跑過預註冊批次。9/24 的 R536（localized feedback）預註冊寫了，但沒有發射。
