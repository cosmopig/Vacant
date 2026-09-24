# 2026-09-24：pi 的**常駐 extension 那條路**第一次拿到真模型證據（Linux，vacant-dev）

> **證據等級：L-real**（真 agent、真模型、真流量）。**路＝常駐 extension**：`vacant install` 寫進
> `~/.pi/agent/extensions/vacant.ts` 的那支，pi 用**完整路徑**叫（不經 PATH shim），pi 讀的是
> 使用者自己的 `~/.pi/agent/`，模型呼叫走常駐 proxyd。
>
> 🔴 **跟 `../possess_pi_real_20260922/` 不是同一條路，不可合併。** 那批五格全走 PATH shim
> （`gateshim` 把 `PI_CODING_AGENT_DIR` 搬到暫存目錄，常駐 extension 不在路上）⇒ 那批只記
> `possess.SHIM_MEASURED["pi"]`。本批才是 `possess.CHANNEL_MEASURED["pi"]` 要的那條路。
>
> 🔴 **這條路沒有閘門、沒有收據。** 本批量的是**通道**（每一通模型呼叫都經過 Vacant、
> 金鑰借得到、掛鉤有燒），**不是裁決**。互動模式的閘門（`agent_before_settle`）還沒做
> （`piext` 誠實邊界 5）。

- 執行端：**vacant-dev**（Ubuntu 24.04.4，kernel 6.8），`VERSIONS.txt`
- agent：**pi 0.87.0**（npm 隔離 prefix；該機常駐的是 0.85.1，extension API 要 0.87.0，本批沒用 0.85.1）
- HOME：**隔離**（`/var/tmp/vacant_piext_20260924/home`），vacant-dev 真的 `~/.pi` 一個位元都沒碰
  （該機還有別的實驗與人類的 session 在用 pi）
- 模型：`gemma-4-12b-it-qat` @ **1004**（non-thinking，本批當場用 17 隻羊探針量：`reasoning_content` 無）
- 程式碼：`fix/pi-integration-review` @ `1ca6683c`（code review 三項修正合併後）
- 常駐後端：`--service bare`（`status` 照實寫「撐不過重開機，不准說成常駐」）

## 〇、為什麼要在 1004 前面放一個要金鑰的中繼

LM Studio 不要金鑰 ⇒ 直連量不出「extension 借來的金鑰有沒有真的送到上游」（code review 修正 #2
的核心主張）。`tools/relay.py` 在 `100.124.254.83:18899` 查 `Authorization: Bearer <secret>`，
對了才轉 1004；**日誌只記 `auth: ok|missing|wrong`，不記金鑰**。secret 只活在 vacant-dev 的
`secret`（600），**本目錄 221 個檔 grep 過，零命中**。

控制組（curl）：沒帶 401、帶錯 401、帶對 `GET /v1/models` 200、串流 chat 200。

## 一、裝：上游自己從 pi 的設定找到（修正 #2 的第一半）

使用者的 `~/.pi/agent/models.json` 只有一個 provider `mylab`（baseUrl＝中繼、`apiKey`＝`$MYLAB_KEY`），
`settings.json` 的 `defaultProvider` 是 `mylab`。**沒有給 `--upstream`、沒有設任何 `*_BASE_URL`、
裝的時候也沒有設 `MYLAB_KEY`**：

```
上游  openai=http://100.124.254.83:18899/v1（pi:providers.mylab）
改過的檔  ~/.pi/agent/extensions/vacant.ts（create）＋ environment.d（create）
```

- `models.json`／`settings.json`：裝前裝後 sha256 相同（`install/pre_sha256.txt`）
- extension 烤進去的：`UPSTREAM`＝中繼、`KEY_FROM="mylab"`、`BAKED_MODELS=[]`（見 §六-2）
- 整個 HOME grep 金鑰：**0 個檔**（裝完、以及所有模型呼叫之後各查一次）

## 二、金鑰借得到嗎：沒有 Vacant ／ 有 Vacant 兩組，同一組 key 形式

每格都是 `pi -p "Reply with exactly: OK"`（完整路徑，命令列零個 vacant）。

