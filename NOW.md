# NOW — R-loop (auto/qwen27b)

## 第 1171 輪 (2026-11-07)
**票 P20261107_0644-1 驗收完成：max_row_first 抽取頂層單一事實來源＋單元測試（0 呼叫、0 元、0 發射）**

- commit c0e64ff4：`checks.py` 內嵌 max_row_first 區塊→單行 `_max_row_first(rows, rc)`（頂層、`_mean_int_col` 前、行為逐位元組同）；`tests/test_reqloop_checks.py` 新增 `test_max_row_first_standalone_helper`（平手取首列／非平手取最大／缺 sel·out 欄／無可解析列／輸出欄不可解析→UnknownSource）。
- 驗收：`pytest tests/test_reqloop_checks.py -k max_row_first -v` → **2 passed**（改前 1 passed）；全檔 58 passed；slice 15 passed；repair selftest 13/13。票已移 done/、doing/ 空。
- 效果：純重構＋測試（單一事實來源、防審計端複製解析迴圈漂移）；非效果進展、不宣稱變好。
- 卡點（如實）：下一步全為候需求端點名的發射——vq-6rp（1753）、vq-5nz.6（停滯 8 格換方法）、dab_055 2 格、dab_426 切片（現可用 `_max_row_first` 做單一事實來源預檢）。
- 下一步：點名後發射（新成本另報）；點名前不發射、不同題重跑、不改文件湊進展。

（NOW 上限 3 KB、覆寫不追加）
