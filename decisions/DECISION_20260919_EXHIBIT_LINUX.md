# DECISION 2026-09-19 — 整條展件線搬到展場那種機器（Linux）上跑一次

## 一句話

**搬得動、跑得起來、沒掛。** 18 格輪播在 Ubuntu 24.04 上連續跑了 21 分鐘、11 圈、
214 個事件、0 格被擋、RSS 33 MB、fd 5 個；離線（network namespace 只有 lo）照跑；
收據頁在瀏覽器裡把 19 條鏈、41 筆 Ed25519 簽章逐筆驗過。

**但有一條會在布展當天咬人的**：這台 VM 的中文字型是**前一個 session 手動丟進
`~/.local/share/fonts/` 的兩個檔**，不是系統套件。把它們搬走再跑一次，
電視是**滿畫面豆腐字**——一個中文字都認不出來。乾淨的展場機預設就是那個狀態。

## 為什麼現在做

`DECISION_20260919_TWIN_LIVE.md` §九「還不能說的話」第 3 條：「canvas 實際畫出來的
樣子還沒有人看過」。Mac 那一格已經補上；**Linux 那一格是空的**，而
[展場機是 Linux VM](../CLAUDE.md)（人類 2026-09-07 確認）。CLAUDE.md 的三條展場硬需求
（離線可跑、無人值守、秒級互動）**只在 Linux 上驗過才算數**。

## 目標機器與怎麼搬

`vacant-dev` ＝ `user1@100.124.254.83`，Ubuntu 24.04.3、kernel 6.8.0、8 核、7.9 GB RAM、
Python 3.12.3、磁碟當時剩 4.8 G。

**沒有 clone，也沒有 worktree**（這個 repo 一份 786–789 MB，磁碟吃不下）。
只搬需要的東西，三個 tar 共 **63 MB**，scp 15 秒：

| 搬什麼 | 從哪來 | 大小 |
|---|---|---|
| `ops/exhibit/twin/**` ＋ `examples/twin_viewer.html` | `git archive twin/v2-live-mobile` | 1.4 MB |
| `vacant/`（**非搬不可，見下**） | 同上 | 1.2 MB |
| `vacant_hm/world3/` | 工作樹 | 59 MB |

落點 `~/exhibit-linux/{Vacant,vacant_hm}`——這個相對位置是 `exhibit_boot.sh` 的
`HM="$(cd "$REPO/.." && pwd)/vacant_hm"` 推出來的，擺對就不用給 `--hm`。

## 逐項驗證結果

### 1. `exhibit_boot.sh` 在 Linux 上跑不跑得起來 → **跑得起來，但第一次是炸的**

`bash -n` 過。路徑推導、`python3 -m http.server`、埠綁定在 Linux 上都正常。
`LAN_IP` 那一行的 macOS 專用 `ipconfig getifaddr en0` 會失敗、正確 fall back 到
`hostname -I | awk '{print $1}'`，量到 `192.168.76.135`。

> ## ⚠ 更正（2026-09-20）：**上面這一段是讀碼讀出來的，不是量出來的**
>
> **原文一個字都沒改**——改掉它等於讓紀錄描述一件沒發生過的事。這裡只加註。
>
> 上面那句「正確 fall back 到 `hostname -I`」**從來沒有被執行過**。
> `LAN_IP` 那一整塊在 `if [ "$BIND" = "0.0.0.0" ]` 底下，**只有加 `--lan`
> 才會跑**，而這一輪跑的是不帶 `--lan` 的版本（腳本最後印的是
> 「⚠ 只綁本機：手機連不到。展場要用 --lan。」）。
>
> 真的跑下去的結果是 **exit 1、一個字都不印**：這台只有 `lo`／`ens33`／
> `tailscale0`，`ip -4 -o addr show en0` 回 1，而腳本開著 `set -o pipefail`
> ⇒ 整條管線回 1 ⇒ `set -e` 當場結束，連 `hostname -I` 那一行都到不了。
> 在 `systemd` 底下就是每 10 秒重啟、journal 只有 `status=1/FAILURE`。
>
> ⚠ **不要把這件事讀成「後來有人把腳本改壞了」。** 那條路
> **從第一天就是這樣**——這一份描述的是**碼**，不是**行為**。
> 兩者的差別在紀錄上看起來一模一樣，這正是它隱蔽的地方。
>
> 修法、實測與**新加的可執行判準**（`--print-host`、`preflight --lan`、
> 四條測試）在 `DECISION_20260919_EXHIBIT_UNATTENDED.md` §五-1。
>
> 留下來的那一句：**從讀碼描述一條路徑，不等於量過它。**

