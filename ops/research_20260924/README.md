# 2026-09-24 研究：不包模型端點的中介 ＋ 通用驗證器與 token 控管

先讀 `SUMMARY.md`（一頁結論），再讀兩份裁決：
`decisions/DECISION_20260924_MEDIATION_WITHOUT_MODEL_WRAP.md`（問題一）、
`decisions/DECISION_20260924_GENERAL_VERIFIER_TOKEN_BUDGET.md`（問題二）。

## 目錄

```
mediation/                         問題一：旁路 sidecar 在真 Claude Code 上的量測（L-real）
  run_cell.py                      一格一個目錄的量具（誠實基線、攻擊、真值格）
  cells/                           v2（正式）：28 格，每格 cell.json／events.jsonl／receipts_sidecar.*／verify.json
  cells_v1/                        v1：規則有誤的第一批（量具說謊紀錄，DECISION 問題一 §4-5）
  cells_managed_envvar_IGNORED/    managed 層第一次嘗試：環境變數被忽略，四格零觸發
  wire_extra_call_note.json        wire 比 transcript 多出的那一通的結構（body 不入庫）
  hook_overhead.json               掛鉤每事件開銷
verifier/                          問題二：通用驗證器（`vacant_network/genverify.py`）的量測
  PLAN.md                          評審呼叫之前凍結的分析計畫
  judge_claude.py                  評審後端（子行程 claude -p，全 I/O 落盤，KS-1 防呆）
  exp_visible_gate.py              V0：既有可見測試閘門 vs 隱藏測試（零 token，只讀 runs/）
  exp_ifeval.py                    V1：IFEval（GT＝官方 strict 檢查器）
  exp_ragtruth.py                  V2：RAGTruth（GT＝人工幻覺標註）
  exp_evidence.py                  V3：交付物附逐字引文（GT＝構造的注入錯誤）
  data/                            IFEval 資料＋官方檢查器原始碼（Apache-2.0）；RAGTruth 只留取得腳本（全檔不入庫）
  samples/                         RAGTruth dev／test 抽樣（seed 20260924）
  results/                         judge_calls_*.jsonl（每一通評審的完整 I/O）、*_rows_*.json、v*_report.json
fable/                             Fable 的判斷（逐字）
CITATIONS.md                       引用清單（全文／摘要／間接）
```

## 重跑

環境：`python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`。
問題一與評審需要能在子行程跑 `claude -p`（本研究在 Claude Code 遠端容器，Claude Code 2.1.281）。

```
# 測試
PATH=$PWD/.venv/bin:$PATH .venv/bin/python -m pytest tests/ -q

# 問題一
CELL_OUT=cells .venv/bin/python ops/research_20260924/mediation/run_cell.py all
.venv/bin/python -m vacant_network.vrun.sidecar verify ops/research_20260924/mediation/cells/<cell>

# 問題二
python3 ops/research_20260924/verifier/exp_visible_gate.py                    # V0，零 token
sh ops/research_20260924/verifier/data/fetch.sh                              # 取回 RAGTruth 全檔並驗 sha256
# IFEval 官方檢查器要 absl-py、langdetect、nltk、immutabledict＋ nltk 的 punkt／punkt_tab
NLTK_DATA=<dir> <venv>/bin/python ops/research_20260924/verifier/exp_ifeval.py gt
.venv/bin/python ops/research_20260924/verifier/exp_ifeval.py run --model claude-haiku-4-5-20251001
.venv/bin/python ops/research_20260924/verifier/exp_ifeval.py run --model claude-sonnet-5 --limit 150
.venv/bin/python ops/research_20260924/verifier/exp_ifeval.py report
.venv/bin/python ops/research_20260924/verifier/exp_ragtruth.py sample && ... dev && ... run --model <M> && ... report
.venv/bin/python ops/research_20260924/verifier/exp_evidence.py gen && ... run && ... report
```

評審呼叫有斷點續跑：`judge_claude.Judge` 讀回 `results/judge_calls_<exp>.jsonl` 裡成功的那一通
（鍵＝sha256(model, system, prompt)）。要**重新抽樣**評審，換一個 `results/` 目錄或刪掉那個 jsonl。

### 用本機模型重跑（1003／1004，本研究碰不到）

評審後端只有一個介面：`Judge.ask(system, prompt, tag) -> {ok, text, tokens_in, tokens_out, cost_usd}`。
要換成 LM Studio（OpenAI 相容）只要另寫一個同介面的類別（`POST /v1/chat/completions`，
`usage.prompt_tokens／completion_tokens`），`exp_*.py` 的 `from judge_claude import Judge` 換掉即可。
**本研究沒有寫也沒有跑那一個**——數字全部來自 Anthropic 的 Haiku 4.5／Sonnet 5。

## 隱私

- Claude Code 的 transcript 與模型請求 body 含帳號識別資料 ⇒ **不入庫**；只留雜湊與骨架
  （`cell.json` 的 `transcript_contains_account_email` 記的是「有沒有」）。
- 評審 I/O 全部入庫：內容只有公開資料集（IFEval、RAGTruth）與本研究產生的文字。
