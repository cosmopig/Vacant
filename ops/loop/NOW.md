# NOW — Vacant（ops/loop 鏡像）

## 現況：r1297 落地 — freeze_check 崩潰失裁負控制（vq-el4.39，已關）
- **修復落地**：`ops/reqloop/freeze_check.py` main() 每項檢查經 `run_check` 包層——
  檢查拋異常（FILING JSON 損毀／缺失／filing 條目非 dict）時點名記 BROKEN
  （CRASH: <ExcType>: <msg>），9 項全在輸出＋單一裁決行必現（I-4：未測量不是通過）。
- **驗證**：freeze_check 10 passed（含新負控制 1）＋frozen_anchors 5＋ci_contract 2＝17 passed；
  實跑 9/9 OK → VERDICT: FROZEN_STATE_OK rc=0；沙盒 FILING 損毀再現：舊碼空 stdout＋無裁決行
  →新碼 9 項全在＋CRASH 點名＋FROZEN_STATE_BROKEN rc=1。
- **紅線不變**：G3 未發射（vq-1zf 待人工核准）、無新模型呼叫、不 push。

## Next（依序）
1. vq-1zf G3：待人工明確核准 → 然後 `--fire`（manifest 已 planned）。
2. CI：現 HEAD（qwen27b 90a5fbc4／argon eafda98f5／worker c4b931b1f）pending；
   新提交（r1297）需 CI 綠。
3. CI 綠→收尾；紅→依證據診斷（不猜）。

## 常規
- TDD RED→GREEN＋負控制；fail-closed；不得以改文件／同步數字充實進程。
- STATE.md＝完整賬本；ops/STATE.md＝鏡像（標題＋Current State）；
  NOW.md 與 ops/loop/NOW.md byte 一致；≤5 行/≤3KB。
- 提交於 auto/qwen27b → 簿記同步 /home/user1/dev/wt/{worker,argon}。
