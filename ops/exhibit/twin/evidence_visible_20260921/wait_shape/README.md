# 等待態：給等待一個形狀（2026-09-21）

**要解決的那一格**：觀眾在手機上按下送出，走到電視前面，**畫面上一個像素都不會動**。
改動前 `world3/index.html` 的接線只有一行：

```js
WorldBridge.onSubmission(sub => spawnQueue.push(sub));
```

分身要真的生出來才有東西可以演。本 repo 落盤證據量到的真模型生成延遲是
**15.6–53.6 秒**（n=7，見第六節）。這段時間畫面上什麼都沒有。

**做的事**：等待本身變成畫面上的一件事——一團**屬於他的**黏土，在暖光底下被揉、
在心跳、慢慢長出他自己的輪廓；而且**永遠不會自己長完**。

> 🔴 這份 README **涵蓋兩輪**。
> **第一輪（08:37–09:02）** 寫出等待態本身，工作基底是**抵達層還沒併進來之前**的
> `index.html`（blob `427ce17`，3403 行）。證據編號 `01`–`50`。
> **第二輪（11:00–12:10，本輪）** 把它 rebase 到**已經有抵達層**的現行樹上、接好兩層
> 之間的接縫、用**真的來源鏈**重錄一遍，因此抓到兩個「第一輪測起來是綠的、
> 產品路徑上卻壞掉」的洞（第三節）。證據編號 `60`–`93`。
> **要引用就引用第二輪那一組**；第一輪留著是因為它是那兩個洞的標本。

---

## 一、判準（`CLAUDE.md`：觀眾走到展場前面時，這件事有沒有差別）

| 人類 2026-09-21 的四點 | 做法 | 證據（第二輪） |
|---|---|---|
| 1. 要有「屬於他的」東西在動，**不要進度條** | 成形曲線 `formingLevel` 是**漸近**的 `0.93·(1−e^(−t/26))`，顯影高度上限＝身高的 82.4% ⇒ **頭頂永遠埋在土裡**。造型／顏色／心跳相位全部從他的卡與不透明 id 折出來 | `60_seam_waiting_49s.mp4`、`71_ON_elapsed7s.jpg`（一小坨）→`72_ON_elapsed32s.jpg`（長出身體與手，頭還在土裡）、`80_motion_wait_window.json` |
| 2. 退化要分得出來 | `fallback_deterministic` ⇒ 黏土去飽和成冷灰藍、光柱換 `shaft_cool_*`、中央掛一張字卡，**措辭逐字沿用 `twinEngineNote`** | `73_DEGRADED_while_waiting_elapsed13s.jpg`、`62_degraded_while_waiting_29s.mp4` |
| 3. 超時／他走了怎麼辦（§5.1-7 退役程序） | 到 `centerS` 之後讓出整格、縮到右下角**繼續跳、繼續數秒**；到 `retireS`（預設 900 秒）演一段退役儀式：手收回去、土沉回去、字幕給結束一個形狀。**生成不取消**，後來成形的走正常佇列上台 | `61_phases_centre_corner_retire_45s.mp4`、`74_corner_card.jpg`（「三角鐵 還在成形 · 已經 27 秒 · 他好了就會上台」）、`75_retirement.jpg`、`84c_console_phases.log`（`退役完成（生成沒有被取消）`） |
| 4. 不要讓等待變成焦慮 | (a) 世界不停（旁邊的居民照常在做事）(b) 把時間講出來：「已經 32 秒 · 我們量過的是 16 到 54 秒」——**講已經多久，不講還剩多久**（後者我們不知道）(c) 超出量過的範圍就直說 (d) 心跳永不停 | `72_ON_elapsed32s.jpg`、`80_motion_wait_window.json`、`81_waitcheck_80.txt` 的 W3／W8 |

---

## 二、**接縫**：抵達層（另一個代理）與等待層怎麼分工

兩條線同一天各自落地在**同一個檔**，這一輪把它們接起來。分工是時間軸上的切割：

