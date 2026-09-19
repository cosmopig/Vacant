# DECISION 2026-09-19／20 — 展件「無人值守」剩下的四塊

> 做於 2026-09-19 深夜～09-20 凌晨。目標機器 `vacant-dev`＝`user1@100.124.254.83`
> （Ubuntu 24.04.3、kernel 6.8.0、Python 3.12.3、chromium snap 3529）。
> 上一份：`DECISION_20260919_EXHIBIT_LINUX.md`（整條線搬到 Linux 上跑過一次）。

## 一句話

四塊都做了、都在 Linux 上跑過。順手挖出**兩個原本會在布展當天才現形的 bug**
（`exhibit_boot.sh --lan` 在 Linux 上 exit 1 一個字都不印；直式螢幕整個版面爛掉），
以及**一件不能說的話**（「零外網」對展件成立，**對瀏覽器不成立**）。
**沒做的是整機重開機**——理由在 §六。

---

## 一、`--token`：選「自動生」，不是「拒絕啟動」

### 判斷與理由

**`--lan`（非 loopback 綁定）沒給 token 就自動生一把**，編進 QR 的網址裡；
要關掉得明講 `--no-token`。

為什麼不是「拒絕啟動」——理由只有一條，但它是決定性的：

> **拒絕啟動預設有一個站在鍵盤前面的人。無人值守的開機流程沒有那個人。**
> 第二塊做完之後，展件是 `systemd` 拉起來的。拒絕啟動 ＋ `Restart=always`
> ＝ 每 10 秒失敗一次、一整天都失敗，而**畫面上看不出來**（電視只是黑的）。
> 那正好是第二塊要消滅的失效模式。

自動生達成的是**同一個保證**——「不存在沒有門檻的區網監聽」——代價只是
token 每次開機會換，而那個代價落在「上一次開機留下來的舊分頁」身上，
成本是一次 403 ＋ 一句「請重新掃電視上的 QR」。

而且 token 的唯一入口本來就是 QR（觀眾不打字），所以自動生對觀眾是**零成本**。

### 口徑（這條比實作重要）

**這不是身分驗證。** token 就印在電視上，拍一張照就帶得走。
它擋掉的是「連上同一個 hotspot、但沒站在展件前面」的人，**不是現場的人**。
不要把它讀成授權、防竄改或「只有我們能控制展件」。
這句話逐字寫進 `serve_twin.py` 的誠實邊界 §3、開機橫幅、與
`resolve_token()` 的 docstring。

### 一個差點做錯的設計

第一版的分流規則是「**對端是不是 127.0.0.1**」。那會在展場當天才炸：
電視開的網址是 `?live=http://<區網IP>:8899/...`，QR 那張圖也是
`http://<區網IP>:8899/qr.png` ⇒ 瀏覽器連到**自己這台機器的區網位址**時，
核心挑的來源位址是那個區網位址、不是 127.0.0.1 ⇒
**電視自己會被當成外人，畫出來的 QR 沒有 token，全場一顆鍵都按不動**。

改成 **「對端位址 ＝ 本端位址」**（`Handler._is_same_machine`）。
兩種接法（127.0.0.1 與區網 IP）都成立。

### 改了什麼

| 檔 | 改動 |
|---|---|
| `ops/exhibit/twin/serve_twin.py` | `resolve_token()` 純函數（四條規則）；`--no-token`；`Stage.token`＋`phone_url(with_token=)`；`state(with_token=)`＋`control_token_required`；`Handler._is_same_machine`；`/control` 三處收 token（body／query `t=`／`X-Twin-Token`）＋`secrets.compare_digest`；橫幅逐條講明 |
| `ops/exhibit/twin/phone.html` | 從自己的網址讀 `?t=`，帶進 `POST /control`；403 改講「這個連結過期了——請重新掃電視上的 QR」 |
| `ops/exhibit/twin/exhibit_boot.sh` | `--token`／`--no-token`／`VACANT_TWIN_TOKEN`；`--lan` 沒給就自己生（**由這一支生，不交給 serve_twin**——QR 與橫幅都是這一支印的，兩邊各生一把＝橫幅印 A、伺服器認 B） |
| `ops/exhibit/twin/venue_check.sh` | 第七節從 `warn` 升成**硬傷**；加「電視這一端拿不拿得到 token」 |
| `tests/test_serve_twin.py` | 8 條新判準 |

