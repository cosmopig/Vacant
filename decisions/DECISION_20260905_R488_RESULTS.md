# R488 結果：`ts` 解出來了；時點曝光的安慰劑設計壞掉，P-2 無結論

日期：2026-09-05（round759，Opus 5）
判準 `6ac4d2e`／P-1 量具 `d37813b`／P-2 量具 `30df8b0`。資料＝已落盤快照，本輪未打 8766。
中止準則已驗：`r486_gateway_snapshot_v2.json` sha256 `060efe0c…` 與 round757/758 逐字元相同。

## P-1：`TS_IS_START`（採用，但看揭露節）

```
verdict TS_IS_START  population_sensitive=False
  all   TS_IS_START  n_pairs=2898 inv={ts:0.22291, ts_plus_lat:0.00035, ts_minus_lat:0.22912}
        sign best=ts_plus_lat second=ts b=646 c=1 p=2.219e-192
  chat  TS_IS_START  n_pairs=785  inv={ts:0.02038, ts_plus_lat:0.00127, ts_minus_lat:0.19236}
        sign best=ts_plus_lat second=ts b=16  c=1 p=0.000274658203125
  calibration recovered 3/6 directional  rule_broken=False  wrong_direction=[]
  calibration strict  rule_broken_strict=True strict_mismatch=[pos_start_j1, pos_start_j0.2, neg_end_j0.2]
```

⇒ **閘道的 `ts` 是「請求起始」時刻，`id` 在完成時指派。** 兩個母體一致。
逆序比例與 R487-B 的原始輸出**逐位數相同**（換的是邊際規則，不是資料）。

**⚠ 這不是獨立確認。** 判準是在已知舊規則排名方向之後設計的，
`DECISION_20260905_R488_POINTWISE_CONCURRENCY_PREREG.md` 的揭露節寫在前面。
R487-B 的舊判準與舊輸出**原樣保留**，後輪要收回仲裁權以舊輸出為準。

### 判準有兩個讀法，兩個都記

預註冊寫「負對照必須判 `TS_IS_END`」，又把作廢條件寫成「**方向**判錯任一個」。
兩句在「吐 UNRESOLVED」時矛盾。**我沒有默默選對自己有利的那個讀法**，兩個都算：

- `wrong_direction`＝0 ⇒ `rule_broken=False`（本輪採用這個，它是預註冊寫下的作廢條款）
- `rule_broken_strict=True`（3 個 UNRESOLVED）⇒ **原樣留在輸出裡**，後輪可據此不採用 P-1

三個沒回收的母體全部是「**正確的鍵已經排在第一、b>c 方向也對，只是 discordant pair 太少**
（b=4,c=0,p=0.125）」——不是判錯方向，是樣本不足時的保守。`neg_end_j0.2` 與
`pos_start_j0.2` 是同一個構造的鏡像，兩邊套不同標準才是雙重標準。

### 順手抓到一條死碼（已刪，不留空綠燈）

原本 `b > c` 的方向擋門是**死碼**：
1. `best` 是逆序**計數**的 argmin（同一組 pair、同分母）⇒ `#viol(best) <= #viol(second)` ⇒ `c <= b`，`b < c` 不可達；
2. 剩下唯一能讓 `b > c` 為假的是 `b == c`，而 `b == c` 使 `binom_two_sided(b,2b) == 1.0 > 0.01` ⇒ p 擋門已經先擋掉。

兩半都用**窮舉斷言**寫進 selftest（不是註解宣稱）。刪掉後真實資料與全部校準母體
**判決逐字元相同**（`/tmp/r488_before.json == /tmp/r488_after.json` ⇒ `identical: True`）。
`M8_SWAP_BC` 因此從「必須被抓到」變成**真正的 no-op**（binom p 對 b↔c 對稱，
方向由排名 `best_key` 承擔），已改列為第二個 no-op 對照並補窮舉對稱性斷言；
**它原本 MISSED 的輸出記在 GAIN_STATE.md round759**。補上 `M9_RANK_BY_MAX`
打真正承重的排名。selftest 44/44、mutants 8/8（含兩個 no-op 對照）。

## P-2：`PLACEBO_UNSCANNED` ⇒ **本輪沒有答案**（安慰劑設計壞掉，不是資料不夠）

主判＝ P-1 解出的 H=start：

```
P-2 verdict PLACEBO_UNSCANNED   ts_verdict=TS_IS_START ts_resolved=True sensitivity_agrees=False
  H=start PLACEBO_UNSCANNED  n_subset=728 n_hi/lo=371/357 cov=1.000
        real ratio=1.8652 CI=[1.6844, 2.1051] buckets_used=5
        placebo -3600s ratio=None cov=0.870 n_hi/lo=630/3
        placebo -1800s ratio=None cov=0.919 n_hi/lo=667/2
        placebo +1800s ratio=None cov=0.999 n_hi/lo=725/2
        placebo +3600s ratio=None cov=0.996 n_hi/lo=715/10
        common-rowset n=630 verdict=PLACEBO_UNSCANNED ratio=1.7534 CI=[1.6695, 1.8427]
  H=end   PERIOD_CONFOUNDED  real ratio=0.8540 CI=[0.7056, 1.1247]
        placebos 0.9839 / 1.0559 / 1.0020 / 0.6804
```

### ⛔ 不准引用 1.865

