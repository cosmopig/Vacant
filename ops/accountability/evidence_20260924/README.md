# 可究責追緝——2026-09-24 的證據（L-fake）

> **證據等級：L-fake。** 模型是照劇本回答的假上游（`ops/intake/mock_model.py`），沒有真模型、
> 沒有 API 金鑰。這裡證明的是**機制**在四個真 agent 的真掛鉤、真工具迴圈上接得起來，且歸因規則在
> 乾淨的埋錯下給出期望的答案。**不證明**真模型下產出會更接近需求——那是
> `decisions/prereg/PREREG_20260924_R536_LOCALIZED_FEEDBACK.md` 的事（草稿，待人類簽字）。

## 1. 四個真 agent × 八個埋錯情境＋Claude 的背景子 agent（`e2e_trace_SUMMARY.md`、`e2e_trace_results.json`；子 agent／`curl` 的對抗審查修正**之後**重跑）

重跑：

    python ops/accountability/e2e_trace.py --bin <pi/opencode/codex 所在目錄> --out <dir>

| 量什麼 | 結果 |
|---|---|
| 歸因正確（狀態／類別／等級／指到的步驟／來源都對） | **33/33** |
| B（agent 憑空寫錯）⇒ `provable`，指到寫報告那一步；重跑前那個位置沒有這個值、之後不過且有 | 4/4 |
| A（輸入本來就錯）⇒ `input`／`lineage_exact`，來源＝`inputs/summary.txt`；agent 沒被記過錯 | 4/4 |
| C（腳本錯）⇒ `lineage_internal`，指到**寫腳本**的那一步（不是寫報告那一步） | 4/4 |
| D（agent 走了之後有人在外面改檔；負控制）⇒ `UNOBSERVED`／`gap`；沒有任何行動者被記 | 4/4 |
| F（網頁本身就錯：`curl http://portal.vacant-lab.test/…` 抓回來的頁面寫著 58、照抄；實驗環境用 `http_proxy` 把這個名字接到假模型）⇒ `input`／`lineage_exact`，來源是那個網址；agent 不背；網址記進來源帳 | 4/4 |
| I（**平行委派**兩個子 agent：A 把列數寫進 `count.txt`、B 把 96 寫進 `figure.txt`；主 agent 兩個都讀、照抄）⇒ 指到 **B** 寫 `figure.txt` 的那一步（不怪 A）。跑的時候發現：先收尾的委派呼叫會把兄弟子 agent 還沒收尾的寫入掃進自己的差異——修了（委派呼叫自己不寫檔；同一個版本歸真正寫它的那一步） | 4/4 |
| H（**人標記**了契約檢查不到的錯：第一跑總數對、「Region: South」錯 ⇒ 收件 accept；人下 `vacant flag report.md:4 "the region is North, not South"`；第二跑是新的工作階段）⇒ 回合結束時把標記回饋給 agent（契約過了也照樣）、追緝指到第一跑寫下那一行的那一步、改好之後標記解決 | 4/4 |
| G（只有 Claude Code：子 agent 在**背景**跑——Claude 的預設；主 agent 從 `<task-notification>` 照抄）⇒ 同 E，指到子 agent；子 agent 還在做時回合結束的驗收**先不跑**（不催主 agent 重做） | 1/1 |
| E（子 agent 算錯寫進 `figure.txt`、主 agent 照抄）⇒ `agent`／`lineage_internal`，指到**子 agent** 寫 `figure.txt` 的那一步，行動者帶子 agent 的 id（Claude `general-purpose`、Codex `default`、pi `worker`、OpenCode `subagent`） | 4/4 |
| 有位置的回饋出現在下一次模型請求裡 | Claude Code、Codex、pi：**是**（A／B／C／E／F／H／I＋Claude 的 G，22 格）；OpenCode `run`：**否**（既有邊界：`run` 在第一個 idle 就結束） |
| 給 agent 的回饋裡有行動者識別 | 0/33 |
| 改好之後，病歷記「已解決」、收件 accept | Claude／Codex／pi 的 A／B／C／E／F／H／I＋Claude 的 G：22/22 |
| 病歷簽章鏈驗得過 | 33/33 |
| 每次掛鉤的額外時間 p95 | 7.2–16 ms（小工作區；大專案見第 3 節）；Codex 的 F、H 兩格各有一次 40–50 ms（那兩格只有 12–13 次掛鉤，p95 就是最慢那一次；p50 5–6 ms） |
| 行動者帳本 | 每個 agent 一格（6 跑）；B 記 1 筆可證明的錯；A 記在來源 `inputs/summary.txt`、F 記在那個網址；D 記在該平台的整合覆蓋率；E 是推論層（`lineage_internal`），照規則不進信譽 |

