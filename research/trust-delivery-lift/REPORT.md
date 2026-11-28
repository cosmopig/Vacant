# trust-delivery-lift 結果報告

**分支：** `research/trust-delivery-lift`  
**模型：** Qwen2.5-0.5B-Instruct（CPU，transformers）  
**截止：** 2026-11-28（台北）；確認性批次同日跑完  

## English abstract

We tested **evidence-located repair (EVR)** vs cheap baselines under a **fixed two-call budget** and **paired call-1 drafts**, using a typed visible/hidden scorer with synthetic must-equal/must-differ controls. On **24 held-out org-profile tasks** (12 pilot mechanism, 12 confirmatory), **Qwen2.5-0.5B** achieved **1/12 whole-deliverable success** for both **BLIND** and **EVR** (8.3%, Wilson 95% CI [1.5%, 35.4%]). **No net lift** (0 paired wrong→right exclusive to EVR; 0 harms exclusive to BLIND). **Conclusion:** under this small model and task mix, **accountability-style feedback does not measurably improve delivery**; failure is mostly **capacity/formatting**, not missing repair signal after visible checks were strengthened.

---

## 1. 測了什麼

| 項目 | 內容 |
|------|------|
| 任務 | 24 份合成「公司簡介」結構化抽取（5 必填欄位／來源段落） |
| 機制 | **EVR**：可見檢查失敗欄位 + 來源摘錄；**BLIND** 全量重寫；**BLANKS**／**KEEP** 等基線 |
| 成本 | 每題 **2 次模型呼叫**：共用 **call-1 初稿**（`freeze_drafts.py`）+ 各臂 **call-2** |
| 評分 | **可見**：格式、幣別、城市不含逗號、數字需出現在來源；**隱藏**：typed gold（事後） |

預註冊：`PREREG.md`（確認性主比較 **EVR vs BLIND**，baseline 由 pilot_v2 凍結為 **BLIND**）。

## 2. 主要結果（確認性，holdout）

| 臂 | 完整交付成功 | 率 | 95% Wilson CI | wrong→right | right→wrong | completion tokens |
|----|-------------|-----|---------------|-------------|-------------|-------------------|
| BLIND | 1/12 | 8.3% | [1.5%, 35.4%] | 0 | 0 | 801 |
| EVR | 1/12 | 8.3% | [1.5%, 35.4%] | 0 | 0 | 781 |

- **配對差異：** EVR − BLIND = **0 pp**（同一題成功：1 題兩臂皆過；11 題兩臂皆敗）。
- **預註冊門檻（≥5 pp 且 CI 下界 > baseline）：** **未達成**。

## 3. 機制篩選（pilot_v2，paired）

| 臂 | 成功率 | net_gain_pp | 備註 |
|----|--------|-------------|------|
| BLIND / BLANKS / EVR | 1/12 (8.3%) | 0 | 同一初稿下 call-2 未翻轉成敗 |
| KEEP | 0/12 | −8.3 | 1 次右→左（相對初稿） |

增強可見檢查後，EVR 確實收到欄位級證據提示（例：`money_missing_currency`、`hq_city_must_be_city_only`），但 **0.5B 仍常原樣輸出**。

## 4. 評分器（P0）

`synthetic_controls`：**must-equal / must-differ** 全過（含百萬/十億、正負號、幣別、10% vs 10）。

## 5. 是否支持「問責／信任機制改善交付」？

**在此設定下：否（null）。**

條件：

- 模型：**Qwen2.5-0.5B** CPU
- 任務：短文來源、5 欄 JSON
- 預算：2 calls，無人工

**未排除**在較強小模型、更長上下文、或程式驗收任務上出現差異；本線僅證明 **訊號已到達但修復能力不足以改變整份成功率**。

## 6. 重現

```bash
cd research/trust-delivery-lift
../../.venv/bin/python harness.py --selftest-scorer
../../.venv/bin/python freeze_drafts.py --split confirm_ids --out data/confirm/drafts.jsonl
../../.venv/bin/python harness.py --split confirm_ids --arms BLIND,EVR --drafts data/confirm/drafts.jsonl --out data/confirm
../../.venv/bin/python recompute.py --rows data/confirm/rows.jsonl --out data/confirm/summary.json
```

原始列：`data/pilot_v2/rows.jsonl`、`data/confirm/rows.jsonl`。