### 量到什麼（vacant-dev，`--lan`、systemd 拉起來的那一份）

```
本機 127.0.0.1  /state.phone_url  → http://192.168.76.135:8899/phone.html?t=bu44Ccd0qKXI
本機經區網位址  /state.phone_url  → …?t=bu44Ccd0qKXI      ← 電視就是這樣連的
POST /control 不帶 token          → 403
POST /control 帶錯                 → 403
POST /control 帶對                 → 200
```

**從另一台機器**（Mac，經 Tailscale 打 `100.124.254.83:8899`）：

```
/state.phone_url            → http://192.168.76.135:8899/phone.html   ← 沒有 t=
/state.control_token_required → true
POST /control 不帶 token     → 403
```

電視畫面上也確認了（`standby_live_1920.png`、`tv_1920x1080.png`）：
QR 底下那行字是 `192.168.76.135:8899/phone.html?t=xOmAx0x0t1Xn`——**token 在 QR 裡**。

### 還不能說的話

- **沒有用真的手機掃過那張 QR。** 驗到的是「QR 的內容＝帶 token 的網址」
  （`test_qr_encodes_the_runtime_phone_url` 逐 byte 比對）與「帶對 token 會 200」，
  **不是**「某支手機掃進去按得動」。
- **`venue_check.sh` 量不到「token 會不會外流給區網上的其他人」**，因為它跑在
  展場那台機器上，而判準是「對端＝本端」⇒ 從自己打自己一定拿得到 token。
  那一條現在明寫「沒量到，要拿另一台裝置」（鐵律 3）。上面 Mac 那一組是我手動補的，
  **它不是 `venue_check.sh` 的一部分**。
- token 在網址裡 ⇒ 會進瀏覽器歷史、會被截圖帶走。**設計如此**，不是疏漏。

---

## 二、開機自動啟動

### 形狀

```
vacant-exhibit.service          system unit、開機起、不需要有人登入
  ├ ExecStartPre  exhibit_preflight.sh     缺什麼就擋下來並寫進 journal
  └ ExecStart     exhibit_boot.sh --lan    （裡面是 8420 靜態站 ＋ 8899 展件伺服器）

vacant-exhibit-kiosk.service    **user** unit、要圖形工作階段（全螢幕瀏覽器）
```

**為什麼分兩支**：伺服器那一半不需要有人登入就能活；瀏覽器需要一個圖形工作階段。
綁在一起＝伺服器也要等登入，而登入是展場最容易壞的一環
（自動登入被關掉、螢幕鎖、更新後停在密碼畫面）。

### 四個必答題

| 題 | 怎麼處理 | 為什麼 |
|---|---|---|
| **字型** | 開機時**只警告不擋**；`install.sh` 時**擋**；`venue_check.sh` 第五節維持硬傷 | 開機的時候沒有人能去跑 apt。**豆腐字的展件比黑畫面近可用得多**。裝的時候有人在——那是最後一個「有人站在鍵盤前面」的時刻 |
| **`cryptography`** | 開機時**硬擋**（preflight 直接 `import serve_twin`，不逐個猜套件名） | 它根本起不來。`serve_twin` 自己只有 stdlib，但 `to_events` 會拉 `vacant_network.logbook`（2026-09-20 的 `fb7f4bfb` 把套件從 `vacant` 改名成 `vacant_network`；preflight 不受影響，因為它 **import 真正要跑的那一支**、不逐個猜套件名） ⇒ `cryptography`（原生 wheel，乾淨的展場機不保證有） |
| **埠被佔** | 佔用者的 cmdline 對得上 `serve_twin.py`／`http.server` ⇒ `VACANT_EXHIBIT_KILL_STALE=1` 砍掉重來（unit 裡預設開）；**對不上就失敗並印出 pid 與 cmdline** | 「上一次開機留下來的自己」是真實情境；「別人的服務」不是展件可以拿來當理由去砍的東西 |
| **失敗要不要重試** | `Restart=always`＋`RestartSec=10`＋**`StartLimitIntervalSec=0`** | 預設是「10 秒內失敗 5 次就永久放棄」。開機時網路還沒好正好會連續失敗 ⇒ 放棄之後**一整天都不會再起來，而且只是黑的**。展場要的是「一直試」 |

