# NOTE 2026-11-25 — 零設定交件前檢查把抄對的值判成「沒有出處」（D2′ 冒煙發現）

只記事實與待查的原因。這件事直接關係到「紀錄要自己能用」：紀錄本身完整，但根據紀錄做的判斷錯了，
而且錯的判斷被送回給 agent、讓交件變差。

## 發生了什麼

- 情境：D2′ 冒煙，`smoke_d2_gemma12b_1003`，組 s40 的初稿（c0）。
  - pi＋gemma-4-12b（1003，不思考）。
  - 掛的是 `vacant install --agents pi` 真的寫出的擴充，`mode: evidence`（產品預設）。
  - 任務：依 5 張產品頁把 report.md 的 20 個空格填上。
- agent 的步驟（從病歷重建，seq 是鏈上的序號）：
  1. seq 6：一個 bash 指令，`curl -s …/p1.html > p1.html` 連續抓 5 頁，各自存成檔。
  2. seq 7–11：用 read 工具把 p1.html … p5.html 全文讀進來（每份約 1.2 KB）。
  3. seq 12：一次 edit 填好 20 格。**20 格全對**（和改動清單的第 0 週期真值逐條比對）。
- 交件前檢查（seq 13 的 review 事件）：`unsourced` 12 條，全部是對的值，例如 `$9`、`300`、`$39`、`1,800`、`14`。
  這些值都在 seq 7–11 讀到的內容裡。
- 後果：
  - 多跑 2 回合（review 動作 `continue` 兩次，第三次才 `allow`）。
  - agent 把 11 條對的值後面加上「(assumption)」，2 條加上「(from p1.html)」「(from p3.html)」。
  - 交件的值仍然對，但每一條都變成自稱是假設——讀的人會以為它沒查。
- 證據：
  - `~/dev/ops/d2_runs/smoke_gemma12b/cells/s40/c0/`：`report.md` 是交出的版本；`snapshot/vh` 是病歷。
  - `cells/s40/c0/run/agent.log` 是 pi 的事件流。
  - 這些都在本機，沒有入庫。

## 待查的原因（推測，還沒驗）

`evidence.py` 判斷「看過的東西裡找得到這個值」時，可能把 **agent 自己寫出的檔**（p1.html 是 seq 6 的 curl 導出來的）
排除在來源之外——為了防止 agent 自己寫一個檔再讀回來洗出處。但這裡寫檔的那一步本身就是抓網頁，
內容是抓回來的，不是 agent 打的。`blame` 有對應的規則（`curl … > 檔` ⇒ 值是抓回來的），`evidence` 可能沒有共用到。
要驗：用這一份病歷離線重播 `evidence`（它是純函式，只讀病歷）。

## 對 D2′ 的處置

D2′ 改用 `vacant install --agents pi --mode observe`：照樣記錄每一步，只是不把檢查結果退回給 agent
（`ops/d2/DESIGN_LOG.md` 第 4 筆）。這是**另一個功能的誤報**，不應該混進「出處重查」的成本與誤改裡。
結論檔會有一節專門講它。修正要另外做，修完要用這一份病歷重播確認 12 條都不再被判成沒有出處。
