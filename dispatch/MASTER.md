# Master dispatch — the actual prompts you paste

Two modes. Pick one. **Mode 1 is recommended.**

---

## Mode 1 — Per-stage starter (recommended)

**Use this when**: you want clean PRs you can actually review, parallelism (P1+P2, P3+P6), and isolation (one stage failing doesn't poison the rest).

For each stage, open a new Claude Code session at https://claude.ai/code, connect `cosmopig/Vacant`, and paste this **starter prompt**, replacing the file name with the stage you want:

```
請執行 dispatch/P0_bootstrap.md。

規則：
1. 先讀 /CLAUDE.md（重要：load-bearing theory invariants 必須遵守，不要靜默更動）
2. 再讀 architecture/CONSTANTS.md（全部數值的單一來源，引用它而不是自己編）
3. 然後讀 dispatch/P0_bootstrap.md 全文，嚴格按照 Scope / Acceptance / Out of scope 執行
4. 開 branch:feat/p0-bootstrap
5. 寫 code + tests，跑 uv run ruff check . && uv run mypy src/ && uv run pytest 直到全綠
6. commit + push 該 branch
7. 用 gh pr create（或手動）開 PR，標題用該檔案 Output 行寫的標題
8. 不要自己 merge — 等我 review
9. 規格有模糊處：開 architecture/decisions/D###_<topic>.md ADR 釘死你的解讀，在 PR description 列出
10. 跑超過 2 次還是失敗的 test：停下來、開 blocked PR、ping 我

完成後在 chat 裡跟我說「P0 done, PR #N，已通過 CI，等 review」。
```

**順序與平行性**（每段做完、merge 後再開下一段）：

| Stage | 檔名換成 | 可平行 |
|---|---|---|
| 1 | `dispatch/P0_bootstrap.md` | — |
| 2a | `dispatch/P1_runtime.md` | 跟 2b 同時開兩個 session |
| 2b | `dispatch/P2_identity.md` | 跟 2a 同時 |
| 3 | `dispatch/P4_registry.md` | — |
| 4a | `dispatch/P3_reputation.md` | 跟 4b 同時 |
| 4b | `dispatch/P6_protocol.md` | 跟 4a 同時 |
| 5 | `dispatch/P5_composite.md` | — |
| ★ | `dispatch/Padv_review.md` | 在每個敏感 PR merge 後跑（P2/P3/P4/P5/P6） |
| 6 | `dispatch/P7_mvp.md` | — |

每段你只做兩件事：(1) 貼 starter prompt 換檔名 (2) 收到 PR 就 review。

---

## Mode 2 — One-shot orchestrator (autonomous)

**Use this when**: 你想走開不管，回來看結果。
**接受代價**：(a) 不可平行 (b) 一段卡住整個鏈卡住 (c) PR 之間沒人類把關，theory invariant 被靜默改了不會被擋下 (d) 雲端 session 有 token / 時間上限可能跑不完。

開一個 session，貼下面整段：

```
你的任務：把 cosmopig/Vacant repo 的 14 週 MVP 做完，逐段執行
dispatch/{P0,P1,P2,P4,P3,P6,P5,P7}_*.md，每段一個 PR，等我 merge 再進下一段。

執行順序（嚴格遵守）：
  1. P0_bootstrap
  2. 完成 P1_runtime（不要跟 P2 合併 — 它們在 Mode 1 是平行段，
     這裡你串行跑，但仍然分兩個 PR）
  3. P2_identity
  4. P4_registry
  5. P3_reputation
  6. P6_protocol
  7. P5_composite
  8. P7_mvp（這段是 14 週工作的 4 週，自己分多個 PR）

每段執行流程：
  a. 讀 /CLAUDE.md + architecture/CONSTANTS.md（每段都重讀，不要相信 cache）
  b. 讀對應 dispatch/P*_*.md 全文
  c. 開 branch feat/p<n>-<slug>
  d. 寫 code + tests，跑 uv 三件套到全綠
     （uv run ruff check . && uv run mypy src/ && uv run pytest）
  e. push + gh pr create，標題用該檔案 Output 行
  f. 在 chat 對我說「Stage Px ready, PR #N. Reply 'merged' to continue.」
  g. **停下來**等我回 'merged'。**不要**自己 merge 也**不要**進下一段。
  h. 我回 'merged' 才繼續下一段。

關鍵不變式（CLAUDE.md 已寫，這裡再強調，發現衝突就停下來問我）：
  - D1-D5 是主要 birth path；不實作 Path A
  - Registry 是 per-vacant，不是中心節點
  - Sunk heartbeat = identity custody attestation，不是 liveness
  - Lineage 才是無限進化的主體，不是個體 vacant
  - same-* 三線是 cost-raising，不是 prevent
  - LOCAL state = 完整可運作的 vacant，只差 visibility=none
  - 沒有 central judge / oracle / 任何中央 LLM

對抗審查（Padv_review.md）：在 P2 / P3 / P4 / P5 / P6 五段 merge 後，
你要主動跑 dispatch/Padv_review.md 對該 PR 攻擊，開另一個 PR 命名
"Padv #<原PR編號>: adversarial review"，每段至少 3 個攻擊測試。

任何時候卡住、規格模糊、test 跑 2 次還失敗：停、ping 我、開 ADR、不要硬幹。

開始 P0。
```

---

## 實際操作建議

我（人類論文作者）的真實建議：**用 Mode 1**。

原因：
1. **Review 體驗**：8 個 PR 各自獨立，每個 1500-3000 行，你看得懂；Mode 2 一個 PR 也許 8000+ 行，等於你白給。
2. **平行性**：Mode 1 的 P1+P2 / P3+P6 各省 2 週，14 週 → 12 週實際可達。Mode 2 全串列，反而更慢。
3. **失敗隔離**：P3 卡住，Mode 1 你還可以同時推 P5/P6；Mode 2 一卡全卡。
4. **Token 成本**：Mode 1 每 session prefix 重複讀 spec 沒錯，但 caching 起作用、總開銷未必比 Mode 2 高。Mode 2 後段 context 爆掉時要 compact，吐字品質可能下降。
5. **theory invariants 把關**：8 次 PR review = 8 次你檢查它有沒有偷改不變式的機會。Mode 2 只有最後一次。

Mode 2 適合場景：你完全不在乎品質，只要「跑得起來」的 demo，或是你要趕 thesis defense 前 48 小時硬塞。

---

## 起手式（你現在就做）

1. ☐ 確定 branch protection 已設（步驟在 `HOW_TO_DISPATCH.md`）
2. ☐ 確定 `ANTHROPIC_API_KEY` 已加進 repo secrets
3. ☐ 開 https://claude.ai/code
4. ☐ Connect repo: `cosmopig/Vacant`
5. ☐ 貼 Mode 1 的 starter prompt（檔名：`dispatch/P0_bootstrap.md`）
6. ☐ 等
7. ☐ Review PR → merge → 開兩個新 session 同時跑 P1 + P2

走完一輪你會找到節奏。
