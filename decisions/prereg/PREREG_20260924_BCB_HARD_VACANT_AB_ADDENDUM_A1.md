# 預註冊補充 A1：執行環境（發射前、零筆 BCB 資料時寫）

> 主檔：`PREREG_20260924_BCB_HARD_VACANT_AB.md`（sha256 `db4ecd51…`，commit `c6fe0349`）。
> 本補充**不改任何假說、指標、檢定、停止規則**，只補三件執行環境的事。寫的時候 BCB 批次一格都還沒跑。

## A1-1 圍住 agent（bwrap）

pi 沒有內建沙箱（它自己的 `docs/security.md`：「Pi does not include a built-in sandbox … run pi in a
contained environment for unattended automation」）。本批無人看管跑 7 小時，機器是共用的（別的實驗、
別人的 session），題庫裡有「刪檔、搬檔、砍行程、呼叫系統指令」這類題。

⇒ **四組的每一個 pi 行程（含 GATE 的 shim／launcher）都包進 `bwrap`**：
`--ro-bind / /`、只有那一格的工作區與那個後端的 HOME 可寫、`--tmpfs /tmp`、`--unshare-pid`
（`kill` 碰不到外面的行程）、`--die-with-parent`；**網路保留**（要連模型）。
四組一樣 ⇒ 不影響組間比較。venv 因此唯讀（agent 不能 `pip install` 改掉後面每一題的環境）。
⚠ 這是保護機器，**不是**安全邊界：網路是通的，圍牆外什麼都連得到。

## A1-2 閘門驗收的環境（兩個明講的開關）

建庫實測：`sandbox._clean_env` 把驗收的 PATH 寫死 ⇒ 驗收用 `/usr/bin/python3`、沒有題目要的函式庫
⇒ **連參考解都 import 失敗、被判拒交**；512 MiB 的 RLIMIT_AS 下 `import matplotlib` 就炸。
若不修，H1 會「成立」，但那是閘門擋下一切，不是擋下假完成。

⇒ 新增 `VACANT_ACCEPT_PATH_PREPEND`（venv/bin 排最前）與 `VACANT_ACCEPT_MEMORY_MB`（2048）；
沒設時行為逐位元不變（有測試）。實際值跟著 sandbox 的 `describe()` 進收據。
量具（參考解過、退化樁擋）用**同一組**設定量；可見與隱藏計分也用同一個 2 GiB 上限。

## A1-3 每個測試檔的逾時

`VACANT_TEST_TIMEOUT` 依題庫量具量到的測試檔牆鐘決定（建庫 agent 回報的建議值），在發射紀錄裡寫明實際值。
預設 120 秒。

## 不變的

四組、三層、H1／H2／H3、α、停止規則、口徑、「中途不看結果」——全部照主檔。