```
t=0      觀眾按下送出
         └─ bridge 輪詢（1000 ms 上限）→ WorldBridge.onSubmission
t≈0      arrivals.arrive(sub)        ← 抵達層：信飛進來、落進投遞口、旁邊的人轉頭
t≈1      （抵達層自己排的換景：切到郵筒那一幕）
t≈2.8    ARRIVE_HOLD 結束
t≈3.3    routeSubmission(sub) 從 backlog 取出 → director.startWaiting()
         └─ 等待層：光柱、黏土、成形中的輪廓、心跳、字卡
t≈16–54  分身真的生出來 → director.twinArrived() → spawnQueue → startVisitor()
         └─ arrivals.spawned(id) 把陶牌上那一列劃掉
```

介面**只有三個點**，全部寫在碼裡：

1. **`WorldBridge.onSubmission(sub => { arrivals.arrive(sub); routeSubmission(sub); })`**
   ——抵達層原本那一行的 `spawnQueue.push(sub)` 換成 `routeSubmission(sub)`，其餘一字未動。
   `routeSubmission` 在**所有**不適用等待態的情況（`?wait=off`、`twin.status` 讀不出來、
   分身已經有話了）都退回 `spawnQueue.push(sub)` ⇒ **抵達層的行為沒有被改到**。
2. **`arrivalsHolding()`**（新增，防禦式）——`routeSubmission` 與 backlog 排程都先問它。
   ⚠ 這一條是**併起來才會出現的坑**：`startWaiting()` 會 `enterScene("s04")`，而
   `arrivals.arrive()` 排了一次「落地後切到郵筒那一幕」的換景（`cutAt ≈ 0.97s`）。
   先開等待態的話那一刀會在一秒後把 s04 切掉，成形的土堆就落在別的景上。
   走 backlog ⇒ 抵達那 2.8 秒先演完；而那 2.8 秒畫面上是信在飛、在落、人在轉頭，
   **一秒都沒有空的**（`70_arrival_envelope_lands.jpg`→`70b_seam_handoff.jpg`）。
   backlog 的排程間隔同時從 1500 ms 降到 500 ms——抵達演完再讓觀眾多等最多 1.5 秒，
   在展場就是「信落下去了，然後畫面停住」。
3. **繪圖順序**：`drawForming()` 排在 `arrivals.draw()` **前面**。成形那一團是舞台
   地板上的東西；飛進來的信與陶牌是「剛剛發生的事」，要蓋在它上面才讀得出先後。

**兩層可以各自關掉，互不影響**（`77_NEGCTL_arrive_off.jpg`：`?arrive=0` ⇒ 沒有信、
沒有陶牌，等待態照常；`76_NEGCTL_wait_off.jpg`：`?wait=off` ⇒ 信照飛，等待態不開）。

演練（`?waitdemo=1`）也走同一個接縫（`arrivals.arrive()` ＋ `routeSubmission()` 兩句
逐字同形），否則演練看到的就不是觀眾會看到的那一段。

---

## 三、🔴 這一輪抓到的兩個洞：**測試綠 ≠ 接上產品路徑**、**讀不到等於沒講**

### 3-1 退化字卡在產品路徑上不會出現

第一輪那張退化截圖（`12_degraded_while_waiting.jpg`）是用 CDP 探針
（`43_degraded_probe.js`）生的，而那支探針**直接寫了 `w.sub`**。
產品路徑（`waitResolverTick` 讀本機快照發現 `engine === "fallback_deterministic"`）
只翻了 `cur.degraded` 與 `cur.rgb`，**沒有換掉 `cur.sub`**。而那張字卡的唯一來源是
`waitEngineBadge(w.sub)` ＝ `twinEngineNote(w.sub)`。

⇒ **真的走產品路徑的時候，黏土會變成冷灰藍、但「⚠ 他說的話是查表湊的，
這一次沒有模型參與」那一句不會出現。** 顏色變了而字沒出來，等於要觀眾自己看懂
顏色的意思——那正是展場版鐵律 5 要擋的事。

