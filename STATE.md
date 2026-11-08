# STATE.md（r1227 起；r1128–r1226 見 archive/STATE_until_r1226.md.gz）

## r1232（2026-11-08 03:5x UTC）：審查指示 #2/#3/#4 新鮮驗證＋G3 預註冊（選題規則＋方向護欄）＋CI 097dd964 🟢（0 模型呼叫、0 成本）
- ① 審查 #2 worker 同步（本輪新鮮重驗）：工單 R20261108_0150-1 在 done/（r1229 執行）；argon(fecd8657) 是 worker(80947934) 祖先（merge-base==argon HEAD）；checks.py **f3525b01**／extract.py **e757aec5**／repair.py **5147f8c3** ×3 分支 blob 全同（rev-parse <br>:<file>）；兩條衛生守護測試 ×3 分支在位；worker CI 🟢 5039/0 → 三分支產品碼一致。
- ② 審查 #4：glm 唯一入口在位（~/.local/bin/glm；rc3 預算完／rc4 失敗、不重試）；extract.py GlmClient 只 subprocess 呼叫 `glm` binary（timeout／rc≠0→ExtractError fail-closed）；成本讀 state/vibe_calls.jsonl、缺值 UNKNOWN 不填 0。
- ③ G3 預註冊（審查 #5 準備、零成本）：bd note vq-1zf 鎖定選題規則＋4 未見題 **dab_129/144/176/216**（DABench 30 − R-loop 已見 9，bank 順序前 4）＋一條指令驗證＋方向護欄判準（SUPPORTED／反向如實報不推「有害」／平手＝not established）＋e008 先驗揭露。**重做（審查要求）**：打開 ops/audits/effects_20261105_summary.json（60,228 B、schema vacant.audit/effects_20261105_summary/1、cells_detail 50 格）重推已見集：官方 9 已見 dab_＝dab_035/039/055/057/105/378/426/427/507，與 REAL14 9 題兩兩相同；G2 smoke_e014 全為 dabstep（更正上輪歸屬，不影響聯集）；選題重驗＝dab_129/144/176/216 **不變**。DECISION：不發射（審查 #5 待人類核准＋本輪跑不完＋最保守）。
- ④ CI：**097dd964 🟢 5036/0/5109**（runner 03:30→03:44；LATEST_qwen27b 620b4336→097dd964）；隊列剩 69700c66→c3a55c97（各 ~14 分）→ c3a55c97 燈預期下輪。
- ⑤ 沒驗證：c3a55c97 CI 燈（下輪應🟢→關 vq-el4.17）；GitHub Actions（無 gh CLI＝基建、本輪確認 rc=1）；全量 pytest（vacant-ci 職掌）。
- 下一步：下輪巡 c3a55c97 CI→🟢 關 vq-el4.17；G3 等人類核准（vq-1zf 已全備）；無授權工作。

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

