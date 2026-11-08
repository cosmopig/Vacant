# STATE.md（r1227 起；r1128–r1226 見 archive/STATE_until_r1226.md.gz）

## r1227（2026-11-08 01:4x UTC）：argon ff 同步 fecd8657（純簿記審查）＋守護測試驗證（0 模型呼叫、0 成本）
- ① 審查 qwen27b 3 個新 commit（98ea2961..fecd8657）：僅 NOW.md＋STATE.md、產品代碼 diff＝0 行（git diff --stat；vacant_network/ops/tests diff 0 行）→核准（r1226 簿記＋redo）。
- ② DECISION：argon 98ea2961→fecd8657 merge --ff-only｜純祖先零衝突、純簿記、最保守可逆；auto/qwen27b＝auto/argon＝fecd8657（rev-parse 全同）→分支差距＝0（r1226 收在 98ea2961、qwen27b 已進 3 commit）。
- ③ argon worktree 驗證：守護 5 檔（指示3 點名）**109 passed（0.51s）**；checks.py blob qwen27b＝argon＝**f3525b01**（本輪 git hash-object 新鮮重算、兩 worktree 一致）；worker aca58a95 🟢 5034/0 在位。
- ④ 沒驗證：fecd8657 CI 燈（qwen27b＋argon 同 HEAD；ci/state.json idle@01:39、pass ~24 分間隔→下輪巡）；GitHub Actions（無 admin＝基建問題）；本輪未跑全量 pytest（vacant-ci 職掌）。
- 下一步：下輪巡 fecd8657 CI→應🟢（ci_status.py）；等審查派工（G3 須派工、不自發射大成本）；worker pearson2 未派工不自動做、不改 repair.py。
- ⑤ 審查 redo（本輪點名 3 檔原未開→現補開＋接地）：(a) `ops/audits/effects_20261105_summary.json` python json 加載：60,228 B、mtime 2026-11-05 11:25、git 乾淨、最後改動 26f23af5（argon、已核准）；schema vacant.audit/effects_20261105_summary/1、snapshot d38d2eb2、50 cells；policy30(30)：generic w2r **7**（still 3、preserved 5、365 calls／16,284,659 tok）／localized **6**（still 4、preserved 5、550／17,385,851）、rtw 0；once20(20)：generic **7**（still 3、preserved 0、165／6,210,682）／localized **4**（still 6、preserved 0、292／13,293,271）、rtw 0；**current_code_vs_independent_mismatches 兩相皆 []**（30/30、20/20）；local（d38d2eb2 舊 checker）vs independent 5 格分歧現碼全解（matches 45→50）；scope_note＝開發選樣單 rep、不宣稱任何一方優、無硬 token 上限。(b) `extract.py` 補開：**1217 行**、頭部＝G2.5 擷取驗證/組裝層（quote 非逐字→丟棄；verifier 不在 SUPPORTED_VERIFIERS 或參數不合→unverified＝UNKNOWN 不當通過；client 例外→空集 fail-closed；GlmClient subprocess 走 `glm` 指令＝唯一入口）、git 乾淨、最後改動 ebe4344c（已核准）。(c) `repair.py` 補開：**2795 行**、頭部＝G2 切片規則（保留原候選、重驗讀權威快照 source_tampered 退出碼 20、FAIL→UNKNOWN 不算修好、unresolved 列明）、git 乾淨、最後改動 399f68b6（已核准）。交叉核對：r1227 STATE/NOW/工單未引用該三檔任何數字（僅「不改 repair.py」邊界）→無矛盾、無需改數；邊界陳述現以本輪新鮮開啟接地。
- 工單 tickets/done/R20261108_0147-1；vq-el4.13 close。

## r1228（2026-11-08 01:5x UTC）：G2.5 新鮮複驗全三門＋審查指示#1「備案」落地（0 新模型呼叫、0 token）
- ① CI 巡：f6d29d1d（qwen27b）CI 執行中（01:49 起跑）；argon fecd8657 同；worker aca58a95 🟢 5034/0。f6d29d1d＝純簿記（NOW/STATE、產品 diff 0）→核准。
- ② 新鮮重跑 `run_eval.py --all`（全程離線、0 新呼叫：vibe_calls 末筆仍 11-07T18:35）：**exit 0**；G1 39/39（100%、0 冤枉）／REAL14 9/9（冤枉 0/5）／PHASE3 fixed7 unres2 rtw0 err0——與審查點名數字一致。
- ③ 備案（指示#1）：新增 `ops/audits/build_g25_all_gates_filing.py`（讀 out/all/phase{1,2,3}.json、fail-closed 斷言三門、附 raw sha256＋成本＋邊界）→ `g25_all_gates_filing.json`（schema vacant.filing/g25_all_gates/1、三門 PASS、git f6d29d1d、ticket vq-el4.14）。
- ④ fail-closed 驗證：篡改 raw（G1 FAIL／REAL14 冤枉 2／P3 err1）→**exit 2、不寫備案**；守護 test_reqloop_extract_run_eval＋test_repo_beads_shared_db **38 passed**。
- 沒驗證：f6d29d1d／fecd8657 CI 燈（下輪巡→應🟢）；GitHub Actions（無 admin＝基建）；未跑全量 pytest（vacant-ci 職掌）。
- 工單 vq-el4.14 close（vq-el4.15 重複、併入）；下一步＝巡 CI＋等 G3 派工（不自發射大成本）、不改 repair.py。
- ⑥ redo（審查點名 extract.py 原未開啟）：補開 `vacant_network/reqloop/extract.py`（1217 行、blob e757aec5）——核對 quote_is_verbatim:132（逐字、paraphrase 必 False→丟棄）、build_requirement_set:665（unverified→UNKNOWN 不當通過、client/解析例外→空集 fail-closed）、GlmClient:927（`glm` 唯一入口、rc≠0 不重試）、extract_requirements:1185；run_eval.py:40 自本檔匯入 build_requirement_set/extract_requirements/parse_model_output→G1/REAL14 門禁依賴它。**redo**：備案新增 `code` 段（extract.py sha256=51abfec3、checks.py=c7589c61[=blob f3525b01 與 r1227 一致]、run_eval.py=332cd324）＋boundaries 錄入驗證語義；fail-closed 重驗仍 exit 2 攔篡改；38 passed 不變。