### 量到什麼

**A. preflight 真的擋下了一個真的問題（不是演的）。** 第一次 `install.sh --now`
就紅了：8899 被上一個 session 留下來的一支測試 socket 佔著，cmdline 對不上白名單
⇒ 拒絕啟動、把 pid 與整串 cmdline 寫進 journal。

**B. 擋住之後它自己一直試，障礙清掉就自己起來——沒有人碰它。**
`NRestarts` 從 2 一路到 9，`is-active` 全程是 `activating`（**不是 `failed`**）；
把那支佔埠的行程砍掉之後，下一輪 preflight 五條全綠、`Started`。

**C. 開機時網路還沒好的那一種**（用 drop-in 灌 `VACANT_LAN_IP=169.254.7.7` 模擬）：

```
抓不到可用的區網 IP（抓到 '169.254.7.7'）。
手機會連不到 ⇒ **不啟動**，免得展場掛一張掃不開的 QR。
status=2/INVALIDARGUMENT → Scheduled restart → 一直試
```
把 drop-in 拿掉、`daemon-reload`，**沒有再下任何 start 指令**，
它在下一輪自己 `active`，`/state` 200、`phone_url` 帶著一把新的 token。

**D. 當掉會自己回來。** `kill -9` 主行程 ⇒ 14 秒後 `active`、`/state` 200。

**E. `systemctl stop` 之後沒有孤兒。** 8420／8899 都空了（`KillMode=control-group`）。
這一條很重要：孤兒正是下一次開機「埠被佔」的來源。

**F. `is-enabled` ＝ `enabled`，symlink 在 `multi-user.target.wants/`。**

**G. 起來之後 `venue_check.sh` 七節全過**（硬傷 0、5 條 warn，見 §五）。

### 還不能說的話

- **沒有真的重開機。** `vacant-dev` 上有兩個人類留著的長壽 session
  （`claude --resume win1003` 17 天、另一個 29 天），重開會把它們一起帶走。
  我驗到的是「enabled ＋ 同一條 ExecStart 路徑起得來 ＋ 失敗會一直重試 ＋
  障礙清掉會自己起來 ＋ 當掉會自己回來」；**沒驗到的是開機時序本身**
  （`network-online.target` 到位的時機、snap／VMware 服務的先後）。
  人類要補的一行：`sudo reboot`，回來之後
  `systemctl status vacant-exhibit && ops/exhibit/twin/venue_check.sh`。
- **kiosk 那一支（`vacant-exhibit-kiosk.service`）完全沒驗。** `vacant-dev` 沒有
  圖形工作階段（`DISPLAY` 是空的、沒有 Xorg／Wayland），所以那個 unit 是**寫出來的，
  不是量出來的**。它的兩個已知陷阱寫在檔案裡：
  (a) `loginctl enable-linger` **不會給你圖形工作階段**，自動登入必須另外開；
  (b) ExecStartPre 會等電視那一頁回 200 才開瀏覽器（否則一張錯誤頁停在那裡不會自己重整）。
- **`install.sh --kiosk` 的 user unit 安裝路徑沒跑過。**

---

## 三、其他解析度的版面

工具：`~/cdp_shot_stdlib.py`（vacant-dev 上，零依賴 CDP 截圖）對著跑起來的
headless chromium（`--remote-debugging-port=9223`）截。
截的是**真的在跑的展件**（systemd 拉起來那一份 ＋ 活模式事件流）。

### 結果

| 解析度 | 比例 | 待機／引導 | 故事（監視器那一種） |
|---|---|---|---|
| 1920×1080 | 16:9 | ✅ 乾淨（基準） | ✅ 乾淨 |
| 2560×1080 | 21:9 | ✅ 乾淨 | ✅ 乾淨 |
| 3840×2160 | 16:9 4K | ✅ 乾淨 | 沒截到 |
| 1280×1024 | 5:4 | ✅ 可用（網址那行貼到陶板邊） | 沒截到 |
| 1024×768 | 4:3 | ✅ 可用 | ⚠ **三處重疊**（下面） |
| 1080×1920 | 直式 | ⚠ 修過，剩一行擦邊 | ❌ **整個爛掉** |

### 找到什麼