**第一次起不來**：`to_events.py:226` `from vacant.logbook import LogEntry` →
`ModuleNotFoundError: No module named 'vacant'`。

> ⚠ **這推翻了「只有 stdlib」的說法**。`serve_twin.py` 自己確實只有 stdlib
> （唯一沾網路的 import 是 `http.server`，那是**監聽**不是外連），但它 `import`
> 的 `to_events` 會拉 `vacant.logbook`，而 `vacant.logbook` 要 `cryptography`
> ——**一個原生 wheel，不是 stdlib**。
> 這台 VM 剛好有 `python3-cryptography 41.0.7`（Ubuntu 的 dist-package），所以補上
> `vacant/` 就好了。**乾淨的展場機不保證有**。
> `pack.py` 另外要 `vacant.vrun`、`run_twin.py` 要 `vacant.vrun.launcher`、
> `make_consent_demo.py` 要 `vacant.{consent,crypto,canonical,identity,logbook}`。

補上 `vacant/` 之後：兩台都起來、18 格、9 對、輪播正常。

### 2. `serve_twin.py` 真的零外網嗎 → **是，而且用 namespace 證明過**

- **靜態**：`serve_twin.py`／`to_events.py` 沒有 `urllib`／`requests`／`httpx`。
  `phone.html`、`examples/twin_viewer.html`、`world3/index.html` 三個頁面
  **一個 `http(s)://` 外部資源都沒有**（`grep` 掃過，扣掉 `w3.org` 的 XML namespace）。
- **動態**：整條線放進 `sudo unshare -n` 的 network namespace 裡跑——
  只有 `lo`、**沒有 default route、DNS 解不開**（`curl https://github.com` 回 000）。
  五個端點全 200、電視頁 200、事件流在 6 秒內從 6 行長到 18 行（輪播在動）。
  `ss -tanp` 沒有任何非 loopback 連線。

> 這比「拔網路線」強：拔線是拔掉一條路，namespace 是**根本沒有路**。

⚠ 但 `unshare -rn`（非 root）在這台**不能用**（`/proc/self/uid_map: Operation not
permitted`，userns 被關）。要 `sudo`。

### 3. 無人值守 → **會自己輪播，不會卡死；D2 的防線真的擋得住**

**連續 21 分鐘無人干預**：`emitted` 214、`laps` 11、`skipped` 0、
RSS 32.3 MB → 33.0 MB、fd 4 → 5、`events.jsonl` 穩定在 31 KB（一圈截檔一次，
沒有無限長）。

**D2（一格沒 `verdict` 會不會卡死整個佇列）**：`ops/exhibit/twin/` 一個 byte 沒改，
用探針在記憶體裡把某一格的 `verdict` 事件整個拔掉（模擬 `infra_void`
不簽收據不發裁決），`advance()` 叫 40 次：

```
毒藥格：DUL-89__s1_01_addmul__held
  emitted=37  laps=2  skipped=3
  毒藥格有沒有混進事件檔：False
  原因：DUL-89__s1_01_addmul__held 開了但沒有 verdict：電視會一直等這一格（整個佇列卡住）
  事件檔裡開了但沒 verdict 的格：（沒有）
D2 判定：通過（擋下、記原因、佇列沒卡死）
```

擋下、講明原因、佇列繼續跑。**D2 在 Linux 上成立。**

⚠ 一個小的、不致命的觀察：`Stage.skipped` 是**沒有上限也不去重**的 list，
而 `/state` 整份回傳。一格永久壞掉的話，每一圈都會再 append 一筆。
dwell=30s × 18 格 ≈ 9 分鐘一圈 ⇒ 一天 8 小時約 53 筆、約 10 KB。
**不是洩漏，但展期多天要記得它只會長不會消。**

**電視端也驗了**：不碰它、每 20 秒截一張、連截 8 張（172 秒）——電視**自己**
離開了「碰一下開始」的待機畫面，走進場景（徽章從「待機」變成「幕 3」再變成「步 11」）。
`page errors` 是 `[]`。**無人值守在電視那一端也成立。**

### 4. `file://` 的 CORS 陷阱 → **結論對，但裁決文寫的理由是反的**

