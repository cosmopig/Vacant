<!-- 狀態：**已簽（2026-09-25，人類在對話裡的選擇，見最下面「簽字」）＝凍結**。
     這一份與它釘住的東西在正式批次開跑之後不准再改；要改＝另一份預註冊、另一個實驗。 -->

# 預註冊：裝了零設定 Vacant 的 pi，在 DABstep 上的答對率有沒有比沒裝好

依據：`decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md`（評測計畫與人類裁決）、
`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md`（C 組的行為，第 2.1 版）、
校準紀錄 `ops/eval/evidence_20260925/pilot/calibration/CALIBRATION.md`。

## 一、要回答的問題

同一個 agent（pi 0.87.1）、同一個模型、同一個題目、同一個環境，**只差有沒有照 README 裝 Vacant**，
DABstep 的答對率有沒有不同？

- **A 組**：Harbor 官方的 pi agent（`--agent pi`）。
- **C 組**：同上，加使用者的安裝指令（`ops/eval/harbor_vacant.py`：apt 的 pipx、`pipx install <wheel>`、`vacant install`）。
  不設任何 Vacant 環境變數、不寫契約。B 組不做（人類裁決）。

## 二、釘住的東西

| 項目 | 值 |
|---|---|
| 評測框架 | Harbor `laude-institute/harbor` @ `6cb9ff3167596c456e0b24622d473b59fc9ab6c7` |
| agent | pi `@earendil-works/pi-coding-agent@0.87.1`；`--ak max_turns=15 --ak model_api=openai-completions --ak version=0.87.1` |
| 環境映像 | `vacant-eval/dabstep-env:1`，ID `sha256:0e2cbfab8265d048f6ad45866b5f39f6a393b013ddbcde59c5e7a98ac8972728`（官方 Dockerfile＋沙箱憑證修正；資料 7 檔 sha256 見 `ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json`） |
| 題目 | 正式 79 題：`ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json`（sha256 `ddf4a962f612b5821175a8d06d20eaaed74d75e9d4f2a0105bb4fbf65efc7319`；每題 `tests/` 的 sha256 在裡面；72 題簡單＋7 題困難 dev，和 dev 重複的用 dev 的真答案） |
| 評分 | 每題自己的 `tests/scorer.py`（官方 DABstep 評分） |
| Vacant | 程式碼 commit `8b22c7cc05632c79d8331d919314a2eb141760b4`（`vacant_network/` 與 wheel 建置時的 `58bf3ea7` 相同）；wheel `vacant_network-0.8.0-py3-none-any.whl` sha256 `6de8f714decd4b135f0a4e23d8cc83e2bfb3a59772d83244940c0fa6888782fd` |
| 規則檔 sha256 | `trace/evidence.py` `401ccc69…1896`；`trace/review.py` `167e90d2…8ae0`；`trace/zerostop.py` `953dd564…7d40c`；`adapters/mode.py` `76151415…3a52`；`adapters/hook.py` `0df13147…c256`；`adapters/agents.py` `dd97a424…3d13c` |
| 評測工具 sha256 | `ops/eval/harbor_vacant.py` `7b93b0e3…cc34`；`ops/eval/pilot/run_one.sh` `937366e8…b1e5`；`ops/eval/formal/run_formal.py` `9b1bf696…ecd2`；`ops/eval/orproxy.py` `0ad70316…e595` |
| 模型與供應商 | `google/gemma-4-26b-a4b-it` @ `deepinfra/fp8`；`qwen/qwen3.8-27b` @ **`parasail/fp8`**（原訂 `darkbloom/fp4`，校準時幾乎每一通限流，人類 2026-09-25 裁決改用）。`allow_fallbacks=false` |
| 思考 | 記帳代理強制：開＝`reasoning.enabled=true, effort=medium` |
| 每一跑的上限 | 15 回合（C 組的退回也算在內；Harbor 中止之後 pi 不進 Stop，C 組拿不到額外回合）；0.30 美元 |

## 三、主要指標與檢定

- **指標**：每一題答對與否（Harbor 的 `reward`）。
- **主要比較（只有一個）**：**gemma-4-26b 開思考**，C 對 A，**77 題**（正式 79 題去掉第 5、70 題，見第七節第 5 點），
  配對的 McNemar 精確檢定，雙尾 α＝0.05（`vacant_network/research.py` 的 McNemar）。只用 A、C 兩邊都有評分的題。