| key 形式（models.json） | 沒有 Vacant：中繼看到的 POST | 有 Vacant：中繼 | 有 Vacant：proxyd journal | rc |
|---|---|---|---|---|
| 字面值 | ok → 200 | **ok → 200** | POST 200 | 0 |
| `$MYLAB_KEY`（有設） | ok → 200 | **ok → 200** | POST 200 | 0 |
| `!cat <secretfile>` | ok → 200 | **ok → 200** | POST 200 | 0 |
| 錯的字面值（負控制） | wrong → 401 | wrong → 401 | POST 401 | 1 |
| `$MYLAB_KEY`（沒設） | 沒送（pi 自己擋：No API key found） | 沒送 | 沒有 POST | 1 |

- **三種形式都借得到，而且送到上游的就是使用者的金鑰**（中繼判 ok）。錯的那格 401
  ＝金鑰確實是從 `models.json` 來的，不是別的地方。
- 每一格「有 Vacant」的 POST 都同時出現在 proxyd journal ⇒ 模型呼叫走的是 `vacant` provider，
  不是使用者原本的 `mylab`（那條直連中繼，不會進 journal）。
- ⚠ **量具錯誤一次，留檔不刪**：`cells/bare_envname_is_literal_TESTBUG/` 用的是裸字 `MYLAB_KEY`。
  pi 0.87.0 的規則是 **`$VAR` 才是環境變數，裸大寫字串是字面值**（`docs/models.md`「Value Resolution」）
  ⇒ 那格 401 是**我寫錯測試**，不是 pi 或 Vacant 的問題。

## 三、R534 五題：常駐 extension 那條路

prompt、工作區四個檔、純度 fail-closed 擋門、題目都與 `../possess_pi_real_20260922/` 相同；
**唯一刻意差異是路**（本批不經 shim ⇒ 沒有閘門、沒有收據）。`tools/task_cell.sh`。

| 題 | rc | 秒 | 模型呼叫（中繼 POST＝proxyd POST，全部 auth ok／200） | 工具呼叫 | `solution.py` | 可見 | **隱藏（GT）** |
|---|---|---|---|---|---|---|---|
| `lcb_3522` | 0 | 12 | 6 | 5 | ✓ | 過 | **27/27** |
| `lcb_3584` | 0 | 1536⚠ | 41 | 3 | **✗** | 不過 | 沒有交付物 |
| `lcb_3649` | 0 | 29 | 8 | 7 | ✓ | 過 | **26/26** |
| `lcb_3715` | 0 | 277 | 7 | 5 | ✓ | 過 | **26/26** |
| `lcb_3789` | 0 | 248 | 14 | 6 | **✗** | 不過 | 沒有交付物 |

- **通道：76 通模型呼叫，76 通都經過常駐 proxyd，76 通都帶著借來的金鑰（中繼 ok／200）。**
  每一格的掛鉤日誌都是常駐 extension 寫的（`session_start → canary → vacant_on →
  user_prompt_submit → before_provider_request ×N → pre_tool_use／tool_result ×N → stop → session_end`），
  工具事件的時機只有 pi 知道。
- **兩格 agent 退出碼 0、工作區裡沒有 `solution.py`，而這條路上沒有任何東西擋它。**
  同一個形狀在 shim 那條會被閘門以 exit 20 擋下（09-22 那批的 `lcb_3584` 就是），
  但**本批沒有跑 shim，不能寫成「本批會被擋」**。能說的是：互動／直叫這條路目前**只有通道，沒有牙齒**。
- ⚠ **`lcb_3584` 的 1536 秒含一段 VM 暫停**：`journalctl` 在 02:39 記了 tailscaled
  `time jump detected (slept 3m46s), probably wake from sleep` 與 systemd-resolved
  `Clock change detected`；中繼日誌同一段有一通呼叫等了 276 秒（02:35→02:39）。
  實際執行約 1310 秒，所以 1500 秒的 `timeout` 沒有觸發（rc 0 不是 bug）。同一段時間 Mac 的 ssh 也斷了。
