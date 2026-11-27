# 證據控制器：較難題池（cc40）預註冊——在任何模型資料之前凍結

日期：2026-11-27。接在 `DECISION_20261127_EVIDENCE_CONTROLLER.md`（修正 3／4）之後；**不修改該檔**。
背景：Haiku 在 Exercism 37 題候選上 A 臂 hidden 37/37（天花板），那個題池看不出控制器有沒有差。
本檔只做「建一個 Haiku A 臂成功率落在 25–70% 的題池並校準」，**不跑四臂批次**。探索性，不作效果宣稱。

## 來源
- `deepmind/code_contests`（HuggingFace，`main` 分支的 `data/valid-*.parquet` 與 `data/test-*.parquet`，**不碰 train**）。
  兩檔 sha256 於建構時記入 manifest（下載值：test `aa426cbd…`、valid `02e8c1cc…`）。
- 只取 `source==2`（Codeforces）且 `cf_rating>0` 的題。
- 本 repo 先前的 `ops/fl/` 用過 APPS 與 LiveCodeBench，不用。

## 候選規則（機械套用，依序）
1. 評分帶：B1 [1200,1500)、B2 [1500,1800)、B3 [1800,2100)、B4 [2100,2400)、B5 [2400,∞)。每帶最多 8 題，共 ≤40。
2. 帶內順序＝`sha256(f"20261127:{name}")` 十六進位升冪，同值依 name；依序驗證，通過有效性規則者收入，湊滿 8 就停；湊不滿就有幾題用幾題並回報。
3. 排除（描述層）：描述含 `<image>`（資訊缺失）；描述含互動／特殊評判線索（不分大小寫）：
   `interact|flush|any of (them|these)|print any|output any|prints? any|if there are (several|multiple|many)|multiple (answers|solutions)|several (answers|solutions)|any (valid|correct|possible)|in any order|you may (print|output)|absolute or relative|relative error|absolute error|precision`；`input_file`／`output_file` 非空。
4. 測資：public＋private＋generated 合併，依輸入全文去重；輸入或輸出 >1 MiB 的案例丟掉；預期輸出含浮點樣式記號（`-?\d+\.\d+`）的題整題排除；去重與截尺寸後 **≥20** 筆才算候選。
5. 單題最多取 60 筆：以 `random.Random(f"20261127:{name}")` 洗牌後取前 `min(n,60)`；**前 n//2 筆＝可見（驗收）半、其餘＝hidden（評分）半**（每半 ≥10）。
6. 每案時限 `L = 2×time_limit + 2` 秒（time_limit 缺或 0 當 1 秒）。
7. 比對：stdout 與預期輸出以空白切詞後逐詞相等。

## 有效性規則（參考解要過、空殼要擋）
- 取 `language==3`（Python 3）的解，依資料庫順序最多試 8 份，以 `python3 -I -S`（不載 site-packages，只有標準庫）跑。
- **需要 ≥2 份不同的解在兩半全部案例通過、且每案單獨執行的牆鐘 ≤ 0.5×L**（取第 1 份通過者為參考解）。
  理由：特殊評判題（多解皆合法）上，兩份獨立解的輸出會不同、而預期輸出只是其中一種；兩份都逐詞一致才當作「精確比對是對的」。
  這**只是下界檢查**，不是證明：兩份解可能共享同一個確定性的選擇（例如都輸出字典序最小者）。
- 空殼 `solution.py`（只有註解）在兩半都不得全過（兩半都要有失敗）。
- 通過有效性者才進題庫；被排除的題與原因全記入 manifest（含 `excluded` 清單）。

## 題庫格式（沿用既有 harness，不改 `redo.py`）
- `<題庫>/cc_<name>/workspace/{goal.md, contract.md, solution.py（只有註解的空殼）, solution_test.py, cases.json}`；
  `hidden/{solution_test.py, hidden_cases.json}`；`scorer.py`＝`build_ctl16.SCORER_TEMPLATE`（逐字）。
- 測試是 unittest（每案一個 test 方法，也可被 pytest 收集）；測試檔內嵌其資料檔的 sha256，資料檔被改動則該案失敗（防竄改）。
- 單案逾時 `L`；同一次執行累計 3 次逾時後，其餘案例直接失敗（防掛住）。
- 題庫放 `/opt/ctlwork/bm_tasks/cc40`（與 ctl37 同根，沙箱不須重做負控制；若根不同才重跑）。
  repo 內只放建構器與 manifest（逐檔 sha256），不放資料集本身。

