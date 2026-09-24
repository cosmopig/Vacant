# Vacant repo — 工作約束（2026-07-04 起；交付定位 2026-08-06 更正）

## 現在是什麼

本 repo 是 Vacant 的**程式碼本體**：可究責層（Phase-1）＋ credit-memory 改動1/3 ＋
實驗基建。規劃與理論的正典在
`~/Library/Mobile Documents/com~apple~CloudDocs/專題/`（尤其
`Vacant_最新成果彙整_2026-07-03/` 與 `Vacant_展望_2026-08-06/`）；
**與規劃衝突時以 15 號判決文為準**（其裁決凌駕 09–14），
**唯獨交付定位以下面這一節為準**。

## 唯一交付物：畢業專題 ＝ 實體場地展覽

**不產出畢業論文，也不投稿。**（2026-08-06 人類明確更正）

舊版這裡寫的是「雙軌交付：畢業軌／投稿軌（MPS、AAMAS、X2–X5 主跑）」。那個描述
已經不成立，而且它會主動製造發散——照著它規劃，工作會一路長向「論文貢獻」
「有沒有被先行研究搶先」「統計顯著性」。2026-08-06 就這樣把工作誤拆成畢業／投稿／
展覽三個身分，被當場糾正。**判斷任何工作要不要做，問的是「觀眾走到展場前面時，
這件事有沒有差別」，不是「審稿人會不會問」。**

具體後果，每一條都會改變技術決策：

1. **實體場地 ⇒ 秒級互動是硬需求。** 真模型每題實測約 114 秒（E10），現場不可能等。
   展件跑機制模擬（`entrycost`）或預跑重放，**畫面上必須明講「這是機制模擬」**——
   把模擬講成證明是鐵律 5 的展場版本。
2. **實體場地 ⇒ 離線可跑、可無人值守循環。** 不能假設網路、不能假設有解說員。
   任何依賴外部端點的東西都要有 fallback。
3. **先行研究仍然重要，但理由變了。** 不是新穎性，是**不能對觀眾說錯話**。
   展場說「我們發現脈衝攻擊」而它 2005 年就有名字（Srivatsa），那是騙不懂的人。
4. **統計檢定力不必到發表標準。** E10 的 p=0.332 對展覽不是問題；能讓外行一眼看懂
   的反事實對照比 p 值重要。
5. **口徑用「可究責性 / 讓依賴有根據」，不要用「信任」。** 經典定義（Gambetta 1988、
   Mayer 1995）把「不依賴監督」寫進信任的必要條件，而監督正是本系統的全部。
   觀眾比口委更容易被誤導，所以展場的措辭要求**更嚴格**不是更寬鬆。
6. **倫理是第一線需求不是附錄。** 展覽用真人資料生成分身。Hollanek 2024：
   **捐贈者同意不夠，互動者也必須能同意**——動物園的性質就是有人在旁邊看。
   詳見 `專題/Vacant_展望_2026-08-06/03_人類動物園_展覽設計.md` 第五節。

展件施工順序與凍結清單見 `專題/Vacant_展望_2026-08-06/04_接下來的步驟.md`。
**凍結不等於刪掉**：通道分離那六個改動、X-cap／X-check 等證據都很強，但它們不影響
展場，排在展件可運作之後。

## 程式碼地圖（實驗承重件）

- `vacant_network/logbook.py` — 簽章 hash-chain；stream_id＝創世 hash、真 head()（改動1）
- `vacant_network/envelope.py` — Envelope＋**ReviewEnvelope**（改動3 的簽章 review）
- `vacant_network/registry.py` — record_review 只收驗簽＋head 新鮮＋去重；weight 內生；
  同源非線性降權 floor/k＋**行為推斷同源降權**（鑑別題一致率，零 controller_id）
- `vacant_network/reputation.py` — 五維 Beta；**改動2 三元組 key**(stream,branch,substrate)＋
  牙齒（decay 半衰期 200 事件向先驗回歸、slash 乘法扣減）
- `vacant_network/memory.py` — MemoryStream（episode 上鏈）＋MemoryManager M0/M1/M2
  （X1 的實驗處理本身）＋KS-1／A4 可執行防呆
- `vacant_network/auditor.py` — 確定性稽核（sha256 抽樣、checks.py 沙箱、provable-fault）
- `vacant_network/router.py` — trust on/off 單開關（on＝UCB、off＝確定性隨機）；
  probation 路由端牙齒（蓋 0.55＋每 10 筆見習配額）