- ⚠ **不可以跟 09-22 那批逐題比**：那批 `3715` 拒交、`3789` 交付，本批反過來；
  但路、後端（1003 thinking via Funnel ／ 1004 non-thinking via 中繼）都不同，而且各 n=1。
- 隱藏尺：`tools/` 沿用 `possess_pi_real_20260922/tools/score_hidden.py`（只改 REPO 路徑），
  run 結束之後才跑，GT 那棵樹從沒進過工作區。

## 四、互動 TUI（真 pty，真模型）

`tools/tui_real.py`／`tools/tui_cycle.py`，判準在掛鉤日誌與 journal，不在畫面。

| 格 | 操作 | 狀態列 | 掛鉤日誌 | journal／中繼 |
|---|---|---|---|---|
| `tui_real` | 送 prompt | `(vacant)` | `user_prompt_submit`→`before_provider_request`→`stop` | POST 1 通，auth ok 200 |
| | `/vacant off` | `(vacant)`→`(mylab)`，畫面「切回 mylab/gemma…」 | **`vacant_off` ×1**（payload 雜湊比對＝指令自己那筆） | — |
| | `/vacant on` | `(mylab)`→`(vacant)` | `vacant_on` ×1 | — |
| `tui_cycle` | Ctrl+P（使用者自己切走） | `(vacant)`→`(mylab)` | **`vacant_off` ×1**（雜湊＝`model_select` source `cycle`） | — |
| | Ctrl+P（切回來） | `(mylab)`→`(vacant)` | **沒有任何一筆**（見 §六-3） | — |
| `tui_real_counterfactual_noflag` | 同 `tui_real`，但把 extension 裡 `&& !offInProgress` 拿掉 | 同上 | **`vacant_off` ×2** | 同上 |

- **反事實這格回答了 code review 留下的疑問**：真 pi 0.87.0 裡，extension 自己 `await pi.setModel()`
  **會同步觸發 `model_select`**（拿掉旗標就變兩筆），所以 `offInProgress` 在真 pi 上是有作用的，
  不是剛好沒事。做完把 extension 拷回原檔，sha256 對得上（`logs/ext_sha_before_counterfactual.txt`）。
- ⚠ **第一次 TUI 作廢（留檔）**：`cells/tui_real_try1_STARTUP_ATE_INPUT/`。新 HOME 第一次開 pi
  會下載 `fd`／`ripgrep`（約 30 秒，畫面「Startup is still in progress」），驅動器照時間表送的字
  全部黏成一行 `/vacant statusReply with exactly: OK/vacant off`。量具的錯，不是 extension 的；
  修法是等狀態列出現 `(vacant)` 才開始送。

## 五、還原

`vacant uninstall`：rc 0，extension 刪掉、proxyd 停掉（`port_still_open: false`）、
`models.json` sha256 **相同**。`settings.json` **不同**——差的是 pi 自己第一次開互動模式時寫的
`"lastChangelogVersion": "0.87.0"`（03:11:25，第一次 TUI 當下），**`defaultProvider` 仍是 `mylab`**
⇒ 那不是 Vacant 寫的，也順便證實 extension 的 `setModel` 只在 session 層、沒有寫進使用者的預設。
留下來的是刻意保留的 journal 與掛鉤日誌（`kept_on_purpose`）。

## 六、這一跑抓到的問題（code review 之外的新發現）

1. **本機位址的上游會落到 sink**（`cells/localprov_dryrun/detect.json`）：pi provider 指
   `http://127.0.0.1:1234/v1`（LM Studio 預設）或 `http://localhost:11434/v1`（Ollama 預設）⇒
   上游＝sink、借不到金鑰；`192.168.x`／`100.x` 正常。那條略過規則原本是防 proxyd 把**自己**
   當上游，但它把使用者真正的本機模型也一起丟掉——**展場 1003 就是本機 LM Studio**。
   ⚠ `out_GREP_MISLEADING.txt` 是我第一次用 grep 看的輸出，它把 anthropic 那條的 sink 行
   誤讀成 openai 的；以 `detect.json`（直接呼叫函式）為準。