- **次要**（描述，不做主要結論）：qwen3.8-27b 開思考（錢夠跑到哪裡就報到哪裡）；第 5、70 題兩個模型的結果另外列。
- **一跑壞掉**（Harbor 例外、逾時、代理 402、供應商錯誤讓 pi 沒拿到任何回答）：記成 `infra_void`，批次最後照順序補跑一次；
  補跑也壞 ⇒ 那一**對**從分析拿掉並列出來。C 組 `vacant_check.json` 的 `c_arm_ok=false`（沒裝上、沒記到步驟）**不是**
  infra_void，照算 C 的成績（意向治療）。`stop_reached=false`（回合用完、沒走到交件前檢查）照算，另外報。

## 四、同時要報的（不是「改善」的證據）

1. 翻轉表：A 對 C 錯、A 錯 C 對，逐題列出。
2. **傷害**：C 組第一次交件是對的、被退回之後改錯的題數（從 C 組病歷裡第一次 Stop 時的答案檔判斷）。
3. 退回：C 組有被退回的題數、每一類（要求的檔不存在／失敗步驟／測試說法／沒出處的值／沒打開）各幾次；走到交件前檢查的比例。
4. 成本：兩組的請求數、prompt／completion／reasoning token、美元（記帳代理逐通紀錄），C 組多花的比例。
5. 時間：兩組每題的牆鐘時間。

## 五、跑的順序與停止規則

- 條件依序：**gemma-4-26b 開思考** 先跑完 79 題，再 **qwen3.8-27b 開思考**。
- 題目順序：`random.Random(20260925).shuffle(formal_79)`（`ops/eval/formal/run_formal.py` 的 `order()`；第 1 到 12 題是
  9、7、70、1305、25、53、35、46、47、48、50、54）。同一題的 A、C **同時**開跑；同時最多 2 對（4 個容器）。
- 停止：開新的一對之前看記帳代理的累計花費，4.80 美元減掉它少於 0.30 美元就不再開新的，等在跑的跑完。
  **不看中間結果決定要不要繼續**（驅動程式只讀花費，不讀評分）。
- 分析在批次結束（或錢用完）之後做一次。

## 六、預算

累計上限 4.80 美元（金鑰不加值）；開跑前已花 0.202 美元（閘門 1、研究、校準）。校準（困難題 1716）：
gemma 每跑約 0.04 美元（15 回合用完的情況）；簡單題在閘門 1 是 0.003（做完）到 0.038（回合用完）。
預估 gemma 一輪 158 跑約 2.4～4 美元，剩下的給 qwen。沒有試點（人類裁決：校準顯示困難題大多只會看到回合用完）。

## 七、已知的偏差（簽字時一併認可）

1. 官方 DABstep 用 smolagents；這裡用 Harbor 轉接版＋pi（官方的沒有可掛鉤的 agent 程序）。
2. 回合上限 15、每跑 0.30 美元上限（官方沒有）。
3. 環境映像多了這台沙箱的憑證修正；資料是同一份（sha256 核對過）。
4. C 組的 `vacant install` 裝在 Harbor 給 pi 的設定目錄（`PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent`）；Vacant 從 wheel 裝，
   依賴從 PyPI 裝；機器沒有 pipx 就用 apt 裝。
5. **規則是看過正式題的紀錄之後改的**：閘門 1 在第 5、70 題（A 組、其他模型）的真實紀錄重播之後，加了「要求寫出的檔不存在」、
   改了「cd 資料夾不算讀」「只寫答案限一行」。⇒ 主要分析去掉這兩題（人類裁決）。
6. qwen 的供應商從 fp4 換成 fp8（上面第二節）。

## 八、會怎麼說結果（先寫死）

- 顯著、C 較好：「在這 77 題、gemma-4-26b 開思考、這個設定下，裝了 Vacant 的 pi 答對率較高（McNemar p＝…）」——
  不外推到別的題庫、別的模型、別的回合上限。
- 不顯著：「這一輪沒有量到差別」＋翻轉數；**不說**「沒有效果」。
- C 較差且顯著：照實寫，並列出傷害表。

## 簽字

人類（本專案作者，對話中回答，2026-09-25）對三個問題的選擇，逐字：
1. qwen 供應商：「換 fp8：Parasail（建議）」
2. 試點與簽字：「不跑大試點，直接簽、跑正式（建議）」——該選項註明「選第一項＝你同意預註冊草稿、用你這三題的選擇當簽字」
3. 第 5、70 題：「拿掉，主要分析用 77 題（建議）」