- `vacant_network/batch.py` — RunLedger 斷點續跑＋Watchdog（裁決 B4）
- `vacant_network/x1.py` — X1 任務族＋run_x1 三臂迴圈＋transfer_curve＋pilot_report
  （一票否決）＋finalize_run_package（RECORD_SPEC 合格包）＋require_usage 成本紀律
- `vacant_network/codebench.py` — 六坑型族程序生成＋**EvalPlusMBPPLoader**（378 題
  sha256 釘死、V/GT 分離、fail-closed）
- `vacant_network/research.py` — M1–M6＋McNemar＋bootstrap＋**預註冊四函式**
  （holm_bonferroni／tost_equiv_boot／wilcoxon_signed_rank_exact／mcnemar_power）
- `vacant_network/record.py` — RECORD_SPEC pack/check（紀錄紅線：不 pack＝沒跑過；
  私鑰 identity.key 排除，SPEC §7）
- `vacant_network/suitegauge.py` — 驗收套件的量具（參考解要過、每個已知壞樁都要被擋）；
  `gain_run.probe_instrument` 與 `peerexec.commit_suite` 共用這一份判準，**單邊保證**
  （擋得住已知壞解 ≠ 涵蓋真需求）寫在 docstring，不准讀成「套件固定點已解」
- `vacant_network/suitemutate.py` — 純 AST 變異器（零新依賴），把 suitegauge 的刻度從
  「擋得住 1 個壞樁」細到「擋得住 N 種我們造得出來的錯」。致死率**另外算、
  不綁 `GaugeOutcome.ok`**（綁了＝改掉閘門語意，r452c 那批歸檔資料會失去可比性）；
  且**永遠是下界**（運算子表有限＋等價變異體不可判定）。實跑：
  `ops/gain/mutation_score_banks.py` ＋ `ops/gain/data/suite_mutation_*.json`
  ——LCB v2 有參考解的 12 題中位數 0.784／最低 0.600（12 題裡 11 題不滿分）；
  MBPP+ 抽樣 10 題中位數 1.000／最低 0.611、HumanEval+ 抽樣 10 題中位數 0.967／最低 0.688。
  ⚠ **MBPP+ 的 1.000 不是強度證據**：那 10 題裡有 6 題的變異體只有 ≤2 個
  （變異體數 1,1,1,2,2,2,8,17,17,18），分母小到量表沒有解析度；HumanEval+ 最低也有 4 個。
  **有解析度的是 LCB**（每題 9–20 個）。兩個題庫的數字不可混講成一個。
  ⚠ **`return None`（量具自己用的那個退化樁）在某些分支上活著**：
  `mbppplus_Mbpp/260` L3、`humanevalplus_HumanEval/154` L12/L14、`/106` L11/L15
  ——整支函式回 None 會被擋，**某一條分支回 None 擋不住**，代表可見測資沒走到那條路徑
- `vacant_network/suitespec.py` — **驗收套件是資料不是程式**（R452）：SuiteSpec（entry_point＋
  字面值 (args, expected)＋比對設定）＋確定性渲染器；執行器只跑自己渲染的碼，
  有狀態／雜湊黑名單／擬態三種攻擊**不可表達**，殘餘＝覆蓋不足＋比對旗標