`DECISION_20260919_TWIN_LIVE.md` 說「電視在 `file://` 下 `fetch` 會被 CORS 擋，
**一個字都拿不到**」。在 Linux／Chromium 153 上分開量兩種 fetch：

| 從哪裡開 | 跨來源抓事件流 | 抓自己的 `scenes/index.json` |
|---|---|---|
| `file://…/world3/index.html` | **成功 200 / 38190B** | **被擋：Failed to fetch** |
| `http://127.0.0.1:8420/…`（`exhibit_boot.sh`） | 成功 200 | 成功 200 / 4140B |

**被擋的是電視自己的場景資料，不是事件流。** 事件流反而是 `file://` 下唯一活著的
那一個——因為 `serve_twin` 自己送 `Access-Control-Allow-Origin: *`，而 `file://`
的 `Origin` 是 `null`，`*` 收得下。

> **這比原本的說法更危險**，所以要改口徑：雙擊開 `index.html` 會得到一個
> **半活的頁面**——導播列有字在跳（事件流通了），但場景、sprite 一個都沒載進來。
> 「整頁死掉」有人會馬上發現，「看起來在動但其實是空的」不會。
>
> **`exhibit_boot.sh` 確實處理掉了**（它就是為此存在的），結論不變：
> **展場一定要本機 http server**。只是理由要寫對。

### 5. 實際畫面 → **Linux 上截到了**（不是拿 Mac 的圖代替）

Mac 上那三條路的教訓在 Linux 上同樣成立，所以走 CDP。但這台**沒有 pip**，
裝不了 `websocket-client` ⇒ 自己刻了一個 **stdlib-only 的 WebSocket client**
（握手**不送 `Origin`**，否則 Chromium 153 的 DevTools 拒絕握手）。
瀏覽器＝`snap install chromium` 153.0.8010.36（吃掉 1.5 GB 磁碟，剩 3.0 G）。

截到並親眼看過：

| 畫面 | 結果 |
|---|---|
| 電視 · 待機 1920×1080 | 正常：「你需要什麼？／走過 371 件真實任務的一群人」 |
| 電視 · 場景（步 11） | 正常：「你可以一直看下去／這個世界 不會停」，底部誠實列在 |
| 電視 · **把中文字型搬走之後** | **滿畫面豆腐字**，只有「371」認得出來 |
| 手機 `phone.html` 430×932 | 正常，版面沒有溢出，「這一頁證明不了什麼」那一塊在 |
| 收據頁 `viewer.html` | 正常，**19 條鏈 / 41 筆 Ed25519 逐筆驗過，全過** |

底部誠實列逐字是「背景活動＝機制模擬 · 判決與數字＝真紀錄重放 · 手機選了：介面扣住」
——**「機制模擬」四個字在畫面上**（CLAUDE.md 硬需求 1）。

圖檔：`vacant-dev:~/exhibit_linux_evidence_20260919/`（6 張 ＋ `SHA256SUMS`，8.0 MB）。
**沒有進 repo**（沒人要我加二進位檔）。

### 6. `--lan` 與 `--token` → **`--token` 真的有效**

在只有 lo 的 namespace 裡對 `/control` 打三次：

```
沒帶 token   403 {"ok": false, "error": "token 不對"}
帶錯 token   403 {"ok": false, "error": "token 不對"}
帶對 token   200 ok=True
GET /state   200（唯讀端點不擋，設計如此）
```

`--token` **確實擋得住寫入端點**。`/control` 的七個 action
（`held`／`pc`／`next`／`tamper`／`untamper`／`resume`／未知）在 Linux 上行為與契約一致；
壞 JSON 回 400、未知端點回 404。

**布展預設建議**：`--lan` **一定要配 `--token`**。沒有 token 的 `0.0.0.0`
＝同一個區網上任何人都按得動這台電視（`/control` 沒有驗身分、事件流沒有簽章）。
`venue_check.sh` 第七節會在「綁 0.0.0.0 且沒 token」的時候發警告。

⚠ `--token` 只是**共享密鑰、明文 HTTP**。它擋的是路過的人，不是攻擊者。
展場更穩的做法是給展件一個只有現場手機連得到的獨立熱點。

## Linux 特有的坑（Mac 上不會遇到）