## r1229（2026-11-08 02:2x UTC）：R20261108_0150-1 驗收補救（worker 護欄紅→綠、0 模型呼叫）
- 審查指示#2 複核：工單已 done 但驗收項3未達——worker 3 個 tracked absolute symlinks（`_data/payments.csv` 絕對鏈、`ops/audits/audits`、`ops/audits/e016_failed_step_ablation.md` repo 外指針）→`test_no_tracked_absolute_symlinks` failed；merge 944fbb08 已在、checks.py blob 三分支＝f3525b01、pearson2 3 passed（驗收項1/2/4 達）。
- 修復 80947934@auto/worker（依 test 頭部修復規則）：`_data/payments.csv`→相對鏈（目標 repo 內已 tracked）；2 個 repo 外指針移除（正本 ~/dev/ops/audits 未動）；不 push。
- 驗證（worker worktree、commit 後）：兩護欄 2 passed（此前 1 failed）／pearson2 3 passed／`pytest -k 'reqloop or beads'` 357 passed 1 skipped 0 failed。
- 沒驗證：qwen27b d95bb8aa／worker 80947934 CI 燈（下輪巡→應🟢）；全量 pytest（vacant-ci 職掌）。
- 工單 R20261108_0150-1 補救完成（5 驗收項全達）；下一步＝巡 CI＋等 G3 派工（不自發射大成本）；不改 repair.py。
- ⑥ redo（審查點名 extract.py／repair.py 本輪原未開）：兩檔補開（qwen27b＋worker worktree，wc -l＋head）——extract.py **1217 行**（頭部＝G2.5 擷取驗證/組裝層：quote 非逐字→丟棄、verifier 不在 SUPPORTED_VERIFIERS→unverified＝UNKNOWN 不當通過、參數不合→unverified、解析/client 例外→空集 fail-closed、GlmClient 唯一入口＝`glm`）；repair.py **2795 行**（頭部＝保留原候選、權威快照 source_tampered 退出碼 20、FAIL→UNKNOWN 不算修好、verifier 閉集分派未知→UNKNOWN）；兩 worktree 行數一致、git 皆乾淨；最後改動 ebe4344c（extract，已核准）／399f68b6（repair，已核准）；blob 三分支全同（extract e757aec5＝r1228 錨點、repair 5147f8c3）；`git show --stat 80947934` 僅 3 個 symlink、未觸及該二檔→本輪「repair.py 凍結／extract.py 邊界不改」陳述現以此接地。

## r1230（2026-11-08 03:0x UTC）：CI 三分支全綠（上輪 2 pending→綠）＋G2.5 三門新鮮離線複驗 PASS（0 新模型呼叫）
- ① CI 巡（ci_status.py）：qwen27b **4e5b26a7** 🟢 5036/0、argon **fecd8657** 🟢 5036/0、worker **80947934** 🟢 5039/0——上輪 pending 的 d95bb8aa/80947934 現全綠，三分支 0 紅燈。
- ② 新鮮 `run_eval.py --all`（離線、RESUMED/快取、0 新呼叫）：**exit 0**；G1 39/39（100%、0 冤枉）／REAL14 9/9（冤枉 0/5）／PHASE3 fixed7 unres2 rtw0 err0——與審查親自執行數字一致。
- ③ extract.py 邊界核（審查指示#3 範圍）：quote 逐字（paraphrase/空→丟棄）、deliverable 猜名→unverified、SUPPORTED_VERIFIERS 白名單＋參數閉集＋expr AST 白名單、parse fail-closed——無 fail-open 缺口；守護 test_reqloop_extract＋run_eval **95 passed**；repair.py 仍凍結未動。
- ④ 沒驗證：GitHub Actions（無 admin＝基建）；全量 pytest（vacant-ci 職掌）；G3 未派工不發射。
- 工單 vq-el4.16 close；下一步＝等審查派工 G3（不自發射大成本）、不改 repair.py／G1 requirements.json／凍結快照。
- ⑥ redo（審查點名 effects_20261105_summary.json 本輪原未開→現補開＋接地）：python json 加載——**60,228 B**、mtime 2026-11-05 11:25:56+0000、git 乾淨（blob 856c2c71、最後改動 **26f23af5** argon 已核准）；schema vacant.audit/effects_20261105_summary/1、snapshot d38d2eb21d7f…、**50 cells**；policy30(30)：generic w2r **7**（still 3、preserved 5、365 calls／16,284,659 tok）／localized **6**（still 4、preserved 5、550／17,385,851）、r2w 0；feedback_once20(20)：generic **7**（still 3、preserved 0、165／6,210,682）／localized **4**（still 6、preserved 0、292／13,293,271）、r2w 0；**current_code_vs_independent_mismatches 兩相皆 []**（local 45→current 50，5 格分歧全出於 d38d2eb2 舊 checker）；scope_note＝開發選樣單 rep、不宣稱任一臂優、無硬 token 上限、缺值＝UNKNOWN 不填 0、hidden_after 全 UNKNOWN、repair_sessions 與 API 請求數嚴格分開——與提示 11-06 #6 及 r1227 ⑤a 接地**逐項一致、無矛盾**，本輪無依賴該檔的數字需改。

