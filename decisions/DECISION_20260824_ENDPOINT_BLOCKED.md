# DECISION 2026-08-24（第二份）：OFF 失敗率沒量到——後端額度耗盡，停下來問人類

**前一份 `DECISION_20260824_OFF_BASELINE.md` 的判準完全不動。**
這份不是改判準，是記錄「那張判決表這一輪用不上，因為擋門先觸發了」。

## 一、發生什麼事

前一輪（commit `11fe5d7` 之後）照 baseline 決定跑了那條指令，產物在
`runs/g_off60_20260824/`。實測結果：

```
arms.OFF.tasks       = 60
arms.OFF.calls       = 0
arms.OFF.infra_void  = 60
arms.OFF.failed_attempts = 60
arms.OFF.wall_s      = 16.0
arms.OFF.cost_usd    = 0.0
arms.OFF.correct_delivery_rate = None
```

**60 題全部 infra_void，一次成功呼叫都沒有。** 16 秒就結束（預估是 13 分鐘）。

baseline 判準的擋門：`infra_void > 6（>10%）⇒ f 不准拿去對判決表，run 記成 incomplete`。
`infra_void = 60` ⇒ **擋門觸發，這一輪沒有 f 可報。**
這不是「量到 OFF 失敗率很低」，也不是「量到 0」——**是這 60 格全都沒量到**（鐵律 2）。

## 二、根因（實測，不是推測）

`calls.jsonl` 每一筆的 `error` 都是 `HTTPError: HTTP Error 403: Forbidden`，
三個模型家族（glm-5.2／deepseek-v4-flash／kimi-k3）、六個 agent 全中，
latency 250–330ms（**快速拒絕＝認證／權限關卡，不是容量或逾時**）。

直接打端點取回 403 的 body（`urllib` 只留 status，所以另外用 curl 取）：

```
$ curl -s -X POST https://api.cline.bot/api/v1/chat/completions \
    -H "Authorization: Bearer <key1>" -H "Content-Type: application/json" \
    -d '{"model":"cline-pass/kimi-k3","messages":[{"role":"user","content":"say OK"}],"stream":false}'
{"error":{"code":"ENTITLEMENT_ERROR","message":"Error 403: the user is not subscribed to required model plan"}}
HTTP=403
```

兩把 key 都一樣。兩把 key 是**兩個不同帳號**：

| key | 帳號 | `cline-pass/*` | 計費模型 | Cline Credits 餘額 |
|---|---|---|---|---|
| 1 | `cosmo20050801@gmail.com` | 403 ENTITLEMENT_ERROR | 402 insufficient_credits | **$0.005192** |
| 2 | `cwk181227@gmail.com` | 403 ENTITLEMENT_ERROR | 402 insufficient_credits | **$0.005434** |

（餘額出自 402 body 的 `current_balance` 欄位；帳號出自 `GET /api/v1/users/me`。）

其他試過的路：

- `cline-free/kimi-k3` → 403 `API_REQUEST_ERROR_CODE`：
  「only available via Cline product surfaces」。
  **要用它就得把 runner 偽裝成 Cline 官方客戶端＝繞過存取控制，不做。**
- `anthropic/*`、`cline-pro/*`、`cline-byok/*` → 402 insufficient_credits（同上餘額）。
- 本機沒有第二個後端：`codex` **執行檔不存在**（`~/.codex` 只剩資料目錄，
  `find ~ -name 'codex*' -type f -executable` 無結果）。裝它要 sudo ⇒ 要問人類。

**兩個帳號合計 ≈ $0.0106。** 這一輪要跑的 OFF n=60 估 **$0.39**（≈ 37 倍）。
連 6 題 smoke（$0.0388）都不夠。

## 三、有一件事沒辦法從外面判斷——人類買之前要知道

403 是 `ENTITLEMENT_ERROR`（訂閱方案），402 是 `insufficient_credits`（餘額）。
**這是兩個不同的錯誤碼。** 我分不出以下哪一個為真：

- (a) `cline-pass` 方案訂閱到期了 ⇒ **只加值 credits 不會恢復**，要重訂方案；
- (b) 餘額歸零時 gateway 就回 entitlement 錯 ⇒ 加值 credits 就會恢復。

證據只指向「兩個帳號同時既沒錢又被 entitlement 擋」，跟兩種解釋都相容。
2026-08-20 的 smoke 是**真的用 credits 計費**的（`cost_usd == market_cost_usd == 0.0388`，
不是 $0 的 BYOK），所以那時候方案與餘額都在。

⇒ **建議人類先加值一筆小額試打一次 `cline-pass/kimi-k3`**，
用那一次的回應碼區分 (a)/(b)，再決定要不要買方案。不要一次買足。

## 四、要多少錢（照 smoke 實測單價外推）

smoke 實測每臂單價（`summary.json`，不是估的）：
OFF $0.00647/呼叫、ON $0.00938/呼叫、OFF5 $0.00521/呼叫。

