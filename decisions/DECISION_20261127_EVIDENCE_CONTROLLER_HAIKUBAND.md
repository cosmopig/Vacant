# DECISION 2026-11-27 — Haiku 帶內題池搜尋（25–70%）：預註冊

執行者：雲端接手代理。授權：擁有者方向指示（校準便宜、可多做；選題規則在看資料前寫死；若落在 25–70% 則跑**一個**四臂批次；總花費上限 $30，校準含在內；不在天花板池跑正式批次）。
本檔不修改主設計檔 `DECISION_20261127_EVIDENCE_CONTROLLER.md`；控制器門檻與規則表不動。每個候選的建置與選題規則在該候選的資料之前寫入並推送。
花費：以 Claude CLI JSON 的 `total_cost_usd` 加總，記在 `ops/redo/results/ctl_haikuband_20261127/SPEND.jsonl`。

## 候選 1：cchard-L（同 39 題 cchard ＋ 大／最壞測資）— 建置規則（凍結，在任何 cchard-L 的 Haiku 資料之前）

來源：與 cchard 相同的 valid＋test parquet（sha256 同 cchard manifest）、同一批題（`bank_cchard_MANIFEST.json` 的 39 題）。
**聲明：這些題 Haiku 在 cchard 校準時已經做過一次（35/39）；cchard-L 是新題池（新目錄 `/opt/ctlwork/bm_tasks/cchardL`、新 manifest），不是重新評分。**

1. 對每題，原本的 60 案（30 可見＋30 hidden，同 cchard 的種子切分）原樣保留。
2. 大測資生成器：每題由 `claude -p --model haiku`（單次呼叫、不給工具、輸入＝題目描述＋一筆範例輸入；要求輸出一支 Python3 腳本 `gen.py`，
   用法 `python3 gen.py SEED KIND`，KIND∈{max, mid, edge}，依題目限制寫到標準輸出一筆輸入：max＝各參數取上限的隨機輸入、mid＝約上限的 1/10、
   edge＝極端但小的邊界）。生成器提示語不含責任／懲罰措辭（KS-1）。生成器寫壞（執行錯誤或空輸出）時重問一次，仍壞則該題不加大測資。
   提示語、原始回覆、費用全部落盤 JSONL。
3. 每題產 12 筆候選：max×6（seed 1–6）、mid×3（seed 1–3）、edge×3（seed 1–3）。
4. 答案來源：該題資料庫裡的 C++ 正解（至多前 12 份，沿用 `build_cchard.validate` 的挑選與通過判準：通過原 60 案、每案 ≤0.5×限時）。
   一筆候選保留的條件：**≥2 份正解都以退出碼 0 執行、輸出逐 token 一致，且每份牆鐘 ≤0.5×限時（限時＝2×原限時＋2 秒，同 cchard）**；
   答案取一致的輸出。輸入 ≤1 MB、輸出 ≤1 MB。不一致或任一份逾時／當掉＝丟棄。（生成器違反題目限制時，兩份正解可能一致地吞下無效輸入——這是已知殘餘風險，輸入合法性**沒有**獨立檢查。）
5. 保留的大測資洗牌（種子 `20261127:<題名>:L`）後對半分入可見／hidden（同切分規則：前半可見、後半 hidden）。每題至多 12 筆。
6. 題收錄條件：至少 4 筆保留的大測資，且可見與 hidden 各 ≥2 筆；參考解（兩半都過）＋空殼（兩半都不過）寫出後再驗（同 cchard 的 `real_check`）。不符者排除並列出。
7. 輸出：`ops/redo/banks/build_cchardL.py`（建置器）；manifest 與資料集的 sha256 在 `ops/redo/results/ctl_haikuband_20261127/`，資料集本身不進 repo。
8. 校準：Haiku A×1／題、jobs=4（CPU 與別的批次共用，保守）、600 s 嘗試、1800 s 預算、hidden 獨立評分，**計時敏感的評分以序列重評為正式**。落在 25–70% ⇒ 進選題；其餘 ⇒ 轉候選 2。
   帶內判準以 hidden 通過率（通過＝hidden 全過）為準。

### 候選 1 建置紀錄（Haiku 校準資料之前寫入）
- 39 份生成器各一次呼叫成功（39/39 第一次就過 edge／max 各一筆的執行檢查；總費用見 `SPEND.jsonl`，約 $0.07）。生成器寫者與受測 worker 同為 Haiku 家族（`claude-haiku-5-5`）；已知偏誤，生成器只決定輸入不決定答案。
- 建置結果：37 題收錄、2 題排除（cc_1567F、cc_1599D：保留的大測資只有 3 筆 <4）；37/37 參考解兩半皆過、空殼兩半皆不過。manifest sha256 `8490ffbf…99c6`（`ops/redo/results/ctl_haikuband_20261127/cchardL/bank_cchardL_MANIFEST.json`）。
- 校準計畫 `ops/redo/plans/ctlcal_haiku_cchardL_A.json`（37 題、A×1、jobs 4）。沙箱沒有改動（cchard 時已含 g++／python 正控制 25/25），這一輪**沒有**重跑負控制。

