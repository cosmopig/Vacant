# NOW（r1235，2026-11-08 04:4x UTC）

## 現況（本輪驗證）
- **G2.5 三門本輪新鮮重跑**（HEAD ad87a1e0、`run_eval.py --all`、RC=0、離線 0 模型呼叫）：G1 抓錯 39/39、冤枉 0（41 呼叫/328,550 tok）；REAL14 9/9、冤枉 0/5（74 呼叫/732,826）；PHASE3 fixed 7、unresolved 2、rtw 0（15 sess/275 calls/15,087,278 tok）——與備案 ops/audits/g25_all_gates_filing.json（r1228）**逐數一致、無漂移**。審查 #1 由本輪自跑確認。
- **審查 #2 已滿足（審查資訊過時）**：其寫 worker HEAD=aca58a95／blob 410e1118；實際 worker HEAD=**80947934**（r1229 補救）、工單 **R20261108_0150-1 已在 tickets/done/**（驗收證據齊：pearson2 3 passed、hygiene 2 passed、reqloop+beads 357 passed）；**checks.py blob 三分支全＝f3525b01**（qwen27b/argon/worker 逐一 ls-tree 核）。
- 審查 #3 新鮮重驗：repair.py **2795 行/5147f8c3**、extract.py **e757aec5**、checks.py **f3525b01**（本輪 HEAD）——凍結與邊界未動。
- CI：LATEST_qwen27b＝441f88c3 🟢 5036/0/5109；**HEAD ad87a1e0（r1233 redo）CI 尚無檔**（loop 職掌、下 cycle）；argon fecd8657 🟢、worker 80947934 🟢 5039/0。
- G3（vq-1zf）：/srv/vlab/queue 空、done 無新件、審查 #5 明確等核准 → **0 模型呼叫**（本輪 0 呼叫、0 成本）。

## 下一步（下輪 r1236）
1. 驗 HEAD **ad87a1e0** CI 轉 🟢（純簿記、產品 diff 0→應綠）；紅燈才歸因。
2. G3：見核准信號→照 vq-1zf 發射（3 臂×dab_129/144/176/216、≤12 格、glm 唯一入口 ≤2M tok/日 fail-closed、scorer=/srv/vlab、四類分報）；未核准→0 呼叫。
3. 無其他工作：vq-el4 18/18 完結、工單 done、repair.py 凍結、不碰 main、不自發射大成本實驗。
