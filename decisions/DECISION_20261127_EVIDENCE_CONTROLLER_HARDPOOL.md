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