**1）直式：整個覆蓋層系統以 `H` 為尺規。**
所有座標都寫成 `H*0.04`、`H*0.235`、`s = H*0.165`。在 16:9 上剛好，
螢幕一變窄 `H` 就變成一個**跟可用寬度無關的大數** ⇒ 元素全部漲大、互相疊死。
待機頁的症狀：左上角那張 QR 漲到 317px、蓋住副標「用你自己的手機就好」，
底下的網址整行橫跨畫面壓在陶板上。故事頁更糟：大標、監視器、案例橫幅、字幕**全部疊在一起**。

**修了哪一塊**：`drawQrCorner` 改吃 `uiScale() = Math.min(W, H)`。
選 `min(W,H)` 而不是 `min(H, W*9/16)` 的理由是**零回歸**：
任何橫式螢幕 `W>H ⇒ min＝H`，所以 1920×1080／1024×768／1280×1024／2560×1080／
3840×2160 **逐像素與舊版相同**（4:3 的截圖前後比對確認過）；只有直式才換尺規。
實測 1080×1920 下 QR 從 317px 變 178px（掃得到、不蓋副標）。

**沒修的**：故事頁在直式下的其餘覆蓋層。那要把整套尺規換掉（~40 支繪圖函數裡的每一個
`H*`），是另一件事，而且會動到已經驗過的 1920×1080。

**2）4:3 的故事頁有三處重疊**（`story_1024x768.png`）：
證據橫幅「AI 真的動手了」壓到置中大標的前半；
監視器裡「關掉這層有收據嗎／沒有（那一臂不簽收據）」標籤與值互相疊；
底部字幕與副字幕貼在一起。**這三處在 1920×1080 與 2560×1080 都不存在**。

### 給布展的一句話

> **展場螢幕請用 16:9 或更寬。** 1920×1080、2560×1080、3840×2160 三種都驗過乾淨。
> 4:3／5:4 待機可用、故事頁會疊字；**直式不要用**。

### 順手驗到的（不是這一塊的目標）

- 手機頁在 390×844 與 360×640 兩種尺寸都乾淨（`phone_*.png`）。
- 收據頁在 1024×768 正常（`viewer_1024x768.png`）。
- **中文字型**：`sudo apt install -y fonts-noto-cjk fonts-noto-cjk-extra` ＋ `fc-cache -f`
  之後 `fc-list :lang=zh` 從 2 變 82，所有截圖一個豆腐字都沒有。

### 證據落在哪

vacant-dev `~/shots_20260919/`，以及本機 `~/vacant-exhibit-shots-20260919/`（27 張 PNG）。
sha256 逐張如下（節錄，關鍵四張）：

```
42569dd1b67bba412956583bc72928b6ebcd3b12fb8deb4a68dd586f75fc0e31  tv_1920x1080.png       基準
87c82ecbb8af3710e0c259d8eff3d17fc64831e040f3ee92a84d4b99e68866c2  tv_1080x1920.png       直式（修之前）
8996b035d15886613dc1ada3a36a198eafacf43141183778ab5e9979f1f4dc11  v3_1080x1920.png       直式（修之後）
e8bc362d300815d879773cf3cf8aae46271fd082941916c745e6953826650113  story_1080x1920.png    直式故事頁＝爛掉的那張
6da19df9a81ce964fde3d3082217c8b2ee33fbfd21b55882be595ee616ffe7b5  story_1024x768.png     4:3 三處重疊
583ca23a72002756833ebd0bb9cc08945bcb12ffc19cc6cb27eaf431a44df173  standby_live_1920.png  活模式待機＝27
a2d674fadef1ea547a009d3574cc0b4f96dbc5f3b66c81157039853c5060f8f9  standby_frozen_1920.png 凍結重放待機＝371
```

### 還不能說的話

- **沒有在真的螢幕上看過。** 全部是 headless chromium 的 `Page.captureScreenshot`，
  `deviceScaleFactor=1`。真展場的電視有自己的 overscan、色溫與可視距離——
  那三件事**一件都沒量到**。
- 4K、5:4 只截了待機，**故事頁沒截**。
- 每一種解析度只抓了**一兩幀**。輪播 27 對 × 兩邊 × 十幾拍，我沒有掃過全部組合，
  所以「乾淨」的範圍僅限於截到的那幾幀。

---

## 四、`371` 的出處

### 查到什麼（不是編的）

