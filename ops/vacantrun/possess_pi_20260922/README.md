# 自裝驗證 2026-09-22：`vacant install --agent pi` → 打開 pi → `/vacant on|off|status`

> **證據等級：L-fake（假上游）。** 這一批證明的是**通道與閘門的形狀**：pi 的每一通模型呼叫
> 有沒有經過 proxyd、掛鉤有沒有燒、shim 那條的退出碼對不對、裝與還原是不是逐位元。
> 它**不證明**任何模型能力，也**不能寫成「pi 可以用 Vacant」**（`docs/AGENT_COMPAT.md` 開頭那條線）。
> `possess.CHANNEL_MEASURED["pi"]` 因此**仍是空字串**：常駐這條路的真模型要在 vacant-dev 補。

- 執行端：Claude Code 遠端容器（`VERSIONS.txt`：kernel 6.18、Python 3.11.15、node v22.22.2）
- agent：**pi 0.87.0**（`npm install --prefix … @earendil-works/pi-coding-agent@0.87.0 --ignore-scripts`，
  ⚠ vacant-dev 上的是 0.85.1，兩個版本的差異本批沒量）
- 上游：`tools/fake_openai.py`（`/v1/models` 回一個 `fake-gemma`；`/v1/chat/completions` 固定回
  `OK (fake upstream)`，支援 SSE）
- HOME：隔離的 scratchpad HOME（`--home`），**沒有動容器的真 HOME**；常駐後端 `--service bare`
  （容器裡沒有 systemd，`status` 照實標 `supervised: no`）
- 沒有 bwrap ⇒ 沒有 enclosure ⇒ **每一格的級別都是 B′**（`attested: false`）。那是量出來的，不是設定。

## 一、裝

```
vacant install --agent pi --home <HOME> --service bare --upstream openai=http://127.0.0.1:18999 --no-shell-probe --port 18787
```

| 項 | 結果 |
|---|---|
| preflight | proxyd 在聽、`/v1/models` round-trip 200 才寫檔 |
| 寫的檔 | **只有一支** `~/.pi/agent/extensions/vacant.ts`（`resident/vacant.ts.installed`）＋ `environment.d/50-vacant-possess.conf` |
| `models.json` | **沒寫**（裝之前不存在，裝之後也不存在） |
| `auth.json` | 沒讀沒寫（`NEVER_TOUCH`） |
| 烤進 extension 的模型清單 | `["fake-gemma"]`（裝機當下透過 proxyd 問 `/v1/models` 抓到的） |
| `startable` | ✓（`pi -p ping` 起得來） |

## 二、印字模式（`pi -p`，**完整路徑、不經 shim**）

`resident/pi_print.stdout`：`OK (fake upstream)` ⇒ 答案是假上游回的 ⇒ 那一通經過 proxyd。

常駐 proxyd journal（`resident/proxyd_index.jsonl`）逐通：

```
GET  /v1/models                                     200   ← preflight
GET  /v1/models?vacant_canary=install               200   ← 裝機抓模型清單
GET  /v1/models?vacant_canary=refresh-<run>         200   ← pi 啟動時呼叫 refreshModels
GET  /v1/models?vacant_canary=<run>                 200   ← hookcli 的 canary（session_start）
GET  /v1/models?vacant_canary=status-<run>          200   ← extension 的 proxyAlive 探針
POST /v1/chat/completions                           200   ← 模型呼叫本體
```

掛鉤日誌（`resident/pi_e38ce618-….jsonl`，**pi 自己 spawn 的**）：
`session_start` → `canary` → `canary_result(200)` → `vacant_on(source=session_start)` →
`user_prompt_submit` → `before_provider_request` → `stop` → `session_end`。

## 三、互動 TUI（真 pty，`tools/tui_drive.py`）

狀態列顯示 **`(vacant) fake-gemma`**（`tui/tui_second_attempt.raw` 出現 12 次）。
依序送 `/vacant status`、`/vacant off`、`/vacant on`、`/vacant status`、`/quit`：

| 指令 | 畫面 | 掛鉤日誌 |
|---|---|---|
| `/vacant status` ×2 | 「Vacant status」×2，含 proxyd 在聽、requests_seen、掛鉤日誌路徑 | — |
| `/vacant off` | 「Vacant 關」 | `vacant_off` ×2（一筆是指令、一筆是 `model_select` 事件看到切走了） |
| `/vacant on` | 「Vacant 開」 | `vacant_on` |

