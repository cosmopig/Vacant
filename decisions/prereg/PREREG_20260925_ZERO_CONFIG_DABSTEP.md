<!-- 狀態：**草稿，待人類簽字**。簽字之前任何數字只能說「看得到差別」（鐵律 5）。
     簽字方式：人類在最下面「簽字」一節寫上名字與日期，並確認第八節的三個選項；之後這份檔案與它釘住的東西不准再改。 -->

# 預註冊：裝了零設定 Vacant 的 pi，在 DABstep 上的成績有沒有比沒裝好

依據：`decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md`（評測計畫與人類裁決）、
`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md`（C 組的行為，第 2.1 版）。

## 一、要回答的問題（只有一個主要問題）

同一個 agent（pi 0.87.1）、同一個模型、同一個題目、同一個環境，**只差有沒有照 README 裝 Vacant**，
DABstep 的答對率有沒有不同？

- **A 組**：Harbor 官方的 pi agent（`--agent pi`）。
- **C 組**：同上，加使用者的安裝指令（`ops/eval/harbor_vacant.py`：apt 的 pipx、`pipx install <wheel>`、`vacant install`）。
  不設任何 Vacant 環境變數、不寫契約。
- B 組（只加一段角色提示）**不做**（人類裁決）。

## 二、釘住的東西（改了任何一個＝另一個實驗）

| 項目 | 值 |
|---|---|
| 評測框架 | Harbor `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` |
| agent | pi `@earendil-works/pi-coding-agent@0.87.1`；旗標 `--ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1` |
| 環境映像 | `vacant-eval/dabstep-env:1`（ID 見 `ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json`；官方 Dockerfile＋沙箱憑證修正；資料 7 檔 sha256 同一份） |
| 題目 | 正式 79 題（`ops/eval/pilot/tasks.json` 的 `formal_79`；組法 `ops/eval/dabstep_formal.py`，每題 `tests/` 的 sha256 在 `FORMAL_MANIFEST.json`） |
| 評分 | 每題自己的 `tests/scorer.py`（官方 DABstep 評分：數字容許誤差、字串模糊比對） |
| Vacant | commit 〔簽字前填〕、wheel sha256 〔簽字前填〕、`evidence.py`／`review.py`／`zerostop.py` 的 sha256 〔簽字前填〕 |
| 模型 | `qwen/qwen3.8-27b` @ `darkbloom/fp4`；`google/gemma-4-26b-a4b-it` @ `deepinfra/fp8`（不准換供應商：`allow_fallbacks=false`） |
| 思考 | 經記帳代理強制：開＝`reasoning.enabled=true, effort=medium`；關＝`enabled=false` |
| 每一跑的上限 | 15 回合（C 組的退回也算在這 15 回合裡；Harbor 中止之後 pi 不會進 Stop，C 組拿不到額外回合）；0.30 美元 |

## 三、主要指標與檢定

- **指標**：每一題答對與否（Harbor 的 `reward`，0 或 1）。
- **檢定**：配對的 McNemar 精確檢定（雙尾，α＝0.05），每個（模型、思考）條件各自一個；主要比較＝〔第八節選項 1〕。
  多個主要比較時用 Holm 校正（`vacant_network/research.holm_bonferroni`）。
- **一跑壞掉**（Harbor 例外、逾時、代理 402）：記成 `infra_void`，照順序補跑一次；補跑也壞 ⇒ 那一**對**從分析拿掉並列出來。
  C 組的 `vacant_check.json` 顯示 Vacant 沒裝上或沒檢查（`c_arm_ok=false`）**不是** infra_void，照算 C 的成績（意向治療）。

## 四、同時要報的（不是「改善」的證據）

1. 翻轉表：A 對 C 錯、A 錯 C 對，逐題列出。
2. **傷害**：C 組第一次交件是對的、被退回之後改錯的題數（從 C 組病歷裡第一次 Stop 時的答案檔判斷）。
3. 退回率：C 組有被退回的題數、每一類（要求的檔不存在／失敗步驟／測試說法／沒出處的值／沒打開）各幾次。
4. 成本：兩組的請求數、prompt／completion／reasoning token、美元（記帳代理逐通記錄），C 組多花的比例。
5. 時間：兩組每題的牆鐘時間；C 組交件前檢查的秒數。

## 五、跑的順序與停止規則

- 順序：〔第八節選項 2〕的條件，題目用種子 `20260925` 打亂（`random.Random(20260925).shuffle(formal_79)`），
  同一題的 A、C **同時**開跑（同一時段、同一個供應商狀態）。同時最多 4 個容器。
- 停止：跑到預算用完為止（第六節的配額）；分析只用 A、C **兩邊都跑完**的題。**不准**看了中間結果再決定要不要繼續。

## 六、預算（〔校準之後填〕）

剩約 4.70 美元（金鑰不加值）。校準（題 1716，四個開思考的條件）與試點（10 題，不和正式重疊）量到的每跑成本：〔填〕。
配額：〔填〕。

## 七、已知的偏差（簽字時一併認可）

1. 官方 DABstep 用 smolagents；這裡用 Harbor 轉接版＋pi（官方的沒有可掛鉤的 agent 程序）。
2. 回合上限 15、每跑 0.30 美元上限（官方沒有）。
3. 環境映像多了這台沙箱的憑證修正；資料是同一份（sha256 核對過）。
4. C 組的 `vacant install` 裝在 Harbor 給 pi 的設定目錄（`PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent`），因為 Harbor 用自訂端點時
   pi 不讀 `~/.pi/agent`；Vacant 從 wheel 裝（PyPI 上是舊版），依賴照樣從 PyPI 裝。
5. **規則是看過正式題的紀錄之後改的**：2026-09-25 用閘門 1 的真實紀錄重播時，加了「要求寫出的檔不存在」這一類、改了
   「cd 資料夾不算讀」「只寫答案限一行」——閘門 1 的 DABstep 紀錄是正式集裡的第 5、70 題（當時是 A 組、其他模型：
   gemma-3-12b、gemma-4-26b、qwen3.5-9b）。規則本身不是針對這兩題寫的，但它們確實影響了規則。〔第八節選項 3〕

## 八、要人類決定的三件事

1. **主要比較**：(a) 只有一個：qwen3.8-27b 開思考；(b) 兩個：qwen3.8-27b 開思考、gemma-4-26b 開思考（Holm）；
   (c) 〔依校準成本建議〕。
2. **跑哪些條件**（錢只夠一部分）：〔依校準成本列出選項〕。
3. **第 5、70 題**：(a) 照跑、照算，偏差欄寫明；(b) 從主要分析拿掉（剩 77 題），另外列出。

## 九、會怎麼說結果（先寫死）

- 顯著（p<0.05，C 較好）：「在這 N 題、這個模型與設定下，裝了 Vacant 的 pi 答對率較高（McNemar p＝…）」——不外推到別的題庫、別的模型。
- 不顯著：「這一輪沒有量到差別」＋事前算的最小可偵測效果；**不說**「沒有效果」。
- C 較差且顯著：照實寫，並列出傷害表。

## 簽字

〔人類：姓名、日期、第八節的選擇〕