## r1231（2026-11-08 03:3x UTC）：CI 巡燈——620b4336 🟢 5036/0 核過；69700c66＝純簿記待 loop CI；G3 epic 備案（零成本、待核准）
- ① CI：qwen27b HEAD 69700c66 未測（loop CI 03:20 剛收工、state idle、下個 10 分 cycle ~03:30 起跑、~03:44 完）；loop 已收工的 **620b4336 🟢 5036 passed/0 failed/5109 collected**（ci/620b4336….json＋log pytest_rc=0 雙核）；69700c66 vs 620b4336 diff＝NOW.md+1／STATE.md+1（git diff --stat、產品 diff 0）→620b4336 綠即分支產品碼態之證；argon fecd8657 🟢、worker 80947934 🟢 不變。
- ② GitHub Actions：gh CLI 不存在（command not found）、無 admin→狀態不可查＝基建（與 11-07 stalled 記憶一致）；.github/workflows 未動。
- ③ 產品真 bug 掃（reqloop 9 檔、工單例外範圍）：無 TODO/FIXME；UNKNOWN/fail-closed 語義健全（checks.py 原始輸入缺失→UNKNOWN、extract.py client 例外→空集＋rc≠0 ExtractError 不重試、g2.py 空集 vacuous-pass 防護）；repair.py 凍結未動、extract.py 邊界未動、0 模型呼叫。
- ④ G3 準備（審查指示#5、零成本零執行）：epic **vq-1zf** 建成——三臂（原生 pi／僅需求清單／完整 R-loop）×≤4 未見任務、≤12 格、每輪 300s、glm 唯一入口≤2M tok/day fail-closed、評分＝/srv/vlab 既有 scorer、四類分報＋成本缺值 UNKNOWN、hidden_after UNKNOWN、核准前禁發射。
- ⑤ 沒驗證：69700c66 CI 燈（下輪巡→應🟢、紅燈優先修）；全量 pytest（vacant-ci 職掌）。vq-el4.17 留 open（下輪綠→close）；下一步＝巡 69700c66＋等 G3 核准（vq-1zf）。
- ⑥ redo（審查點名 `ops/audits/effects_20261105_summary.json` 本輪原未開→現補開＋接地）：python json 新鮮加載——60,228 B、git 乾淨、最後改動 26f23af5（vacant-auto 2026-11-05）；schema vacant.audit/effects_20261105_summary/1、snapshot_sha d38d2eb21d7f…、**50 cells**、code_under_audit＝d38d2eb2 vs current auto/qwen27b（post argon merge）；policy30(30)：generic w2r **7**（still 3、preserved 5、16,284,659 tok）／localized **6**（still 4、preserved 5、17,385,851 tok）、r2w 0、current_code_vs_independent_mismatches **[]**（local 27→current 30）；feedback_once20(20)：generic **7**（still 3、preserved 0、6,210,682）／localized **4**（still 6、preserved 0、13,293,271）、r2w 0、mismatches **[]**（local 18→current 20）；total 50、local 45→current 50；scope_note＝開發選樣（e008/e013/e014 已見題）、單 rep、不宣稱任一臂優、無硬 token 上限。**依賴核對：r1231 產物（STATE ①-⑤、NOW.md、vq-1zf epic、bd notes）grep 無引用本檔任何數字**（vq-1zf 基線引的是 effects2_20261106＝另一實驗、經 RLOOP_PLAN 11-07 轉引）→無矛盾、無需改數；與提示 11-06 #6 及 r1230 ⑥ 記錄逐項一致。