2. **上游要金鑰時，`vacant` provider 的模型清單是錯的**：裝機的 `probe_models` 與 extension 的
   `refreshModels` 都沒帶金鑰 ⇒ 401 ⇒ 永遠退回 `DEFAULT_MODEL`（`gemma-4-12b-it-qat`）。
   **本批剛好就是用那個模型所以通了**；使用者的 provider 若是 `gpt-…` 之類，每一通都會 404。
3. **Ctrl+P／`/model` 切回 vacant 不留痕**：只有切走會記 `vacant_off`，切回來沒有 `vacant_on`
   ⇒ 日誌讀起來像「這個 session 後半段都沒經過 Vacant」，跟事實相反。
4. **`/vacant <亂打>` 會安靜地跑 status**（`statusReply…` 被當成 status）。
5. **這條路永遠點不亮 `proven`**：`mark_proven` 只有 `gateshim`（shim 那條）會呼叫。本批 133 通經過
   常駐 proxyd，`vacant possess status`（含 `--reprobe`）照樣寫「中介 **未證實**」
   （`uninstall/status_before.txt`、`status_reprobe.txt`）。產品自己的狀態跟量到的事實相反。
6. （小）狀態列對沒在用的 anthropic 那條也印 `🔴 sink：沒有真上游`，只裝 pi 的人會以為壞了。
7. （小）journal 有一筆 `GET /v1/models` 的 `status 0`（`tui_cycle`），像是 pi 退出時被中斷的抓取。

1–5 另開修正（`551fdd1c` possess、`7c6665f1` piext，合併於 `ecd44491`），修完在同一台機器上重驗，
結果寫在 §七。6、7 沒修（小，且不影響中介）。

## 七、修正後重驗（同一台、同一個 pi 0.87.0、同一張卡）

為了把 #1 與 #2 分開量，換一個**只認別名 `lab-gemma`** 的中繼（`tools/relay_alias.py`：要金鑰、
`/v1/models` 只回 `lab-gemma`、POST 的 `model` 不是 `lab-gemma` 就 404、是的話改寫成
`gemma-4-12b-it-qat` 轉 1004），同時開在 **`127.0.0.1:18898`**（本機位址）與
**`100.124.254.83:18897`**（非本機）。控制組：沒帶金鑰 401、要 `gemma-4-12b-it-qat` 404、要 `lab-gemma` 200。

每格都是新鮮 HOME、使用者自己的 provider `homelab`（模型只有 `lab-gemma`、金鑰 `$MYLAB_KEY`），
先**不裝 Vacant** ping 一次當基線，再 `vacant install`（不給 `--upstream`）再 ping（`tools/p2.sh`）。

| 格 | 程式碼 | provider 指向 | 沒有 Vacant | 裝完的上游 | 有 Vacant：中繼看到的 POST | proxyd | `status` |
|---|---|---|---|---|---|---|---|
| `p2_old_local` | `1ca6683c`（修前） | 127.0.0.1 | ok／lab-gemma／**200** | **sink** | **沒有**（fail-closed，一個位元組都沒出去） | POST 502 ×4 | 中介 未證實 |
| `p2_old_tail` | `1ca6683c`（修前） | 100.x | ok／lab-gemma／**200** | 中繼（pi:providers.homelab） | ok／**gemma-4-12b-it-qat**／**404** | POST 404 | 中介 未證實 |
| `p2_new_tail` | `ecd44491`（修後） | 100.x | ok／lab-gemma／200 | 中繼 | ok／**lab-gemma**／**200** | POST 200 | **中介 ✓（extension 路）** |
| `p2_new_local` | `ecd44491`（修後） | 127.0.0.1 | ok／lab-gemma／200 | **127.0.0.1:18898**（pi:providers.homelab） | ok／**lab-gemma**／**200** | POST 200 | **中介 ✓（extension 路）** |

- **#1 修好**：本機位址的 provider 被當成上游（修前 sink）。
- **#2 修好**：`vacant` provider 的模型清單借自使用者的 provider，要的是 `lab-gemma`（修前 `gemma-4-12b-it-qat` → 404）。
  `/vacant status` 多一行「模型清單　借自 models.json 的「homelab」」。
