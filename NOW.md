# NOW.md（r1238 redo，2026-11-08 05:3x UTC）

## 主線
G2.5（vq-el4）18/18 完結；G3（vq-1zf）發射前置門已交付（88697cd6），仍待人類核准（queue 空→0 呼叫）。
**argon 合併（vq-1zf.2）：預檢全綠，只差 `ci/e847c56e.json` 綠燈**——本輪已把 reviewer 驗收指令在「實際合併樹」上預跑通過；CI 迴圈順序 qwen27b→argon→worker，argon 排在後（預計 ~05:51 出燈），超出本輪 05:46 硬限→**順延 r1239 合併**。

## 本輪成果（r1238）
- **redo（審查點名 effects_20261105_summary.json 本輪原未開）**：已 head＋json.load 補開（blob 856c2c71＝已提交、無漂移；50 格、policy30 g7/l6、once20 g7/l4、r2w0、local45→current50/50、local-vs-獨立分歧 3+2 全舊 checker、current-vs-獨立 mismatches 0）——與 r1237 redo 記錄逐欄一致；r1238 各陳述無引用此檔→**無需改數**，交付物不變。
- **一條指令（比上輪好）**：真實合併預演（detached worktree＋`git merge --no-commit auto/argon`，RC 0 無衝突）→ 在合併樹上跑 reviewer 點名驗收指令
  `~/dev/Vacant/.venv/bin/python -m pytest tests/test_reqloop_extract_run_eval.py tests/test_reqloop_g3gate.py -v` → **53 passed in 0.55s**、`ls /tmp/g3gate_*` 無殘留（上輪 53 passed 只在 argon 側樹；本輪是合併結果樹）。
- 合併範圍＝審查過的 4 檔（`git diff a364b2cc..auto/argon --stat`）：filing builder（硬路徑→`__file__` 動態＋`--out`）、filing json（僅 generated_at/head/sources.path）、2 測試檔（mkdtemp→tmp_path＋2 守護測試）；門禁數字與 sha 未變。
- 兩個新守護測試已逐個審查：洩漏守護（禁 /tmp 根建 g3gate_*）＋worktree 隔離（禁寫死路徑、`--out` 落 tmp_path、sources.path 依當前 repo）——邏輯正確。
- **凍結錨點三分支核對（比上輪多 worker）**：repair.py 2795 行/blob 5147f8c3、extract.py 1217 行/blob e757aec5、reqloop/checks.py blob f3525b01——qwen27b/argon/worker 全一致。
- 提示點名檔案全數開啟：build_g25_all_gates_filing.py、test_reqloop_g3gate.py、g25_all_gates_filing.json、repair.py、extract.py。
- 紅線核對：/srv/vlab/queue 空（G3 未發射、0 模型呼叫）；worker 工單 R20261108_0455-1 已 done；open 工單無；main 未動。

## 下一步（r1239）
`python3 ~/dev/ops/ci_status.py` 巡燈→**`ci/e847c56e.json` 🟢**（且收集數 ≥ 1d560930 的）→ `git merge --no-edit auto/argon` ＋上列 53 passed 驗收＋`/tmp` g3gate_* 檢查＋錨點重驗＋`bd close vq-1zf.2`；紅/缺則 DECISION 入 STATE 續等。之後續等 G3 人類核准。