### 候選 1 校準結果
cchard-L Haiku A×1：hidden 33/37＝**89.2%**（序列評分），帶外 ⇒ 不跑正式批次，轉候選 2。細節 `ops/redo/results/ctl_haikuband_20261127/cchardL/README.md`。

## 候選 2：Aider polyglot（非 Python、非 JS）— 建置與選題規則（凍結，在任何 polyglot 的 Haiku 資料之前）

來源：`Aider-AI/polyglot-benchmark`（commit `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`）；內容為 Exercism 練習，每題目錄各有 Exercism 的 MIT LICENSE（README 註明依 Exercism 開源授權使用）。
本 repo 已用過：Python（`polyglot_py`、`exercism_py_*`）與 JavaScript（`exercism_js*`）⇒ 一律略過。語言只考慮 C++、Go、Rust、Java。

1. **工具鏈正控制**：只收在 worker 沙箱（`claude_sandbox_agent.py` 的 deny 規則）裡能用的語言：由 Haiku 在沙箱裡實際執行該語言的 hello-world／測試命令，看得到預期輸出才算。
   沙箱原本 PATH 只有 `/usr/local/bin:/usr/bin:/bin`，Rust 工具鏈在被 deny 的 `/root`。處理方式（部署事項，不改共用檔）：把 Rust 穩定版工具鏈複製到 `/opt/polytools/rust`、
   另寫 `ops/redo/claude_sandbox_agent_poly.py`（只覆寫環境的 PATH／GOCACHE／CARGO 相關變數，其餘 import 原檔）。Java 需要 Maven Central 的 JUnit／AssertJ，沙箱無網路 ⇒ 正控制若失敗則 Java 整個語言排除（記錄實測）。
2. **資格**（機械判定）：該語言的測試檔恰好一個；原生測試函式數 ≥10（C++：`TEST_CASE`；Go：頂層 `func TestXxx(t *testing.T)`；Rust：`#[test]`；Java：`@Test`）；Rust 的 Cargo.toml 不得有 `[dependencies]`；
   參考解（`.meta/example.*`）在建置環境過全部測試；空殼（原始 stub）在可見半與 hidden 半**都不過**（通過＝該半全過，同 cchard）。Go 因表驅動多為單一測試函式，這條自然篩掉大部分。
3. **切分**：測試函式依出現順序編號，以種子 `20261127:<語言>:<題名>` 洗牌，前 `n//2` 個＝可見、其餘＝hidden；非測試函式的輔助程式碼兩半都保留；Rust 的 `#[ignore]` 一律移除。
   可見半＝工作區裡的測試檔（hidden 的測試函式被刪掉）；hidden 半＝只含 hidden 測試函式的同一份檔，評分時覆蓋進工作區副本。
   驗收介面：工作區有 `solution_test.py`（unittest；執行該語言原生測試一次、每個測試函式一個 test method），契約說明可用原生命令或這支 Python 包裝器；hidden 評分用同一支包裝器的 hidden 版（經 cchard 的 `scorer.py`）。
4. **候選規則**：資格題依「語言、題名」排序；總數 ≤40 全收；否則每個語言上限＝使總數 ≤40 的最小均分上限（不足上限的語言全收，餘額分給其他語言），超過上限的語言從排序後清單取等距位置（floor(i·n/cap)）。
5. 校準同候選 1：Haiku A×1、jobs 4、hidden 序列評分、帶內判準 25–70%。

### 候選 2 建置紀錄（Haiku 校準資料之前寫入）
- 工具鏈正控制（沙箱內、Haiku 實跑，`polyglot3/toolchain_probe.stream.jsonl`）：Rust `cargo test`（`test result: ok. 1 passed`）、Go `go test ./...`（ok）、C++ g++（`cppok`）通過；Java：沙箱 PATH 沒有 gradle，且 JUnit／AssertJ 要從 Maven Central 取、沙箱無網路 ⇒ **Java 整個語言排除**（未再進一步嘗試）。
  部署：`/opt/polytools/rust`（複製的 Rust stable 工具鏈）、`/usr/local/bin/redo-claude-agent-poly` → `ops/redo/claude_sandbox_agent_poly.py`；`ops/redo/claude_negctl_poly.py` 在該環境下重跑負控制：第一次 worker 拒絕送出 B／T 探針（無效，非通過），第二次 25/25 通過。
- 建置器 `ops/redo/banks/build_polyglot3.py`。機械資格後：C++ 15 題（有 ≥10 個測試且可解析；`clock` 等 <10 者排除）、Go 3（paasio、react、simple-linked-list；其餘多為 2 個測試檔或 <10 個測試函式）、Rust 20。
  有效性（參考解兩半皆過、空殼兩半皆不過）：C++ 15 題全過；Go 2（paasio 在可見半因刪掉測試後 `runtime` import 未使用而編譯失敗，排除）；Rust 13（alphametics、decimal、doubly-linked-list、pig-latin、poker、macros、wordy 的參考解在這個環境不過，排除）；C++ meetup（需要 boost）排除。
  合計 30 ≤ 40 ⇒ 全收（C++ 15、Go 2、Rust 13）。manifest sha256 `227092e4…c0e0`，排除原因全在 manifest `excluded`。
- 校準計畫 `ops/redo/plans/ctlcal_haiku_polyglot3_A.json`（30 題、A×1、jobs 4、驗收逾時 400 s）。
