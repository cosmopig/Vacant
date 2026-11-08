# NOW.md（r1237，2026-11-08 05:1x UTC）

## 主線
G2.5（vq-el4）18/18 完結；G3（vq-1zf）發射前置門已交付（88697cd6），仍待人類核准（queue 空→0 呼叫）。
本輪新項：**argon dd978829 審查完，合併等 CI 綠燈**（規則：跨分支合併等對應 SHA 綠燈；不輪詢）。

## 本輪成果（r1237）
- **一條指令（比上輪好）**：argon worktree `pytest tests/test_reqloop_g3gate.py tests/test_reqloop_extract_run_eval.py` → **53 passed in 0.67s**（含新洩漏守護＋worktree 隔離守護測試；上輪該兩測試不存在且 /tmp 有洩漏）。
- dd978829 審查（4 檔）：filing builder 硬路徑改 `__file__` 動態、g3gate 測試 mkdtemp→tmp_path、＋2 守護測試；filing 再生成僅 generated_at/git.head/sources.path、**門禁數字與 sha 全未變**。
- 清除 **3 個 /tmp/g3gate_* 洩漏目錄**（各僅 1 個測試 manifest.json）——新洩漏守護測試會因此紅燈，現 `ls /tmp/g3gate_*` 無殘留。
- 凍結錨點在 a364b2cc 重驗：repair 2795 行/5147f8c3、extract e757aec5、checks f3525b01（qwen27b/argon 一致）；d826f5b5/a364b2cc 純簿記、產品 diff 0。

## 邊界與紅線
- **G3 未發射**：待人類定案（/srv/vlab/queue 空）；不新開工單、不碰 main、不發射大成本實驗。
- 不讀 /srv/eval hidden 與 scorer.py；本輪 0 模型呼叫；成本缺值 UNKNOWN、cost_usd=0 不報 0 成本。

## 下一步
巡 CI（argon dd978829／qwen27b a364b2cc，頭報還沒跑完）→🟢 後：`git merge --no-edit auto/argon`（ff 至 e847c56e）＋兩測試檔驗收（預期 53 passed）＋`git ls-tree HEAD -- vacant_network/reqloop/repair.py` 錨點重驗＋簿記 commit；之後續等 G3 人類核准。
