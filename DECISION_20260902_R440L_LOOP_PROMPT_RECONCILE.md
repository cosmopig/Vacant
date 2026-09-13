# R440L：迴圈 prompt 合併——repo 的 ops/LOOP_PROMPT.md 改為迴圈實際在讀的內容，再切 loop.sh

（2026-09-02 05:35 UTC，Fable 5.1，Mac 端 session「vacant」。）

## 問題
round440k（f6c29fa）讓 loop.sh 改讀 repo 的 `ops/LOOP_PROMPT.md`。但那份是 8/15 的
展件優先版（§二：黏土視覺第一、G 實驗第四），而迴圈這一週實際讀的 `~/vacant/LOOP_PROMPT.md`
是 8/28 版：**8/24 人類改向「展件由 Mac 端接手，你不要再碰；唯一優先是 G 實驗」**。
直接切過去，迴圈整夜會去做黏土視覺，TASKS_OVERNIGHT 的 E1 檢查點沒人做。

## 決定
`ops/LOOP_PROMPT.md` := 迴圈實際在讀的 249 行（8/28 G 優先本體＋R440J 追加的模型政策、
平行實驗規則含 E1 視窗六條、R440G 閘門），檔頭加註來源。展件優先版保存在 f6c29fa。
**放棄**：把兩份手工合併成一份新結構——兩份的開場步驟（STATE.md vs GAIN_STATE.md）與
優先序互斥，合併等於替人類決定優先序；改向是人類 8/24 的決定，只能由人類推翻。
**推翻條件**：人類明說要迴圈回去做展件，屆時 `git show f6c29fa:ops/LOOP_PROMPT.md` 取回。

## 執行序（vacant-dev，人類授權）
1. 本 commit push → vacant-dev pull
2. `cp ~/vacant/Vacant/ops/loop.sh ~/vacant/bin/loop.sh`（round440k 版，讀 repo prompt）
3. `touch ~/vacant/STOP` → 等第 4915 輪（local，最晚 06:00 UTC）收尾 → 迴圈退出
4. `rm ~/vacant/STOP` → `setsid nohup /bin/bash ~/vacant/bin/loop.sh …`（同 R189 標準）
5. 驗 iter log 印出的「實際讀的檔與行數」＝`~/vacant/Vacant/ops/LOOP_PROMPT.md`、249+ 行
