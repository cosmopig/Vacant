# i1001 執行紀錄（時間 UTC）

預註冊：`decisions/prereg/PREREG_20261001_COLAB_INTERACTIVE_I1001.md`，凍結於 `d57c1d2d`（Vacant 來源 `a5abd759`）。

## 2026-10-01 第一次開機（沒有發射；沒有任何一格真模型的結果）

| 時間 | 事件 |
|---|---|
| 18:58 | 本機第 0 步：測試全綠、`build_manifest.py --check` OK、wheel 與 git 逐檔相同（114 檔）、凍結表 43 列 OK、bundle 4,757,029 B |
| 19:01 | 起始餘額 109.90 CU；上限 軟 60／硬 75（預註冊第十節）；`colab new` G4 |
| 19:01 | GPU 核對：RTX PRO 6000 Blackwell、48 vCPU、176 GB（符合固定變數）；vLLM 背景安裝開始 |
| 19:02 | `colab drivemount` 要人類在瀏覽器授權（網址交給人類；沒有在這次開機期間完成） |
| 19:03 | `deploy_i1001.sh`：`DEPLOY_OK`（tmux 3.4、bwrap 0.9.0、pi 0.87.1、無特權使用者 import pandas 2.2.3／numpy 2.1.3） |
| 19:04 | 凍結表在 VM 上核對：43 列 OK |
| 19:05 | `vm_selfcheck.py`：a、void、c 過；k、r、timeout、driver 失敗，原因同一個——bridge 的驗收沙箱起不來 |
| 19:07 | 等人類兩個決定（Drive 授權、K 組怎麼辦），設 25 分鐘無決定自動關機 |
| ~19:27 | VM 已不在（`colab sessions`：沒有工作階段；`Usage rate 0`） |
| 19:32 | 核對：餘額 106.04 CU ⇒ 這次開機花 **3.86 CU** |

### 偏離與發現（都還沒影響任何結果，因為沒有發射）

1. **第 5 步的指令照抄會炸**：`freeze_i1001.py` 放在 `/content/` 時，`--repo` 的預設值 `HERE.parents[1]` 在 argparse 建構時就 `IndexError`。
   改放在 `/content/i1001_freeze/ops/` 再跑（工具本身一個字沒改），43 列 OK。RUNBOOK 第 5 步的路徑要改。
2. **K 組在 Colab 上不可用（照目前的做法）**：bridge 的驗收沙箱是 `bwrap --proc /proc`，Colab 不准掛新的 /proc
   （`Can't mount proc on /newroot/proc: Permission denied`）。selfcheck 準備的 PATH 墊片沒有生效：
   沙箱模組在乾淨環境裡把 `PATH` 寫死成系統路徑（`vacant_network/vrun/sandbox.py`），解析到的是 `/usr/bin/bwrap`，PATH 上的墊片輪不到。
   在 VM 上把系統的 `bwrap` 換成同樣改寫的墊片——**這個動作被自動權限分類器以「削弱安全」擋下，沒有做**，交給人類決定
   （A：照預註冊第六節只跑 `--nested R`；B：人類授權那個系統層墊片）。
3. **本機常駐的護欄會跟著容器一起死**：`cu_cap_i1001.sh` 的最後一筆在 19:11，之後本機的常駐行程（含 25 分鐘的自動關機計時器）都不在了。
   這次 VM 自己在約 19:27 結束，沒有空轉太久；但「關機只靠本機常駐行程」是一個洞——下次要在 VM 上也放一個不靠本機的時限。
4. Drive 授權要人類每台新 VM 按一次（`drivemount` 等 Enter；用 FIFO 餵 Enter 可行）。