⚠ **第一次跑（`tui/tui_first_attempt_enter_eaten_by_autocomplete.raw`）`/vacant off|on` 沒送出去**：
pi 的指令自動補全彈窗會吃掉第一個 Enter。那是量具（驅動腳本）的問題不是 extension 的，
修法是送 Esc 再 Enter。留著第一次的 raw 是為了分得出「沒送出」與「送了沒反應」。

## 四、shim 那條（`~/.vacant/possess/bin/pi -p …`，閘門）

| 格 | 工作區 | 驗收 | 退出碼 | `accepted` | `stop_reason` | `agent_rc` | `requests_seen` | 收據 |
|---|---|---|---|---|---|---|---|---|
| 無套件 | `ws4` | none | **21** | `null` | `ungated` | 0 | 2 | `runs/possess_pi_1790054851_1a3f5e` |
| 拒交格 | `ws_refuse`（沒有 `solution.py`） | `tests_visible/`（`check_add`） | **20** | `false` | `visible_fail` | 0 | 2 | `runs/possess_pi_1790054916_13b38b` |
| 交付格 | `ws_deliver`（預先放 `solution.py`） | 同上 | **0** | `true` | `visible_pass` | 0 | 2 | `runs/possess_pi_1790054919_901365` |

四張收據 `verify_receipts --selftest` 先 PASS，再逐一驗：**總判全部 OK**，每張都帶
`! 未認證 tier=B′`（沒有圍牆——正確）。

### 🔴 修掉的洞（`runs/shim_before_fix_bedrock.stderr`）

第一次跑 shim 那格：`wire 1 通`（只有 canary）、stderr 出現
`UnrecognizedClientException: The security token included in the request is invalid.`
——pi 沒帶 `--provider` 時用**它自己的預設 provider**（這台容器環境有 AWS 變數 ⇒ 落到 Bedrock），
那一通**根本沒經過這一跑的 proxy**。`gateshim` 只寫 `models.json` 不會讓 pi **選**那個 provider。
收據誠實地判 **B′**（工具層有紀錄、模型通道沒完整看到）——量具沒說謊，是接線漏了。
修法：`gateshim.exec_inner` 另寫 per-run `settings.json` 的 `defaultProvider=vacant`／`defaultModel`
（pi `settings.md` 寫明的啟動預設）。修完 `runs/shim_after_fix.stderr`：`wire 2 通`、答案來自假上游。
⚠ 這個洞在本次改動**之前就在**（`CHANNEL_MEASURED["pi"]` 一直是空的，所以沒人量到）。

## 五、還原

`vacant uninstall --home <HOME>`（`resident/uninstall_report.json`）：`ok: true`，
extension 刪掉、environment.d 刪掉、shim 刪掉、埠 18787 關閉。
留在 HOME 裡的 `auth.json`／`models-store.json`／`settings.json`／`sessions/` 是 **pi 自己**在跑的時候寫的，
不是我們的（`NEVER_TOUCH` 從頭到尾沒讀過 `auth.json`）。

## 六、不能說的

1. **不能說 L-real**：假上游碰不到 SSE 分塊細節、工具呼叫格式、逾時、上下文長度。
2. **不能說「裝好就有」對 pi 成立**——那句話要等 vacant-dev 的真模型格。
3. **不能說 A 級**：這台沒有 bwrap。
4. **不能說「不會被繞過」**：extension 在 `$HOME`，`/model` 切走或刪檔都做得到；差別是日誌會留 `vacant_off`／canary 不燒。
5. 互動 session **沒有裁決收據**（只有通道與掛鉤），閘門仍只在 `pi -p` 經 shim 那條。

## 重跑

```
python3 tools/fake_openai.py 18999 &
vacant install --agent pi --home <HOME> --service bare --upstream openai=http://127.0.0.1:18999 --no-shell-probe --port 18787
pi -p "reply with the single word OK"                     # 完整路徑；看 <HOME>/.vacant/possess/proxyd/wire/index.jsonl
python3 tools/tui_drive.py out.raw pi                     # 真 pty
<HOME>/.vacant/possess/bin/pi -p "…"                      # shim；工作區旁放 tests_visible/（tools/suite_test_add.py）
vacant uninstall --home <HOME>
```