`real ratio=1.8652 CI=[1.6844, 2.1051]` **不是本輪的結論**，它沒有通過安慰劑擋門。
（它和 R487 用壽命重疊算出的 1.852 幾乎一樣，這個巧合**更該當警訊而不是佐證**。）

### 安慰劑為什麼壞掉——診斷（post-hoc，不計入預測帳）

安慰劑的低曝光臂整個塌掉（`n_lo` 728 列裡只剩 2–10），所以每桶 `>=20` 列的門檻一格都湊不到，
`ratio=None` ⇒ 依判準記 `PLACEBO_UNSCANNED`。直接量：

```
exposure AT OWN START   : mean 0.601  frac==0 0.464
exposure AT RANDOM TIME : mean 1.569  frac==0 0.025
gap from start_i back to nearest PRECEDING end: median 0.109s  frac<0.5s 0.908  frac<2s 0.961
server has >=1 chat open for 97.8% of the window (531.4 min total)
```

⇒ **客戶端是依序的**：90.8% 的請求起始落在前一筆結束後 0.5 秒內（中位數 0.109 秒）。
「請求起始」這個時點在機制上**就是一個位子剛空出來的瞬間**，
而伺服器 97.8% 的時間至少有一筆 chat 開著。
⇒ **平移時點採樣到的是一種結構上不同的瞬間**（2.5% 空 vs 起始時的 46.4% 空），
它不是這個估計量的虛無，兩者的 `|log ratio|` 本來就不該拿來比大小。

**⇒ 修法（下輪的設計，不是本輪結論）：安慰劑改成「別筆請求的起始時點」**
（把 start 時刻在請求之間**置換**）。那保住了「位子剛空出來的瞬間」這個結構，
同時切斷與這一筆請求的因果連結。時間平移這個形式已證明不可用。

## 可證偽性自查（預註冊列的五條，逐條回答）

1. **P-1 三條門檻各自可假嗎？** 可以，且都有夾具看得見：`MIN_PAIRS`（`pop_small_n20`）、
   `MAX_BEST_INV`（`neg_noise`／`dec_high_inv`）、sign p（`pop_start_j1`）。
   **第四條 `b > c` 是強制綠燈（死碼），已刪並窮舉證明。**
2. **`PERIOD_CONFOUNDED` 會被強制成立嗎？** 本輪沒有（H=start 先被 `PLACEBO_UNSCANNED` 擋下）。
   但**擋門順序有缺陷**，見下一條。
3. **`PLACEBO_UNSCANNED` 結構上永遠不觸發嗎？** 相反——它就是本輪的判決，
   **在真實資料上證明有牙齒**。
4. **有兩條預測在數同一個事件嗎？** P-1 與 P-2 量的是不同的量，但**不獨立**：
   P-1 的判決**選擇** P-2 用哪一支當主判。P-1 若判 END，P-2 主判會變成
   `PERIOD_CONFOUNDED`（H=end 那支）。收官引用時兩條要一起看。
5. **鏡像問：訊號完美時判準有沒有可能仍吐不出判決？** **有，這是本輪找到的第二個形式缺陷。**
   安慰劑擋門是**無條件的**且排在 `NO_TAX` **之上** ⇒ 真實效應越接近虛無，
   越容易被一個同樣接近虛無的安慰劑「超車」。真的沒有效應時會被報成 `PERIOD_CONFOUNDED`
   而不是 `NO_TAX`（＝**強制綠燈的鏡像**）。判準已鎖，**本輪不當場修**，
   只用 selftest 兩條斷言把它釘成可見的事實（`placebo gate outranks a null real effect`、
   `NO_TAX is reachable only when real is further from 1 than every placebo`）。
   下輪修時**唯一可用的理由是語意或合成復現**。

## 預測帳（照實記）

| 預測 | 結果 |
|---|---|
| P-1 `TS_IS_START` | **兌現**（但有偏，見揭露節） |
| P-2 `PERIOD_CONFOUNDED` | **未兌現**：主判（H=start）是 `PLACEBO_UNSCANNED`。H=end 那支確實是 `PERIOD_CONFOUNDED`，但那不是主判，**不算命中** |

## 推翻條件（事前寫的，本輪觸發情況）

- P-1 負對照方向判錯 ⇒ `RULE_BROKEN`：**未觸發**（`wrong_direction=[]`）。
- P-2「安慰劑與真實不是同一組列」⇒ 必須在共同列集合再算：**已照做並已報**
  （H=start common-rowset n=630 ratio=1.7534，安慰劑仍全 None ⇒ 判決不變）。
- 與主 run `g_r461_lcb3_three_arm` 衝突以主 run 為準：本輪無衝突（主 run 未收官）。

## 誠實邊界

- **零模型呼叫**；`gain_run.py` 一個 byte 沒改；沒起／沒殺任何 run；
  **沒有 `git add` 主 run 目錄**；沒動門檻檔；沒碰 `world/`／`design/`／`vacant_hm`；
  沒改 `max_tokens` 或 `--request-timeout-s`；沒刪 R487-B 的任何判準或輸出。
- 本輪未引用任何被認證的數字；`cert_drift_gate.py` 仍照跑：rc=0
  `STALE_CERTS_PRESENT`（`paired_ci.py`、`r447_gauge_capability.py`，與上輪紀錄相同，未變動）。
- 快照本身的已知限制沿用 R485/R486：端點非獨佔，窗口內有別人的請求。
