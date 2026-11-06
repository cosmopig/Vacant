# NOW

## 現在在哪（r1144）
- r1144：執行資深審查 2026-11-06 兩條指示（零模型呼叫、零發射）：
  1. auto/argon `23fd09eb`（reqloop checks 強化：read_table_deliverable 損毀行／重複鍵、csv_structure 缺欄假 PASS、kv/plain_recomputed 早退分支補 expected_in_evidence）合併入 auto/qwen27b（merge `c7755793`，無衝突）；5 檔驗收 218 passed。
  2. 切片收斂：刪除 `ops/reqloop/g2/realtask_manifest.json`（針「1628」/「0.020500」皆非真重算值——實算為 2081990 / 0.120132；且把 not_an_integer/not_a_number 格式錯誤標為 mismatch 內容錯）＋test_reqloop_g2.py 三枚專屬測試。
- 單一真實內容錯誤切片＝`real_slice/manifest.json`（dab_378-pi-C，2 臂 2 格）：--baseline 9 PASS / 2 FAIL，FAIL＝pre/post_kurtosis（草稿 -1.17 vs 真重算 -1.13，problem=mismatch_with_recomputation，expected_in_evidence=false）。
- 針「-1.13」由 checker 自己的 col_stats 路徑對凍結 task/data/2014_q4.csv 實算確認（raw -1.12955…→round2 -1.13）；新增守衛測試 test_real_slice_needle_is_true_recomputed_value（針漂移即紅）。
- 驗收：pytest tests/test_reqloop_g2.py tests/test_reqloop_real_slice.py＝44 passed；5 檔全集＝218 passed（220−3 移除＋1 新增）。

## 唯一切片（NOT_fired）
- real_slice/manifest.json：dab_378-pi-C × generic/localized＝2 格；六要素齊備；FROZEN_PENDING_NAMING（等需求端點名）。
- 已無第二份重疊 manifest（realtask_manifest.json 已刪；smoke/smoke_e013/smoke_e014 為管線冒煙/回歸凍結，非對照切片，保留）。

## 下一步
- 需求端點名 vq-6rp（dabstep-1753 模型側硬缺口）或 vq-5nz.6（停滯草稿換方法）；或授權後對 real_slice 做最小 A/B——generic/localized 兩臂起始草稿 sha256 完全相同（現 manifest 已凍結同一 draft 71c5097b…）、報告原始結果（localized 是否修好 pre/post_kurtosis 且保住其餘 9 項、成本 ≤ generic）、模型流量＝新成本先另報。
- 未授權：0 發射、0 新票、不加 regex／靜態 prompt。

## 紅線
不碰 main、不自 push（loop 自動推 auto/qwen27b）、不讀 /srv/eval hidden／scorer 源、缺值＝UNKNOWN 不填 0、不為「每輪有 commit」加 regex／靜態 prompt／未授權重跑／純文檔修補／補欄位水工單、批內開發選樣不宣稱 localized 較好、兩臂起始 hash 不一致不稱同草稿公平比較、tamper/UNKNOWN 不算成功。
