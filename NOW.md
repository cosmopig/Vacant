# NOW — 第 1178 輪（2026-11-07，≤ 3 KB、覆寫不追加；細節放 bd）

## 現在：r1178 收尾——票 P20261107_0001-1（extract.py 接 glm 後端＋真擷取 orders_monthly）已完成（done/），doing/ 空

- **驗收全綠**：`python3 -m vacant_network.reqloop.extract --task ops/reqloop/g1/tasks/orders_monthly --model glm53`
  →「條目 9、丟棄 0、unverified 2」RC=0（N=9≥3）；`tail -1 ~/dev/ops/state/vibe_calls.jsonl`＝
  glm53／orders_monthly 擷取需求／rc=0／7416 tok。commit `fa96421f`（extract.py＋tests＋輸出 json）。
- **功能**：`extract.py` 新增 `GlmClient`（subprocess 只走 `glm` 指令，非 0 一律 fail-closed 不重試）、
  `build_task_prompt`（request 全文＋資料檔欄位與前 5 列＋12 個 verifier 清單與輸出格式；
  kind 限定 explicit/assumption/preference）、`csv_preview`、`run_task`、`main` CLI
  （預設寫 `ops/reqloop/extract/out/<task>.<model>.json`，含 report）。
- **擷取結果**：9 條目全留（rowset_filter×2、csv_structure、monthly_sales_metrics、
  monthly_top_products、summary_numbers、summary_metrics_consistency 等）；R6 缺 required_columns、
  R8 缺 tag → unverified（fail-closed，檢查時 UNKNOWN）。首次跑 9/9 被丟棄是模型自造 kind，
  已在 prompt 寫明合法值後復跑通過（2 次模型呼叫合計約 15k tok，遠低於每日 200 萬 token 上限）。
- **下一步**：等規劃者下一票（vq-el4.3：run_eval.py 第一項 G1 用擷取需求重跑）。
- effects2_20261106 讓它跑完、未重跑未改快照；dab_055 發射仍候點名；1753 維持排除。

## 紅線（不變）
main 不動；不手動 push；不讀 `/srv/eval` hidden/scorer；不洩露金鑰；不繞過 glm 直連 vibe；
不發 frozen 實驗、不做大重跑。本輪 2 次 GLM 5.3 擷取呼叫（票內授權）。
