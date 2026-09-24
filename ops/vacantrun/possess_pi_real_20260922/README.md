# 2026-09-22：真 pi ＋ 真模型跑 R534 那五題，走 **`vacant install` 的 extension 路徑**

> 🔴 **更正（2026-09-24，code review）：本批是 PATH shim 那條路的 L-real，不是常駐 extension 那條路。**
> 標題與下面「常駐附身那條路第一次拿到真模型證據」「掛鉤是 pi 自己的 extension 燒的」兩句**說過頭了**：
> 五格都由 `gateshim.exec_inner` 起 pi，它把 `PI_CODING_AGENT_DIR` 設到這一跑自己的暫存目錄
> （自己的 models.json／settings.json、自己的 proxy 埠），`cells/*/hook_install.json` 的 `target` 是
> `/tmp/vacant-possess/run-pi-*/extensions/vacant.ts`——**`~/.pi/agent/extensions/vacant.ts`
> （`vacant install` 寫的常駐那支）在這五格裡從來沒有被載入**。掛鉤確實是 pi 自己燒的，但燒的是
> shim 當場裝的 per-run extension。
> ⇒ 本批只記進 `possess.SHIM_MEASURED["pi"]`；`possess.CHANNEL_MEASURED["pi"]` **仍是空字串**，
> 常駐 extension 目前只有 L-fake（`../possess_pi_20260922/`）。原文保留不改，以本段為準。
> （2026-09-24 稍晚：常駐 extension 那條的 L-real 另外量了，見 `../possess_pi_ext_real_20260924/`；
> 本批仍然只屬於 shim 路。）

> **證據等級：L-real**（真 agent、真模型、真流量）。**pi 的常駐附身那條路第一次拿到真模型證據**
> ——在這一批之前 `possess.CHANNEL_MEASURED["pi"]` 一直是空字串。
>
> 🔴 **與 `ops/vacantrun/pi_tty_20260920/` 那 40 格不可合併、不可相減。** 三個變因同時不同：
> 路徑（本批＝PATH shim／那批＝`vacant run -- wrap_agent.sh`）、pi 版本（0.87.0／0.85.1）、
> 上游形態（公開 Funnel／LAN 直連 1003）。本批只回答一個問題：
> **「使用者裝一次、之後照舊打 `pi`，Vacant 的中介與閘門在真模型下還成不成立。」**

- 執行端：Claude Code 遠端容器（`VERSIONS.txt`）；HOME 隔離、`--service bare`；沒有 bwrap ⇒ **每格 B′**
- agent：**pi 0.87.0**，print 模式（`-p`，`DECISION_20260920_PI_TTY_VS_PRINT_MODE` 的預設落點）
- 模型：**`gemma-4-12b-it-qat`**（人類的 LM Studio，經公開 Funnel `1003.taild870c4.ts.net`）
- 題目：`ops/gain/r534/templates` 的 `lcb_3522`／`3584`／`3649`／`3715`／`3789`（與那 40 格同一組）
- prompt、工作區四個檔、純度 fail-closed 擋門、`--sandbox none`、test-timeout 120、retry none
  ——**逐字沿用 `pi_tty_cell.sh`**（凍結那支），唯一刻意差異是走 shim 不走 `vacant run`
- 命令列上**零個 vacant**：`cd <ws> && pi -p "<prompt>"`，shim 在 PATH 上接手

## 一、五題的結果（兩格都成立）

| 題 | 退出碼 | 秒 | `stop_reason` | `agent_rc` | `requests_seen` | 模型通數 | 可見 | **隱藏（GT）** | 工具呼叫 | 級別 |
|---|---|---|---|---|---|---|---|---|---|---|
| `lcb_3522` | **0** | 69 | `visible_pass` | 0 | 8 | 7 | 3/3 | **27/27** | 6 | B′ |
| `lcb_3584` | **20** | 355 | `visible_fail` | **0** | 5 | 4 | 0/1 | 沒有交付物 | 2 | B′ |
| `lcb_3649` | **0** | 197 | `visible_pass` | 0 | 14 | 13 | 2/2 | **26/26** | 10 | B′ |
| `lcb_3715` | **20** | 221 | `visible_fail` | **1** | 8 | 7 | 0/1 | 沒有交付物 | 3 | B′ |
| `lcb_3789` | **0** | 219 | `visible_pass` | 0 | 7 | 6 | 2/2 | **26/26** | 5 | B′ |

**3 交付 ∕ 2 拒交。** 閘門有牙齒，而且不是永遠說不——那兩件事必須同一批量到才算數。

五張收據：`verify_receipts --selftest` 先 PASS（負控制），再逐一驗，**五條鏈總判全部 OK**。
每一張都帶 `upstreams_public_allowed: true`——上游是公開 Funnel 這件事**寫在收據裡**，不靠這份 README 記得。