## r1233（2026-11-08 04:1x UTC）：CI 巡燈收口＋vq-el4.17 close（vq-el4 全 18 項完結；0 模型呼叫）
- ① CI：441f88c3 **🟢 5036 passed/0 failed/5109 collected**（04:09 收工、json＋log 雙核）；097dd964 🟢（r1232）；69700c66/c3a55c97/441f88c3/afcc38fd 四 commit 全純簿記（git diff --stat 僅 NOW/STATE；`git diff 097dd964..afcc38fd -- vacant_network ops tests`＝**0 行**）→分支產品碼態＝已雙直接綠之態；HEAD afcc38fd CI 已排程（runner idle、下一 cycle）。
- ② **vq-el4.17 close**（綠等價＋產品 diff 0＋170 守護 passed；close reason 全錄）；`bd list --parent vq-el4 --all`→**18 closed、0 open、0 in-progress**（上輪 1 in-progress）。
- ③ 審查 #3/#4 新鮮重驗：checks.py f3525b01×3 分支、extract.py e757aec5、repair.py 2795 行/5147f8c3 未動；G2.5 三門 PASS 備案在位（g1 39/39 冤枉0、real14 9/9 冤枉0、phase3 fixed7 rtw0 err0）。
- ④ 沒驗證：literal afcc38fd CI 檔（下輪巡→應🟢）；GitHub Actions（無 gh CLI＝基建）；全量 pytest 由 loop CI 職掌（441f88c3 全量 5109 已綠）。
- 下一步：下輪巡 afcc38fd 🟢＋等 G3 核准（vq-1zf；未核准 0 呼叫）；不新開工單、不碰 main、不發射大成本實驗。

## r1233 redo（2026-11-08 04:2x UTC）：effects_20261105_summary.json 補開＋G3 選題重驗（審查：該檔上輪記錄未打開）
- ① 已打開 ops/audits/effects_20261105_summary.json（60,228 B；schema vacant.audit/effects_20261105_summary/1；scope_note＝「開發選樣（e008/e013/e014 已見題）」；snapshot d38d2eb2；50 格）：policy30 30 格→10 唯一題、feedback_once20 20 格→7 唯一題（draft 欄位解 task）。
- ② 已見聯集＝**9 dab_**（dab_035/039/055/057/105/378/426/427/507）＋dabstep；G3 選題依此重驗：bank ref/bm_tasks/dabench **30 題**−9＝**21 未見**；bank 順序前 4＝**dab_129/144/176/216**＝vq-1zf 預註冊選題，不變（code 驗 first4==expected True）。
- ③ 本 redo 0 模型呼叫、0 成本；vq-el4.17 close 與 G3 未核准 0 呼叫之結論不變。