`world3/data/replay_371.json`（→ `world2/data/replay_371.json`）的 `source` 欄：

```json
{"on_run":  "runs/g_onoff5_371_r123_20260825",
 "off_run": "runs/g_off371_20260825",
 "model":   "qwen/qwen3.6-35b-a3b",
 "note":    "每一格都是實驗當時落盤的原值，未經加工"}
```

對照 `runs/INDEX.md`：兩個 run 都是 **2026-08-25、MBPP+ v0.2.0、371 題**
（同一份題庫 R529 也在用，`runs/INDEX.md` §二列成「MBPP+ 371 題」）。
檔案裡 `tasks` 陣列剛好 **371** 筆。
**371 對得上，而且對得上的是那一批凍結重放。**

展件的 54 格是**另一批**：`twin_pack.json` 的 `source.runs` ＝
`runs/twin_real_20260919`，2026-09-19、`vacant run` 真跑、
三位合成居民 × 9 題 × 兩種題面 ＝ 54 格（27 對）。

### 那一句話

> **兩批都是跑完落盤的真紀錄，但不是同一批，也不是子集。**
> 371 ＝ 2026-08-25 的 MBPP+ 371 題（`qwen3.6-35b-a3b`），電視**凍結重放**的資料源；
> 54 格（27 對）＝ 2026-09-19 的 `vacant run` 真跑，手機能導播的那一批。
> 題庫、模型、跑法、日期全都不同；共同點只有「未經加工」。

### 怎麼處理（改文案，但改得最小）

舊版把 371 **寫死**在 `SCENES.s00.sub`。凍結重放下那句話是對的；
活模式下它先說「走過 371 件真實任務的一群人」、接著演 54 格
⇒ **觀眾會以為眼前這些格就是那 371 件**。那不是措辭問題，是一句
**在活模式下為真的東西作不實見證**的話。

改成數字由**現在載進來的那一批**算出來（`standbySub()`，放在
`LIVE-BEGIN…LIVE-END` 的純函數區，所以可執行地測得到）：

- 凍結重放 ⇒ `REPLAY.tasks.length` ＝ **371**，**與舊文案逐字相同**
- 活模式 ⇒ `/state.pairs.length` ＝ **27**
- 兩邊都還沒載進來 ⇒ 不給數字（「走過真實任務的一群人」）

畫面上確認過：`standby_frozen_1920.png` 印「走過 371 件真實任務的一群人」、
`standby_live_1920.png` 印「走過 27 件真實任務的一群人」。

判準：`vacant_hm/tools/livecheck.mjs` **L19／L19b／L19c／L19d**。
出處寫進 `world3/SPEC.md`（S0 那一節）與 `world3/docs/LIVE_INTERFACE.md`。

### 還不能說的話

- **「27」是我選的計數單位**（＝`(居民, 題)` 的組合數，每組跑兩次＝54 格）。
  它為真，但它不是從舊文案推出來的——舊文案的「件」在凍結重放那邊指的是
  `tasks` 一筆（一題）。**兩個「件」不是同一個單位**，只是在各自的資料裡都成立。
  要不要改成講「54 格」是人的決定，不是我能替展覽決定的。
- `runs/twin_real_20260919` 在 `runs/INDEX.md` 裡是 `0／0`（不是 `real_run`）。
  那一批的證據在 `DECISION_20260919_TWIN_REAL_RUN.md`，**不在 INDEX 的 98 個 real_run 裡**。

---

## 五、順手挖出來的東西（都會在布展當天咬人）

### 1. `exhibit_boot.sh --lan` 在 Linux 上 exit 1，**一個字都不印**

兩個坑疊在一起：

- 介面名字寫死成 `en0 en1 eth0 wlan0`，而 `vacant-dev` 的網卡叫 `ens33`
  ——名單全部落空。展場機叫什麼**沒有人保證得了**。
- 更糟的是那一行 `LAN_IP="$(ip -4 -o addr show "$IF" … | head -1)"` **沒有 `|| true`**，
  而這支腳本開著 `set -o pipefail`：`ip` 對不存在的介面回 1 ⇒ 整條管線回 1 ⇒
  `set -e` 當場結束腳本 ⇒ **exit 1、零輸出**，連下面 `hostname -I` 的退路都走不到。