1. **中文字型（最嚴重）。** 這台的中文字能顯示，**只因為前一個 session 手動把
   `NotoSerifCJKtc-Regular.otf`／`NotoSansMonoCJKtc-Regular.otf` 丟進
   `~/.local/share/fonts/`**。系統套件只有 `fonts-dejavu-*`，**DejaVu 沒有 U+6A5F（機）**。
   電視的字型堆疊是 `"Songti TC","Noto Serif TC",Georgia,serif`、
   手機是 `system-ui,-apple-system,"Noto Sans TC","PingFang TC",sans-serif`
   ——**這五個名字在 Ubuntu 上一個都不存在**，全部 fall back 到 DejaVu ⇒ 豆腐字。
   把那兩個檔搬走重截，確認是整頁豆腐。
   - 而且只有 **Regular**、沒有 Bold ⇒ 大標是**合成粗體**，不是設計的樣子。
   - **字型是在瀏覽器啟動時讀進去的**：裝完字型要**重開瀏覽器**才生效
     （這一點是我自己踩到的——還原字型後沒重開，截出來還是豆腐）。
2. **`--kiosk` 在 Linux 上是靜靜的空操作。** `exhibit_boot.sh` 只認
   `/Applications/Google Chrome.app/…`，`[ -x ]` 在 Linux 必然失敗 ⇒
   **不開瀏覽器、也不講一句話**。展場要無人值守全螢幕，這條現在沒有 Linux 分支。
3. **`exhibit_boot.sh` 不做啟動健檢。** serve_twin 炸掉（例如埠被佔），腳本
   **照樣把三個網址的橫幅印出來**，traceback 在上面捲掉了。
   exit code 是 1（fail-closed 沒壞），但**螢幕上最後一段是「一切正常」**。
   展場重開機、舊 process 還佔著 8899，就是這個情境。
4. **Python stdout 導進檔案會被緩衝**，serve_twin 的啟動橫幅不會立刻出現在 log 裡
   ——看起來像卡住。`python3 -u` 或 `PYTHONUNBUFFERED=1` 可解。
5. **`unshare -rn` 非 root 不能用**（userns 關掉），要離線隔離得 `sudo`。
6. **`hostname -I` 這台回三個位址**（`192.168.76.135`、Tailscale `100.124.254.83`、
   IPv6）。`--lan` 取第一個，這次剛好對，**是運氣不是設計**。展場插網路線的順序
   會改變它。建議布展時明確指定，不要靠第一個。
7. **snap chromium 自己會連外網**（log 裡有 GCM `registration_request`，
   `venue_check.sh` 量到 15 條對外連線）。**展件沒有打外網，瀏覽器有。**
   真正離線的 kiosk 要加 `--disable-background-networking --disable-sync`
   `--disable-component-update --no-first-run` 一類旗標。
8. snap chromium 有 AppArmor dbus 噪音（`ListActivatableNames` AccessDenied），
   **無害**，不影響畫面。
9. **`fc-list` 預設不存在**（只有 `fontconfig-config` 和 lib，沒有工具）。
   第一次量字型量到「0」其實是 `command not found`——
   **那是「沒量到」，不是「量到 0」**（鐵律 3）。要先 `apt install fontconfig`。

## 不是 Linux 問題的（避免誤判）

- 兩處撞版（跨場景「機制模擬」徽章＋大框、路由拍的「開」圓圈壓字）**沒有重報**，
  另一條線正在修。Linux 上沒有出現**不一樣**的版面問題：
  字型在的時候排版與 Mac 一致，1920×1080 與 430×932 都沒有溢出。
- `world3/data/replay_371.json` 與 `world3/sprites/cast40/manifest.json`
  **在 http 下也是 404**——`world3/data/` 這個目錄**在 Mac 的工作樹裡就不存在**，
  `sprites/` 是空的。這是既有狀態，不是搬運掉的。活模式不吃這兩個檔，
  頁面 `page errors` 是 `[]`，所以現在看不出問題；**但獨立重放模式會少東西。**

## 交付

- `ops/exhibit/twin/venue_check.sh` — 布展當天一行自驗，**只讀不寫、零模型呼叫**。
  七節：端點活著／電視頁拿得到／輪播自己在動（實際等一個 dwell 再比 `emitted`）／
  有沒有格子被 D2 擋下／中文字型／零外網／`--lan` 有沒有配 token。
  硬傷 → exit 1。已在 Linux 上跑過成功與失敗兩條路徑。
- 本檔。

`venue_check.sh` 自己的誠實邊界寫在它的結尾：它證明的是「端點活著、輪播在動、
字型在」，**它不驗簽章，也沒有看畫面長什麼樣**——那要人真的站到電視前面看一眼。

