# VERIFY：手機端「觀眾自己那半」獨立複驗（2026-09-21）

複驗對象＝`vacant-world-cloud` 的 `exp/post-submit-look-up-20260921-v2`。
**不是讀它的截圖，是自己起服務、自己跑、自己截。**

- 服務：`vacant-world-cloud` 的**釘住副本**跑在 **port 3378**（`DATA_DIR` 在 scratchpad）。
  釘住的原因：驗證期間 `public/index.html` 被另一個行程即時改了兩次。
  被測檔 sha256 = `594fd936e924857122c2a15352cbf6d047e71fe9c59839f9a51946de85799bd9`
- 一律 390×844、`deviceScaleFactor:2`、`isMobile:true`。
- ⚠ 沒有動 port 8420 上那個不是我起的行程。

## 量到的數字（不是印象）

| 問題 | 量法 | 結果 |
|---|---|---|
| (a) 送出一秒內看得出來嗎 | rAF 觀測 click→p5 真的可見 | **560.2 ms** ✅ |
| (b) 哪一個是我 | 記號 canvas 實際畫素 | 264×264、17328 px 非透明 ✅ |
| (c) 等待期間知道發生什麼嗎 | queued 段不動它 150 秒 | 計時器 **`""`**、永遠「抵達了」🔴 |
| (c) 同上，claimed 段 | claimed 後 90 秒 | `已經等了 0:01 → 1:38` ✅ |

## 負控制（都是我自己關掉、自己截）

- `negctl-lookup/` — `window.triggerLookUp` 覆寫成空實作。
  覆寫前 `typeof === "function"`（證明蓋掉的是真的那一個，不是蓋到空氣）。
  ON：`lookup.on` 出現；OFF：**從沒出現**，直接無聲跳完成頁。
- `negctl-safecenter/` — 注入 `.panel{justify-content:center!important}`。
  ON：`h2Top=+92.8`（標題看得到）；OFF：**`h2Top=-73.75`**（標題被切到視窗外）。
- `regress/R1` — `/api/result` 回 done **但不帶 card_png**（HTTP 200、
  伺服器確實 `status=done` 且無 `card_url`）⇒ 畫面停在「正在成形」、第三格沒亮。✅

## 我自己發現、原交付沒提的

`overlap/` — 完成頁剛到時，固定的「撤回碼…刪掉它」那一條（88% 不透明、z-index 6）
蓋住「換一支手機也能用它把這張卡刪掉」**75%**、
「⚠ 記號是公開的…撤回碼是秘密的」**48%**。`.panel` 的 `padding-bottom` 是 `0px`。
捲到底就不蓋了 ⇒ 可回復，但**觀眾抵達那一眼**正好蓋住那句安全提醒。

`scripts/` 是上面每個數字的產生器，可重跑。