* 修法：`waitResolverTick` 那一支加 `cur.sub = sub;`（一行，碼裡有註解說明為什麼）。
* 修完：`73_DEGRADED_while_waiting_elapsed13s.jpg` —— 字卡出現，逐字等於 `twinEngineNote`。
* 判準：新增 **W11a–W11g**（含掃描負控制 W11d，與行為面 W11f／W11g：
  同一個人只差有沒有換 `sub` ⇒ 一邊 `null`、一邊有字）。

### 3-2 退役那一句讀不到

退役字幕「他先回到土堆裡 · 帳本上留著『還沒成形』，沒有被丟掉也沒有被演成完成」
是整段等待態**唯一一句誠實承諾**。它原本走 `drawTitle` 的副標（0.82 不透明度細字），
而退役儀式的背景正好是光柱＋塵：`75b_retirement_BEFORE_no_plate.jpg` 實拍，
**中段整句被洗掉**，只剩頭尾讀得出來。

* 修法：退役那一句改走 `waitPlate` 的底板（這個 repo 對「讀不到等於沒講」已有前例：
  監視器底下那一欄、右下角帶 ⚠ 的那一行都補過底板）。大標照舊，**只有退役那一句**
  這樣做，平常那句時間不搶畫面。同一段字（`waitCaption(...).sub`），沒有第二份措辭。
* 修完：`75_retirement.jpg`。
* 判準：新增 **W12a–W12f**（含掃描負控制 W12f）。

### 3-3 這兩個洞的共同負控制

`83_waitcheck_NEGCTL_two_lines_removed.txt`：把 `cur.sub = sub;` 與
`waitPlate(d.waitPlateText, …)` 兩行拿掉重跑 ⇒ **W11c 與 W12b BROKEN、退出碼 1**。
這把尺抓得到這兩個 bug。

⚠ **怎麼抓到的**：第二輪不再用 CDP 探針，改成**扮演 `twinlink loop`**——
`44_drive_snapshot.py` 按時間改寫一份 `visitors_probe.json`，頁面那一側走的是
`bridge.js` 的 snapshot 那一層 → `deliver()` → `WorldBridge.onSubmission`，
跟展場真的有人投卡時**同一條碼**。`84a_console_seam.log` 裡的
`WorldBridge 已啟動 · 來源鏈 snapshot=live/visitors_probe.json` 是那條路的憑據。

---

## 四、視覺的負控制：**把它關掉，看得出差別**

| | 開 | 關（`?wait=off`） |
|---|---|---|
| 靜照 | `71_ON_elapsed7s.jpg`／`72_ON_elapsed32s.jpg` | `76_NEGCTL_wait_off.jpg` |
| 影片 | `60_seam_waiting_49s.mp4` | `64_NEGCTL_wait_off_22s.mp4` |
| 投卡後畫面上是 | 「手風琴 正在成形 · 已經 7／32 秒 · 我們量過的是 16 到 54 秒」＋一團在跳的黏土 | 「**世界多了一個人 / 那是你託付的需求**」——已經在演故事了 |

🔴 **這張負控制順便抓到一個既有的誠實問題**：關掉等待態之後，那一筆
`arrival／working／handover／engine` **全是 `null`** 的投稿會被直接推進 `spawnQueue`，
電視於是對著一個**還沒生出來的分身**宣告「世界多了一個人」。
這不是本輪新增的 bug，是本輪之前就在的行為；等待態同時把它擋掉了
（`twinPending(sub) === true` 的那一筆不進佇列）。

另一組負控制 `?arrive=0`（`77_NEGCTL_arrive_off.jpg`）：抵達層關掉之後，
沒有信、沒有投遞口陶牌，**等待態照常開始**——兩層真的是分開的。

---

## 五、「它真的在動」是量出來的，不是用看的

`80_motion_wait_window.json`（產生器 `41_motion.py`）。判準＝相鄰兩格在同一塊區域的
平均絕對灰階差。**三條線缺一條這個數字就沒有意義**：