## 布展前必須做的事

1. **裝中文字型**：`sudo apt install -y fonts-noto-cjk fonts-noto-cjk-extra`，
   然後 **`fc-cache -f` 並重開瀏覽器**。沒有這一步＝滿畫面豆腐字。
   （可選：要完全比照設計就把 Bold 補齊。）
2. **裝 `fontconfig`**（`fc-list`／`fc-match`），否則 `venue_check.sh` 第五節
   只能回報「量不到」。
3. **把 `vacant/` 一起搬**，並確認 `python3 -c "import cryptography"` 過。
4. **起完一定要跑 `./venue_check.sh`**，不要只看 `exhibit_boot.sh` 的橫幅。
5. **`--lan` 一定要配 `--token`**；或改用獨立熱點。
6. **不要雙擊 `index.html`**。一定要走 `exhibit_boot.sh` 的本機 http server，
   否則會得到一個「看起來在動、其實沒有場景」的半活頁面。
7. 要無人值守全螢幕的話，**`--kiosk` 的 Linux 分支還沒有人寫**，得自己下
   `chromium --kiosk`（並加上關掉背景連線的旗標）。

## 還不能說的話（沒驗到的，以及為什麼沒驗到）

1. **沒有量過「一整天」。** 最長連續 21 分鐘。RSS 在那 21 分鐘裡從 32.3 MB 長到
   33.0 MB。**那個斜率不能外推成 8 小時或 3 天**——21 分鐘看不出慢速洩漏、
   看不出 `skipped` 長期累積的實際影響、也看不出 canvas 長時間跑的記憶體行為。
   **「21 分鐘沒事」不等於「一天沒事」。**
2. **沒有在真的展場機上跑過。** `vacant-dev` 是一台 8 核 7.9 GB 的 VM，
   **沒有 GPU、沒有實體螢幕、沒有觸控**。畫面是 headless Chromium 的
   `Page.captureScreenshot`，**不是投到電視上拍的照片**。
   真機的解析度、縮放、觸控、GPU 合成、螢幕比例**全部沒驗**。
3. **沒有真的用手機連過。** `--token` 是用 `curl` 驗的，
   `--lan` 綁 `0.0.0.0` 之後**手機在區網上實際連線的行為沒有測**
   （也沒測熱點、沒測多支手機同時按）。
4. **沒有測真人操作。** 沒有人連續亂按、沒有兩個人同時按、沒有按到一半走掉。
   `/control` 的併發行為**沒量過**。
5. **沒有測斷電重開。** 展場最常見的事故是拔插頭，**開機自動啟動這條線沒有做，
   也沒有測**（沒有 systemd unit）。
6. **`venue_check.sh` 的第四節（D2 警告路徑）沒有在真的壞資料上跑過。**
   D2 本身用探針驗過了，但 `venue_check.sh` 印出「有 N 格被擋」的那一段
   只在 `skipped` 為空的情況下跑過。
7. **沒有驗簽章這件事本身沒變。** 事件流沒有簽章、`/state` 不是信任來源。
   收據頁在 Linux 上確實把 19 條鏈 41 筆簽章驗過了，但那是**那一份 pack 的**
   ——另一條線正在收官的 56 格真跑資料**還沒在 Linux 上驗過**。
8. **`--kiosk` 完全沒有在 Linux 上驗過**，因為它在 Linux 上根本不執行。
9. 裝了 chromium 之後 **`vacant-dev` 只剩 3.0 G 磁碟**。這是我的施工造成的，
   不是展場機的狀態，但這台要繼續跑別的東西的話要注意。

## 不影響本次結論的施工痕跡

- `vacant-dev:~/exhibit-linux/`（63 MB）＝這次搬過去的那一份，**是複本，不是 clone**，
  沒有 git 歷史。要清就整個刪。
- `vacant-dev:~/exhibit_linux_evidence_20260919/`（8 MB）＝六張截圖與 SHA256。
- `vacant-dev:~/{cdp_shot_stdlib,cdp_burst_stdlib,cors_probe,cors_probe2}.py`、
  `~/exhibit-linux/Vacant/d2_probe.py` ＝探針，**沒有進 repo**。
- 為了截圖 `sudo snap install chromium`、為了量字型 `sudo apt install fontconfig`。
- **展件的內容與措辭一個字都沒有改。** 這一輪驗的是「搬得動、跑得起來、不掛」。
