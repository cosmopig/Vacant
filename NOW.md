# 現在（第 1209 輪後，2026-11-07）

## r1209：巡燈＋auto/worker 紅燈根因輪（0 模型呼叫、0 產品改動）
- 本分支：57ce9625 本地 CI 🟢 5028 passed/0 failed（收集 5101）；HEAD d46ef020
  僅 NOW/STATE 文檔、代碼逐位元組同 → 本分支代碼級綠燈成立（d46ef020 的 CI
  下一周期跑）。
- auto/worker fa10658f 紅燈 6 failed 根因已核實（我分支同 6 測試 9/9 passed）：
  (a) bbd54fff 改凍結 dabstep-10 草稿 30→5 行散文、未重釘 manifest
  → draft sha 漂移×3；(b) real_slice_dab055/manifest.json 被換成懸空 symlink
  →wt/worker/.../smoke_e013/...（目標不存在）→ 3 個 dab055 測試 FileNotFoundError。
  DECISION: 不動 auto/worker（他人 WIP、無授權、其提示自帶紅燈）；備案修法＝
  還原 manifest（自 manifest.json~auto_argon）、刪 2 懸空 symlink、草稿還 30。
- argon 新 WIP 3cf31e81（在 d46ef020 上）未審未合。
- redo：點名 6 檔案（effects summary、eval_phase3、progress、run_eval、extract、repair）
  已補開，依賴結論全部重驗吻合（7/10・6/10、7/10・4/10、6/9＋263 calls／14 sessions、
  fail-closed 機制在位、repair 2,795 行凍結）→ 原結論不變。

## 下一步
1. 等 G2.5 後續/審查新派工（vq-el4 全 closed、bd ready 空、無新工單）。
2. 若審查點名 worker 紅燈：照備案三動作修，不擴範圍。

## 紅線（不變）
main 不動；不手動 push；不讀 /srv/eval hidden／scorer；不繞 glm 直連 vibe；
不改 repair.py／G1 requirements.json／凍結快照；成本缺值＝UNKNOWN 不填 0。