## 二、兩個拒交格不是同一種失敗（收據分得開）

兩格的可見驗收失敗原文都是 `ModuleNotFoundError: No module named 'solution'`
（凍結工作區裡**沒有 `solution.py`**，只有原本那四個檔）。但**退出碼以外的欄位把它們分開**：

- **`lcb_3584`：`agent_rc = 0`。** agent 跑了 355 秒、叫了 4 通模型、**只用了 2 次 `read` 工具、一次都沒 `write`**，
  然後宣告完成、退出碼 0 走人。**閘門在行程結束那一刻擋下來。**
  這正是 `goal.md` 說「跨框架成立、最適合對觀眾講」的那一句，在 pi ＋ 真模型 ＋ 常駐附身路徑上**又出現一次**。
- **`lcb_3715`：`agent_rc = 1`。** 工具序列是 `bash` → `read` → `read`，agent 自己就失敗了。
  這一格**不是**「宣告完成卻沒交」，寫報告時不可以跟上面那格併成一句。

## 三、三個交付格的隱藏尺：3/3 全過，**但這證明不了什麼**

`lcb_3522` 27/27、`lcb_3649` 26/26、`lcb_3789` 26/26——沒有出現「過了可見、沒過隱藏」。

⚠ **不可以拿這個去對比 R532 的 14.8%。** n=3，而且題目不同、模型不同、批次不同。
本批能說的只有「這三格的交付物在 GT 上也對」，不能說「V/GT 落差消失了」。

**隱藏尺的負控制先跑過**：五題各餵一個退化樁（`def <entry>(*a, **k): return None`），
**5/5 全擋、0/27–0/26**——與凍結那批 §五「5/5 全擋，0/26–28」的數字一致 ⇒ 是同一把尺。
（`tools/score_hidden.py`；GT 那棵樹永遠不進工作區，失敗訊息也不回饋給模型，R534 紅線。）

⚠ `lcb_3649` 是人類 2026-09-20 點名的那題。**本批沒有重現它的「不終止解」現象**：
模型寫的是 n≤8 的全排列暴力解（8! = 40320），跑得完而且 26/26。**那是「這一跑沒踩到」不是「那個現象沒有了」。**

## 四、通道：`requests_seen` 說了話

五格的模型通數是 4–13，`requests_seen` 比它多 1（每格一通 `session_start` 的 canary）。
掛鉤是 **pi 自己的 extension 燒的**——`pre_tool_use`／`tool_result` 帶著工具名（`read`／`write`／`bash`），
那是**腳本不可能知道的時機**，只有 pi 知道。

`vacant possess status` 的 `proven` 欄在第一格跑完就被 `mark_proven` 點亮（`requests_seen > 0`）。

## 五、不能說的

1. **不能說 A 級**：這台沒有 bwrap ⇒ 沒有 enclosure ⇒ 五格全是 **B′**，收據寫 `attested: false`。
2. **不能說「pi 裝好就有」是無條件的**：本批量的是**裝了之後打 `pi -p`**。互動 TUI、長任務、MCP、
   並行多格**都沒量**。而且 shim **打完整路徑就繞過**（通道仍在，閘門不跑）。
3. **不能說這是 LAN 的成績**：上游是**公開 Funnel**，每一通模型呼叫走公開網際網路與 Tailscale 中繼。
   延遲與失敗模式跟 LAN 的 1003 不是同一件事。
4. **不能說 n=5 有統計意義**：五題各一次，沒有 rep。
5. 🔴 **量測當下那個 Funnel 端點對整個網際網路開著而且不要金鑰**（`GET /v1/models` 無憑證回 200、
   `POST /v1/chat/completions` 無憑證回 200 ＋ 真的推論）。這是**那台機器的狀態**，不是 Vacant 的性質，
   但它會出現在這批證據的上游欄位裡，所以記在這裡。

## 重跑

```
# 1) 起 proxyd 並把 extension 寫進 ~/.pi/agent/extensions/
vacant install --agent pi --home <HOME> --service bare --port 18791 \
    --upstream openai=https://<你的端點>/v1
# 2) 一格＝一題（tools/cell.sh 逐字）
bash tools/cell.sh lcb_3649 1
# 3) 隱藏尺（run 結束之後才跑，不回饋給模型）
python3 tools/score_hidden.py lcb_3649 <run-dir>/_frozen_RUN-ON
# 4) 驗鏈：負控制先過
python3 -m vacant_network.vrun.verify_receipts --selftest
python3 -m vacant_network.vrun.verify_receipts --glob <run-dir>
vacant uninstall --home <HOME>
```