| 區域 | n | 最小 | 中位 | 低於 0.5 的格數 |
|---|---|---|---|---|
| `clay` 他那一團 | 73 | **1.71** | 5.19 | **0** |
| `ambient` 左上暗牆（空間對照組＝膠捲顆粒底噪） | 73 | 0.04 | 0.33 | 66 |
| `frozen` 同一格重複（**這把尺自己的負控制**） | — | — | **0.000000** | — |

判讀：純等待態那 **38.3 秒**裡**沒有任何一格**掉到底噪水準；clay 的中位數是 ambient 的
**15 倍**；而量法本身對真正靜止的輸入回傳精確的 0 ⇒ `verdict: MOVING`。
（`80b_motion_whole_capture.json` 是含前 10 秒待機／抵達的整段 49 秒，
 `clay` 那一塊在那段裡本來就有別的東西在動，所以**分開算、分開講**。）

⚠ **錄影幀率是錄影環境的限制，不是展件的幀率。** 這幾支影片是在
macOS headless Chrome（SwiftShader 軟體渲染）下錄的，本輪實測 rAF 1.3–4.8 fps。
影片是照**真實時間戳**組起來的（`42_mkvid.py` 用 `frames.json` 的 `t` 做 concat
duration），所以播放速度＝當時的牆鐘速度，只是格數少。

---

## 六、數字的出處（🔴 派工單上那兩個數字查不到出處）

畫面上印的「我們量過的是 16 到 54 秒」來自本 repo 落盤的真模型生成延遲，
`engine` 以 `lmstudio:` 開頭且不是合成樁 `fake-1003` 的那幾筆，**n=7**：

```
15633 / 19823 / 28241 / 33850 / 37463 / 40200 / 53561 ms
（min 15.6s · median 33.9s · max 53.6s）
```

* `ops/exhibit/twin/evidence_1003_20260920/12_visitors_from_1003.json`
* `ops/exhibit/twin/evidence_twinchain_20260920/11c_event_stream.json`
* `ops/exhibit/twin/evidence_1003_fallback_20260920/09_remote_roster_negative.json`

全部是 1003 上的 `lmstudio:gemma-4-12b-it-qat`，2026-09-20。

🔴 **派工單寫的「生成實測中位 312 秒、最長 727 秒」在兩個 repo 裡都查不到出處**：
`grep -rn "312 秒" / "727 秒" --include="*.md"` 在 `Vacant` 與 `vacant_hm` **都零命中**，
而全庫 `latency_ms` 的最大值是 **53561**。查不到出處的數字**沒有印在展場螢幕上**
（`waitcheck.mjs` 的 W9d 是這條的可執行防呆：畫面文字裡不准出現 312／727）。
如果那兩個數字有別的來源，請連同落盤路徑一起補進 `TWIN_WAIT.obs*` 的註解。
**設計本身沒有假設上限**：超過量過的範圍畫面會改口說「⚠ 比我們量過的最久那次還久 ·
他還在做，沒有卡住」（W8c），所以真的出現 727 秒也不會說錯話。

退役門檻 900 秒是**政策值不是量出來的**，程式碼裡有標。

---

## 七、可執行判準

`tools/waitcheck.mjs`（新檔，**刻意不動 `tools/livecheck.mjs`**——2026-09-21 同一天有
十幾個代理在改同一個 repo，新檔＝零合併衝突）。它把 `index.html` 的
`LIVE-BEGIN…LIVE-END` 整段抽進 `vm` 沙箱跑，加上三段原始碼掃描，**80 條全過**
（`81_waitcheck_80.txt`），其中**八條是負控制**：

* W2f／W2g：線性進度條、`ceil=1` 的曲線——判準必須抓得到
* W3e：把脈動綁成形程度（「會凍住」的實作）——判準必須抓得到
* W4e3：由前往後判階段的舊寫法——同一組參數下會答錯
* W7d：把觀眾原文塞進字幕——掃描必須抓到
* W10f：把一根 `fillRect(..., 200*lv, 8)` 塞進繪圖段——掃描必須抓到
* W11d：把 `cur.sub = sub` 拿掉——掃描必須抓到（第三節 3-1）
* W12f：把退役底板那一行拿掉——掃描必須抓到（第三節 3-2）