在 systemd 底下的症狀就是每 10 秒重啟一次、journal 裡只有 `status=1/FAILURE`。
**改成列出真的存在的 global scope IPv4**，並跳過 `tailscale`／`docker`／`veth`／
`br-`／`virbr`／`zt`／`wg`。另外加一條：抓到 `100.64.0.0/10`（CGNAT，Tailscale 住那）
會**警告**——展場 hotspot 上的手機連不到那種位址，QR 會掃不開。

> ⚠ 這與 `DECISION_20260919_EXHIBIT_LINUX.md` §1 的記載不一致：那一份寫
> 「`ipconfig getifaddr en0` 會失敗、**正確 fall back 到 `hostname -I`**，量到
> 192.168.76.135」。在**今天這台同一台機器**上它 exit 1。
>
> **（2026-09-20 補：查到了。）** 前一份**沒有跑過 `--lan`**。
> `BIND=0.0.0.0` 那一整塊只有加 `--lan` 才會執行，而那一次跑的是不帶 `--lan`
> 的版本——腳本最後印的是「⚠ 只綁本機：手機連不到。展場要用 --lan。」。
> ⇒ 那句「正確 fall back 到 `hostname -I`」是**讀碼讀出來的描述**。
> 那段邏輯讀起來完全合理，但**從來沒有被執行過**。
> 機制側也實測對上了：這台只有 `lo`／`ens33`／`tailscale0`，
> `ip -4 -o addr show en0` 回 1，`set -euo pipefail` 底下當場斷掉。

### 這一條要留下來的不是教訓，是判準

> **從讀碼描述一條路徑，不等於量過它。**

一句教訓會被下一個人讀過去；一個**跑得起來的判準**不會。所以這一輪順手補上：

| 補了什麼 | 它擋住什麼 |
|---|---|
| `exhibit_boot.sh --print-host` | 讓那一段偵測**單獨跑得起來**（以前它只能連著整條線一起跑，所以沒人跑過）。離開碼是契約：**0**＝抓到並印出來、**2**＝抓不到但說了為什麼、**1**＝不該出現 |
| `exhibit_preflight.sh --lan` | **每一次開機都把它跑一遍**，結果寫進 journal（`✓ 區網 IP 抓得到：192.168.76.135`）。unit 的 `ExecStartPre` 已經帶著 `--lan` |
| `tests/test_serve_twin.py` 四條 | 釘的是**離開碼的契約**不是「抓到哪個位址」（那跟跑測試的機器有關，釘不得）：`--lan` 只准回 0 或 2；回 2 一定要有 stderr；不能用的位址（`169.254.*`）要回 2 ＋ 講理由；**程式碼裡不准再出現 `eth0`／`wlan0`**，而且 `ip …` 那條管線一定要有 `\|\| true` |

⚠ 最後那一條測試只掃**非註解行**。解釋這個 bug 的註解裡本來就會寫 `eth0 wlan0`，
那段字**應該留著**——把註解一起掃進來，判準就會逼人刪掉歷史才會綠，
那是拿判準去換紀錄。

在**出事的那台機器上**（沒有 `en0`、介面叫 `ens33`）逐條驗過：
`--lan --print-host` → `192.168.76.135` exit 0；不帶 `--lan` → `127.0.0.1` exit 0；
`VACANT_LAN_IP=169.254.7.7` → exit 2 ＋ 三行理由；
重裝 unit 之後 journal 裡每次啟動都看得到那一行。

### 2. 「零外網」對展件成立，**對瀏覽器不成立**

展件本身乾淨（`serve_twin`／`to_events` 連 `urllib` 都沒 import；
上一份用 network namespace 證過）。但**瀏覽器自己會對外連線**：
一顆乾淨的 snap chromium 起來就有
`google_apis/gcm/engine/registration_request.cc … DEPRECATED_ENDPOINT`。

加上 `--disable-background-networking --disable-component-update
--disable-domain-reliability --disable-sync` 之後，log 裡那類訊息從 6 行降到 1 行，
**但 `ss` 仍然數得到 5 條到 Google 的 ESTAB**（含 GCM 的 5228）。

⇒ **旗標是減害不是解法。** 真正的離線保證只能來自「機器根本沒有外網」或防火牆。
`venue_check.sh` 第六節數到的「對外連線」多半就是這幾條，它的措辭本來就是
「可能是瀏覽器自己在連」——**那句話是對的，現在有數字了**。
旗標已經寫進 kiosk unit，理由也寫在裡面。

