# NOW — r1376 (2026-11-10)

## Current State
- r1376 實質修復（vq-el4.66 開→關、非簿記輪）：真產品 bug（planner 例外條款；vq-el4 66/66 全閉後唯一授權之非等待工作）——G3 `QuotaGuard` 對 unknown-usage 通道 **fail-open**：只在 `usage.tokens` 非 None 時累計 `known_tokens`，通道若每通回報 unknown（None）→`known_tokens` 恆 0、`daily_token_cap` 永不觸發→舊碼放行無限呼叫，違反紅線「撞日額度即停、不得重試」（實證 cap=250 仍放行 50 次）。
- 修復（TDD）：`tests/test_reqloop_g3.py` 先增 2 測試→RED；`g3.py` `QuotaGuard` 增 `max_calls` fail-closed 後備（呼叫數恆可測、不依賴「用量恰好被測到」）＋`run_g3` 以 plan 上界（擷取每 task 一次＋每格 max_rounds）傳 `max_calls`→GREEN。缺值仍報 UNKNOWN（不假裝 0）、但放行有界。
- 驗收（本輪全數新跑）：`test_reqloop_g3.py` 18/18 PASS；守衛 7 檔 pinned 測試 48/48 PASS（anchors 5／ci 2／ves 19／g3gate 22）；freeze_check 10/11 OK（唯一 BROKEN＝`wt_clean`、僅因本輪 2 檔未 commit＝期中預期、commit 後 11/11）；ves 7/7 OK。
- **未 commit**（AGENTS.md 保守檔：未獲明確授權不 commit）；建議 `git commit -am 'r1376: QuotaGuard fail-open fix (unknown-usage bounded by max_calls)'`。

## Next Step (r1377)
1. 若獲授權：commit 本輪 2 檔（g3.py＋test_reqloop_g3.py）→freeze_check 應 11/11 OK。
2. CI 一次讀取：三分支 HEAD per-sha→記 GREEN/RED/UNKNOWN（不 poll）。
3. 待人類：G3 `--fire`（vq-1zf、不代發、不入 queue）；CI 通道裁決。

## Red lines
- 無 push；.github/workflows/ 只讀；不讀 /srv/eval/hidden/ 或 scorer.py；G3 未經人類核准不得發射（不代發 --fire、不入 queue）；/srv/vlab/queue/ 不放任務；無 reset/rebase；凍結檔（repair.py 2795 行、extract.py 1217 行、checks.py、run_eval.py）與 filing 不改；只跑相關測試、不自啟 full pytest；無 sleep poll CI；0 模型呼叫。