- `vacant_network/blayer.py` — B 層機制驗收六情境（0→70% 步進 × on/off 雙組，判準寫死）
- `vacant_network/checkpoint.py` — V1 存檔點認證＋回溯稽核（18 §2；存檔點自身成鏈）
- `vacant_network/dashboard.py` — 觀測台＋/api/roster/scoreboard/**snapshot**（面板非信任來源）

### `vacant_network/intake/` ＋ `adapters/` — **通用收件口與四個 agent 的接法**（2026-09-24）

裁決：`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md`（**部分取代** COMPLETE_MEDIATION：
新產品路徑裡模型中介不再是收件的前提）。證據：`ops/intake/evidence_20260924/`（L-fake，四個真 agent）。

- `intake/contract.py` — 任務契約（未知欄位一律拒絕；`inputs` 以 sha256 釘住；`authority` 四種）
- `intake/artifact.py` — 內容定址隔離區（竄改可偵測，不是不可能）
- `intake/verifiers.py` — 驗證原語，結果只有 PASS／FAIL／UNKNOWN／CONFLICT；**驗證器壞掉＝UNKNOWN**
- `intake/policy.py` — 裁決規則寫死；事實主張只收獨立證據；分母是契約
- `intake/keys.py`／`approval.py` — 長期金鑰（verifier／approver／reviewer／**owner**）＋**收件端自己的**
  簽章者清單；綁定內容、一次性的批准；**契約鎖**（`vacant contract lock`＝owner 簽「這個任務＝這個契約
  雜湊＋放行政策」，收件端只依被鎖過的契約放行）。清單裡已有別人的 owner／approver／reviewer 時本機金鑰不自動加入
- `intake/recipients.py` — `vacant release` 的接受點：自己重驗一切（契約鎖、裁決、隔離區、綁**解析後**
  目的端的批准、帳本沒被截短）、發布、讀回（`dir:`／`git:`）。⚠ 只管它自己寫的那個目的端
- `intake/ledger.py` — 每個任務的終態（含 `infra_void`），分母＝開過的任務
- `intake/server.py` — HTTP 收件口（提交者給不了裁決；沒 token 不啟動）
- `adapters/agents.py` — pi／Claude Code／OpenCode／Codex 的翻譯表（headless、加法式掛鉤、常駐安裝、技能）
- `adapters/hook.py`＋`hookpolicy.py` — `vacant hook`：四種原生格式 → 一份政策
- `adapters/install.py` — 鍵層級可逆安裝（使用者沒改過就逐位元還原）
- `adapters/run.py` — `vacant do`：隔離工作區（`~/.vacant-work`，**不可在 `$VACANT_HOME` 底下**）＋headless＋交件；
  中斷殺行程群組並記 `infra_void`；只在有必要主張 FAIL 時重試
- 收件口的驗證沙箱一律 **hermetic**（`vrun/sandbox.py` 的 `hermetic=True`：不讀成果裡的 shell 啟動檔、
  不載 python user site、HOME 不在成果裡）；**vrun 的 `bash -lc` 舊行為不動**（歸檔 run 可比）
- 對抗審查（裁決 §十一，60 條逐條重現）的回歸：`tests/test_{intake_gate,intake_verifier,adapters}_hardening.py`

🔴 口徑：✅「不合格的版本沒有出現在收件端的目的地」（只對經過 `vacant release` 的那個目的端）；
❌「agent 不會繞過」「Vacant 讓 agent 做得更好」（回饋後改對是劇本）；❌「OpenCode 有交件前回饋」
（`opencode run` 在第一個 idle 就結束）。⚠ `vacant install` 現在是通用安裝器，舊的模型通道常駐安裝是
`vacant possess install`；`vacant uninstall`（不帶 `--agents`）會一起拆掉它。

### `vacant_network/vrun/` — 產品本體（`vacant run` / `vacant install` 那一層）

⚠ **這 15 支在 2026-09-20 之前完全沒有出現在這張地圖上**，而它現在是「**Vacant 附身在
任何 agent 上**」的全部實作。裁決在 `decisions/DECISION_20260920_*.md` 五份。

- `possess.py` — **`vacant possess install`**（0.8.0 時叫 `vacant install`）：把 proxy 端點寫進五個 agent **自己的常駐設定檔**
  ⇒ 通道層做得到**真正的預設**（關掉終端機、重開機、打完整路徑都還在）。
  `NEVER_TOUCH` 守住所有 `auth.json`。也釘 Codex 的 `sandbox_mode` 並把
  `agent_posture{sandbox_mode, approval_policy, flags[]}` 寫進收據
  （讀不出來寫 `null` **不寫空字串**）。
- `gateshim.py` — 閘門那一側（PATH shim）。退出碼 `0`／`20` 拒交／**`21` 沒有驗收可跑**
  （`accepted=null`）／`22` infra_void／**`23` `requests_seen==0` 裁決不可歸因**
  ／**`24` B 級**／**`25` B′ 級**／**`26` C 級拒發收據**。
  ⚠ **`21`／`23` 的既有語意不可以動**；級別**不准蓋 `22`**。
  ⚠ PATH shim **打完整路徑就繞過**，而且對 `bash -c`（腳本／cron／`ExecStart=`）**收不到**
  ——那條**修不掉、只能明講**。**它不承重**，承重的是下面那兩層。
- `wireproxy.py` ＋ `proxyd.py` — 中介與常駐反向代理。**`sentinel=""`：Authorization 原樣穿透，
  proxyd 永不持有金鑰**（改碼要保住，有兩面測試＋正控制）。
  `proxyd` 有 **AF_UNIX listener**（`--port` 與 `--unix` 是 xor）＝ enclosure 那扇門；
  `path_policy` 跟著聽法走（`--unix` ⇒ `model` fail-closed、`--port` ⇒ `any` ＝舊行為），
  非模型 path **在開任何連線之前**回 403、另計 `refused_path`（**刻意不併進 `blocked`**）。
  ⚠ **政策在 path 層不在內容層**：擋得住 `/admin` ≠ 擋得住
  「把資料裝進一個合法的模型請求帶出去」。
- `sandbox.py` — `BwrapSandbox`。⚠ **這支的招式是整個方案的關鍵**：最小 rootfs 之下
  那條通道**不可表達**，而不是「存在但我們不准」。**同一招用在網路上就是 enclosure**
  （netns ＋ mount ns）。⚠ **`unshare -n` 單獨不夠**——只殺抽象 socket，
  **路徑型 socket 要 mount ns**。分辨錯整個結論就垮。
- `attest.py` ＋ `hookcli.py` — 收據認證。四個欄位
  `enclosure{ns_id,policy_sha256,applied}`／`framework_hook{canary_fired}`／
  `reconciled{unexplained}`／`tier`，簽進 `ws_verdict`。
  **級別由探針決定，不准用「我們裝過了」推論「它在」**（`canary_fired=null` ＝沒裝過、
  `=false` ＝裝了沒燒）。三態防呆可執行：**`0` 混進布林欄位會炸**、
  數字欄位**先把 `bool` 踢掉**（`isinstance(True,int)` 為真）。
  ⚠ `VACANT_ATTEST` **預設 `warn` 不是 `fail`**（macOS 沒 bwrap ⇒ 預設 fail 等於
  Mac 上每跑都拒發收據）。**展場那條線必須 `VACANT_ATTEST=fail`。**
- `verify_receipts.py` — `mediation_of()`／`attestation_of()`／`--require-tier`（**預設關**）。
  四值裁決 OK→0、VOID→3、BROKEN→1、UNVERIFIABLE→1。
- `envmap.py` — `SINK_UPSTREAM`／`is_sink`：**未指定 upstream 要 fail-closed**，
  不可以安靜地去打公開 API（`envmap` 誠實邊界 2 有活體標本）。

**證據落盤**：`ops/vacantrun/enclosure_20260920/`（圍牆＋門，兩支一鍵重跑，
`run_probes.sh` **一定先跑負控制**）、`ops/vacantrun/codex_managed_20260920/`
（Codex managed requirements，26 個 probe 檔）、`ops/vacantrun/possess_linux_20260920/`。

🔴 **口徑（不准漂）**：
- ❌ 「不會被繞過」——圍牆**外面**什麼都連得到。
- ❌ 「**這個 agent** 是 A 級」——級別是**這一跑**的屬性。
- ❌ 「閘門擋下 X 格」——那個數字**綁在那一個框架＋那一個後端上**
  （三家判決方向一致只有 4/10 題）。
- ✅ 「**A 級的那一跑**，每一通模型呼叫都經過 Vacant，且都對得上一個工具事件。」
- ✅ 跨框架成立的那句：「**agent 自己宣告完成、退出碼 0 走人，閘門仍在行程結束那一刻擋下來**」
  （11 個拒交格裡 9 格如此，三個框架都出現）。

- `examples/x1_pilot.py` — 遷移 pilot 進入點（--loader x1|builtin|evalplus、--stub 閘門）
- `examples/b_layer.py` — B 層六情境掃描 runner（預設每格 1000 seeds）
- `docs/PREREG_V2.md` — 預註冊凍結總表（草稿待人類簽字＋ledger 簽入）
- `ops/gain/gain_run.py`＋`ops/gain/brain_cline.py` — G 實驗（SPEC_GAIN.md，
  2026-08-17 定調為主張本身）三臂等預算 runner 與 Cline 後端；
  OFF5 多數決走與 ON 相同的受限 worker（2026-08-20 修正）。
  `ops/gain/VERIFICATION_2026-08-20.md`＝外部交付包 22db0d7 的獨立驗證紀錄，
  含「敘述超出實際交付」清單（deadline quorum、五呼叫重配、corpus 13/4/9
  都不在交付物內，引用時不可當成已存在）
- `runs/INDEX.md`（人讀）＋`runs/INDEX.json`（機器讀）— **要引用任何 run／題庫／log
  之前先讀這一份**：598 個項目哪些是證據（98 個 real_run）、哪些是冒煙／中止、
  哪 136 個 `_analysis_*` 是衍生物不可當原始資料，LCB v1/v2/v3＋MBPP+＋HumanEval+
  的 sha256／日期窗／已知壞題（**HumanEval+ 的分母是 156 不是 164**），
  以及哪些 log 只活在 vacant-dev 沒有備份。成組收官的兩批各有一節：
  §二 R529 跨題庫 37 塊、§三 R460R 三次同題複製 18 塊——它們的 `headline` 是 `—`
  但**不代表沒被稽核**（裁決檔用 glob 點名整批）。產生器
  `ops/gain/build_runs_index.py`（`--check` 可驗索引沒漂）。
- `decisions/` — **實驗紀錄的家**（2026-09-18 從 repo 根搬進來，227 份，純 `git mv`、
  內容一個 byte 沒動）。根目錄留給「這個專案是什麼」，外人打開 repo 第一眼要看得到
  `vacant_network/`。配置：`decisions/`＝`DECISION_*.md`（205）、`decisions/criteria/`＝
  `CRITERION_*.md`（14）、`decisions/conclusions/`＝`CONCLUSION_*.md`＋`FINDINGS_*.md`（4）、
  `decisions/prereg/`＝`PREREG_*.md`（2）、`decisions/notes/`＝日期型一次性筆記（2）。
  **新的裁決／預註冊一律寫進 `decisions/`，不要再寫回根目錄。**
- **發射指令的路徑**：R440G 閘門（`gain_run.py`，凍結碼）只認 `--decision <路徑>` 能不能
  開啟，所以現在要寫 `--decision decisions/DECISION_xxx.md`。
  ⚠ **各份預註冊檔內文裡的逐塊指令仍寫著舊的根目錄路徑，那是刻意不改的**——
  預註冊的重點是發射前凍結，事後改寫它記載的指令等於讓紀錄描述一個沒下過的指令；
  而且 `docs/paper_2026-09-14/source_manifest.json` 對其中 13 份釘了 sha256。
  照抄會被閘門擋下（`拒絕啟動：DECISION 檔不存在`，fail-closed 不是安靜跑錯），
  自己補 `decisions/` 前綴即可。實際在跑的 `ops/gain/r5xx/*_queue.sh` 已經是新路徑。
- `ops/check_repo_links.py` — 死連結／死路徑擋門（markdown 連結、`ROOT / "..."` 字面值、
  `--decision` 參數、GitHub 絕對網址四類）。上面那兩類「刻意不改」的東西是**具名排除**、
  `--verbose` 數得出來，不是安靜跳過。它同時擋「根目錄有落單的紀錄檔」：
  **住哪裡由檔名前綴決定**（`_RECORD_HOME`，單一真相來源），不是一次性的搬家清單。
  在搬家之前開的分支合併進來時，那份新裁決會以根目錄路徑落單——
  `python3 ops/check_repo_links.py --relocate` 一行歸位（glob 掃當下的樹＋`git mv`，
  不吃寫死的檔名），CI 也會在落單時就紅。

### 展件可直接複用的（實體場地，秒級互動）

- `vacant_network/entrycost.py` — 機制模擬。**現場的雙世界對照跑這個**，不跑真模型
  （真模型每題約 114 秒，展場等不起）。畫面上必須標明是機制模擬。
- `vacant_network/logbook.py` ＋ `vacant_network/checkpoint.py` — 出口那張「可驗證收據」的機制；
  同一套也用來做展覽自己的同意／刪除證明（用自己展示的機制證明自己守約）。
- `真模型_2026-07-26/E10/{on,off}/rows.jsonl` — 主視覺的資料來源。兩行路由序列
  （`X`＝工作被交給破壞者）是手上最容易被外行看懂的東西，且是真模型真資料：
  ```
  關  ......X.....X.XXX.X.X..X....X.X.X.X..XXX..X....XX....X..X...
  開  ....XX....XX......XX..X.....X.....X...X..X..................
  ```
- `examples/e10_mediator.py` — 重算上面那兩行（零機時，只讀已歸檔 JSONL）。
- `ops/gain/replay/r454/r454_exhibition_receipt.{json,txt}` ＋
  `examples/receipt_viewer_multiparty.html` — 「三把金鑰的收據」展件：內嵌 r454 真跑的
  三條完整簽章鏈（1840／1840／1899＝5579 筆），瀏覽器內從創世驗到鏈頭、逐格重算裁決／
  指名／出貨（368 題可選），並示範翻票⇒簽章紅、少一票誠實⇒平手不指名（R454 §三-3）、
  換平台字串⇒毫無反應（未簽章 metadata）。零外部資源、file:// 直開；
  組裝與驗收＝`ops/gain/replay/build_multiparty_viewer.py`（`--check`）、
  `ops/gain/replay/multiparty_viewer_node_check.mjs`、`tests/test_receipt_viewer.py`。
  隱藏測資只出現在頁面上圍起來的「給觀眾的答案，機制看不到」那一塊。

### 對外發布與存證

- `examples/publish_now.py` — 產出 `now.html` 的三類資料（現有知識／走過的路／
  還沒走的路）。**未來方向那組刻意沒有 result 欄位**，`future_run` 寫死 0——
  沒跑就是沒跑，資料結構不該給「填上結果」留一個看起來很自然的空格。
- `examples/publish_archive.py`、`examples/build_archive_index.py`、
  `examples/verdicts.py` — 檔案庫資料與機器可讀索引；裁決的**單一真相來源**在
  `verdicts.py`，兩支腳本共讀，否則索引會比網頁樂觀。
- `examples/archive_citations.py` — 引用備份。**用過、引用過的東西都要有落盤證據**
  （A 全文／B 僅摘要／人工核對引文三級，含 sha256）。拿不到也要記下拿不到。

## 鐵律（違反＝run 作廢）

1. **KS-1**：任何 prompt 模板禁止「你有責任／會被懲罰」類措辭；三臂模板逐字
   相同，唯一差異＝MemoryManager 注入的記憶區塊（`memory.assert_ks1_clean`
   是可執行防呆，不要繞過）。
2. **A4**：教訓只准坑型層級抽象、禁止逐字測資（`lesson_leaks_test_data`）。
3. **全 I/O JSONL 落盤**、retry×4、`infra_void` 規則（09 §3.5；06-30 稽核紀律）。
4. 記憶**不跨臂共享**、行為依賴歷史的部分禁用快取。
5. demo 只能說「看得到提升」；「證明提升」保留給預註冊 batch run。
6. wire-format：logbook 已 break（2026-07）；`~/.vacant-mcp` 等舊資料要清掉重鑄。

## 後推項（不要提前做）

~~改動2~~、~~牙齒~~、~~B 層六情境~~、~~V1 存檔點~~——**已於 2026-07-21 落地**
（feat/complete-vacant-p0-p1-p4 分支，經人類裁決提前 P4）。仍後推：
Thompson 路由、工具面 v2 再擴、V0 離線重放、X2/X3/X4 主跑、THEORY_V5 回灌。

**2026-08-06 加上的凍結項**（證據都很強，但不影響展場，排在展件可運作之後）：
通道分離六改（commit-reveal 評審、專長 profile、拒絕原語＋calibration 維、
面板拓撲控制、Delphi 第二輪、評審期間不揭露信譽）、X-attr 跨基質遷移、
X-cap 能力階梯、X-check 可查證度分層、`slash` 改成只動均值不動 n
（會改變牙齒形狀 ⇒ 要重跑 B 層六情境，現在動不划算）。
理由與最小可行試驗設計寫在 `專題/Vacant_展望_2026-08-06/04_接下來的步驟.md`。

## 已完成缺口（2026-07-21 對帳 19 號圖 G1–G12）

G1 EvalPlus loader ✓（整合門在本機 skip——官方包在 VM）· G7 統計四函式 ✓ ·
G8 舊 wire-format ✓（本機 tar 備份於 ~/vacant-mcp-backup-2026-07-21.tgz 後清掉）·
G9 死碼 ✓ · G10 硬編 IP ✓（VACANT_ENDPOINT 單一真相）· P0-3 /api/snapshot ✓ ·
T5 record 排私鑰 ✓ · G5 PREREG v2 草稿 ✓（**待人類簽字凍結**）。
未動（機時／人類事項）：P1-0 思考探針、X1 pilot 真跑（harness 已就緒；
展覽不強制需要它，v1 不排）、G12 行政（教授簽字、倫理遞件、機時裁決）。
~~AAMAS 死線~~、~~文獻直驗~~ 已不適用：不投稿；文獻已於 2026-08-06 直驗
（236 筆進 `參考文獻/_引用備份/MANIFEST.json`，全文 197、僅摘要 39）。

## 慣例

- Python 3.11+；runtime 依賴只有 `cryptography`；測試 `.venv/bin/python -m pytest tests/ -q`。
- 模組 docstring 用中文寫「這支在架構裡承重什麼」，並引規劃文件編號（如 12 §4.3）。
- 誠實邊界句（raises-cost 非 prevents 等）是規格的一部分，改碼時保留。