| 要跑的東西 | 呼叫數 | 估價 |
|---|---|---|
| **OFF n=60（本輪被擋的那條）** | 60 | **$0.39** |
| 三臂 n=60（OFF 60＋ON 300＋OFF5 300） | 660 | **$4.76** |
| 三臂 全 371 題 | 4081 | **$29.4** |

**這是花錢的決定 ⇒ 照人類的三條例外規定，停下來問，不自己買。**

## 五、這一輪還是量到了兩件事（都不用花錢，都是真的）

**(1) 量具雙向驗證滿分——而且是在下一輪要用的那 60 題上。**

```
instrument.n = 60   ref_pass = 60   broken_rejected = 60
```

官方參考解 60/60 全過、壞解 60/60 全擋，`detail` 裡 60 筆 `err` 全空。
⇒ 尺是好的，**下一輪拿到額度可以直接 `--probe-sample 0` 跳過重驗**（省錢）。

**(2) 「天花板效應」這個前提，6 題的 smoke 根本撐不起來——這推翻了本輪的出發點。**

人類的指令與 baseline 決定書都寫「三臂全對 ⇒ 天花板效應 ⇒ 實驗答不出問題」。
把 6/6 當成證據來算：

```
P(6/6 全對 | 真實正確率 p):
  p=0.70 -> 0.118      p=0.85 -> 0.377
  p=0.75 -> 0.178      p=0.90 -> 0.531
  p=0.80 -> 0.262      p=0.95 -> 0.735

6/6 的 Clopper-Pearson 95% 單側下界： p >= 0.607
  ⇒ 真實失敗率 f 最高可能到 0.393
```

**f = 0.393 落在 baseline 判決表「f ≥ 0.20 ＝量測窗口可用」那一格裡。**
也就是說 6/6 這個觀測跟「窗口其實可用」完全相容——
6 題的 95% 區間是 `[0.06, 0.64]`（n=60 才收到 `[0.16, 0.37]`）。

⇒ **「天花板效應」目前是一個未經檢定的假設，不是量到的事實。**
   n=60 這一步不只是「加大樣本」，它是**第一次真的去檢定這個假設**。
   在拿到 n=60 的數字之前，**不准**動 worker 池、不准換題庫——
   那些旋鈕是為了「確認有天花板之後」才用的，先動就是拿條件改變去追好看的數字。

輔證（題庫側，零成本）：60 題的 canonical solution **中位數只有 3 行**
（min 3／max 11），MBPP 本來就是簡單題庫；但 plus 測資中位數 **105 筆**
（min 49／max 143），`hidden_check` 用的是 `base + plus`
（獨立覆核：`vacant/codebench.py:660` ＝ `_check_code(..., base + plus, atol)`）。
⇒ 題目本身簡單、但判定很嚴。這正是 MBPP+ 公開 pass@1 常落在 0.65–0.80 的形狀，
對應 f = 0.20–0.35 ＝**正好在可用窗口內**。這是外部知識的類比，不是本機量測，
所以只當旁證，不當結論。

## 六、什麼條件下這份決定該被推翻

- 若加值後 `cline-pass/*` 仍 403 ⇒ 第三節的 (a) 成立，
  「加值就能跑」這個假設作廢，要改買方案或換後端。
- 若 n=60 量出來 `f < 0.05` ⇒ 第五節 (2) 的翻案作廢，
  天花板是真的，回到 baseline 判決表最後一列（改 hasty-only 池）。
- 若 n=60 的 infra_void 仍 > 6 ⇒ 不是額度問題，要回頭查端點本身。

---

## 七、⚠ 本輪稍後自我更正：第二節「本機沒有第二個後端」是錯的

上面第二節寫「本機沒有第二個後端」。**那句話在寫的當下就已經過期了，
不要引用它。** 留著不刪是為了讓紀錄可追。

實際發生的事：本輪進行中（06:15 前後），Mac 端把 `0817edf` 推上 origin，
第三項改動就是**端點可換**（`VACANT_GAIN_API`），而且 commit message 直接
引用了 `runs/g_off60_20260824` 這一輪的 403。本機另一個行程隨即把分支
rebase 到 origin 並 detached 跑了一支本機端點的 n=3 smoke。

⇒ 有一個**免費、可用**的後端：`http://100.119.113.56:1234/v1/chat/completions`
（Tailscale IP ＝ Mac 端那台），模型 `qwen/qwen3.6-35b-a3b`、
`nvidia/nemotron-3-nano-omni`。實測 3/3、`infra_void=0`、`cost_usd=0.0`。

**修正後的結論**：

- 第二節到第四節關於 **Cline 額度耗盡**的量測**全部仍然成立**
  （403 ENTITLEMENT_ERROR、兩帳號餘額各約 $0.005、OFF n=60 需 $0.39）。
- 但「所以這一輪只能停下來等錢」**不成立**——本輪改走本機端點，
  見 `DECISION_20260824_LOCAL_ENDPOINT.md`。
- 「要不要買 Cline 額度」仍然是**人類的決定**，只是**不再擋住本輪的進度**。
  買的價值在於「用原池重跑當對照」，不是「解除封鎖」。
