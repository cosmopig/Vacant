# NOW

## 現在在哪（r1138）
- 審查三點核完：①auto/argon 無需合併（d5105097 綠燈維持、零無效忙碌）；②9329be88 待辦確認已不在 NOW.md（r1135 解除、僅 STATE 有紀錄）；③真實切片離線準備＝樹上已有兩份凍結規格，r1138 全門驗證綠。
- 雙切片（皆 NOT_fired、0 模型呼叫）：
  - A=realtask_manifest.json（sha 6550d7a8、e013 dab_055 CSV 均值＋e014 dabstep-1273 JSON 費率、4 格）
  - B=real_slice/manifest.json（P20261107_0237-1、e008 dab_378 CSV kurtosis、2 格；r1131 auto 51ac77ec 入樹＋tests/test_reqloop_real_slice.py 7 測試；ticket 檔缺失、六要素在 manifest 內）
- r1138 驗證（現樹、含 r1136 g2.py 改動後）：46 passed；A/B --dry-run 皆 EXIT=0（60 calls/4M tok/300s 上限在列）；A --baseline EXIT=0（dab_055 0/2、dabstep-1273 0/1 required、無洩漏）；B --baseline EXIT=0（9 PASS/2 FAIL＝pre/post_kurtosis -1.17 反例、expected_in_evidence=false）。
- HEAD 45527e97（r1137 auto；CI 未跑完、不阻塞、本輪不合併）；/srv/vlab/queue 空、done 無新結果；effects2 數字以 r1135 彙整為準。

## 下一步
- 若授權：fire A（追蹤中候選）或 B（同口徑替代）——要模型流量＝新成本、先另報；二擇一或分批、不並跑。
- 未授權：維持雙凍結、0 新票、不加 regex／靜態 prompt／重跑；候需求端點名 vq-6rp、vq-5nz.6（未點名不擴量）。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文檔修補、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