## 校準與停止規則
- Haiku（`claude -p --model haiku`，`claude_sandbox_agent.py` 原樣）A 臂每題 1 次；預算形狀同 `ctlcal_haiku37_A.json`
  （`attempt_timeout_s` 600、arms.A.attempt_timeout_s 1800、acceptance timeout 120）；`grader.suite_timeout_s` 因每半最多 30 案×L 而調高為 400、`grader.timeout_s` 600（記入計畫檔）。
- infra_void：依計畫 `infra_re`，最多重試 ×4，仍失敗標 `infra_void`、不進分母並列出。
- jobs：先量。把所有參考解兩半同時在 N 路並行下重跑（N∈{32,16,8,4}，取最大的 N 使**所有案例仍通過**），記入結果。
- 結果的停止點：A 臂 hidden 全過比例（每題 hidden 全過＝1）整體與各帶一起回報；**不依結果重選題**。
  若整體落在 25–70% 之外也只回報（不自動換池）。
- 之後回報內容：逐題表、整體與各帶 A 率、修正 3 選題規則會挑的 16 題、Haiku 花費、4 臂×3 重複×16 題的預估成本與時間、缺陷、未驗證事項。

## 限制（預先寫明）
- Haiku 的訓練資料很可能含這些 Codeforces 題與題解（code_contests 為 2021 年資料）；無法排除，成功率可能高估能力。
- 特殊評判洩漏只用關鍵字＋雙解一致排除，不保證沒有漏網。
- 時限是這台機器的 CPython 上的實測，不是 Codeforces 的原時限。

---

## 附錄 1（2026-11-27，cc40 校準之後、cchard 任何模型資料之前）：cc40 結果與難端題池 `cchard`

### cc40 結果（已量到）
Haiku A 臂 40/40（hidden 與驗收皆全過，infra_void 0，費用 $0.361），各評分帶全是 8/8，仍在天花板。
限制：Haiku 對 2021 年 Codeforces 題與題解的熟悉度（訓練暴露無法排除）；「Python 3 參考解要在 CPython 時限內通過」的規則截掉難端
（評分 ≥2700 且過前置篩的 32 題裡只有 2 題有 Python 3 解）；cc_1586I（3500）hidden 半 90% 預期輸出同一個答案；cc_1608C 參考解有執行緒競態。
細節：`ops/redo/results/ctl_hardpool_20261127/README.md`。cc40 不修改。

### 新題池 cchard（規則在看到任何 cchard 資料前固定）
- 來源：同樣的 valid＋test parquet（sha256 同上），Codeforces、`cf_rating ≥ 2400`，且**不在 cc40**（以 cc40 manifest 的題號排除）。
- 描述層排除、測資去重／截尺寸（>1 MiB 丟）、浮點輸出整題排除、≥20 筆、單題最多取 60 筆、種子洗牌、前 n//2 可見其餘 hidden（每半 ≥10）：與前文相同。
- 每案時限 `L = 2×time_limit + 2` 秒；比對為空白切詞後逐詞相等。
- Oracle：資料庫 `solutions` 裡本機跑得起來的任何語言（C++ 以 `g++ -O2 -std=gnu++17` 編譯、Python 3 以 `python3 -I -S`）。
  有效性：**≥2 份不同的正確解在所有保留案例上與預期輸出一致，且每案單獨牆鐘 ≤ 0.5×L**（編譯不計時、編譯失敗＝該份不算）；最多試 12 份（C++ 優先順序＝資料庫順序）；
  兩份解的語言不限。空殼兩半都不得全過；特殊評判排除同前（拿不準就排除）。
- 納入：**所有**過規則者，依 (rating, 題號) 排序，最多 40 題；回報合格題數。
- 題庫格式：同前，但 worker 可交 `solution.py` 或 `solution.cpp`：測試檔若見 `solution.cpp` 就以 `g++ -O2 -std=gnu++17` 編譯（編譯逾時 60 秒、
  編譯失敗＝該案失敗並附編譯器訊息前段）再跑執行檔，否則跑 `solution.py`。兩者都在時用 `solution.cpp`。工作區放空殼 `solution.py`。
  題面敘述用中性字句：「可用 Python 3 或 C++17」。
- 沙箱：沿用 `claude_sandbox_agent.py`；**先做正控制**（沙箱 shell 裡 g++ 編譯＋執行、python 執行都成功）與**重跑一次負控制**（無網路、工作區外讀不到），都在任何 Haiku 嘗試之前。
  若沙箱擋住 g++（例如暫存目錄），調整只限工作區內的環境設定且記錄，不放寬讀寫規則。
