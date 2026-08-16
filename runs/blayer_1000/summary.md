# B 層機制驗收六情境 — 一頁結果

✅ **sig_attribution**（被收下的偽造票數）：on 全拒（max=0）；off 收下 7/7
✅ **same_source**（克隆團總實收權重）：on 末輪克隆團總重 0.04（≤0.5＝floor 曲線）；off 3.04（≥2.0＝路由可被劫持）
✅ **probation_whitewash**（洗白者路由佔比）：on 佔比 max 0.10（≤0.2）；off 1.00（≥0.35）
✅ **reviewer_stake**（reviewer 期末/期初權重比）：on 權重比 0.09（≤0.7）；off 1.00（≥0.9）
✅ **decay_slash**（高信譽期末分）：on 0.7格 0.00（≤0.65）、0格 0.92（≥0.85）；off 0.86（≥0.85）
✅ **memory_wipe**（wipe 前後表現回落）：on 回落 0.90（≥0.3）；off -0.10（≤0.1）

判準事前寫死於 vacant/blayer.py `_verdict`；「拆掉數字沒變」＝裝飾、從一切主張移除（13 §3）。