- **#5 修好**：`status` 點亮「中介 ✓（extension 路）」，並且寫出是哪一份掛鉤日誌、哪一個 journal `call_id`、
  「只證通道，不含閘門／裁決」（`cells/p2_new_local/status_final.txt`）。
- 修前兩格的基線都是 200 ⇒ **壞的是 Vacant 那一層，不是使用者的設定**。
- 四格 uninstall 後 `models.json` sha256 都相同；`settings.json` 只有 pi 自己寫的 `lastChangelogVersion`（互動那格）。

互動（`p2_new_local` 那個還裝著的 HOME）：

| 格 | 操作 | 掛鉤日誌 |
|---|---|---|
| `p2_new_local_tui` | Ctrl+P 切走 → Ctrl+P 切回 | `vacant_off` ×1 → **`vacant_on` ×1**（**#3 修好**；開場的 `vacant_on` 仍只有一筆，switchOn 自己的切換沒有重複記） |
| | `/vacant bogus` | 畫面「用法：/vacant on \| off \| status（收到「bogus」，什麼都沒做）」，狀態列仍是 `(vacant)`（**#4 修好**） |
| `p2_new_local_tui_off` | prompt → `/vacant off` → `/vacant on`（回歸） | `vacant_off` ×1、`vacant_on` ×1；那一通 prompt 中繼看到 ok／lab-gemma／200 |

回歸：`p2_new_local_task_lcb_3522_r1`（R534 `lcb_3522`，修後程式碼、本機位址中繼）——rc 0、24 秒、
11 通全經常駐 proxyd（中繼 ok／lab-gemma／200）、可見過、隱藏 **27/27**。

收尾：三支中繼與 proxyd 都停了；vacant-dev 上的 secret 已 `shred`；本目錄再 grep 一次金鑰，零命中。

## 不能說的

1. **不能說「互動模式有閘門／有收據」**：這條路只有通道。
2. **不能說 A 級、也不能說 B′**：這條路根本不出收據，沒有級別可講。
3. **不能說「pi 裝好就一定經過 Vacant」**：使用者 `/vacant off`、Ctrl+P、`/model` 都能切走
   （會留痕，但不擋）；agent 也刪得掉 extension 檔（`piext` 誠實邊界 2）。
4. **不能說這是展場的成績**：展場是 1003（Windows），這台是 Linux，而且 §六-1 在展場會直接咬到。
5. **n=5 各一次，沒有 rep**；隱藏尺是單邊的（`suitegauge` 誠實邊界）。
6. 中繼是**我們自己放的**，用來量金鑰有沒有送到；真實世界的上游（OpenAI 等）還沒接過。

## 重跑

```
# vacant-dev，工作根 /var/tmp/vacant_piext_20260924（repo 子集＋pi 0.87.0 ＋ 隔離 HOME）
# secret 在收尾時已 shred ⇒ 重跑先自己產生一個（600），它永遠不進 repo
python3 tools/relay.py 100.124.254.83 18899 100.86.226.21 1234 secret logs/relay.jsonl &   # 要金鑰的中繼
python3 tools/set_key_form.py env                                                        # 使用者的 models.json
PYTHONPATH=repo python3 -m vacant_network.vrun.possess install --home home --agent pi \
    --service bare --port 18795 --no-shell-probe                                          # 不給 --upstream
bash tools/ping.sh V_env env 1                                                            # 金鑰形式各一格
bash tools/run_tasks.sh                                                                   # 五題
python3 tools/summarize.py                                                                # 表 ＋ 隱藏尺
bash tools/tui_cell.sh tui_real ; DRIVER=tui_cycle.py bash tools/tui_cell.sh tui_cycle     # 互動
# §七：relay_alias.py 開在 127.0.0.1:18898 與 100.124.254.83:18897，然後
#       bash tools/p2.sh old_local old http://127.0.0.1:18898/v1   （old＝repo、new＝repo_new）
PYTHONPATH=repo python3 -m vacant_network.vrun.possess uninstall --home home
```