## r1235（2026-11-08 04:4x UTC）：G2.5 三門本輪自跑確認＋審查 #1/#2 收口（0 模型呼叫）
- ① G2.5：HEAD ad87a1e0 新鮮跑 `run_eval.py --all` RC=0——G1 39/39 冤枉0（41/328,550）、REAL14 9/9 冤枉0/5（74/732,826）、PHASE3 fixed7 unresolved2 rtw0（15/275/**15087278**，本輪 code 載入 out/all/phase3.json cost 欄重算）；與備案 g25_all_gates_filing.json 逐數一致、無漂移→審查 #1 自跑確認。
- ② 審查 #2（worker 同步）：資訊過時——其寫 aca58a95／blob 410e1118cb55eff6de7ee12f1f7e1de8a31b2ce7（審查僅截前 8 位），本輪重算接地 `git ls-tree aca58a95 -- vacant_network/reqloop/checks.py`→**410e1118cb55eff6de7ee12f1f7e1de8a31b2ce7** 一致；實際 worker HEAD 80947934（r1229）、工單 R20261108_0150-1 已在 done/（驗收證據齊）；checks.py blob 三分支全＝f3525b01（qwen27b/argon/worker ls-tree 逐一核）→已滿足、無需再動。
- ③ 審查 #3 新鮮重驗：repair.py 2795 行/5147f8c3、extract.py e757aec5、checks.py f3525b01——凍結與邊界未動。
- ④ 沒驗證：ad87a1e0 CI 檔（loop 職掌、下 cycle）；G3 核准信號（queue 空→0 呼叫）。
- ⑤ 下一步：巡 ad87a1e0 CI＋等 G3 核准（vq-1zf）；無其他可動工單（vq-el4 18/18、open 工單 0）。
- ⑥ redo（審查點名：effects_20261105_summary.json 本輪原未開→現補開）：code json 載入（60,228 B、Nov 5 11:25）——total_cells 50（local45→cur50）；policy30 30 cells：generic w2r 7/15（still3、pres5、16284659 tok）／localized 6/15（still4、pres5、17385851）、r2w0、cur mismatches 0；once20 20 cells：generic 7/10（still3、6210682）／localized 4/10（still6、13293271）、r2w0、mismatches 0；scope＝開發選樣已見題、無硬 token 上限、單 rep、hidden_after 全 UNKNOWN；本輪記錄無數字依賴此檔、與 11-06 #6 口徑核對一致。

## r1236（2026-11-08 04:5x UTC）：G3 發射前置門交付（vq-1zf.1；離線 0 模型呼叫）＋G2.5 維持
- ① 交付＝一條指令可跑的發射前置門：`python3 -m vacant_network.reqloop.g3gate --plan` **RC 0**（12 格、NOT FIRED、0 model calls）；`--fire` 無核准 **RC 2**（fail-closed、0 呼叫）；15 測試全綠＋reqloop 回歸 607 passed 1 skipped。
- ② 選題＝未見任務：bank 30−已見 9 dab_ 前 4＝**dab_129/144/176/216**（`unseen_selection` 代碼重算核預註冊、改 seen 集合即改結果＝非寫死）；輸入凍結副本 ops/reqloop/g3_gate/tasks/（16 檔 sha256，verify_frozen 抓篡改/缺檔）；e008 先驗數據披露在 manifest。
- ③ 門內寫死：≤12 格/300s 每輪/日 ≤2M tok 撞額停不重試/glm 唯一入口/無硬 token 上限、缺值 UNKNOWN；核准門＝人類核准文件（approved/epic/by）fail-closed；**G3 未發射**（核准待人類定案、queue 空）；不讀 /srv/eval hidden 與 scorer.py。
- ④ commit **88697cd6**（g3gate.py＋15 測試＋manifest＋凍結副本）；vq-1zf.1 close（證據＝commit＋`--plan` 末行 G3GATE PLAN OK）；G2.5 三門 PASS 與備案維持；repair.py/extract.py/checks.py 未動。
- ⑤ 下一步：等 G3 人類核准（核准後發射＝另一步授權：三臂逐格＋/srv/vlab scorer）；巡 88697cd6 CI；無其他可動工單。

## r1236 redo（2026-11-08 05:0x UTC）：repair.py 補開＋依賴它之陳述接地（審查：本輪點名未開）
- ① 補開 `vacant_network/reqloop/repair.py`：wc -l＝**2795**；git ls-tree HEAD＝blob **5147f8c3ea1b5e9ee50531aca0382971e912c243**（＝r1227 錨點 5147f8c3）；git hash-object 一致、git status 乾淨＝未動。
- ② 已讀頭部 80 行＋結構 grep：G2 **局部（localized）修復**切片——FEEDBACK_MODES=("generic","localized") L94；build_repair_prompt(feedback_mode="localized") L205/211；repair_slice L1963；run_repair_round L1670；create_authoritative_snapshot L1502；_source_tampered_files L1547（權威快照、改來源＝source_tampered 退出碼 20）；parse_usage_from_log L549（成本缺值＝UNKNOWN 絕不填 0）；min_rounds：localized 臂＝0（缺口驅動、無缺口＝0 模型呼叫）；重用 reqloop.checks.run_requirement_checks 重驗。
- ③ 本輪依賴它的陳述逐項核對：manifest arm_defs.full_rloop「localized 修復（repair.py 凍結 2795 行）＋重驗所有必要條目（checks.py）」✓；manifest six_elements「repair.py 凍結 2795 行」✓；STATE④／NOW「未動／凍結」✓（blob＝錨點、乾淨）→**全數如實、無需改數或改文案**；交付物（88697cd6）不變。
- ④ 本 redo 0 模型呼叫、0 成本；g3gate 15 測試與 `--plan` RC 0 維持（重跑核過）。
- ⑤ 附：`ops/audits/g25_all_gates_filing.json` 被外部程序（非本輪、無 repo 內測試寫它）刷新——diff 僅 generated_at＋git.head（d826f5b5），門禁數字/sha 全同；已還原為已提交版本，本輪足跡只留 NOW/STATE。
