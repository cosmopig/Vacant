# cchard-L 校準（2026-11-27）：Haiku A 臂 33/37（89.2%），在 25–70% 之外 ⇒ 不跑正式批次，轉候選 2

預註冊：`decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md` 候選 1。**這 39 題 Haiku 在 cchard 校準時已做過一次（35/39）**；cchard-L 是加了大測資的新題池。

## 量到的
- 建置：39 份 Haiku 寫的輸入生成器（每題 1 次呼叫，$0.07 總計）；每題 12 筆候選（max×6、mid×3、edge×3），≥2 份 C++ 正解一致且 ≤0.5×限時才保留。
  37 題收錄（每題 5–12 筆大測資，可見／hidden 各半）、2 題排除（cc_1567F、cc_1599D 保留 <4 筆）；37/37 參考解兩半皆過、空殼兩半皆不過。manifest `bank_cchardL_MANIFEST.json`。
- Haiku A×1、jobs 4、infra_void 0、逾時 0：**hidden 全過 33/37＝89.2%**（序列評分，`CALIBRATION_haiku_cchardL_A.md`／`table.json`）；費用 $0.955；牆鐘中位 121 s、平均 182 s、最長 800 s。
  交付語言：C++ 30、Python 7。失敗 4 題：cc_1558D（C++，35/36 wrong answer）、cc_1599A（py，3/36）、cc_1586G（py，31/36 time limit）、cc_1608G（C++，35/36 runtime error）。
- 與 cchard（35/39）幾乎一樣。
- 憑證掃描（`credscan.json`）：41 個命中全是誤報——37 個是 Claude CLI 自己寫在沙箱 HOME 的 `policy-limits.json.signature.json`（JWT 形狀字串，非我們放入的憑證；是否敏感**未驗證**），其餘 4 個是任務資料／日誌裡的 `aaaa…`、`RLLR…` 之類字串。

## 推論（未驗證）
- 大測資沒有把 Haiku 逼出帶外：它大多選 C++，而 C++ 在這些大輸入上不吃力。
- 生成器的輸入合法性沒有獨立檢查（只靠 ≥2 份正解一致）。生成器作者與受測 worker 同家族。
