# HumanEval × pi 對話介面 × 有/沒有 Vacant —— **量具就緒，跑不完，原因量出來了**

> **狀態：harness 驗證通過，正式批次未跑。** 擋門不是 Vacant、不是 pi、也不是模型，
> 是**這個容器出網過濾器自己的 DNS 不穩**（`BLOCKER.txt` 有逐通實測）。
> 硬跑只會產出一整批 `infra_void`，所以停在這裡等一條穩定的路。

## 一、為什麼用 HumanEval

人類 2026-09-22 要求「**公正的、有量化結果的**」題目，明講不要用本 repo 自己的題庫。

- 來源：`https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz`
  （OpenAI，MIT，164 題），外界有大量公開的 pass@1 數字可對照。
- 抽樣：**等距 `range(0, 164, 8)` ⇒ 20 題**。沒有隨機種子、沒有人工挑選，
  「挑好做的題」在流程上不可表達。清單在 `bank/manifest.json`。
- **可見 ⊂ 隱藏**（與 r534 同一個關係）：可見＝官方 `check()` 的**前 2 條 assert**，
  閘門看它；隱藏＝官方 `check()` **整份**，一題一個布林 ＝ HumanEval 的標準計分
  （pass@1，n=1 樣本）⇒ 算出來的比率跟外界公布的是同一把尺。
- 隱藏那份**永遠不進工作區**，失敗訊息不回饋給模型。

### 尺自己先通過正負控制（`tools/score.py`）

| 控制 | 結果 |
|---|---|
| 官方 canonical solution 要全過 | **20/20** ✅ |
| 退化樁 `def <entry>(*a, **k): return None` 要全擋 | **0/20 過** ✅ |

## 二、兩臂的設計（唯一差異＝有沒有 Vacant）

**兩臂都走對話介面**：真 pty 開 TUI，把**同一句話打進輸入框**（不是 `pi -p`，
也不是命令列帶 prompt）——人類明確要求「最好使用對話的 cli」。

| | ON | OFF |
|---|---|---|
| 命令 | `vacant on pi --workspace … --suite … --retry none` | `pi`（自己的 `models.json` 直接指上游） |
| 模型通道 | 經 Vacant 的 proxy，逐通落盤 | 直連，**沒有任何紀錄** |
| 結束時 | 跑驗收、簽收據、退出碼＝裁決 | 什麼都不做 |
| 打進輸入框的話 | 逐字相同 | 逐字相同 |
| 完成判定／離開 | 同一套（輸出靜默 → `/quit` → Ctrl-D → SIGTERM） | 同一套 |

判定用啟發式的「輸出靜默」而不是掛鉤日誌，理由是 `vacant on` 走 `agentwrap`
**不裝掛鉤**（掛鉤是 `gateshim` 裝的）⇒ 兩臂只能共用同一個啟發式，至少是同一把尺。

## 三、pilot：harness 是通的，被上游打斷

`HumanEval_0` ON 臂（`pilot/`）。轉錄 `HumanEval_0_ON.pty` 逐字可讀：

1. TUI 起來，狀態列顯示 **`(vacantproxy) gemma-4-12b-it-qat`** ⇒ 通道接上了
2. 那一句被打進輸入框並送出 ⇒ `Working` 轉了幾秒
3. **`Error: 403 Host resolves to a private/reserved IP: resolve_no_records`**
4. `/quit` → pi 結束 → **閘門照樣跑完**：
   `拒交（visible_fail）　ws 9a2eabdd730f→9a2eabdd730f　wire 1 通`，退出碼 **20**

⇒ **Vacant 這一側每一段都動了**（中介、打字、閘門、收據、工作區雜湊前後相同）。
   死在第 3 步的是出網。

## 四、擋門（`BLOCKER.txt` 是逐通實測）

```
HTTP/2 403  x-deny-reason: resolve_no_records
HTTP/2 503  DNS resolution failure
```

| 探測 | 成功率 |
|---|---|
| `1003.taild870c4.ts.net` 強制 IPv4 | 4/8 |
| 同上 強制 IPv6 | **0/8** |
| 同上 間隔 3 秒 ×12 | 5/12（≈42%） |
| **對照** `pypi.org`（在容器 `NO_PROXY` 名單裡） | **6/6** |
| **對照** `api.github.com`（不在名單，政策內被擋） | 0/6 |
| **對照** 本機自己解析該名字 | 5/6 |

一個 agent session 要 5–15 通模型呼叫；每通 42% ⇒ 整段跑完的機率約 `0.42^5 ≈ 1%`。
**所以這不是「多跑幾次就好」，是路不通。**

## 五、要跑完需要哪一條（擇一）

1. **加入 tailnet**：容器的 `NO_PROXY` **已經包含 `100.64.0.0/10`**
   ⇒ tailnet 位址**本來就繞過過濾器**，那是設計上穩定的路。
   需要：人類的 auth key ＋ 放行「啟動 tailscaled」那一類動作（先前被分類器擋下）。
2. **在 vacant-dev 上跑**：它與 1003 同在 LAN，完全碰不到這個過濾器。
   `tools/cell.sh` 改一下 `HE_UPSTREAM` 就能直接用。
3. 換一個**過濾器解析得穩**的公開端點（`*.ts.net` 這個名字實測不穩）。

## 重跑

```
python3 tools/build.py 8                  # 重建題庫（等距抽樣，確定性）
bash tools/cell.sh HumanEval_0 ON         # 有 Vacant（對話介面）
bash tools/cell.sh HumanEval_0 OFF        # 純 pi（對話介面）
python3 tools/score.py HumanEval_0 <ws>/solution.py   # 官方隱藏尺
```
