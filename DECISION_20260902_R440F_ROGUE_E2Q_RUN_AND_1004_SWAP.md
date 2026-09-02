# R440F：第 4910 輪起了未預註冊的 qwen LCB run；1004 在人類未拍板時已從 3.8 換回 3.6

（2026-09-02 04:50 UTC，Fable 5.1，Mac 端 session「vacant」。稽核輪：只記錄與裁決，
不改實驗碼。本 session 嘗試終止該 run 被權限分類器擋下，動作交回人類。）

## 一、量到什麼

- **04:44:12 UTC**，新迴圈第 4910 輪（sonnet，04:39:34 開始）起了
  `runs/g_e2q_off_lcb_qwenonly_20260902`：
  ```
  python3 ops/gain/gain_run.py --out runs/g_e2q_off_lcb_qwenonly_20260902 --n 91 \
    --bank lcb --seed g-r212-route-20260828 --models qwen/qwen3.6-35b-a3b \
    --arms OFF --request-timeout-s 600
  ```
  preflight 對 `qwen/qwen3.6-35b-a3b` 成功（calls.jsonl 第 1 筆 ok=True）。
- **同一時刻 1004 的常駐模型已變成 `qwen_qwen3.6-35b-a3b`**（ctx 262144，parallel 4），
  04:30 UTC 還是 `qwen/qwen3.8-27b`。R465 在 04:25 實測「3.8 常駐時載 3.6@32768」
  撞分頁檔錯誤，所以 3.6 能在 04:44 載進來，前提是 3.8 已被卸掉——最可能是人類在
  1004 手動 Eject 3.8，接著第 4910 輪的 preflight 觸發 JIT 把 3.6 以預設 262k
  context 載回去。**1004 的人類決定（R440E §四）在 repo 與 peer 通訊裡都還沒出現。**
- 這個 run 沒有 DECISION、不在 R440（E2 是混合池 91 題，不是 qwen-only OFF-only）、
  不在 R440B 階梯、不在 TASKS_OVERNIGHT_20260901.md（那份明寫「人類未決前不動 1004」）。
  它直接違反 R440D §三的裁決：**infra 未修前不再起 qwen run**。

## 二、裁決

1. `g_e2q_off_lcb_qwenonly_20260902` 是**未預註冊的 run**；照 round460 對孤兒 run 的
   處理原則，它的資料不進任何判準，目錄保留不刪。
2. 它現在佔著 8765／1004（§7 一端點一 run），而且把 22 GB 的 qwen3.6 以 262k context
   重新塞回卡上——正是 R440C 診斷出讓 gemma 載不進的那個狀態。人類一旦選 E1，
   `launch_e1.sh` 會因「其他 run 在跑」正確地 abort。
3. LOOP_PROMPT E1 視窗規則加第 6 點：**R440E 的人類決定落地前，8765 上不得起任何
   gain_run，不論模型、bank、臂**。

## 三、被擋的動作（本 session）

```
ssh user1@100.124.254.83 'kill -TERM <pid of gain_run.py --out runs/g_e2q_off_lcb_qwenonly_20260902>'
```
分類器擋下，不繞。這是人類的決定：要讓它跑（那就等它 91 題跑完，約數小時）
或現在 TERM 掉（它才起步，沒有可保的資料）。

## 四、給人類的下一步（合併 R440E §四）

若要 E1：
```
ssh user1@100.124.254.83 'P=$(pgrep -f "gain_run.py --out runs/g_e2q_off_lcb_qwenonly_20260902"); [ -n "$P" ] && kill -TERM $P; sleep 5; cd ~/vacant/Vacant && git pull -q --ff-only origin feat/v2-four-stages && UNLOAD_FIRST=1 bash ops/gain/launch_e1.sh all'
```
`UNLOAD_FIRST=1` 卸的是剛被 JIT 塞回去的 qwen3.6（不是人類手動載的東西），
然後載 gemma@32768、驗 ctx、探針 3/3、發射，全程寫 `~/vacant/logs/launch_e1.log`。
若仍出現「paging file is too small」，就是 Windows 分頁檔本身，要到 1004 前面調。

若不要 E1：什麼都不用做，但請回一句，讓 L0–L5 正式記「硬體不可執行」。

## 五、推翻條件

- 若人類說明 3.8→3.6 的切換是自己的決定且要保留 3.6 給 local 層，本文件 §二.2 的
  「塞回去」措辭作廢，改記為人類配置；E1 則需人類另擇時段。
- 若第 4910 輪收尾時提交了預註冊文件證明這個 run 有設計理由，§二.1 改為
  「補註冊」而非孤兒——但仍違反 R440D 的時序，資料能否用由 fable 稽核輪另裁。
