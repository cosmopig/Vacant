# 2026-09-24 研究總結（分支 `research/verifier-mediation-20260924`）

## 問題一：不包模型端點，可究責性建立在什麼上面

**一句話**：拿不到模型端點時，承重的是**交付物層**（Vacant 在 agent 行程外拍工作區樹雜湊＋跑事先凍結的驗收）；
「每一步都有紀錄」降成**紀錄級**（掛鉤＋transcript＋工作區三源對帳）。在真 Claude Code 上：
**誠實 13 跑 11 跑 R-full、2 跑 R-opaque、0 誤判；10 種攻擊 8 種被標出，背景偽造＋補寫 transcript 那一種沒抓到。**

- 環境本身就是反例：本 session 的 Claude Code 在 `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 下，`--bare` 直接認證失敗。
- 掛鉤在場時，collector 失聯會**擋下**動作而不是放行（A8／A9：0 個動作在沒紀錄時被執行）。
- 刪掉掛鉤、寫 `disableAllHooks`：Claude Code **同一跑之內就熱重載生效**，但對帳抓得到（沒事前紀錄的動作＋設定雜湊變了）。
- transcript 的 requestId 數**不是**模型呼叫數：wire 真值 4/4 格都多 1 通框架側呼叫。
- 成本：每個掛鉤事件約 127 ms；28 格合計 US$0.80（Haiku 4.5）。
- 裁決：`decisions/DECISION_20260924_MEDIATION_WITHOUT_MODEL_WRAP.md`。原型：`vacant_network/vrun/sidecar.py`。

## 問題二：通用驗證器與 token 控管

**一句話**：能寫成程式的準則，確定性檢查零 token 又比 LLM 評審準；評審只該補殘差，而且它的票預設不算數。
**事實忠實度目前沒有便宜可靠的驗證器**——那一類應該回 unknown 交給人。

| 資料集 | 只用評審 | 確定性優先級聯 | 備註 |
|---|---|---|---|
| IFEval 540 題（Haiku 4.5） | 80.9%，2,329 token／題 | **92.2%，587 token／題** | 確定性單獨 97.5%（覆蓋 73%）、0 token |
| IFEval 同 150 題 | Haiku 79.5%／Sonnet 78.7% | Haiku 89.3%／Sonnet 90.7% | 換貴的評審沒看到差 |
| RAGTruth 300 題 | Haiku 75.2%／Sonnet 75.8%（貴 2.6 倍） | 確定性層在 dev 過不了門檻 ⇒ 退化成評審 | 評審拒絕的 precision 0.68 |
| 歸檔程式 run 3,696 列 | — | 可見測試：拒絕 0 誤殺，接受 14.6% 隱藏不過 | 0 token |
| V3 附逐字引文 | 全文評審 89.9% | **負結果**：原樣產出 45/60 被確定性層誤拒 | 證據單位設計錯（JSON 來源不該用文字引文） |

- token 上限換的是**覆蓋率**（多交給人），不是準確度（已判定準確度在每個上限都 0.73–0.75）。
- 評審在最機械的條件上最差：不准逗號 40/61、字數 36/52（確定性 66/66、52/52）。
- 裁決：`decisions/DECISION_20260924_GENERAL_VERIFIER_TOKEN_BUDGET.md`。原型：`vacant_network/genverify.py`。

## 最大的未解風險

1. **同一個 uid 下的偽造**（A7c）：背景行程對 collector 送假事件、同時補寫 transcript，紀錄級會顯示 R-full。
   只能提高成本（OS 查連線來源行程、具名管道 ACL），不能根除。
2. **Windows 一格都沒量**：掛鉤在 Windows 上的 shell、路徑、退出碼語意；managed settings 的 Windows 路徑（文件沒寫）。
3. **managed 層防拆沒量**：要寫系統政策檔，本 session 被權限分類器拒絕（正確——那會影響同機所有 Claude Code）。
4. **事實類驗證**：評審 75% 且大量誤拒；展場離線，Anthropic 評審不在場。
5. 用量上限事故：評審失敗曾被安靜算成 unknown（已修，見問題二裁決 §六）——同類的「量具說謊」在別處可能還有。

## 建議人類下一步要決定的事

1. 在**展場那台或拋棄式 VM**上（有管理權）量 managed 層：使用者層刪掉掛鉤／`disableAllHooks` 能不能關掉 managed 掛鉤。
2. A7c 要不要補（OS 層查連線來源），還是收據上明講這一格。
3. 要不要做 **V3 v2**（型別化錨點＋RAGTruth 自然錯誤，約 300 通評審）——決定事實類是長出確定性驗證器，還是定案「一律 unknown」。
4. 規格從哪來：展場固定任務 ⇒ **手寫凍結**最實際；自動萃取要另外量。
5. 評審白名單目前是**空的**（量過的類別都沒達到建議門檻）；展場若要評審，只能是本機模型，**一通都還沒量**。
6. 工具層中介（agent 只剩 Vacant 的執行器）值得重測——它是唯一「執行器本身就是 Vacant」的路。

## 測試

`PATH=$PWD/.venv/bin:$PATH .venv/bin/python -m pytest tests/ -q` ⇒ exit 0（新增 `test_sidecar.py` 17 條、`test_genverify.py` 14 條）。
⚠ 不把 venv 放進 PATH 時，`tests/test_exhibit_twin_wiring.py` 會呼叫系統 `python3`，而這個容器的系統 `cryptography` 壞掉——
那是環境問題，與本分支無關（在 `origin/fix/pi-integration-review` 上一樣）。

## 主要 commit

- 全部： `git log origin/fix/pi-integration-review..research/verifier-mediation-20260924 --oneline`
- `a7905d10` 第一段：sidecar＋genverify 原型、v1 格子（量具說謊紀錄）
- `eadc1fd0` 問題二計畫凍結（評審呼叫之前）、V0、IFEval 真值、RAGTruth 抽樣與 dev 門檻
- `220d49f9` 問題一 v2 量測 28 格＋wire 真值＋掛鉤開銷＋引用清單
- `8140481b` 問題一裁決草稿＋IFEval 評審結果
- `829adbbf` RAGTruth、V3、infra_void 事故修正
- 最後一個 commit：問題二裁決、Fable #2、`judge_policy` 白名單、本檔