---

## 六、沒做的事，以及為什麼

| 沒做 | 為什麼 |
|---|---|
| **整機重開機** | `vacant-dev` 上有兩個人類的長壽 session（17 天、29 天）。開機時序是唯一沒驗到的一段，人類補一行 `sudo reboot` 即可 |
| **kiosk unit 實測** | `vacant-dev` 沒有圖形工作階段 |
| **真手機掃 QR** | 手邊沒有第二台裝置接同一個區網 |
| **直式故事頁修到好** | 要換掉整套 `H` 尺規（~40 支繪圖函數），會動到已驗過的 1920×1080。結論是「不要用直式」 |
| **4K／5:4 的故事頁截圖** | 只截了待機 |
| **真螢幕上看** | 全部是 headless 截圖；overscan／色溫／可視距離一件都沒量 |
| **`install.sh --kiosk` 的安裝路徑** | 沒跑過 |
| ~~**為什麼 EXHIBIT_LINUX 那一次 `--lan` 會過**~~ | **2026-09-20 查到了**：那一次**沒有跑過 `--lan`**，紀錄裡那句是讀碼讀出來的。見 §五-1 |

## 七、紅線自查

- **零模型呼叫**：這一整條線一通都沒打。`serve_twin`／`to_events` 沒有任何
  對外 HTTP 客戶端（`venue_check.sh` 第六節那條 grep 仍然綠）；
  `_query_token()` 故意不用 `urllib.parse`，就是為了不去動那條擋門。
- **口徑**：新增的字沒有一處用「信任」。`phone_node_check.mjs` P5 仍然綠。
- **展件內容與措辭**：只改了 §四那一處，而且凍結重放下**逐字相同**。
  版面尺規（§三）不是內容也不是措辭，且在橫式下逐像素相同。
- **鐵律 3**：每一塊的「還不能說的話」都在上面，`venue_check.sh` 第七節
  把量不到的那一條改成明寫「沒量到」。

---

## 八、測試與機器留下來的狀態

### 跑過什麼

| 判準 | 結果 |
|---|---|
| `tests/test_serve_twin.py`（含 8 條新的） | 34 passed |
| `tests/test_qr.py`／`test_twin_events.py`／`test_twin_viewer.py`／`test_twin_fidelity.py`／`test_receipt_viewer.py` | 全過（改名前與改名後各跑一次） |
| `node ops/exhibit/twin/twin_viewer_node_check.mjs` | 全部通過 |
| `node ops/exhibit/twin/phone_node_check.mjs` | 全部通過 |
| `node tools/livecheck.mjs`（vacant_hm） | 全部通過（含新的 L19–L19d） |
| `node tools/live_e2e.mjs`（vacant_hm） | 全部通過 |
| `python3 ops/check_repo_links.py` | OK，沒有死連結／死路徑 |
| `ops/exhibit/twin/venue_check.sh`（vacant-dev，systemd 起的那一份） | **硬傷 0**、5 條 warn，exit 0 |

**全套 `pytest tests/` 我沒有看到它跑完。** 第一次跑到 ~8% 出現一個 `F`，
但那一輪是**被污染的**：跑到一半有另一個 agent 在同一個工作樹上落了
`fb7f4bfb`（`vacant` → `vacant_network`，659 個檔案），樹在腳底下被換掉。
事後把嫌疑檔案 `tests/test_ci_workflows.py`（依累計序號推出來的那一格）
單獨重跑，**12 passed**。⇒ 那個 `F` 我判定是 mid-run 改名造成的，
**但我沒有直接證據**（那一輪的 `-q` 輸出沒有測試名）。
穩定後重開的整套跑在背景，輸出在
`~/vacant-exhibit-shots-20260919/pytest_full_20260920.txt`。

> ⚠ 這一輪從頭到尾都在**跟另一個 agent 共用同一個工作樹**（記憶裡那條
> 「並行 agent 要用 worktree 隔離」）。我送出 commit 的時候 index 裡已經有
> 659 個不是我的檔案，所以兩個 commit 都用 `git commit --only -- <路徑>`
> 逐檔指定。`git show --name-only` 確認過：10 檔 ＋ 2 檔，沒有夾帶。

### vacant-dev 留下來的狀態（下一個人要知道）

