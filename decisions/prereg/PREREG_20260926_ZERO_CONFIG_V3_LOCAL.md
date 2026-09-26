<!-- 狀態：**草稿**（C2 wheel 還沒填；填好、commit 之後才凍結、才開跑）。 -->

# 預註冊：本機 gemma-4-12b 上，沒裝／現版零設定 Vacant／v3，DABstep 答對率

依據：`decisions/DECISION_20260926_ZERO_CONFIG_V3.md`（v3 做什麼、產品等級的檢查）、`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md`（上一輪）、
`ops/eval/evidence_20260926_local/RUNLOG.md`（本機機器的實測與試跑）。

## 一、問題

同一個 agent（pi 0.87.1）、同一個模型（人類自己兩台機器上的 gemma-4-12b-it-qat，關思考）、同一個題目與環境，只差裝了哪一版 Vacant：
1. **主要**：v3（C2）的答對率有沒有比沒裝（A）高？
2. 次要：現版（C1，上一輪的零設定＋兩個誤報修正）比沒裝高嗎？v3 比現版高嗎？

## 二、三組

| 組 | 做什麼 | wheel |
|---|---|---|
| A | Harbor 官方的 pi agent（`--agent pi`） | — |
| C1 | 同上＋使用者的安裝指令（`ops/eval/harbor_vacant.py`），Vacant 現版 | 見第三節 |
| C2 | 同上，Vacant v3 | 見第三節 |

不設任何 Vacant 環境變數、不寫契約。

## 三、釘住的東西

| 項目 | 值 |
|---|---|
| 評測框架 | Harbor `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` |
| agent | pi `@earendil-works/pi-coding-agent@0.87.1`；`--ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1` |
| 環境映像與題目 | 同上一輪：`vacant-eval/dabstep-env:1`（ID `sha256:0e2cbfab…2728`）；正式 79 題 `ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json`（sha256 `ddf4a962…7319`） |
| 模型 | `gemma-4-12b-it-qat`，兩台 LM Studio：`w401c-15.taild870c4.ts.net`、`1003.taild870c4.ts.net`；記帳代理本機模式強制 `reasoning_effort=none`（`ops/eval/orproxy.py`，commit `cd61f35c` 起） |
| C1 wheel | `vacant_network-0.8.0-py3-none-any.whl` sha256 `a722a234e8efe44fcd656458aabcaaaa48c64e21f020b57bc7873a83677a392c`（`vacant_network/` 同 `7f7ec52f`） |
| C2 wheel | `vacant_network-0.8.0-py3-none-any.whl` sha256 `0dcd5d6890eb18139e488dd5a5deb19baf18f63bc529babd87269756e8ff42a2`（`vacant_network/` 同 `11f91f878db3f8900c9dc3c70f5096f31bd9c554`） |
| 驅動 | `ops/eval/local/run_batch.py`、`ops/eval/local/run_local.sh`（本 commit 的版本） |

## 四、跑的方式與停止規則

- 題目順序 `random.Random(20260926).shuffle(formal_79)`；同一題、同一次的三組**用同一台機器、同時開跑**（w401 同時 3 跑、1003 同時 1 跑，
  題目依種子順序按 3:1 加權輪流分配；`run_batch.py --upstreams w401:3 1003:1`）。
- **一次一次跑**：第 1 次（79 題×3 組）跑完才開始第 2 次，依此類推，最多 3 次。
- **停止**：`--deadline 2026-09-27T04:00:00Z`——過了就不再開新的一跑，等在跑的跑完。**只看時間，不看任何評分**（驅動不讀 reward）。
- 一跑壞掉（沒有評分，或模型一個回答都沒拿到）＝`infra_void`：最後照順序補跑一次；補跑也壞 ⇒ 那一題那一次的三組都從分析拿掉並列出來。
  C 組 Vacant 沒裝上照算（意向治療）。

## 五、分析（`ops/eval/local/analyze_local.py`，本 commit 的版本；批次結束後跑一次）

- 題數：77 題（去掉第 5、70 題，和上一輪一樣）。第 5、70 題另外列。
- **完整的次數**：三組 77 題都有評分（或依第四節拿掉）的次數。最後一次沒跑完 ⇒ 不進主要分析，另外描述。
- **主要檢定（只有一個）**：每一題在完整的各次裡的平均答對率，C2 減 A，**Wilcoxon 符號等級精確檢定，雙尾 α＝0.05**
  （`vacant_network.research.wilcoxon_signed_rank_exact`；差為 0 的題去掉）。只有 1 次完整時改用 McNemar 精確檢定（同一個二項檢定）。
- 次要（Holm 校正，家族 2）：C1 減 A、C2 減 C1，同樣的檢定。
- 同時要報的（描述）：每一組每一次的答對數、沒交數、答錯數；A 組兩次之間的翻轉（純運氣）；每一次內的配對 McNemar；
  Vacant 的動作（交件前檢查走到幾次、退回幾次與類別、回合預算提醒幾次、提醒之後有沒有寫檔、還沒說做完就結束的交件說明幾份）；
  **傷害**（第一次交件對、退回後改錯；提醒前手上的答案對、提醒後寫錯無法判斷就不算）；**第一次交件是對的卻被退回的比例**；
  每一跑的請求數（**不變式：不超過 15**）、第一通請求在三組間逐位元組相同（**不變式**，從代理全文紀錄查）；兩台機器分開列；牆鐘時間。

## 六、事先寫死的說法

- 主要檢定顯著、C2 較好：「在這 77 題、本機 gemma-4-12b 關思考、pi 0.87.1、15 回合上限下，裝了 v3 的答對率較高（p＝…）」——
  並一定要同時說：v3 的回合預算提醒**只在 agent 被告知回合上限時**作用，一般互動使用不會觸發。
- 不顯著：「這一輪沒有量到差別」＋點估計與各題差的分佈；**不說**「沒有效果」。
- C2 較差且顯著：照實寫，列出傷害。
- 不外推到別的模型、別的題庫、沒有上限的使用。

## 七、已知的偏差

1. 官方 DABstep 用 smolagents、10 步；這裡用 Harbor＋pi、15 回合（和上一輪一樣）。
2. v3 是看過上一輪 77 題的紀錄之後設計的（`design/nudge_sim` 用的就是那批紀錄）：題目與規則不是獨立的。模型不同（26B 開思考 → 12B 關思考）。
3. 兩台機器的速度不同（1003 讀長提示慢得多），同一題的三組在同一台上，台的差不進組別的差。
4. 試跑（`pilot2`，只有 A 與 C1、部分題目）已經看過；不進這一份的分析。

## 授權

人類 2026-09-26（對話原話）：「總之你幫我把產品修更好迭代好 然後用這個去測試這是我本地算力 https://1003.taild870c4.ts.net/v1
https://w401c-15.taild870c4.ts.net/v1 裡面應該都是一樣的gemma4 12B Q4」。這一份由 agent 在開跑之前凍結；**人類沒有逐條簽字**——
結果只能說「預註冊的本機批次量到／沒量到」，對外當成「證明」之前要人類補簽。
