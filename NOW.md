# NOW — 第 1177 輪（2026-11-07，≤ 3 KB、覆寫不追加；細節放 bd）

## 現在：r1177 收尾——票 P20261107_0822-2 已完成（done/），doing/ 空，等規劃者下一票

- **驗收全綠**：`pytest tests/test_reqloop_checks.py -k group_ratio_stat` → 1 passed（改前 0 選中）；
  `pytest tests/test_reqloop_extract.py -k recompute_type_sets_match_dispatch` → 1 passed；
  reqloop 全線 205 passed。commit `61304ef1`（checks.py＋tests，2 檔 +209/-2）。
- **功能**：`checks.py::_group_ratio_stat`（分組金額比率極值；group_col/sum_col/
  num_sum_col/denom_sum_col、where/num_where、percent/stat min|max/out val|group、
  平手取首見、NaN/inf 忽略、無有效分母→UNKNOWN）；PLAIN_RECOMPUTE_TYPES＋分派鏈同步
  （extract.py 白名單同源）；`out="group"` 非數值答案跳過數值預檢（其餘型別行為不變）。
- **可重現內容反例**（dabstep-16/17 形，合成同形資料）：草稿 7.683437（count ratio 2132/27748）
  → FAIL `mismatch_with_recomputation`；8.907926（volume ratio）→ PASS；out="group" 分組名
  精確比對；重算值不進 detail/evidence（`expected_in_evidence=False`）。
- **下一步**：等規劃者下一票（`bd list --parent vq-el4 --all` 照順序）。bd ready 有
  vq-el4.2（Vibe CLI 後端；依 11/06 指示 5，六要素備齊前不自行開工）。
- effects2_20261106 讓它跑完、未重跑未改快照；dab_055 發射仍候點名；1753 維持排除。

## 紅線（不變）
main 不動；不手動 push；不讀 `/srv/eval` hidden/scorer；不洩露 `secrets/extract.env`；
不發 frozen 實驗、不做大重跑；0 模型呼叫、0 元。