既有的 `tools/livecheck.mjs` **165 條仍然全過**（`82_livecheck_165_merged.txt`），
而**同一支尺跑現行未改的樹也是 165 條全過**（`82b_livecheck_165_baseline.txt`）
——這一對是「這次改動沒有把既有閘門弄紅」的對照，不是單邊宣稱。

---

## 八、怎麼把它裝上去

🔴 `~/Documents/GitHub/vacant_hm` 是**另一個 repo、正在運作的展件**，而且同一天有
十幾個代理在改。所以這一輪**沒有動那棵樹一個 byte**，交付物是 patch。

🔴 **不要直接 `patch -p1`。** 本輪親眼看到 `world3/index.html` 在 40 分鐘內被別人改了
三次；而 `patch` 對漂掉的基底會用 fuzz／offset **套到錯的位置、退出碼仍然是 0**
（實測：套完的檔跟預期的合併結果不相同，但 `patch` 說成功）。所以用附的 rebase 腳本，
它做的是**三方合併、有衝突就停下來**：

```bash
bash <此目錄>/92_rebase.sh ~/Documents/GitHub/vacant_hm
```

* 它會：以 `91_base_world3_index.html`（這份 patch 的基底，sha256
  `709d717d4da5c19e5ad0b6cb6d8e221e160def9cad2213ec7dec319daf85f807`）重建「等待態那一版」，
  三方合併到你當下那一份，放回去，然後跑兩把尺。
* 實跑紀錄：`93_rebase_run.txt`——對**已經又漂掉一次**的樹（sha `c6afedf4…`）
  仍然**零衝突**，waitcheck 80／livecheck 165 全過。
* 直接套 `90_vacant_hm_wait_shape_rebased.patch` 只有在
  `shasum -a 256 world3/index.html` 等於上面那個值時才安全。基底相符時，
  套用後的 sha256 ＝ `d545e75f4e73e8ffef77288d4ee64919d250f9400c45853e57c85a6f12415cb5`
  （4262 行 → 5270 行；`tools/waitcheck.mjs` 359 行為新檔）。
* **還原**：`patch -R -p1 < 90_…patch`（基底相符時逐 byte 還原，實測過），
  或 `git -C ~/Documents/GitHub/vacant_hm checkout -- world3/index.html`。
  ⚠ 反向套用會留下一個 0 byte 的 `tools/waitcheck.mjs`，要不要順手 `rm` 自己決定
  （那是 `patch(1)` 對新增檔的行為）。
* ⚠ `50_vacant_hm_wait_shape.patch`（第一輪那份）**已經套不上去了**：它的基底是
  抵達層併進來之前的 3403 行版本，對現行樹 9 個 hunk 有 2 個失敗、還有一個
  offset 354 行帶 fuzz 的——**不要用它**，留著只是紀錄。

網址參數（全部是現場調校／演練用，展場那條線一個都不帶）：

| 參數 | 意思 |
|---|---|
| `?wait=off` | **負控制**：整個等待態關掉 |
| `?arrive=0` | 抵達層的負控制（不是這一條的，但兩條要能互相關掉） |
| `?waitdemo=1` | 演練：自己生一位假訪客。**螢幕上全程標「演練模式 · 這不是真的觀眾投的卡」**，而且跟產品路徑一樣會先叫 `arrivals.arrive()` |
| `?waitready=<秒>｜fallback｜never` | 演練：幾秒後讓分身落地／退化那一條／永遠不落地 |
| `?waitretire=<秒>` `?waittau=<秒>` `?waitcenter=<秒>` | 退役門檻／成形時間常數／佔住整格多久 |

⚠ `TWIN_WAIT_OVERRIDE` **只准覆寫政策值**；`obs*`（量出來的那幾個）用網址改不動——
不然畫面上那句「我們量過的是…」隨時可以被路過的人改成任何數字。

---

## 九、重現（第二輪的錄法）