- 校準：Haiku A 臂每題 1 次、單次 1800 秒、hidden 評分、retry×4、infra_void；jobs 由負載檢查決定
  （N∈{32,16,8,4,2}，取最大的 N 使所有參考解〔含編譯〕在 N 路並行下兩半全過，各重複 2 輪）。
- 停止規則：A 率（hidden 全過比例）落在 25–70% ⇒ 回報未改的修正 3 規則所選 16 題（先取沒過但 hidden 比例 ≥30%，再交替補沒過 <30% 與通過〔通過上限 4〕）並停止；
  之外 ⇒ 回報並停止。兩種情況都不跑四臂批次，也不依結果重選題。
- 回報：逐題表（含交付語言、失敗型態一行）、測試強度（錯誤解擋下率，同前）、花費與 16×4×3 的預估、缺陷、未驗證事項。
- 另：對 cc_1586I 檢查 Haiku 的解是真演算法還是靠 NONE 佔多數過關（只讀已落盤的檔案與重新評分，不新增模型資料）。

---

## 附錄 2（2026-11-27，在任何 cchard 四臂批次資料之前）：Haiku × cchard 四臂批次——**明確標示的偏離**

### 偏離
`DECISION_20261127_EVIDENCE_CONTROLLER.md` 修正 5 的選擇規則：正式批次只跑 A 臂 hidden 成功率在 25–70% 之內的 (模型, 題池)，沒有就「回報、不跑」。
cchard 的 Haiku A 校準是 35/39＝89.7%，在範圍外，依規則應該不跑。**協調者決定仍然跑**，理由：這是目前唯一出現失敗的 Haiku 題池、成本低、負責人要先看 Haiku 的結果。
這是對預註冊規則的偏離，不是規則允許的選項；報告與任何引用都要帶「偏離」二字。

### 後果（先寫明）
- 接近天花板：A 臂只有 4/39 題在校準時失敗，各臂最多約 10% 的格可能不同；C 對 B、C 對 R 的結果預期只由少數幾題決定。
- 探索性、只判斷方向；不作效果宣稱。校準的 39 次 A 臂**不併入**分析（獨立的 `ctlcal_haiku_cchard_A`）。
- 因為不是挑「失敗的題」，沒有挑選造成的迴歸均值問題；也因為題單是全部 39 題，沒有選題自由度。

### 設計（逐字沿用 `ops/redo/plans/ctl16_pi_qwen9b.json` 的臂與預算）
- 題：**cchard 全部 39 題**（不依校準結果選）。題庫 `/opt/ctlwork/bm_tasks/cchard`（manifest 逐檔 sha256）。
- 臂：A 單次 1800 秒；R 盲重開最多 3 次；B 重開最多 3 次＋`failing_tests` 回饋；C 證據控制器（規則表、門檻不動）；
  單次 600 秒、總預算 1800 秒；每題每臂 3 重複＝39×4×3＝**468 格**；種子 20261127，計畫格式與 `redo.py` 不變。
- 工人：與校準相同的 `claude_sandbox_agent.py`（Claude Haiku，`claude -p --model haiku`），沙箱負控制／正控制在 cchard 題庫上已過（25/25）。
- 並行：**jobs 8**（容器 4 CPU 與其他工作共用；cchard 負載檢查在 8 路於當下機器狀態重跑，全過：`cchard_batch/loadcheck_j8.jsonl`）。
- infra_void：同計畫；最多重試 ×4，仍失敗列出、不進分母；配對比較時任一臂 void 的 (task, rep) 排除。支援續跑（已完成的格不重跑）。

### 計時雜訊護欄（現在固定）
- 批次結束後，**每個交付工作區的 hidden 半逐一（序列）重新評分，序列分數才是正式分數**；報告有多少格和批次內分數不同。
- 迴圈內的驗收計時雜訊無法移除：報告「唯一的可見失敗都是逾時」的每一次嘗試。

### 分析（現在凍結）
- 各臂 hidden 成功率（序列重評分數）。
- 配對（task×rep）差：C−B、C−R，以及 R／B／C 各自 −A；報不一致對數與精確符號檢定（用 `vacant_network.research.mcnemar_exact`）；也報 hidden 通過比例的差。
- 每個成功的 token 與費用；曾通過後被弄壞的比例；牆鐘；控制器規則在真實執行中各觸發幾次的表。
- 同樣的分析再報在「A 臂在批次內至少失敗一次的題」子集（**事後挑選，標示為 post-hoc**）。
- 驗證每一個 C 臂的決策鏈（簽章 logbook 事件），回報驗證數。
- 費用硬上限：Haiku 本批次花費超過 $20 即停下並回報。
