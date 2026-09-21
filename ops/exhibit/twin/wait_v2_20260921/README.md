# WAIT-V2：等待是兩段，第一段以前講不出話（2026-09-21）

手機端（`vacant-world-cloud`）的等待畫面。複驗者實測抓到的洞：

```
queued （展場電腦還沒來取件）  晾 150 秒 → 計時器 = ""    永遠停在「抵達了」
claimed（正在生成）            90 秒     → 0:01 → 1:38    會動
```

**而展場真正的長等待就是第一段**：每人生成中位 312 秒，第 5 個人排到要 26 分鐘。
以前手機端**想講也講不出**——`/api/status` 只回 `{status, origin}`，
序位與送出時間戳都只有伺服器知道。

改的是兩個檔（都在 `vacant-world-cloud`，那是獨立 repo，分支
`feat/wait-queue-position`）：

- `server.js` — `/api/status` 加 `queue{position, ahead, …}`＋`submitted_at`
  ＋`claimed_at`＋`done_at`＋`server_now`；`/api/claim` 記 `claimed_at`；
  載回與 `/api/queue` 明確按 `(ts, id)` 排序。
- `public/index.html` — `WAIT-V2` 區塊：queued 講「你前面還有 N 個人」＋
  「已經排了 M:SS」，claimed 講「正在生成 M:SS」＋括號裡另外講排隊那段。
- `test/wait_queue.test.mjs`（新增 19 條，`npm test` 現在 60/60）。

## 🔴 刻意沒做的：預估剩餘時間

我們不知道還要多久（727 秒那一發是真的）。**會騙人的倒數比沒有更糟。**
序位與已等時間是我們**真的知道**的兩件事，畫面上只講這兩件。

## 畫面（390×844 CSS 視窗，dsf 2 ⇒ 檔案 780×1688）

| 檔 | 是什麼 | 看什麼 |
|---|---|---|
| `shots/00_before_queued_blank.png` | **負控制**：改動前的 server.js ＋ 改動前的 index.html，**同一份 fixture、同一個尺寸** | 標題寫「你的分身正在成形」（那時候機器根本還沒碰他的卡），階段條下面是**一片空白** |
| `shots/01_queued_5th.png` | 改動後，同一個人 | 「你前面還有 **4** 個人」＋「已經排了 4:0x」＋長等待那一句 |
| `shots/02_queued_next.png` | 排到最前面（`ahead=0`） | 「下一個就是你」——不是「你前面還有 0 個人」；長等待那句**不出現**（隊伍短時它是噪音） |
| `shots/03_claimed.png` | 輪到他了 | 「輪到你了」／「正在生成 3:56」／「（排隊等了 4:12）」——兩段各自有標籤，**沒有相加** |
| `shots/05_done.png` | 完成 | 「他到了」＋記號＋分身卡（卡片圖是走真的 `POST /api/result` 寫進去的） |
| `shots/06_tick_a.png`／`07_tick_b.png`／`08_tick_compare.png` | 同一頁、相隔約一分鐘 | 「已經排了 11:27」→「12:36」＝**畫面真的在動**；序位仍是 4（那段時間沒有人被取件，本來就不該動） |

`evidence.json`：改動前後對**同一個 id** 打 `/api/status` 的原始回應
（before＝`{"status":"queued","origin":"audience"}`，after＝含 `queue.position=5`），
以及真的送一張新卡時 `/api/submit` 回應裡就帶著的序位，還有每張圖的 sha256。

## 第 5 個人的 26 分鐘：這是體驗決定，寫在這裡備查

**判準**（CLAUDE.md）：「觀眾走到展場前面時，這件事有沒有差別」。

1. **序位比時間重要。** 「你前面還有 4 個人」是他現在唯一能拿來做決定的資訊
   （要不要等、要不要先去逛）。所以那個數字排版上比計時器大一號。
2. **`ahead >= 2` 才出現那一句建議。** 只差一個人的時候多一段字是噪音。
3. **建議他去看大螢幕，不是叫他「走開，好了會震動」。**
   螢幕一關、切走 App，這頁就收不到也震不了（iOS 根本沒有 `navigator.vibrate`）。
   所以那句話逐字是：「螢幕關掉的時候，這頁提醒不了你。」
   做不到的承諾在展場的代價是一個再也沒回來的人。
4. **`這頁會自己更新——好了會震動告訴你`改成`會亮起來告訴你`**：
   亮是每支手機都做得到的那一件事，震不是。
5. **回到前景就立刻重問一次**（`visibilitychange`）：鎖屏醒來不必等 4 秒
   才看到新的數字。

## 每個綠燈的負控制

| 綠燈 | 負控制 | 結果 |
|---|---|---|
| 畫面講得出序位 | 改動前同狀態的截圖 | `00_before_queued_blank.png` 一片空白 |
| 序位是算出來的 | 把 `ahead` 寫死 0（mutant） | `wait_queue.test.mjs` 19 條紅 5 條 |
| 沒量到寫 null | 手機端把 `null` 改成 `0`（mutant） | 紅 1 條（那一行會變成「下一個就是你」） |
| 時鐘用伺服器的 | 拿掉 `server_now` | 同一支手機算出「184:12」（測試裡那一條） |
| 截圖工具會動 | `about:blank` 正控制 | 1040 bytes ✅。⚠ headless Chrome 截完**不會自己結束**（今天實測 120 秒還掛著），所以 `shot.sh` 背景啟動＋輪詢檔案＋只殺自己那一顆（`--user-data-dir` 當指紋，絕不 `pkill` 一整排） |

## 誠實邊界

1. **這些截圖是 fixture 不是展期真資料。** 卡片內容與時間戳是造出來的；
   真的是那支 `server.js`、那個 `/api/status`、那一頁 `index.html`。
2. **`05_done.png` 的撤回碼欄是「—」。** 那是 `?id=` 這條進入點的性質
   （沒有 localStorage 就不知道他的碼），不是完成頁壞掉。真實動線上他有碼。
3. **`00_before_...` 那張的舊頁加了 3 行 `?id=` shim**，否則 headless 進不去那一頁
   （舊頁只能靠 localStorage 續看）。shim 只影響**怎麼進到那一頁**，
   不影響那一頁顯示什麼。
4. **「你前面還有 N 個人」的前提是取件順序＝送出順序。** 這次把載回與
   `/api/queue` 都釘成 `(ts, id)` 排序，那句話才為真；展場端要是自己挑 id 去
   claim，這句話就會失準——那是消費端的事，這台管不到。
5. **stale claim 門檻 15 分鐘。** 展場電腦取了件就當掉的那一筆，超過門檻不再
   算在「前面」，但會出現在 `queue.stale_claimed`。15 分鐘的根據是實測最長一發
   727 秒（12.1 分）：門檻比它大，才不會把還在跑的算成死的。

## 怎麼重跑

```sh
cd ~/Documents/GitHub/vacant-world-cloud
npm test                     # 60/60（含本次 19 條）
node --test test/wait_queue.test.mjs
```

截圖用的 fixture 與 headless 包裝留在這次的 scratchpad
（`mkfixture.py`／`start_servers.sh`／`shot.sh`／`mk_oldapp.sh`），
不進版控：它們只是產生上面那幾張圖的鷹架，真正要守的是 `wait_queue.test.mjs`。
