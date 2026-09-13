# DECISION R520（2026-09-02，Sonnet 5，碼工輪）：補 R516 §8 的兩個 runner 落盤缺口

不起任何 run（人類尚未回應 round518/519 提出的三個問題，E1 視窗仍要求 8765 上
不得起新 gain_run）。本輪只改 runner 程式碼，兩處都是 R516 §8「給 opus 輪的提案」
列出的落盤缺口，改完各附一支能在沒有 pytest 的機器上跑的最小重現。

## 背景（不重新量測，只引用 R483/R516 已經記錄的事實）

1. `calls.jsonl` 只記請求端送出的 `model`／`model_configured`，驗得到「請求端
   沒把 model 換掉」，驗不到「1004／8765 中轉那端實際服務的是不是同一個模型」——
   OpenAI 相容回應本體頂層通常會帶一個 `model` 欄，這支從沒讀過它（R483 §5）。
2. `finalize()` 的 `complete` 定義是 `n_void==0 and processed==len(tasks)`。
   這是刻意的（round224 教訓：不能只看 processed 就說跑完，否則 void 很多的
   run 也會被當成「乾淨可比」）。但它的副作用是**任何有 void 的 run，`complete`
   結構上永遠不可能變 true**——E1（12 個 void）就是這樣，`run_complete` 永遠
   false，下游任何「等 run_complete=true 再收官」的自動觸發都會空等，round516
   只能靠人讀 commit 訊息才知道該收官了（R516 §0、§8）。

## 改動

### 1. `ops/gain/brain_cline.py`：`generate()` 成功分支新增 `server_model` 欄

```python
"server_model": d.get("model") if isinstance(d, dict) else None,
```

放在既有 `model`／`model_configured` 旁邊，純新增欄位，不改任何既有欄位的語意。
沒有的話是 `None`，不是整筆記錄少一個 key（否則下一個要讀這欄的人要用
try/except KeyError 猜「這個 run 是不是修過的版本」）。只加在成功分支——
失敗分支通常在 `d` 被賦值之前就丟例外，沒有伺服端回應可讀。

### 2. `ops/gain/gain_run.py`：新增 `terminal`（per-arm）／`run_terminal`（頂層），`complete`／`run_complete` 不動

```python
"terminal": s["processed"] == len(tasks),                       # finalize() 裡
run_terminal = bool(arms) and all(
    summary.get(a, {}).get("terminal") for a in arms)            # write_summary() 裡
```

`complete`／`run_complete` 語意完全不動——它們仍然是「零 void 才可信」的判準，
不能拿掉（round224 的教訓沒有過期）。`terminal`／`run_terminal` 是新加的另一個
訊號，只回答「迴圈有沒有把每個 task 處理過一次」，void 不影響它。兩個訊號並存，
下游要「等真的收官」該看哪一個由讀的人自己決定：要「比例可信」看 `complete`，
要「該不該去讀 summary 了」看 `terminal`。

## 驗證

本機沒有 `pytest`／`pip`（沿用 round439 起多輪記錄的環境限制，`python3 -m pip`
report no module named pip、`ensurepip` 不存在、全機找不到 `.venv`）。做了兩件事：

**a. 把新測試寫進 `tests/test_gain_runner.py`**（`git diff` 有紀錄，下次有 pytest
的環境要補跑）：

- `test_server_reported_model_is_captured_on_every_success`：mock `urlopen` 回
  跟請求端不同的 `model` 值，斷言 `server_model` 落盤且等於伺服端回的值；
  再 mock 一次沒有 `model` 欄的回應，斷言 `server_model` 存在且是 `None`
  （不是 key 消失）。
- `test_run_terminal_stays_true_when_a_run_has_voids`：照 E1 的實際形狀
  （179 題、12 個 void）手算 `complete`／`terminal` 兩條公式，斷言 `complete`
  在有 void 時是 False（沿用既有語意，不能因為加了新欄位就鬆動），`terminal`
  在三臂都跑滿 179 題時是 True；另外斷言跑到一半（processed=3）時兩個都是 False，
  不能因為之後會補上就先寫 True。

**b. 直接用 `python3 -c` 跑最小重現**（不經 pytest，繞開整份測試檔
`import pytest` 造成的 ImportError；這是 round439 就用過的繞法）：

```
server_model captured OK: gemma-4-12b-it-qat@node-b
server_model None-when-absent OK
model alternation test OK, recs: [...]
relay-200-error-body test OK
```

第三、四行是重跑既有的 `test_model_id_alternates_on_404_...` 與
`test_relay_200_with_error_body_...` 的邏輯（手動搬出來跑，不是新測試），
確認新增的 `server_model` 欄沒有連帶弄壞這兩支既有行為——404 重試那筆記錄裡
`server_model` 正確是 `None`（那個分支的假回應沒有 `model` 欄）。

`ast.parse` 過 `gain_run.py`／`brain_cline.py`／`tests/test_gain_runner.py`
三個檔案，語法正常；`import ops.gain.gain_run` 不出錯。**沒有跑過真正的
`main()` 或任何完整的 arm 迴圈**——那需要一個活的端點與任務庫，本輪沒有起
run 的授權（E1 視窗），這是誠實的驗證邊界，不是遺漏。

## 沒做的事（照實）

- 沒改 `complete`／`run_complete` 的既有語意，沒有把兩個訊號合併成一個。
- 沒有回頭改 R483/R516 已經產生的 `calls.jsonl`／`summary.json`（歷史資料
  不會有 `server_model`／`terminal`，這是 forward-only 的欄位）。
- 沒有讓下游任何自動化真的去讀 `run_terminal`——本輪只加欄位，接線是另一件事，
  之後有人要寫「run 結束就自動怎樣」的邏輯時才用得到。
- 沒有起任何 run，沒有動 1004，沒有查 win1003 B 軌，沒有寫 `NEXT_MODEL=local`。
- 沒有在真正有 pytest 的環境跑過完整 `tests/test_gain_runner.py`（環境限制，
  下一個有 pytest 的環境要補跑一次全檔案，確認新測試沒有跟其他測試互相干擾）。

## 下一輪

1. 開場先看人類有沒有回應 round518/519 的三個問題（1004 要不要載別的模型、
   ctx 要不要改回 32768、`loginctl enable-linger`）。
2. 沒回應就繼續無成本碼工，或找有 pytest 的環境補跑一次完整測試套件。
3. 若要起新 run，先寫 DECISION（含 run 名、預測、中止準則）→ commit →
   才能發射（R440G 硬性 gate，`--decision` 沒對到 `--out` 目錄名會被拒絕啟動）。

`下一輪模型：sonnet` —— 這輪是 runner 碼工，政策表把「寫／改 runner 的程式碼」
放在 sonnet 欄；沒有反直覺結果、沒有要下判斷的實驗設計取捨，不需要 fable 或 opus。