- `vacant-exhibit.service` **enabled ＋ active**，佔著 `8420`／`8899`，
  30 秒輪播一格（現在 emitted 102、laps 1、skipped 0）。
  **這是刻意留著的**——它就是這一塊要驗的東西。擋路的話：
  `sudo systemctl disable --now vacant-exhibit`。
- `~/exhibit-linux/{Vacant,vacant_hm}` 是 2026-09-19 的快照，**不是 git checkout**，
  不會自己跟上 repo。
- 中文字型是**系統套件**了（`fonts-noto-cjk`＋`-extra`，82 個），
  不再是上一次那兩個手動丟進 `~/.local/share/fonts/` 的檔。
- 截圖在 `~/shots_20260919/`（27 張）。
- 我起的兩顆 headless chromium（9223／9224）已經收掉。

### 附帶回報：`fb7f4bfb`（`vacant` → `vacant_network`）打破了兩樣**凍結**的東西

不是我的改動，**我也沒有動手修**——重新祝福一個凍結的 pin 是人的決定，
不是清理工作。這裡只把量到的東西釘住，免得它變成「跑了但沒人回報」。

**1）全套 `pytest` 有 5 條紅的，跟展件零重疊，全部指向同一次改名。**
在**穩定後的樹**上單獨重跑仍然紅（所以不是 mid-run 污染）：

| 紅的 | 量到的理由 |
|---|---|
| `test_gain_harness_arms.py::test_t12_existing_arms_and_generate_are_byte_identical` | `arm_conform` 的 sha256 從 `b987a2fa…` 變成 `7f4d1e8b…`。那條 pin 的訊息是「**H 臂不准動既有臂**」。`ops/gain/harness_arms.py` 最後一次被改就是 `fb7f4bfb`，現在裡面有 8 處 `vacant_network` |
| `test_gain_harness_arms.py::test_visible_report_classifies_the_five_documented_outcomes` | 同一支 |
| `test_r449c_launcher_prereg.py`（2 條） | 測試逐字比對 R449c 那份**預註冊**裡的 `git diff … -- <四個檔>` 指令，而那份文件裡的路徑被改名改成了 `vacant_network/checks.py` |
| `test_cert_drift_gate_r477.py::test_selftest_passes` | `G.selftest()` 回 3（應為 0） |

> ⚠ 前兩條的份量不只是「測試紅了」。那條 sha256 pin 存在的理由是**跨 run 可比性**
> （同 CLAUDE.md 講 `suitemutate` 致死率不綁 `GaugeOutcome.ok` 的那個理由：
> 一綁，r452c 那批歸檔資料就失去可比性）。既有臂的位元組變了 ⇒
> **已經歸檔的 G 實驗 run 還能不能跟新的逐位元比，需要一個裁決，不是一次重新釘 hash。**
>
> ⚠ R449c 那兩條撞的是 CLAUDE.md 白紙黑字的規矩：「**各份預註冊檔內文裡的逐塊指令
> 是刻意不改的**——事後改寫它記載的指令等於讓紀錄描述一個沒下過的指令」。

**2）`docs/paper_2026-09-14/source_manifest.json` 的凍結 sha256 有 3 份**對不上了**——
不是漂了，是**那個路徑不存在了**：

```
釘了 29 份 → 對上 23、漂了 1、缺檔 5
  缺檔  vacant/logbook.py · vacant/canonical.py · vacant/codebench.py   ← 改名造成的
  缺檔  CONCLUSION_20260904_R445_… · CONCLUSION_20260904_R446_…        ← 2026-09-18 搬進 decisions/，與改名無關
  漂了  runs/INDEX.md                                                   ← 與改名無關
```

那三份 pin 現在**連驗都驗不了**。是要把 pin 指到新路徑（等於承認凍結的東西會跟著改名走），
還是別的做法，是人的決定。

**方法備註**：這兩件都是「我以為在跑全套 pytest」才撞到的。全套在這一輪
**從來沒有乾淨跑完過**——兩次都跑到一半被平行 agent 的 commit 換掉腳下的樹
（第一次是 `fb7f4bfb` 的 659 檔改名，第二次是 `8b309147` 刪掉 R481 夾具）。
**在共用工作樹上跑全套 pytest 不會得到可信的結果**，這件事本身也是一個結論。