```bash
# 1. 一棵「現行樹 ＋ 這份 patch」的鏡像（不要碰 8420，那是展場那一台）
#    做法：把 vacant_hm 每個項目 symlink 進一個暫存目錄，只有 world3/index.html
#    與 tools/waitcheck.mjs 換成套過 patch 的實體檔，world3/live 換成可寫的複本。
python3 -m http.server 8437 --bind 127.0.0.1

# 2. 自己的 headless Chrome（**不要碰使用者那一個**，另開 port 與 user-data-dir）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --remote-debugging-port=9337 --window-size=1920,1080 --hide-scrollbars \
  --autoplay-policy=no-user-gesture-required --user-data-dir=<暫存> about:blank

# 3. 錄（45_run_cap.sh＝44_drive_snapshot.py ＋ 40_cap.mjs 同時跑）
Q=twinfile=live/visitors_probe.json
bash 45_run_cap.sh ./r_main     50 "$Q&waitcenter=999&waitretire=99999" 7:A
bash 45_run_cap.sh ./r_deg      30 "$Q&waitcenter=999&waitretire=99999" 7:A 16:D
bash 45_run_cap.sh ./r_land     34 "$Q&waitcenter=999&waitretire=99999" 7:A 24:F
bash 45_run_cap.sh ./r_phases   46 "$Q&waitcenter=14&waitretire=30"     7:A
bash 45_run_cap.sh ./r_off      22 "$Q&wait=off"                        7:A
bash 45_run_cap.sh ./r_noarrive 25 "$Q&arrive=0&waitcenter=999&waitretire=99999" 7:A

# 4. 量 + 組片
python3 41_motion.py ./r_main_waitonly motion.json   # 只取等待窗口（t≥10s）的那些格
python3 42_mkvid.py  ./r_main waiting.mp4            # 需要 ffmpeg；本機要
                                                     # DYLD_FALLBACK_LIBRARY_PATH=/usr/local/Cellar/x265/4.1/lib
```

⚠ **每一次錄影要換一個 probe id**（`45_run_cap.sh` 自動帶時間戳）：`bridge.js` 的
`seenIds` 會落 `localStorage`（48 小時 TTL），同一個 id 第二次進來會被當成「看過了」
直接跳過——第一次錄完之後第二次就不會有人進來，而畫面上看起來只是「什麼都沒發生」。
**本輪第一次錄退化就踩到這個**（那一輪 `mode=invite`、console 裡沒有 `等待態開始`）。

---

## 十、誠實邊界（改碼時保留）

1. **`formingLevel` 的上限 < 1 是規格不是調味。** 它保證「完成」只可能由
   `director.twinArrived` 造成，不可能由時間造成。把 `ceil` 改成 1、或把顯影高度
   改成線性，等待態就變成一根偽裝的進度條。
2. **退化的措辭直接轉呼 `twinEngineNote`**，不另寫一份。兩處各寫一句遲早會漂。
   ⇒ 而且**要換掉 `w.sub`**，不然那一句根本不會出現（第三節 3-1）。
3. **退役那一句要讀得到。** 它走底板不是美術決定，是「讀不到等於沒講」（3-2）。
4. **重讀器不自己挑來源。** 它只重讀 `WorldBridge.sourceState().url`（橋上一次
   真的成功的那一個）；橋沒成功過就一通都不打，畫面改口說
   「⚠ 我們讀不到他成形了沒 · 畫面不會自己變成完成」。
5. **退役不宣稱刪除。** 字幕是「帳本上留著『還沒成形』，沒有被丟掉也沒有被演成完成」
   ——`twinstore` 是 append-only，而撤回入口（`DECISION_20260921_TWIN_CONSENT_AND_ERASURE`
   §三-2）**還沒接**，所以這裡不准出現任何「可以刪」的承諾。
6. **公共大螢幕不印觀眾原話。** 等待態的每一句話只有代號＋類別
   （`visitorCode`／`visitorCategory`），W7 是可執行防呆。
7. **`?waitdemo=1` 會憑空生一位訪客 ⇒ 螢幕上一定要標「演練」**（鐵律 5 的展場版本）。
8. **`12_degraded_while_waiting.jpg`（第一輪那張）不可以單獨引用。** 它是探針寫
   `w.sub` 生出來的畫面；在修掉 3-1 之前，產品路徑上**不長那樣**。