模型實際收到的回饋（Claude Code，情境 B，第 2 次請求）：

```
The task contract's checks do not pass yet (this is feedback from `vacant check`, not a final decision):
- total: FAIL — report.md:3 says "999"
  expected 69 (column 'amount', 3 rows)
  this value first appeared at step 2 (Bash)
Run `vacant check` to re-check before finishing.
```

## 2. R536 的管線冒煙（`r536_mock_smoke_*.json*`）

2 題 × 3 臂，Claude Code 對假模型：RS（重抽、無回饋）3 次都錯；RF、RL 第 2 次改對。
**只證明管線接得起來**（假模型看到回饋開頭就照劇本改對），任何效果數字都不能從這裡來。

## 3. 大專案的掛鉤時間（`perf/`）

重跑：

    python ops/accountability/perf_scan.py --out <dir> --sizes 100,1000,10000,40000,60000 --steps 10

真的掛鉤進入點（`python -m vacant_network hook claude …`，含行程啟動，約 130 ms）。每個大小：第一次 Pre（冷）→
10 對 Pre／Post（每一步改一個檔）→ Stop（驗收＋追緝＋在重建的前後狀態上重跑；第 1 步埋了 `999`）。
`perf.md` 是表，`perf.json` 是原始數字，`stop_40000.json`／`stop_60000.json` 是 agent 收到的回饋原文，
`machine.txt` 是機器。

| 量什麼 | 結果 |
|---|---|
| 4 萬檔：第一次 Pre／之後每次 p95／Stop | 5.7 s／597 ms／1.9 s（都在 30 秒上限內；改之前第一次 Pre 是 33.8 s；同一支腳本三次量測的第一次 Pre 是 5.7–8.2 s） |
| 1 萬檔：同上 | 3.1 s／325 ms／0.56 s |
| 每一步多存多少（1000 檔以上） | 0.9 KB（差異索引；改之前 4 萬檔每一步 4.9 MB） |
| 6 萬檔（超過 5 萬檔上限） | 第一次看改到背景、背景看不完 ⇒ 關掉逐步掃描；之後每次掛鉤 p95 227 ms；Stop 的回饋仍有 `report.md:2 says "999"`，但沒有「第一次出現在第幾步」 |
| 一個 12 GiB 的檔（審查 #5 的重現） | 第一次 Pre 8.2 秒改到背景，之後每次 0.14 秒（改之前每一次都被 30 秒上限砍掉、什麼都沒記） |

這一節的表是**對抗審查修正之後**重跑的（`ops/accountability/review_scale/FINDINGS.md`：8 條全部成立、全部修掉）。

誠實邊界：檔案都很小（大檔的雜湊另計）；本機磁碟、快取是熱的，網路檔案系統會更慢；4 萬檔的第一次掃描貼著
8 秒的時限，換一台慢一點的機器就會改到背景（那段時間的步驟記成「沒觀察到」）。只量 Claude Code 格式的掛鉤
（四個平台走同一個 `hook.handle`）。

## 4. 沒有做到的（照實寫）

- 子 agent：Codex 的 multi-agent v2 沒有端到端跑（有 `ops/accountability/capture/` 的可觀測面實測）。
  平行委派（情境 I）是兩個子 agent 寫**不同**的檔；兩個子 agent 同時寫**同一個**檔時只能說「是其中之一」。
- pi 的子 agent 靠 Vacant 的 pi 擴充在工具呼叫期間放進環境的標記認出來：平行的工具呼叫下，標記可能指到兄弟呼叫
  （工作階段仍然對）；不是 pi 擴充啟動的 pi 行程（例如使用者自己在另一個終端機開的）不會被當成子 agent。
- Claude Code 的掛鉤不帶模型 id ⇒ 信譽格的 substrate 是 `unknown`（逐字稿裡有自稱的模型，封存了，
  但沒拿來當鍵）。
