# G3.3 預註冊假說（H0 門跨獨立呼叫穩定性；單題 dab_725）

- 狀態（2026-11-12 r1477）：**凍結完成（P20261112_0119-1）；未發射（0 model calls）**——
  manifest `ops/reqloop/g3_3/manifest.json`（schema `vacant.reqloop.g3gate.plan/1`）＋
  任務輸入凍結副本 `ops/reqloop/g3_3/tasks/dab_725/`（與 g3_2 byte-identical、逐檔 sha256 核）
  ＋預檢查 `ops/audits/g3_3_precheck.py`（--selftest 離線雙核）＋單測
  `tests/test_reqloop_g3_3_manifest.py`。官方乾跑
  `python3 -m vacant_network.reqloop.g3 --manifest ops/reqloop/g3_3/manifest.json --dry-run`
  → DRY-RUN OK（RC 0、0 模型呼叫）。發射＝核准後另一步（approval gate fail-closed；本票不發射）。
- 依據（全部 in-repo 證據）：
  - G3.2 結果：`ops/audits/g3_2_fire_summary.json`＋`ops/audits/g3_2_interpretation.md`
    （H1_REFUTED；26/26 UNKNOWN；主因 deliverable_not_in_request 20/26）。
  - H0 門不穩定證據：dab_725 同 input_sha256（9ba533c0…）、同模型 glm53，兩次獨立
    extract 呼叫→確定性 claim 2（預跑 r1469、`ops/audits/g3_2_h0_prerun_report.json`）
    →0（fire r1472、`ops/audits/g3_2_fire_summary.json`）、claim 分解 7→6；
    dab_587/657/517 兩輪一致（0→0）。
  - 機制口徑：H0 門＝單次 extract 呼叫；門量的是「該次呼叫」，不是「該題」。
  - 上游假說：`ops/reqloop/g3_2_candidate_hypothesis.md` §6（G3.3 問首提處；§6 原文
    保留於 g3_2 檔不改歷史，本檔為其獨立確立版）。

## 1. H2（G3.3 可證偽假說，帶分母）
> 同題 dab_725（唯一預跑 H0_MET 題）、同模型 glm53、同 input：3 次獨立 extract
> 呼叫（已有 2 次＝預跑 r1469＋fire r1472，另 1 次新呼叫）中，**≥2/3 次產出 ≥1 條確定性
> claim（PASS/FAIL、程式重算）**。
- 既有 2 點已含 1 達 1 未達，故 H2 等價於：**第 3 次獨立 extract 呼叫產出 ≥1 條確定性 claim**。
- **否決條件**：第 3 次呼叫 0 條確定性（即 1/3 達）→ 單呼叫 H0 門為呼叫隨機、
  對「fire 時同題能否產出確定性重算」的保證力弱；修正方向（多呼叫共識門／
  交付物命名強化／解凍 extract.py＋checks.py）＝人類裁決，本系列不改凍結四檔。
- **成立（第 3 次 ≥1 條，即 2/3 達）**：單呼叫 H0 門可重現，G3.2 fire 失靈為
  孤立漂移；G 系列可續（下候選＝G3.4 多呼叫共識門，見 §5 任務單 2）。
- 口徑：UNKNOWN 非裁決非通過（I-4）；extract/parse 失敗＝空集合、不計確定性
  claim（同 H0 門口徑）；單 rep 方向性；不宣稱 superiority；不外推其他模型/題（H-12）。

## 2. 選題規則（防 cherry-pick）
- dab_725＝G3.2 H0 預跑 4 題中唯一 has_deterministic_claim=true 者
  （`ops/audits/g3_2_h0_prerun_report.json`：dab_725 2/7 確定性 R1,R6；dab_587/657/517 皆 0），
  且為唯一具「跨呼叫不穩定」證據之題（預跑 2 達 vs fire 0 未達）。
- 選題不讀 hidden/scorer、不靠隱藏分反推；`ops/audits/g3_3_precheck.py` 機械核此規則
  （report 中恰 1 題 n_deterministic_claims≥1 且該題＝dab_725）。

## 3. 範圍與成本
- 1 次 extract 呼叫（dab_725 單題）、0 answer 呼叫；參考 7313 tok（預跑 dab_725 實測）；
  成本從 raw usage 讀、缺值 UNKNOWN 不填 0。
- 不讀 hidden/scorer；不碰 G3.1/G3.2 既有產物；0 產品碼改動
  （凍結四檔 repair/extract/checks/run_eval 不動）。
- 日額度 ≤2,000,000 tok 撞額停不重試；glm CLI 唯一入口（--enabled-tools none、空暫存目錄）；
  無硬 token 上限能力、不得聲稱等 token。

## 4. 停止規則
- H2 否決 → G 系列停止、上報人類；不得加同題重試／靜態 prompt／錯誤字串 regex 工單。
- H2 成立 → 進 §5 任務單 2（仍需人類核准）。

## 5. 後續任務單（方向，各需獨立人類核准）
1. **G3.3**（本問）：H2 穩定性檢驗（1 呼叫，最便宜否決）——本檔即其預註冊。
2. 若 H2 成立 → **G3.4 候選**：3 呼叫共識 H0 門（≥2/3 達才發完整批）——
   機制層改動（g3.py 依核准工單可改），需凍結面重審＋新預註冊。
3. 若 H2 否決 → **人類裁決**：解凍 extract.py／checks.py（交付物命名強化／
   重算集擴充）或終止 G 系列。

## 6. 核准與凍結
- 核准文件：`/home/user1/dev/ops/approvals/g3_vq-1zf_fire_20261111.json`
  （approved=true、epic=vq-1zf、by=人類擁有者；2026-11-11 常設定案第 5 條）。
- 凍結（2026-11-12、票 P20261112_0119-1）：manifest＋tasks 副本＋precheck＋單測；
  發射＝核准後另一步，本票 0 model calls；approval gate fail-closed（無核准信號→RC 2）。