---

## 十一、沒做、不知道、還沒對帳的

* **展場機器上沒跑過。** 全部證據都是這台 Mac 的 headless Chrome。展場機是 1003
  （Windows，記憶〈展場機器是 1003〉），那裡的 GPU 解碼與字型渲染都不同。
  「幀率」與「字讀不讀得到」兩件事**都需要在那台機器上再看一次**。
* **沒有跟真的 `twinlink loop` 對接過。** `44_drive_snapshot.py` 扮演的是寫快照那一方，
  格式逐欄比照 `visitors.sample.json`；但真的 loop 會不會在中途寫出別的 `status`
  組合（例如 `claimed`），**沒有量過**。`twinPending` 對沒見過的 `status` 回 `null`，
  而 `null` 不進等待態 ⇒ 最壞情況是退回舊行為，不是演錯。
* **同時多人投卡只驗到「排隊」那一半。** `waitBacklog` 的邏輯有跑過（`routeSubmission`
  回 `"backlog"`），但**沒有錄下三個人同時投卡的畫面**。陶牌那一側（「你是第 2 個」）
  是抵達層的既有能力，不是這一輪加的。
* **`SIMPLE` 那條線沒有納入設計。** 本輪最後一次 rebase 併進了別人加的
  `SIMPLE`（人類「畫面太複雜了」，預設開，砍監視器列數與案例橫幅）。它**不碰**
  等待態的任何一筆繪圖（`grep SIMPLE` 只命中 QR 位置／`drawMonitor`／案例橫幅三處），
  所以這批畫面不受影響；但**「等待態自己會不會太複雜」沒有被那個標準檢視過**。
* **`70_arrival_envelope_lands.jpg` 是第二輪較早那一次錄的**（抵達層那段碼在兩次
  之間一個字沒動；最後一次重錄的幀率只有 2 fps，0.62 秒的飛行落在兩格之間沒拍到）。
  最終樹上的接縫用 `70b_seam_handoff.jpg`。

---

## 附：檔案清單

**第二輪（本輪，可引用）**

| 檔 | 是什麼 |
|---|---|
| `60_seam_waiting_49s.mp4` | 主交付：抵達→等待整段 49 秒（真來源鏈） |
| `61_phases_centre_corner_retire_45s.mp4` | 中央→角落→退役儀式 |
| `62_degraded_while_waiting_29s.mp4` | 等待中被判定為查表湊的（修完之後） |
| `63_twin_lands_36s.mp4` | 分身真的生出來、接回既有故事線 |
| `64_NEGCTL_wait_off_22s.mp4` | 負控制：`?wait=off` |
| `70`,`70b` | 信落進投遞口／抵達交棒給等待的那一格 |
| `71`,`71b`,`72` | 等待 7 秒／最初幾秒那句「剛剛送出的那一張，是他」／等待 32 秒 |
| `73` | 退化字卡（修完） |
| `74`,`75`,`75b` | 角落卡／退役（有底板）／退役（修之前，字被洗掉） |
| `76`,`77` | 兩組負控制：`?wait=off`／`?arrive=0` |
| `80`,`80b` | 動態量測（等待窗口／整段） |
| `81`,`82`,`82b`,`83` | waitcheck 80 條、livecheck 165 條（改動後／未改動基線）、waitcheck 負控制 |
| `84*`,`85*` | 每一次錄影的頁面 console 與快照驅動 log（**stderr 沒有被吞**） |
| `44`,`45` | 快照驅動器與錄影腳本 |
| `90` | patch（基底 sha 見第八節） |
| `91` | 那份 patch 的基底檔，逐 byte 釘死 |
| `92`,`93` | 三方合併腳本與它的實跑紀錄 |

**第一輪（歷史，勿直接引用）**：`01`–`15`、`20`–`22`、`30`–`33`、`40`–`43`、
`50_vacant_hm_wait_shape.patch`。
