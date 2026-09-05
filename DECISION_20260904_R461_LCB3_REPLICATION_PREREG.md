# R461：造 `lcb_bank_v3`（189 題全新難題）並預註冊 P-R459-2 的**乾淨複製**

日期：2026-09-04（round728，Opus 5）。判準寫在**造 bank 之前、任何 run 發射之前**。
上游：`DECISION_20260904_R460_HARD_BANK_FEASIBILITY.md`（P-R459-1 已作廢）、
`DECISION_20260904_R459_R447_SETTLEMENT.md` §九／§十二。

## 一、拍板：走 P-R459-2，**不走**「再找更大的題庫買 5pp」

R460 量到 LCB lite 在「functional × medium+hard」契約下的**全部存量是 309 題**，
而 5pp 解析度需要 360。⇒ 5pp 這條路在這個來源上結構性走死，本輪不碰。

改答**買得起的問題**。R459 §九 的探索性發現：

```
OFF5 − OFF   MBPP+ (r445, n=371)：+0.81pp CI[−2.78,+4.28]  ⇒ RULED_OUT
OFF5 − OFF   LCB2  (r447, n=120)：+12.50pp CI[+3.12,+19.19] p=0.0081
```

兩個題庫給出**相反**的答案。但 LCB2 那個數字是**看過資料之後才寫的探索性分析**
（R459 自己標明「不准當結論引用」）。要把它變成能引用的東西，唯一的辦法是
**在沒看過的新題上預註冊、再量一次**。R460 產出的 189 題新題正好是這個資產。

## 二、bank 設計：`lcb_bank_v3` = **189 題新題，不含 v2 的 120 題**

- 來源視窗：`test.jsonl`(119) + `test2.jsonl`(37) + `test3.jsonl`(33)，
  即 R460 量到、**從未被任何 run 用過**的三個視窗。
- 轉換器：`ops/gain/build_lcb_bank.py`（**一個字都不改**）。改了就是換量具，
  r447 的 120 題基準就不可比。
- **刻意不做成 309 題的超集**：v2 的 120 題 r447 已經跑過，混進來 (a) 白燒 2.5 小時算力，
  (b) 把「乾淨的樣本外複製」污染成「序貫加樣本」（memory 規則：看過期中結果才加大 n
  ⇒ 併庫 p 偏樂觀）。**併庫 309 的分析在事後另外做，且新樣本必須單獨報一份。**
- 命名誠實聲明：`v3` **不是** `v2` 的超集，是 disjoint 的另外 189 題。
  接線時 `codebench.py` 的 docstring 要一併寫出 v3 的真實日期範圍
  ——R460 C3 已判定現行那句「本 bank 都在 2024-08 之後」對 v3 **為假**
  （189 題全部早於 2024-08-10）。不改這句就是留一個假宣稱在量具裡。
- 接線方式：`LCB_BANKS` 加一個 `"v3"` 條目（sha256／題數釘死）＋ `gain_run.py`
  的 `--bank` 加 `lcb3`。**加法式**：v1／v2 的路徑、sha、count、預設版本一個字不動。

### 事前預測（bank 構造）
1. `build_lcb_bank.py` 吃這三個檔產出 **恰好 189 題**（medium 152／hard 37，取自 R460 census）。
   ⇒ 不是 189 就代表 R460 的計數器與正式 builder 有分歧，**停下來查，不准繼續**。
2. 189 個 `task_id` 與 `lcb_bank_v2.jsonl` 的 120 個**零交集**。
3. 日期範圍 2023-05-07 → 2024-08-10。

## 三、C4 難度窗口——**這是發射閘門，不是事後備註**

`SPEC_GAIN` 的成效定義第一條：OFF 的需求=產出率要明顯低於 100%，失敗率窗口 **40–60%**。

風險（R460 已具名）：這 189 題**日期更早**（2023-05 起，比 v2 的整個視窗早）、
**medium 佔比更高**（152/189 = 80.4%，v2 是 55/120 = 45.8%）⇒ 兩個方向都指向「更簡單」。
⇒ **有可能掉出窗口下緣，天花板效應回來。**

**閘門 run：`runs/g_r461_off_gate_lcb3`**（`--arms OFF --n 189`，約 189 次呼叫）。

判決（**照這張表，不准量完再改**）：

| OFF 失敗率 | 判決 | 動作 |
|---|---|---|
| 40–60% | `GATE_PASS` | 發射三臂主 run |
| 30–40% | `GATE_MARGINAL` | 仍發射，但主 run 的結論**必須**在標題帶「窗口下緣」但書 |
| < 30% | `GATE_FAIL_TOO_EASY` | **不發射**，照實寫「189 題新題太簡單」，P-R459-2 在此來源作廢 |
| > 60% | `GATE_FAIL_TOO_HARD` | **不發射**，寫「地板效應」 |
| 任一 `infra_void` > 20% | `GATE_UNSCANNED` | 不是「量到 0」，是「沒量到」；查 infra 再說 |

**事前預測：失敗率 38–52%（點估計 45%），判 `GATE_PASS` 或 `GATE_MARGINAL`。**

⚠ 誠實邊界（現在就寫，免得下輪把它當獨立篩檢）：閘門用的是**同一批題**，
所以它是**設計閘門**不是獨立篩檢。為了不重複使用同一格資料，
**閘門 run 的 OFF 資料只用於 C4 判決，不併進主 run 的 OFF 臂**；主 run 自己重跑 OFF
（189 次呼叫的代價換配對完整性，$0，只花牆鐘）。

## 四、主 run 的預註冊（**閘門過了才發射**）

**run 名：`runs/g_r461_lcb3_three_arm`**，`--arms OFF,CONFORM,OFF5 --bank lcb3 --n 189`，
worker `gemma-4-12b-it-qat`（與 r447 同一個模型、同一個 8765 中轉端點——**換了就不可比**）。

| 代號 | 假說 | 事前 MDE（`power_paired.mde_at_n`，用 r447 實測 disc rate） | 事前預測 |
|---|---|---|---|
| **P-R461-1**（主）| OFF5 − OFF > 0 | disc 24.17% → n=189 **MDE 8.47pp**；r447 觀測 +12.50pp ⇒ **有檢定力** | Δ ∈ [+3, +20]pp、p<0.05、判 `OFF5_WINS` |
| **P-R461-2** | CONFORM − OFF > 0 | disc 32.50% → n=189 **MDE 8.99pp**；r447 觀測 +19.17pp ⇒ **有檢定力** | Δ ∈ [+8, +28]pp、p<0.05、判 `CONFORM_WINS` |
| **P-R461-3**（等預算，離線）| gate 規則 − 多數決 | disc 19.17% → n=189 **MDE 7.41pp**、併庫 309 **MDE 5.50pp**；r447 觀測 +4.17pp ⇒ **沒有檢定力** | **事前就判 `UNRESOLVED`** |

**P-R461-3 必須現在寫死「預期答不出來」**：不然下一輪會把 UNRESOLVED 讀成
「等預算打不贏」。memory 鐵律：UNRESOLVED 要分「沒量出來」與「沒有差異」，
而這一格**事前投影就說了是前者**。它照跑（離線重建零 API），但它的價值是併庫，不是自己判決。

### 推翻條件（觸發了照實寫，不准當場補判準）
- P-R461-1 若 `p ≥ 0.05` 或 `c ≥ b`：**R459 §九 的題庫相依假說在乾淨樣本上沒有複製成功**
  ⇒ 那個 +12.50pp 要被重新描述為「可能是 120 題上的抽樣運氣」，且**不准**用併庫 309 去救它
  （併庫含被看過的 120 題，序貫加樣本 ⇒ p 偏樂觀）。新樣本單獨那份才是仲裁者。
- P-R461-2 若不顯著：`CONFORM_WINS` 這個已收官的結論要被標記為題庫／視窗相依，升級 fable 重裁。
- 任一臂 `infra_void` > 20%：整份判 `UNSCANNED`，不是判「沒有差異」。

## 五、本輪（round728）做什麼／不做什麼

做：寫本判準 → commit（判準與量測**分開 commit**）→ 造 v3 bank → 接線（加法式）→
`verify_lcb_bank` ＋ `--arms probe` 雙向驗尺 → 造完就發射**閘門 run**（背景，不在回合內等）。

不做：**不發射三臂主 run**（要下一輪讀閘門結果才准）、不改 `build_lcb_bank.py`、
不改 v1／v2 的任何釘值、不改 `gain_run.py` 的實驗語意、不碰 1004／8766 的設定、不碰展件、
不對已收官的 r445／r446／r447 下新判斷。

## 六、量具覆蓋率的既有缺口（**不是本輪造成的，但要寫**）

LCB 原始資料**沒有官方參考解**，`lcb_probe_solutions.json` 只有 round441 手寫的 12 題，
且那 12 題都在 v2 裡 ⇒ **v3 的 probe 覆蓋率預期為 0/189**。
這代表 `--arms probe` 在 v3 上**不能**做「參考解全過」那個方向。
替代做法（memory 規則：沒有參考解也能證明量具有牙齒）：
1. **壞解方向照做**：probe 的「壞解要全擋」不需要參考解。
2. **好解方向改用能力下界**：閘門 run 跑完後，看有幾題**任一臂通過過一次**
   ——通過過就證明該題的 `hidden_check` 不是恆假。沒被示範的題數是
   **「量具假象」的上界**，不是「壞了幾題」。這個數字要跟失敗率一起報。
3. 若 probe 覆蓋率 0 讓「兩個方向都滿分才准跑」這條 SPEC 規則無法照字面執行，
   **照實寫成偏離**，不假裝通過。

---

# 附錄 A（round728 稍晚追加）：量具覆蓋率缺口的處理與 probe run 命名

§六 預測「v3 的 probe 覆蓋率為 0/189」——**實測命中**（`verify_lcb_bank --version v3`
印 `probe_coverage: 0/189`）。而 `gain_run.py:1299` 有一條硬擋：

```
if pr["n"] == 0:
    raise SystemExit("量具驗證一題都沒驗到——這不是通過，是沒接上。停。")
```

⇒ **覆蓋率 0 的話，v3 上連閘門 run 都發射不了。** 這是 harness 正確 fail-closed，
不是障礙。所以本輪照 round441 在 v1 上做過的同一件事：**手寫參考解並逐題驗證**。

## A.1 選題規則（**寫解之前先訂**，避免挑好解的題）

**按 `task_id` 升冪取前 12 題**，不看題目難易、不中途換題。
寫不出來的題**照實記成 attempted-and-failed**，不准默默換一題填補
——那會讓覆蓋率變成「我解得動的題」的樣本，而不是題庫的樣本。

實際結果：前 12 題（`lcb_2728` … `lcb_2810`，medium 9／hard 3）**全部寫出且全部通過**，
放棄 0 題 ⇒ 沒有發生存活者篩選。

## A.2 誠實邊界（**這是本附錄最重要的一段**）

1. **覆蓋率 12/189 = 6.3% 不是「量具驗過了」**，是「189 題裡有 12 題證明了
   `hidden_check` 不是恆假、也不是恆真」。R440T 的教訓（`instrument N/N`
   被讀成綠燈，實際兩題對任何解都保證失敗）在 v3 上**尚未被排除**。
   `verify_lcb_bank --version v3` 的 `float_5dp_suspects` 是空的
   ——R440T 那個**特定**失效模式沒出現，但那只排除一種模式。
2. **本附錄的「≥8 題才准發射」不是事前閘門。** 12 題是先寫完、先驗完，
   才寫下這個數字的。照實記：它是**已達成事實的記錄**，不是獨立的擋門。
   下一輪不准把它引用成「發射前通過了覆蓋率閘門」。
3. 真正的事前閘門只有兩個，且都是 harness 自己的：`pr["n"]==0` 硬擋、
   以及兩個方向都要滿分。這兩個本輪都是**真的跑過** `--arms probe` 才算數。
4. 未被示範的 177 題，其量具是否可用**沒有量過**。§六-2 的能力下界
   （閘門 run 跑完後數「任一臂通過過一次」的題數）仍然要做，那才是覆蓋這 177 題的東西。

## A.3 本附錄授權的 run 名（R440G 閘門要求 run 名寫進 DECISION）

- **`runs/g_r461_probe_lcb3`**——`--arms probe --bank lcb3`，零模型呼叫、零 API 成本，
  只驗量具。預測：`參考解通過 12/12`、`壞解被擋 12/12`、可見閘門 `12/12` 覆蓋 `12/12`。
- **`runs/g_r461_off_gate_lcb3`**——§三 的 C4 閘門 run（`--arms OFF --n 189`）。
- **`runs/g_r461_lcb3_three_arm`**——§四 的主 run，**閘門判 `GATE_PASS`／`GATE_MARGINAL` 才准發射**。

## A.4 §二 事前預測的對帳（**有一項 MISS，是我自己算錯**）

| 預測 | 實測 | 判 |
|---|---|---|
| 恰好 189 題 | 189 | **HIT** |
| 與 v2 零交集 | overlap=0、union=309 | **HIT** |
| 日期 2023-05-07 → 2024-08-10 | 逐字相同 | **HIT** |
| 難度 medium 152／hard 37 | **medium 135／hard 54** | **MISS** |

MISS 的原因**不是資料有問題**：R460 只報了合併後的 medium 207／hard 102，
我在寫 §二 時把 v3 的分項「回推」出來卻算錯（同一個錯誤也讓 §三 寫成
「v2 是 55/120 = 45.8%」，**v2 實際是 72/120 = 60.0%**）。
用實測值重算：合併 135+72=207、54+48=102 **與 R460 逐字相同** ⇒ 兩份量測一致。

§三 那句「medium 佔比更高 ⇒ 指向更簡單」的**方向仍成立但幅度被我誇大**：
真實是 71.4% vs 60.0%（不是 80.4% vs 45.8%）。⇒ **C4 掉出窗口的風險比 §三 寫的小**，
但 C4 的判決表與事前預測（38–52%）**不因此修改**——那張表寫在量測之前，改它就是量完再訂判準。

---

# 附錄 B（round729 / R462 追加）：**詞彙修正**——§四 的預測寫了兩個沒有仲裁者的判決名

**合法性前提（缺一不可，逐條自證）：**
1. **本輪沒有看過 P-R461-1／2／3 的任何資料。** 三條假說都需要 CONFORM 或 OFF5 臂，
   而此刻只有 OFF 單臂的閘門 run 在跑。R462 的普查工具另有 B6 硬擋門：
   任何讀檔路徑含 `g_r461_off_gate_lcb3` 一律 `RuntimeError`（selftest 有具名突變體 M6 證明它有牙齒）。
2. **§三／§四 的原文一字未改**，本附錄是加法式的（後輪要收回仲裁權，比對上面的原文即可）。
3. **只改「與數字無關」的缺陷**（R462 判準 §六.4 事前授權的範圍：詞彙／死碼／缺仲裁者）。
   **任何窗口、門檻、MDE、預測區間都沒有動。**

## B.1 缺陷（R462 X1／X2）

§四 表格的預測欄寫「判 `OFF5_WINS`」「判 `CONFORM_WINS`」。實測（`ops/gain/data/r462_census.json`）：

```
paired_ci.verdict 的詞彙表（ast 逐字取 return 的字串字面）
  = ['NON_INFERIOR_BUT_UNRESOLVED', 'ON_WINS', 'RULED_OUT', 'UNINFORMATIVE']
全庫掃 ops/gain/**/*.py 有沒有任何工具吐得出 "OFF5_WINS"  ⇒ emitters = []
                                          吐得出 "CONFORM_WINS" ⇒ emitters = []
```

⇒ 這兩個合取項**沒有仲裁者**。照字面永遠判不出真假（`UNRESOLVED`，不是綠燈也不是紅燈）。
這正是 memory 記過的「判準檔寫的欄位名可能不存在」與「四格判定有兩套詞彙」兩個坑撞在一起。

## B.2 修正（**只換名字、不換門檻**）

主 run 收官時，P-R461-1／P-R461-2 的第三個合取項改讀成**四格區間位置表**的判決，
由這條指令產生（`a-arm` 贏就是 `ON_WINS`，那是這張表對「a 贏」的既有名字）：

```bash
python3 ops/gain/replay/pooled_paired_ci.py --stratum lcb3=runs/g_r461_lcb3_three_arm \
    --a-arm OFF5    --b-arm OFF --key deliv     # P-R461-1
python3 ops/gain/replay/pooled_paired_ci.py --stratum lcb3=runs/g_r461_lcb3_three_arm \
    --a-arm CONFORM --b-arm OFF --key deliv     # P-R461-2
```

| 原文寫的 | 改讀成 |
|---|---|
| 判 `OFF5_WINS` | `verdict_pooled == "ON_WINS"`（a-arm=`OFF5`、b-arm=`OFF`） |
| 判 `CONFORM_WINS` | `verdict_pooled == "ON_WINS"`（a-arm=`CONFORM`、b-arm=`OFF`） |

⚠ `--key deliv` 不是預設值（預設是 `meets_demand`＝舊語意）。memory 鐵律：
**旗標預設值是舊語意時，下游要驗產物自己記的 `key`**，忘了帶會安靜翻掉判決且 `rc=0`。

⚠ **`ON_WINS` 這個名字只是「a-arm 贏」，不代表 `ON` 臂。** 收官寫散文時要寫成
「OFF5 − OFF 的 CI 完全在 0 以上」，不要抄工具吐的字串（那正是兩套詞彙的來源）。

## B.3 三個「命中不帶資訊」的警告（R462 X4／X5，**不改任何門檻，只約束怎麼引用**）

1. **P-R461-3「事前就判 `UNRESOLVED`」的綠燈基準率是 79.45%。**
   （在 r447 觀測的 disc=19.17%、b=14／c=9、π=0.6087 下，n=189 拿到 `p<0.05` 的機率只有 **20.55%**。）
   ⇒ 它命中**幾乎必然**，收官引用時要把 79.45% 一起寫上，不准當成「事前預測準」的佐證。
2. **§三 的兩個事前預測強度不同**：數字級「38–52%」基準率 **14.09%**；
   判決級「`GATE_PASS` 或 `GATE_MARGINAL`」基準率 **30.07%**（30–60 佔 0–100）。
   兩者在 **[30.0,38.0) ∪ (52.0,60.0]（共 16.0pp 寬）互相矛盾**：那裡判決級命中、數字級落空。
   ⇒ **收官必須報數字級那個**；只報判決級＝事後挑寬的那條。
3. §四「任一臂 `infra_void` > 20% ⇒ `UNSCANNED`」**不是**強制綠燈：掃過 29 個 run，
   15 個臂（分佈在 9 個 run）真的超過 20%，最高 `g_off60_20260824` 的 OFF 臂 60/60＝**100%**。
   ⇒ 這條擋門是活的，要照跑。

## B.4 本附錄**沒有**動的東西

窗口 40–60／30–40／<30／>60、事前預測 38–52%（點估計 45%）、三條假說的 MDE（8.47／8.99／7.41／5.50pp）、
預測區間 [+3,+20]／[+8,+28]pp、`p<0.05` 的 α、void 門檻 20%、n=189、seed、worker、端點、bank。
**一個數字都沒有動。**

---

# 附錄 C（round731 / R463 追加）：**附錄 B 的收官指令跑不起來**——改指到單 run 尺

**合法性前提**：與附錄 B 相同的自證見 `DECISION_20260904_R463_PAIRED_CI_KEY_GAP.md` §〇
（P-R461-1／2／3 的估計量本輪零讀取；只看了 OFF 臂第 1 列與逐臂列數）。
**§三／§四／附錄 B 原文一字未改，本附錄是加法式的。**

## C.1 缺陷

附錄 B 寫的兩條收官指令用 `pooled_paired_ci.py`，但那支是**多層合併**版，
`:242` 硬性要求 `len(--stratum) >= 2`。R461 是**單一題庫的複製**，只有 `lcb3` 一層：

```
$ python3 ops/gain/replay/pooled_paired_ci.py --stratum lcb3=runs/g_r461_lcb3_three_arm \
      --a-arm CONFORM --b-arm OFF --key deliv
需要至少兩個 --stratum LABEL=dir，或 --selftest
rc=2
```

⇒ 附錄 B 產不出 `verdict_pooled`，P-R461-1／2 的第三個合取項**照字面仍然沒有仲裁者**。
附錄 B 修好了「判決名沒有 emitter」，卻換成「指令跑不起來」——**同型缺陷的復發**。

## C.2 修正（**只換工具與旗標，門檻與判決名對應表一字不改**）

改用單 run 尺 `ops/gain/replay/paired_ci.py`（R462 普查的 `paired_ci.verdict` 詞彙表本來就出自它）。
它原本**沒有** `--key`、寫死 `meets_demand`；R463（`ec5bb5c`）已加法式補上 `--key`，預設維持舊語意。

```bash
# P-R461-1
python3 ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm \
    --a-arm OFF5    --b-arm OFF --key deliv
# P-R461-2
python3 ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm \
    --a-arm CONFORM --b-arm OFF --key deliv
```

| 附錄 B 寫的 | 附錄 C 改讀成 |
|---|---|
| `pooled_paired_ci.py … --stratum lcb3=…` 的 `verdict_pooled == "ON_WINS"` | `paired_ci.py --run …` 的 **`verdict == "ON_WINS"`** |

`ON_WINS` 的語意不變：**「a-arm 贏」，不是 ON 臂**。散文一律寫「OFF5 − OFF 的 CI 完全在 0 以上」。
`PRACTICAL_PP = 5.0`、`MIN_PAIRED = 60`、α、n、seed、worker、端點、bank、
§三 的窗口、§四 的 MDE 與預測區間——**一個數字都沒有動**。

## C.3 為什麼 `--key deliv` 在這裡是實質的、不是形式的

`deliv = accepted ∧ meets_demand`。`OFF`／`OFF5` 臂 `accepted` 恆真 ⇒ **P-R461-1 兩口徑恆等**。
`CONFORM` 會拒交，而 `gain_run.py:588` 拒交時回退到最後一份候選、`:1586` 無條件對它評分
⇒ `accepted=False ∧ meets_demand=True` **可達**：東西沒交出去，卻被舊口徑算成一次交付。
⇒ **P-R461-2 用舊口徑會高估 CONFORM，方向偏向本實驗想證的假說。**

## C.4 這兩條指令**已經原樣跑過**（R463 §一 C-1 新訂通則）

**R478 自記認證 blob sha**（判準 `DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md`）：
下面幾行記的是**認證當時**這幾支工具的 blob sha，由擋門優先讀取。
認證標題的文字若被改寫，`git log -S` 反推會定位到較晚的 commit 而**低報** STALE；
自記值不受標題改寫影響。兩者不一致時擋門會大聲叫（`cert_sha_mismatches`）。

- CERT-BLOB `ops/gain/replay/pooled_paired_ci.py` = `5179f45934ea98a83df308770f9193dd73ca872a`
- CERT-BLOB `ops/gain/replay/paired_ci.py` = `bb146ea0925151a4c9ed093a9f70abe0c860142c`


**通則：預註冊裡的收官指令，寫進判準檔之前必須先原樣跑一次**（可在別的 run 上跑）。
附錄 B 就是沒跑過才寫錯。本附錄在**已收官的** `runs/g_r447_conform_lcb2` 上驗過兩種形狀，
兩條 `rc=0`，且**逐字重現 R459 已發表的收官數字**：

```
CONFORM vs OFF  n=120  b=31 c=8   Δ=+19.17pp  CI[+8.80,+26.46]  p=0.0003  ON_WINS
OFF5    vs OFF  n=120  b=22 c=7   Δ=+12.50pp  CI[+3.12,+19.19]  p=0.0081  ON_WINS
```

⚠ **r447 上 `--key deliv` 與 `--key meets_demand` 同值**（該 run 的分歧格實測為空：
7 個拒交格全部 `meets_demand=False`）⇒ 這是**回歸對照**，**不是** `--key` 有效的證明。
有效性的證明是 R463 的合成夾具 T1 ＋ 具名突變體 M_KEY（`ops/gain/replay/r463_key_teeth_test.py`）。

## C.5 收官時要一起報的（不報＝隱瞞口徑）

1. 產物自己記的 `"key"` 欄位必須是 `"deliv"`（旗標預設是舊語意，忘了帶會安靜翻判決且 rc=0）。
2. `runs/g_r461_lcb3_three_arm` 的 CONFORM 臂 `accepted=False ∧ meets_demand=True` 的**格數**
   （＝ P-R463-3，事前預測 ≥1、基準率約 40–70%）。**0 格也要寫**——那代表兩口徑同值，
   要照實說「本 run 上這個修正沒有改變數字」，不准因此宣稱修正是多餘的。

---

# 附錄 D（round732 / R464 追加）：**P-R461-3 的收官指令從來沒有被寫下來**——補上，並照通則先跑過一次

**合法性前提**：與附錄 B／C 相同的自證見 `DECISION_20260904_R464_EQ5_BANK_FLAG_GAP.md` §〇
（含一次非預期讀取的誠實揭露）。**本輪對 `runs/g_r461_lcb3_three_arm` 沒有跑過任何分析工具。**
**§三／§四／附錄 B／附錄 C 原文一字未改，本附錄是加法式的。**

## D.1 缺口

§四 給了 P-R461-3 名字、MDE 與「事前就判 `UNRESOLVED`」，但**沒有寫用哪支工具、帶什麼旗標**。
這與附錄 C 抓到的 C-1 是同一型缺陷（預測有名字、沒有可執行的仲裁者）。

## D.2 收官指令（**已原樣跑過**，見 D.4）

```bash
python3 ops/gain/r447_eq5_offline.py \
    --run runs/g_r461_lcb3_three_arm --bank lcb3 \
    --json ops/gain/data/r461_eq5_offline_terminal.json
```

**⚠ `--bank lcb3` 不能忘。** `--seed`／`--n` 取自 run 自己的 `summary.json`（R458 修過），
但 **`bank` 沒有這條退路**：全庫 41 份 `summary.json` **沒有任何一份記 `bank`**（R464 實測），
旗標預設是 **`lcb2`**＝舊題庫。這正是 memory 鐵律那個形狀：
**旗標預設值是舊語意 ⇒ 忘了帶就安靜翻掉判決且 rc=0。**

## D.3 收官時要一起驗的三件（不驗＝隱瞞口徑）

1. **產物自己記的 `sampling` 必須是 `{"bank":"lcb3","seed":"g-r461-lcb3","n":189,"offset":0}`。**
   （與附錄 C.5 第 1 點同型：不要相信自己下的指令，要驗產物自己記的來源。）
2. **`verdict` 必須是 `RECONSTRUCTED` 才准讀任何數字。**
   ⚠ R464 實測：**BROKEN 時 `rule_rates` 仍會印出一整塊全是 0 的數字**
   （`n_processed=0, gate_deliv_correct=0, vote_deliv_correct=0`）。
   那些 0 **不是**「閘門 0 分、多數決 0 分」，是「一格都沒量到」。
   `paired_gate_vs_vote` 那時是 `null`（E11 生效，不吐 Δ）——**判 BROKEN 要看 `verdict`，不要看有沒有數字。**
3. **Δ 旁邊必須同時寫 `power.mde_at_n_pp` 與 `power.n_needed_for_5pp`**（R452 §五 W4）。
   §四 事前已把 P-R461-3 判成 `UNRESOLVED`＝**「沒量出來」而不是「沒有差異」**，
   收官不准把它讀成「等預算打不贏」。

## D.4 這條指令已經原樣跑過（R463 §一 C-1 新訂通則）

**R478 自記認證 blob sha**（判準 `DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md`）：
下面幾行記的是**認證當時**這幾支工具的 blob sha，由擋門優先讀取。
認證標題的文字若被改寫，`git log -S` 反推會定位到較晚的 commit 而**低報** STALE；
自記值不受標題改寫影響。兩者不一致時擋門會大聲叫（`cert_sha_mismatches`）。

- CERT-BLOB `ops/gain/r447_eq5_offline.py` = `52975b6ddeb9cdd33f8e6310eeb4468ca8bf33b9`


在**已收官的** `runs/g_r447_conform_lcb2` 上跑過**兩個方向**（R464，本輪實測）：

| 方向 | 指令 | 結果 |
|---|---|---|
| 正確 bank（回歸） | `--run runs/g_r447_conform_lcb2 --bank lcb2` | `rc=0`、`RECONSTRUCTED`，**逐字重現 R458 落盤的十個數字**：校準 54/54、gate 81／vote 76、b=14／c=9、Δ=+4.1667pp、rows 360、sha `cfed36ff71b871f0` |
| **錯的 bank**（陷阱） | `--run runs/g_r447_conform_lcb2 --bank lcb3` | `rc=0`、**`BROKEN`**、`paired_gate_vs_vote=null`、`broken` 列出 **120 條具名 `task_not_in_bank:<id>`**，且 `sampling.bank` 誠實記著 `"lcb3"` |

⇒ **給錯 bank 會大聲壞掉，不會安靜吐一個假的 Δ。** 這條擋門（`r447_eq5_offline.py:145`）
原本**不在 `selftest()` 的任何一條具名 `ck` 裡**，本附錄是它第一次被演練。
前提事實：`lcb2` 與 `lcb3` 的 `task_id` 集合**交集為 0**（R464 實測 120／189／0）
——若兩庫有交集，上面那個測試只是部分覆蓋。

## D.5 本附錄**沒有**動的東西

`PRACTICAL_PP`、`MIN_PAIRED`、α、n、seed、worker、端點、bank、§三 的窗口、
§四 的 MDE 與預測區間、P-R461-3 事前的 `UNRESOLVED` 判決——**一個數字都沒有動**。
也**沒有**改 `r447_eq5_offline.py` 一行（本輪只是跑它、驗它）。

---

# 附錄 E（round733 / R465 追加）：**§六.2 的收官義務也沒有可執行的仲裁者**——補上指令，並照通則先跑過一次

**合法性前提**：與附錄 B／C／D 相同的自證見 `DECISION_20260904_R465_R461_SEC6_GAUGE_ARBITER_GAP.md` §〇。
**§三／§四／附錄 A／B／C／D 原文一字未改，本附錄是加法式的。**
**`ops/gain/r447_gauge_capability.py` 本輪一行都沒改。**

## E.1 缺口

§六.2 寫死了一條收官報告義務——「看有幾題**任一臂通過過一次**……沒被示範的題數是
**『量具假象』的上界**……**這個數字要跟失敗率一起報**」——但**沒有寫出它的指令**。

附錄 B／C 補的是 P-R461-1／2，附錄 D 補的是 P-R461-3。**§六.2 沒有任何附錄覆蓋。**
⇒ 與 C-1／D.1 **同型缺陷的第三次復發**（預測／義務有名字，沒有可執行的仲裁者）。

這一次漏掉的份量特別重：§六.3 已事前承認 v3 的 probe 覆蓋率預期 **0/189**，
「參考解全過」那個方向**照字面不可執行**；§六.2 的能力下界是唯一的替代品。
它沒有仲裁者 ⇒ 收官時 SPEC 的雙向驗尺規則**兩個方向都會沒有可執行的證據**。

## E.2 收官指令（**已原樣跑過**，見 E.4）

```bash
python3 ops/gain/r447_gauge_capability.py runs/g_r461_lcb3_three_arm \
    --json runs/_analysis_r461/gauge_capability.json
```

工具的 `passed()`:89-92 是 `any(bool(r.get("meets_demand")) for r in rs)`，
**逐字就是 §六.2 的「任一臂通過過一次」**；要報的兩個數字是
`n_undemonstrated` 與 `pct_undemonstrated`（§六.2 的「上界」），
連同 `n_demonstrated` 與分母 `n_tasks_complete` 一起報。

⚠ 這支工具**沒有** `--bank`／`--seed`／`--n` 任何旗標（`main()`:228-241 只吃 `sys.argv[1]`
當 run 目錄）⇒ **R464 那型「旗標預設值是舊語意」的陷阱翻不了它**。這是它比附錄 D 那支安全的地方。

## E.3 收官時要一起驗的五件（不驗＝隱瞞口徑）

1. **`run_complete` 必須是 `true`（去 `summary.json` 讀，工具自己不看）。**
   **這支工具沒有任何完整性擋門**——實測（E.4 Y5）把已收官 run 的 rows 截成前 23 列餵給它，
   它吐 `rc=0`、`verdict=="OK"`、`n_tasks_complete=7`、`pct_undemonstrated=28.571`，
   **沒有任何警告、頂層也沒有 `run_complete` 鍵**。而那個 pct 會隨 run 跑完**單調往下飄**：

   | 截斷 | `n_tasks_complete` | `pct_undemonstrated` | `verdict` |
   |---|---|---|---|
   | 23 列 | 7 | **28.571** | OK |
   | 180 列 | 60 | **25.0** | OK |
   | 360 列（完整） | 120 | **21.667** | OK |

   ⇒ **跑到一半讀它，會拿到一個長得完全合理、卻偏高的「量具假象上界」。**
   這是第二型「安靜量不到」（量到的數量掉下來，卻不叫）。收官守則自己要擋。

2. **`n_tasks_complete == 189` 且 `rows_file_lines == 567`。** 對不上就照實寫差多少，不准四捨五入帶過。

3. **`n_tasks_partial_excluded` 要與逐臂 `infra_void` 對帳。**
   `gain_run.py:1583` 把 void 寫進 **`notes.jsonl`**，那一臂**不產生 row**
   ⇒ 該題變成 `len(rs)!=3` ⇒ **被 `complete` 靜靜排除、分母縮水**，
   而 §四 的 `UNSCANNED` 規則讀的是 `summary.json` 的 `infra_void`——**兩個不同的檔案**。
   恆等式（完整 run 上）：`n_tasks_partial_excluded == |{task_id : 任一臂 infra_void}|`。
   **校準過，有 witness、不是零例空綠燈**：

   | run | voided 題數（notes） | partial 題數（rows） | 相符 |
   |---|---|---|---|
   | `g_r443_gemma_lcb` | 4 | 4 | ✓ |
   | `g_r441_gemma_only_mbpp_b` | 12 | 12 | ✓ |
   | `g_r447_conform_lcb2`（零例） | 0 | 0 | ✓ |

   ⚠ 前兩個 witness 都是 `run_complete=false` 的 run ⇒ 它們驗到的是
   **「voided ⊆ partial」這個方向與機制**（voided 臂在 rows 裡確實缺席，兩個 run 都 True），
   **完整恆等式在完整 run 上還沒有被驗過**。照實寫。

4. **判 BROKEN 要看 `verdict`，不要看有沒有數字。**
   與附錄 D.3 第 2 點同型：`BROKEN_BC_MISMATCH`／`BROKEN_CONTRACT_DRIFT` 之下，
   `n_tasks_complete`／`n_demonstrated`／`pct_undemonstrated` **照樣印出一整塊看起來完全正確的數字**
   （實測：M5 突變體在真 r447 資料上吐 `BROKEN_BC_MISMATCH` 配 `120/94/26/21.667`）。
   只有 `verdict=="OK"` 才准引用那些數字。

5. **`pz1_raw_NOT_ARBITER`／`pz1_demonstrated_only_NOT_ARBITER` 不准當成 §三 C4 的失敗率引用。**
   它們自己標了 `NOT_ARBITER`，而且用的是 `_deliv`（交付口徑）不是 `meets_demand`（能力口徑）。
   C4 的仲裁者是 `ops/gain/r461_gate_verdict.py`，不是這支。

## E.4 這條指令已經原樣跑過（R463 §一 C-1 新訂通則）

**R478 自記認證 blob sha**（判準 `DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md`）：
下面幾行記的是**認證當時**這幾支工具的 blob sha，由擋門優先讀取。
認證標題的文字若被改寫，`git log -S` 反推會定位到較晚的 commit 而**低報** STALE；
自記值不受標題改寫影響。兩者不一致時擋門會大聲叫（`cert_sha_mismatches`）。

- CERT-BLOB `ops/gain/r447_gauge_capability.py` = `162d54d51e57d700b310fb9ddad1708a7fe0a1f0`


驗證 run＝`runs/g_r447_conform_lcb2`（已收官、同三臂 `OFF/CONFORM/OFF5`、同 LCB 家族、
同 worker `gemma-4-12b-it-qat`）＝ R461 的**結構孿生**。

- **Y1 `--selftest`**：`SELFTEST_PASS`、rc=0、**14 條 ck 全綠**（A–H ＋ M1／M2／M3／M4／M5／M6）。
- **Y2 真資料**：`rc=0`、`verdict=="OK"`、`n_tasks_complete=120`、`n_tasks_partial_excluded=0`、
  `n_demonstrated=94`、`n_undemonstrated=26`、`pct_undemonstrated=21.667`、
  `window_doubt_triggered=false`、`deliv_contract_drift=null`、`rows_file_lines=360`。
- **Y4 口徑一致**：`r447_gauge_capability._deliv` 與 `paired_ci.py` 的 `KEYS["deliv"]`
  用 `ast.get_source_segment` 逐字取出來**字串相同**
  （`bool(r.get("accepted")) and bool(r.get("meets_demand"))`），四種
  `(accepted, meets_demand)` 組合**逐格相同**。
  **雙向校準**：拿 `KEYS["meets_demand"]` 當負對照，它在 `accepted=False ∧ meets_demand=True`
  那一格分歧（＝附錄 C.3 指名的同一格）⇒ **這個比對方法有牙齒，不是「什麼都判相同」**。
  ⇒ §六.2 與 P-R461-1／2 口徑一致，**不需要**在收官時加口徑但書。
- **Y5 完整性**：見 E.3 第 1 點的表。

## E.5 誠實邊界

1. **`deliv_contract_drift()` 釘的是 `analyze_r447.py` 的 `_deliv`，而 `analyze_r447.py`
   不在 R461 的收官路徑上**（R461 用 `paired_ci.py --key deliv` 與 `r447_eq5_offline.py`）。
   ⇒ 那條契約擋門對 R461 而言是**在驗一個 R461 不會用到的檔案**。
   它不會誤放（Y4 已獨立證明兩支的口徑逐字相同），但它**不是**針對 R461 的保護。
   **本輪不改它**——改工具要另開判準。
2. 工具名字叫 `r447_*`，但它**與 run 無關**（不吃 bank／seed／n，只吃 run 目錄）⇒ 用在 R461 上合法。
3. E.3 第 3 點的恆等式只在兩個 **不完整** 的 run 上校準過（見該點的 ⚠）。
4. 本附錄**只補指令與收官守則，不改 §六.2 的語意，也不動 50% 的 `window_doubt` 門檻**。

## E.6 本附錄**沒有**動的東西

`ops/gain/r447_gauge_capability.py`（一行未改）、任何門檻／窗口／MDE／α／n／seed／worker／端點／bank、
`gain_run.py`、`analyze_paired.py`／`replay/paired_gates.py` 的 `--key` 缺口（R463 刻意留的，仍在）、
§三／§四／附錄 A／B／C／D 的正文。

---

# 附錄 F（round734 / R466 追加）：**§二／§六 的可證偽性普查**——兩條 evidence 級強制綠燈

**合法性前提**：判準見 `DECISION_20260904_R466_R461_SEC2_SEC6_FALSIFIABILITY_CENSUS.md`（`99ec6cb`，量測之前 commit）。
**§三／§四／附錄 A／B／C／D／E 原文一字未改，本附錄是加法式的。**
**`verify_lcb_bank.py`／`gain_run.py`／`r447_gauge_capability.py` 本輪一行都沒改。**

## F.1 為什麼補這一段

R462（`1c6452c`）只掃了 **§三／§四** 七筆。**§二／§六 從來沒被任何普查掃過**，
而收官會引用它們：§二的預測帳寫在附錄 A.4（3 HIT／1 MISS），
§六是量具效度**唯一**的替代證據來源。memory 鐵律：**普查自己的涵蓋範圍就是盲點。**

工具：`ops/gain/r466_r461_sec2_sec6_census.py`（selftest 16 條全綠，
M1／M2／M3／M4／M5／M6 六個突變體各自被指名捕獲）。輸出：`ops/gain/data/r466_census.json`。

## F.2 結果（`verdict=="OK"`，盲測 **5/5**）

| # | intent | 分類 | 關鍵數字 |
|---|---|---|---|
| S2-1 恰好 189 題 | evidence | `EVALUABLE` | 預測 189／實測 189；**同批次有兩筆被推翻**（medium／hard） |
| S2-2 與 v2 零交集 | evidence | **`FORCED_GREEN`** | v2／v3 來源檔集合不相交 ⇒ 交集 0；母體內反例＝0 |
| S2-3 日期範圍 | evidence | `EVALUABLE` | 實測 2023-05-07 → 2024-08-10（逐字相同） |
| S2-4 medium 152／hard 37 | evidence | `EVALUABLE` | 實測 medium **135**／hard **54**（＝A.4 已記的 MISS） |
| S6-1 probe 覆蓋率 0/189 | evidence | **`FORCED_GREEN`** | probe 檔 12 題**全在 v2 內**、v2∩v3=∅ ⇒ 恆為 0 |
| S6-2 能力下界 | evidence | `EVALUABLE` | 孿生 run：complete 120／demonstrated 94／undemonstrated 26（兩個方向都出現過） |
| S6-3 照實寫成偏離 | guard | `NOT_A_PREDICTION` | 報告義務，沒有真值 ⇒ 不進命中率 |

**雙向校準通過**（B5）：正對照「今天載入成功的 v3 恰有 189 列」判 `FORCED_GREEN`、
負對照「v3 medium＝135」判 `EVALUABLE` ⇒ 這個普查不是「什麼都判 FORCED」。

## F.3 兩條強制綠燈要怎麼引用（**這是本附錄的重點**）

1. **S2-2「與 v2 零交集」的 HIT 不帶資訊。** v3 的來源是 `test/test2/test3.jsonl`，
   與 v2 的來源檔**不相交** ⇒ 建不出交集。**不能拿它當「乾淨樣本外複製」的證據**——
   真正承重的是 §二「刻意不做成 309 題的超集」那個**設計決定**，不是這條預測的命中。
2. **S6-1「probe 覆蓋率預期 0/189」在任何情況下都不可能為假。**
   `verify_lcb_bank.py:36` 的 `PROBE_PATH` **寫死** `data/lcb_probe_solutions.json`，
   :160 的 `probe_coverage` 就是拿它算的，**不隨 `--version` 改**；那 12 題又全在 v2 裡。
   ⇒ 附錄 A 開頭那句「§六 預測……**實測命中**」**不算命中**，收官不得計入預測帳。
   （這是 round714 P-Z5b「強制綠燈被誤寫成 HIT」的**第三次復發**。）

### F.3-1 ⚠ 但**不要**把它讀成「v3 沒有量具驗證」——那是相反的錯

`gain_run.py`:181 有 `_default = (LCB_V3_PROBE_SOLUTIONS_PATH if bank == "lcb3" else LCB_PROBE_SOLUTIONS_PATH)`
⇒ **真正的 `--arms probe` 驗尺吃的是 v3 的手寫解檔**（`runs/g_r461_probe_lcb3` 在），
:1299 的 `n==0` 硬擋門也證明它不可能是 0。實測兩個檔**完全互補**：

| bank | `verify_lcb_bank` 印的覆蓋率 | 改用 `lcb_v3_probe_solutions.json` |
|---|---|---|
| v1 | 12 | 0 |
| v2 | 12 | 0 |
| **v3** | **0** | **12** |

⇒ **缺陷只在「報告工具」，不在「量具本身」。** v3 的真實 probe 覆蓋率是 **12/189**。
**收官引用覆蓋率時要寫 12/189，並註明 `verify_lcb_bank --version v3` 會印 0/189 是工具的路徑寫死。**

## F.4 附錄 A.4 那張預測帳要怎麼改讀（**不改 A.4 原文**）

A.4 記「3 HIT／1 MISS」。扣掉 S2-2 這條強制綠燈之後：
**帶資訊的是 2 HIT（總數 189、日期範圍）／1 MISS（難度分項）／1 不帶資訊（零交集）。**
加上 §六 那條被誤記的命中 ⇒ **R461 的預測帳整體要退一格**。
判準與門檻**一個都沒動**，只動「怎麼引用」。

## F.5 誠實邊界

1. S6-1 標的是**確認**（落筆前已讀 `verify_lcb_bank.py:36,160`），**不計入盲測命中率**；
   S6-2 同（落筆前已讀附錄 E.4 Y2）。**盲測 5/5 只含 S2-1／S2-2／S2-3／S2-4／S6-3。**
2. 「forced」的判定時點是**預測落筆當時**（判準 §二.1）：`LCB_BANK_V3_COUNT`
   在 `a3036573`（R461 判準 commit）**尚不存在**、今天存在 ⇒ S2-1 當時可證偽、今天恆真。
   兩個時點都印在 JSON 裡（`v3_pin_existed_at_prediction_time` / `..._today`）。
3. **本輪不修 `verify_lcb_bank.py`**（判準 §五.4）：改量具要另開判準，
   而且 v3 已經發射，改報告工具不會改變 R461 已經發生的事。**這個缺口留給下一輪。**
4. 本普查**只掃 §二／§六 七筆**。**還沒被任何普查掃過的是：附錄 A（除 A.4 的四列）、
   附錄 B／C／D／E 的收官守則本身。** 下一輪要補就從那裡。
5. 本輪**零偷看**：B3 擋門把任何含 `g_r461_lcb3_three_arm` 的讀檔路徑變成例外，
   連 selftest 的探針都指向該目錄下**不存在**的檔名（攔到＝RuntimeError、沒攔到＝FileNotFoundError），
   **主 run 的任何一個 byte 本輪都沒有進過記憶體**。

---

# 附錄 G（round748 / R477 追加）：**認證會過期**——引用 C／D／E 的數字之前先跑擋門

## G.1 缺口（R476 實測，本附錄不重證）

附錄 C／D／E 各自認證了一組數字（「這條收官指令已經跑過、結果如下」）。
R463 §一 C-1 的通則只約束「寫進判準之前要先跑一次」，**沒有任何機制在工具後來被改了時叫**。
R476 逐格重跑，9 格裡 3 格今天不一樣（E.4 Y1 的「14 條」今天是 19 條、E.3 兩格今天改吐
`BROKEN_ROW_ACCOUNTING` 且拒吐能力數字）⇒ **附錄原文的三句話今天為假，而沒有東西會提醒收官的人。**

## G.2 通則 C-1′（R477 補；**這一條是可執行的，不是散文**）

1. （C-1 原文，不動）預註冊裡的收官指令，寫進判準檔之前必須先原樣跑一次。
2. 🆕 **認證段落要記下被認證工具當時的 blob sha**（`git rev-parse HEAD:<tool>`）。
3. 🆕 **收官引用任何被認證的數字之前，必須先跑**：

```
python3 ops/gain/cert_drift_gate.py --json ops/gain/data/r477_cert_drift.json
```

   `rc=0` ⇒ 可以照附錄原文引用；`rc=1`（有 `CERT_STALE`）⇒ **那幾支工具要先重跑一次**
   （R476 那種逐格重跑）才可以引用；`rc=2` ⇒ 先分診，**不准當成乾淨**。

## G.3 今天（2026-09-05 01:5x UTC）它說什麼

```
verdict STALE_CERTS_PRESENT  rc=1  docs=138  cert_headings=6
counts={'CERT_FRESH': 2, 'CERT_STALE': 2, 'TRIAGED_NOT_A_CERT': 1}
  附錄C  cert=a6ecb9b1   ops/gain/replay/pooled_paired_ci.py   CERT_FRESH  (+0)
                         ops/gain/replay/paired_ci.py          CERT_STALE  (+1)
  附錄D  cert=87aec70d   ops/gain/r447_eq5_offline.py          CERT_FRESH  (+0)
  附錄E  cert=f5cf02db   ops/gain/r447_gauge_capability.py     CERT_STALE  (+3)
```

⇒ **收官引用 C.4 與 E.4／E.3 的數字之前要先重跑那兩支**；D.4 的數字（含 `cfed36ff71b871f0`）
blob 逐 byte 相同 ⇒ 可以照原文引用。

## G.4 ⚠ `CERT_STALE` 的意思（**不准誤讀**）

**`CERT_STALE` ＝「引用之前必須重跑」，不是「那個數字錯了」。**
反證就在手邊：`paired_ci.py` 判 `CERT_STALE`，但 R476 逐格重跑後 C.4 的
`+19.17pp`／`+12.50pp` **逐字重現**。本擋門只看 blob 有沒有動，**刻意過度警報**。
`CERT_FRESH` 才是強的一邊：blob 逐 byte 相同 ⇒ 同輸入必得同輸出。

## G.6（round749 / R478 追加）認證時刻改由附錄**自己記**，`-S` 反推降為交叉檢查

判準：`DECISION_20260905_R478_CERT_SELF_RECORDED_SHA.md`（`ddc5d69`，工具之前）。

G.2 通則 C-1′ 第 2 條要求「認證段落自己記 blob sha」——**現在記了**：附錄 C.4／D.4／E.4
各自多了 `CERT-BLOB` 行（共 4 行，見那三處）。擋門改成**自記優先**，`-S` 反推退成交叉檢查：

- 兩者不一致 ⇒ `cert_sha_mismatches` 非空 ⇒ 整份報告 `verdict=BROKEN`、`rc=2`（大聲叫），
  **同時該工具格的 `CERT_STALE` 留在原地看得見**。
- 自記值若不在該路徑的 blob 歷史裡（抄錯／編造）⇒ `BROKEN_CERT_SHA_NOT_IN_HISTORY`、`rc=2`。

補起來的洞是**低報**：認證標題的文字一旦被改寫，`-S<新字串>` 只定位得到改寫那一次，
認證時刻往後移，本該 STALE 的格子會變成 FRESH ＝ 無聲綠燈。實測（R478 §六 M9／M10）：
標題改寫下**舊行為 `CERT_STALE` 2→0、rc 1→0**，**新行為維持 2 並吐 2 筆 mismatch、rc=2**。

⚠ 今天 `cert_sha_mismatches = 0`，但**這是結構強制綠燈**（自記值是照今天的反推值抄的）
⇒ **不准**拿它當「沒有人改過標題」的證據；它的 `intent` 是 guard，牙齒由突變體證明。
G.3／G.4 的判決與誤讀警告**一個字都沒改**（今天仍是 `paired_ci.py` 與
`r447_gauge_capability.py` STALE、`pooled_paired_ci.py` 與 `r447_eq5_offline.py` FRESH）。

## G.5 本附錄**沒有**動的東西

`PRACTICAL_PP`、`MIN_PAIRED`、α、n、seed、worker、端點、bank、§三 的窗口、§四 的 MDE、
A.4 的預測帳、附錄 B／C／D／E／F 的任何一行——**一個數字都沒有動**，
本附錄只新增「引用之前先跑一次擋門」這個義務。

---

# 附錄 H（round750 / R479 追加）：**三條收官義務照釘死的指令量不到**——補可執行的指令，並照通則先跑過一次

判準：`DECISION_20260905_R479_R461_APPENDIX_OBLIGATION_CENSUS.md`（工具與量測之前的 commit `43b1650`）。
普查工具：`ops/gain/r479_r461_appendix_census.py`（自檢 19/19、`verdict=OK`、`live_run_reads=0`）。
**本附錄是加法式的：§三／§四／附錄 A–G 正文一字未改，任何門檻／窗口／MDE／α／n／seed／
worker／端點／bank 一個數字都沒有動。**

## H.1 缺口（R479 普查的結果）

10 條收官義務逐條分類：`EVALUABLE 8`／`FORCED_GREEN 1`／`UNRESOLVED 1`，
**3 條 `executable_as_pinned=False`**、**1 條 `premise_stale=True`**。

| id | 缺口 | 為什麼要緊 |
|---|---|---|
| **C5-1** | 附錄 C.2 釘死的兩條指令**沒有 `--json`**，而 `paired_ci.py` 只在 `args.json` 為真時才落盤，**stdout 六行 print 一個字都沒印 `key`** ⇒「產物自己記的 `key`」根本不存在 | 這條義務本來就是要擋「忘了帶 `--key deliv` ⇒ 安靜翻掉判決且 rc=0」，而它自己量不到 |
| **C5-2** | `accepted=False ∧ meets_demand=True` 的格數**不在 `paired_ci.py` 的產物裡**（`meets_demand` 只出現在巢狀處） | 附錄 C.3 說這一格是 `--key deliv` 實質與否的**唯一**證據 |
| **E3-3** | `infra_void` 頂層沒有；巢狀 `row_accounting.<臂>.infra_void` 有，但那是**逐臂整數**，給不出恆等式右邊要的**逐題集合**（E.3 正文自己寫著 void 落在 `notes.jsonl`） | 恆等式右邊沒有任何釘死的指令產得出來 |

另外一條**不是不可執行、是正文過期**：

- **E3-1 `premise_stale=True`**：E.3 第 1 點寫「這支工具**沒有任何完整性擋門**」並附 23／180／360 列
  都吐 `verdict=="OK"` 的表。R472 之後 `r447_gauge_capability.py` 已有
  `BROKEN_RUN_NOT_TERMINAL`／`BROKEN_NO_SUMMARY`／`BROKEN_ROW_ACCOUNTING` 三道擋門
  ⇒ **那張表今天重跑不出來**。方向是變安全（洞被補了），但**正文過期本身要記**
  ——`CERT_STALE` 的散文版。**E.3 第 1 點的正文本附錄不改**（改它要另開判準）；
  收官讀到那句話時要知道它描述的是 R472 之前的工具。

還有一條事前就標明、**不准當證據**的：

- **D3-3 `FORCED_GREEN`（intent=guard）**：`power` 與 `paired_gate_vs_vote` 在
  `r447_eq5_offline.reconstruct` 的**同一個 `if ok_to_report` / `else` 分支**被指派
  ⇒ 命題 `(pgv is None) == (power is None)` 窮舉兩支恆真、witness＝0。
  ⇒ 收官**不准**把「power 有印出來」當成「檢定力有被檢查過」的證據。

## H.2 補上的收官指令（**已原樣跑過**，見 H.3）

⚠ 三條都**只准在已收官的 run 上驗證**；本輪對 `runs/g_r461_lcb3_three_arm` **零讀取**
（普查工具內建擋門 B3，輸出 `live_run_reads=0`）。收官時把 run 目錄換成主 run 即可。

```bash
# H-1（補 C5-1）：把 C.2 的兩條指令各加一個 --json，key 才落得了盤
python3 ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm \
    --a-arm OFF5    --b-arm OFF --key deliv --json runs/_analysis_r461/paired_off5_off.json
python3 ops/gain/replay/paired_ci.py --run runs/g_r461_lcb3_three_arm \
    --a-arm CONFORM --b-arm OFF --key deliv --json runs/_analysis_r461/paired_conform_off.json
# 然後驗產物自己記的 key：
python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d['key']=='deliv',d['key']" \
    runs/_analysis_r461/paired_conform_off.json

# H-2（補 C5-2）：CONFORM 臂 accepted=False ∧ meets_demand=True 的格數
python3 -c "
import json
n=t=0
for l in open('runs/g_r461_lcb3_three_arm/rows.jsonl'):
    r=json.loads(l)
    if r.get('arm')!='CONFORM': continue
    t+=1
    if (not r.get('accepted')) and r.get('meets_demand'): n+=1
print('CONFORM rows=',t,' accepted=False and meets_demand=True 格數=',n)"

# H-3（補 E3-3）：|{task_id : 任一臂 infra_void}|，恆等式的右邊
python3 -c "
import json
s=set()
for l in open('runs/g_r461_lcb3_three_arm/notes.jsonl'):
    d=json.loads(l)
    if 'void' in json.dumps(d,ensure_ascii=False): s.add(d.get('task_id'))
print('voided_tasks=',len(s))"
```

## H.3 這三條指令已經原樣跑過（R463 §一 C-1 新訂通則）

**R478 自記認證 blob sha**（擋門優先讀取，`-S` 反推只當交叉檢查）：

- CERT-BLOB `ops/gain/replay/paired_ci.py` = `8c0f242096e92d50aa7f26f1d9b6dff917b87caa`
- CERT-BLOB `ops/gain/r479_r461_appendix_census.py` = `ec4b3393c186f1fd001f93a6df2352170d5b21f1`

驗證 run＝`runs/g_r447_conform_lcb2`（已收官的結構孿生）與 E.3 表列的兩個 void run。

**H-1 雙方向（2026-09-05，本輪實測）**

| 方向 | 指令 | 產物自己記的 `key` | `verdict` | `delta_pp` |
|---|---|---|---|---|
| 帶 `--key deliv` | `--a-arm CONFORM --b-arm OFF --key deliv --json …` | **`deliv`** | `ON_WINS` | **+19.1667** |
| **忘了帶**（陷阱） | `--a-arm CONFORM --b-arm OFF --json …` | **`meets_demand`** | `ON_WINS` | **+19.1667** |

⇒ **兩個口徑的數字在這個 run 上一模一樣，只有產物記的 `key` 不同。**
這正是 C.5-1 要擋的東西：**忘了帶旗標，畫面上看不出來**。
（附帶：`paired_ci.py` 今天是 `CERT_STALE`，本輪重跑後 C.4 的 CONFORM−OFF **+19.17pp 逐字重現**
——與 R476 的結論一致：`CERT_STALE` ＝「引用前必須重跑」，**不是**「那個數字錯了」。）

**H-2（孿生 run）**：`CONFORM rows=120`、`accepted=False ∧ meets_demand=True 格數 = 0`。
⇒ 孿生 run 上兩口徑同值（正好解釋上表兩列的 `delta_pp` 為什麼相同）。
**這也是 C.5-2「0 格也要寫」的第一個實例**：0 不代表 `--key deliv` 是多餘的，
只代表**這個 run 上**沒有踩到那一格。

**H-3（三個 run 對照，有 witness、不是零例空綠燈）**

| run | `voided_tasks`（notes） | E.3 第 3 點表列 | 相符 |
|---|---|---|---|
| `g_r447_conform_lcb2` | 0 | 0 | ✓ |
| `g_r443_gemma_lcb` | 4 | 4 | ✓ |
| `g_r441_gemma_only_mbpp_b` | 12 | 12 | ✓ |

⇒ H-3 的一行指令**逐個重現 E.3 第 3 點自己列的三個數字**。

## H.4 誠實邊界

1. **本附錄沒有讓 E3-3 變成 `EVALUABLE`。** 它補的是恆等式**右邊量得到**；
   `class` 仍是 `UNRESOLVED`，因為 witness 是不是 0 要等收官時的 `infra_void`。
   **收官必須對 E3-3 重判一次**（判準 §四.2）：若 `voided_tasks == 0` 且
   `n_tasks_partial_excluded == 0`，它退化成 `0 == 0` 的零 witness 恆等式
   ⇒ 當時要改記 `FORCED_GREEN`，**不准**讀成「對帳通過了」。
2. **R479 普查不是盲測**（判準 §〇.2）：落筆前已讀過三支工具的原始碼
   ⇒ **不准宣稱 `blind_hit_rate`**。事前預測 `class` 10/10、`premise_stale` 10/10 命中，
   `executable_as_pinned` **8/10——C5-2 與 E3-3 事前預測 `True`、實測 `False`，記 MISS**
   （方向是「比我預期的更不可執行」，不是對自己有利的方向）。
3. **普查工具自己踩過一次型二「安靜量不到」**：第一版的鍵抽取器只認
   `out = {...}` 與 `out["k"] = ...`，**漏掉 `out.update(ev)`** ⇒ 一度把
   `run_complete`／`n_tasks_complete` 報成「產物裡沒有」（假缺陷 3 個）。
   修好之後把這個 bug 原樣留成夾具 `M11`，並補了雙向校準擋門 `B7`
   （正：抓得到產物鍵；負：抓不到區域變數）——**B7 會自動抓到當時那個 bug**
   （M11 之下 `verdict=BROKEN_KEYSCAN_CALIBRATION`）。
4. `executable_as_pinned` 的判定規則只看**頂層產物鍵**；巢狀鍵另記
   `probe_keys_nested_only`，不參與判定（規則寫在判準 §二，量測後沒有改）。
5. 本附錄**沒有**驗 D.2 說的「全庫 41 份 `summary.json` 沒有任何一份記 `bank`」
   ——那要掃 run 目錄，會撞到 B3。照實寫：**本輪沒有重驗那條前提**。

## H.5 本附錄**沒有**動的東西

`PRACTICAL_PP`、`MIN_PAIRED`、α、n、seed、worker、端點、bank、§三 的窗口、§四 的 MDE
與預測區間、P-R461-3 事前的 `UNRESOLVED`、附錄 B 的判決名對應表、
附錄 C.2／D.2／E.2 的原指令、E.3 第 1 點的正文（只在 H.1 標註它過期）——**一個字都沒改**。
也沒有改 `paired_ci.py`／`r447_eq5_offline.py`／`r447_gauge_capability.py` 任何一行。

---

# 附錄 I（round751 / R480 追加）：**A.4／B.3／G 普查**——兩條命中不帶資訊、一條的分母沒釘死

判準：`DECISION_20260905_R480_R461_APPENDIX_A4_B3_G_CENSUS.md`（工具與量測之前的 commit `5ce4c2c`）。
普查工具：`ops/gain/r480_r461_appendix_bg_census.py`（自檢 14/14、`verdict=OK`、`live_reads=0`）。
**本附錄是加法式的：§二／§三／§四／附錄 A–H 正文一字未改，任何門檻／窗口／MDE／α／n／
seed／worker／端點／bank 一個數字都沒有動。**

## I.1 收官引用 A.4 時要一起寫的（兩條「命中不帶資訊」）

- **A4-2「與 v2 零交集」＝`FORCED_GREEN`。** 六組來源（v3 的 `test`／`test2`／`test3` 兩兩相配
  ＋各自對 v2 bank 的 120 個 id）**question_id 交集全為 0，witness=0**
  ⇒ 這個預測在挑定視窗的那一刻就不可能為假。
  **且 `union=309` 與它是同一個事件**：`union = 189 + 120 − overlap` 是恆等式，
  overlap=0 一旦成立 union 必為 309 ⇒ **A.4 那一列在預測帳上算一次，不是兩次**
  （同 r718 對 §六-2 的判法）。
- **A4-1「恰好 189 題」＝`EVALUABLE`（真的可能落空）。** `build_lcb_bank.py` **不是 1:1 轉換**：
  三個來源檔共 **612 筆**原始紀錄 → bank **189 題**，**丟掉 423 筆**（只收 functional＋
  medium/hard、單筆測資 repr 上限）。⇒ 這條是「R460 的計數器」與「正式 builder 的過濾器」
  兩份獨立實作的一致性檢查，**witness=423**，命中帶資訊。
  （⚠ R480 判準 §三事前預測它是 `FORCED_GREEN`，**這是 MISS，照 R-1 記在這裡**。）
- A4-3（日期 2023-05-07 → 2024-08-10）`EVALUABLE` 且今天逐字重現；順帶量到
  **未過濾的 612 筆原始紀錄日期範圍也是同兩個日期** ⇒ 那 423 筆的刪除沒有動到端點。
- A4-4（medium 135／hard 54）`EVALUABLE`；`135+72=207`／`54+48=102` 今天重算逐字相同。

## I.2 B.3 的兩個基準率：**沒有任何工具吐得出來**（`executable_as_pinned=False`）

`79.45%`／`14.09%`／`30.07%` 三個數字**只存在於散文裡**，repo 裡沒有任何 `.py` 會產生它們
（全庫 grep 只命中本檔第 231／234 行）⇒ 收官若要引用，必須有人重算。R480 已離線重算：

| 宣稱 | R480 重算 | 差 | 判（容差 ±0.5pp，判準 §二釘死） |
|---|---|---|---|
| B3-1 綠燈基準率 79.45% | **79.45%**（n=189、disc=19.17%、π=0.6087、exact McNemar） | 0.0004pp | 復現 |
| B3-2 數字級 14.09% | 14.0%（照原文「佔 0–100」） | 0.09pp | 復現（**但沒有一種讀法給得出 14.09**） |
| B3-2 判決級 30.07% | 30.0%（同上） | 0.07pp | 復現（同上） |

⚠ **`14.09`／`30.07` 的尾數今天解釋不出來**：連續讀法給 14.0／30.0、k/189 網格除以 190 給
14.21／30.0、除以 189 給 14.29／30.16 —— **三種讀法沒有一種同時吻合**。
差在容差內 ⇒ 判「復現」，**但收官引用時要寫 14.0／30.0 這個可重算的值**，
或標明尾數來源不明。（⚠ R480 判準 §三事前預測「至少一個復現不了」，**MISS，照 R-2 記**：
不是原文錯，是**我的重算模型與原文可能不同**，兩個都寫在這裡。）
矛盾帶 **16.0pp** 今天重算相同（(38−30)+(60−52)）。

## I.3 🔴 B.3-3 的三個計數過期，而且**分母沒有釘死**

正文：「掃過 29 個 run，15 個臂（分佈在 9 個 run）超過 20%，最高 `g_off60_20260824` OFF 60/60＝100%」。
R480 今天重掃（**具名排除還在跑的 `g_r461_lcb3_three_arm`**，`runs_excluded_live=1`）：

| 分母 | runs 掃到 | 臂 >20% | run 數 | 最高 |
|---|---|---|---|---|
| `tasks`（真的那個鍵） | 40 | **7** | **6** | `g_off60_20260824` OFF 60/60 = 100% |
| `n`／`processed`（第一版寫的） | 40 | 13 | 7 | 同上 |

⇒ **母體變大（29→40）但計數變小（15→7）** ⇒ 差異的主因**不是**「後來又多了 run」，
是**分母**。正文沒有寫它用哪個鍵，`summary.json` 的臂裡 `tasks` 才是題數；
用 `n`／`processed` 會有 **13 個臂根本解析不出分母**（R480 把它們記成 `unresolved_arms`，
不准安靜跳過——這正是 M6 夾具重演的型二「安靜量不到」）。

**但 B.3-3 的結論本身不受影響**：兩個分母下都有 witness（7>0、13>0），
最高那格 `g_off60_20260824` OFF **60/60＝100%** 兩邊逐字相同
⇒ **「這條 `infra_void>20%` 擋門是活的、要照跑」成立**。
收官引用時**寫 7／6／40（分母 `tasks`）並附這張敏感度表**，不要沿用 15／9／29。

## I.4 G 段：兩條可執行、一條正文過期、一條自承強制綠燈（自承是對的）

- **G2-3**（引用前先跑 `cert_drift_gate.py`）：今天原樣跑得起來，`rc=1`
  （`STALE_CERTS_PRESENT`）、`CERT_FRESH 3／CERT_STALE 2／TRIAGED_NOT_A_CERT 1`。
- **G3 `premise_stale=True`**：釘死區塊寫 `docs=138 cert_headings=6`、FRESH 2，
  今天是 **`docs=141 cert_headings=8`、FRESH 3**。⇒ 那個輸出區塊是快照，不是可重跑的宣稱。
  **但它導出的義務沒變**：今天 STALE 的仍是 `paired_ci.py` 與 `r447_gauge_capability.py`
  ⇒ 引用 C.4／E.3／E.4 之前仍要先重跑那兩支。
- **G4（`CERT_STALE` ≠ 數字錯了）＝`EVALUABLE` 且今天成立，有原始碼證據**：
  `cert_drift_gate.py` 全檔**沒有任何一處**讀被認證工具的輸出數字
  （逐字掃 `delta_pp`／`verdict ==`／`rerun` 皆 0 命中，19 處 `CERT_STALE` 全由 blob sha 比較決定）
  ⇒ 「只看 blob 有沒有動、刻意過度警報」是結構事實，不是修辭。
- **G6 `FORCED_GREEN`（`intent=guard`，原文已自承）**：7 行 `CERT-BLOB` 的自記值是照當天的
  反推值抄的 ⇒ `cert_sha_mismatches=0` witness 恆為 0。**自承標得對**，收官照 G.6 原文引用即可
  ——`intent=guard` 的強制綠燈是設計如此，不是缺陷（r718 規則）。

## I.5 誠實邊界

1. **本輪不是盲測**（判準 §〇.2 事前寫明）：落筆前已讀過 A.4／B.3／G 與 §二／§三 原文
   ⇒ **不准宣稱 `blind_hit_rate`**。事前預測命中 `class 10/11`／`exec 11/11`／`stale 11/11`／
   `repro 1/2`，**兩個 MISS 都寫在 I.1 與 I.2**。
2. **容差 ±0.5pp 在真資料上沒有被行使**：兩條的差都 ≤0.09pp ⇒ `reproducible=True` 逼近
   強制綠燈。牙齒由夾具 **M7**（把宣稱值 +10pp ⇒ 兩條都要翻 `False`）證明，不是由今天的資料證明。
3. **A4-2 的 witness 母體只有 6 組**（v3 三個視窗兩兩相配 ＋ 各自對 v2 bank）：
   v2 的三個**原始**視窗（`lcb_test4/5/6.jsonl`）不在這台磁碟上，只能拿 v2 bank 的 120 個 id 代替
   ⇒ 「v2 被過濾掉的那些題會不會與 v3 撞號」**沒有量到**。
4. **主 run `g_r461_lcb3_three_arm` 本輪零分析**（G-LIVE 擋門，`live_reads=0`，M1 夾具證明它有牙齒）。
5. 本附錄**沒有**改 A.4／B.3／G 的任何一行原文，也沒有改任何門檻。

## I.6 還沒被普查的是誰（r718 規則，交棒必寫）

R461 的 §二／§三／§四／§六（R462／R466）、附錄 A.4／B.3／C.5／D.3／E.3／G（R479／R480）
**都掃過了**。**沒掃過的剩**：附錄 **B.1／B.2**（詞彙修正本身）、**C.1–C.4**、**D.1／D.2／D.4**、
**E.1／E.2／E.4**、**F**、**H.2／H.3** 的內文宣稱——其中 **C.4／D.4／E.4／H.3 是認證段落**，
已由 `cert_drift_gate.py`（附錄 G）以 blob sha 覆蓋，優先度低於「收官會直接引用」的那些。

---

# 附錄 J（round764 / R492 追加）：**§四 的三個合取項只帶兩份資訊**——`verdict` 那一項與 `p<0.05` 是同一件事

判準：`DECISION_20260905_R492_R461_CLOSING_CONJUNCT_INFORMATIVENESS.md`（量測前單獨 commit `44bf931`）。
**本附錄是加法式的：§四、附錄 B／C 的原文一個字都沒改，門檻／MDE／預測區間／α／n／seed／worker／端點／bank 一個數字都沒動。**

## J.1 缺口

附錄 B 修好了「判決名沒有仲裁者」，附錄 C 修好了「指令跑不起來」，附錄 H 補上了遺漏的收官指令。
**但從來沒有人問過**：`P-R461-1 = A1 ∧ A2 ∧ A3` 這三個合取項，**是不是三份獨立的證據**？
memory 鐵律「合取判準可能從來沒被評估過」與「兩條預測可能在數同一個事件」撞在一起，
而這是**收官前最後一次**能在不看資料的情況下問它的機會。

## J.2 結果（`verdict=="CENSUS_OK"`，`blockers=[]`，`live_reads=0`）

窮舉 `n=189`、`b+c<=189` 的 **18145** 個格，每格都呼叫 `paired_ci.py` 自己的 `diff_ci()`／`verdict()`：

```
P-R461-1   A1_delta_in_3_20     EVALUABLE          others_true=7279  witness b=38 c=0 Δ=20.106pp p=0.00000 v=ON_WINS
P-R461-1   A2_p_lt_0.05         FORCED_BY_OTHERS   others_true=1427
P-R461-1   A3_verdict_ON_WINS   FORCED_BY_OTHERS   others_true=1427
P-R461-2   B1_delta_in_8_28     EVALUABLE          others_true=7279  witness b=6  c=0 Δ=3.175pp  p=0.03125 v=ON_WINS
P-R461-2   B2_p_lt_0.05         FORCED_BY_OTHERS   others_true=2435
P-R461-2   B3_verdict_ON_WINS   FORCED_BY_OTHERS   others_true=2435
P-R461-3   （具名排除）          UNSCANNED_DIFFERENT_EMITTER
calibration  C_POS=FORCED_BY_OTHERS   C_NEG=EVALUABLE
```

**獨立交叉驗證**（另寫一段直接列表，不走分類器）：在全部 18145 格上

```
b>c ∧ p<0.05 的格數 7279，其中 verdict != "ON_WINS" 的： 0
verdict == "ON_WINS" 但 p >= 0.05 的格數：                0
```

⇒ **`verdict=="ON_WINS"` ⟺ `p<0.05 ∧ b>c`，兩個方向各零反例。**
機制：`ON_WINS` 的條件是 `lo_pp>0`＝Clopper-Pearson 下界越過 π=0.5，
而 `exact_mcnemar_p` 是同一個對稱二項的雙尾精確檢定 ⇒ **CP 區間反演與該檢定同界**。
補充掃描 `n ∈ {60, 100}` 分類**完全相同**（不是仲裁者，只說明結論不靠 n=189 這一格）。

## J.3 🔴 收官必須照這樣寫（本附錄的重點）

1. **P-R461-1 由 `A1`（Δ 區間）與 `A2`（p<0.05）單獨承重。`A3` 不帶額外資訊。**
   P-R461-2 同理，由 `B1` 與 `B2` 承重。
   ⇒ **不准**把「三個合取項全中」寫成「三份獨立證據都支持」。那是把同一件事數兩次。
2. **⚠ 但這不代表附錄 B／C 白做了——那是相反的誤讀。** 附錄 B 之前，`A3` 寫的是
   `OFF5_WINS`／`CONFORM_WINS`，**全庫沒有任何工具吐得出來**（B.1 實測 `emitters=[]`）
   ⇒ 整個合取式**照字面永遠判不出真假**。B.2／C.2 把它從「不可評估」修成「可評估但冗餘」，
   **合取式作為整體的可評估性是被那兩個附錄救回來的**。兩件事都要寫。
3. **`FORCED_BY_OTHERS` ≠ 有缺陷**（r718 規則）：`A3` 的 `intent` 是把判決接到有 emitter 的
   詞彙表上，不是提供第三份證據。要警告的只有「收官把它當獨立佐證」這一種讀法。
4. 這**不會**改變 P-R461-1／2 的任何門檻或判決結果——`A3` 冗餘，去掉它答案一樣。

## J.4 誠實邊界

1. **零模型呼叫；`live_reads=0`，本輪沒有讀主 run 的任何檔**（G-LIVE 硬擋門，突變體 M3 證明
   拿掉就讀得到）⇒ P-R461-1／2 的**盲測未被破壞**。
2. **本輪不是對「預測會不會命中」下判斷**，是對「合取項帶不帶資訊」下判斷。兩者不同。
3. **掃描範圍是 `n >= 60`。** `n < MIN_PAIRED=60` 時 `paired_ci.py` 在判決前就走 `BROKEN`
   分支，那條路徑**本輪沒有掃**（真實 run 若 void 率高到配對數 <60 就會走它）。
4. **新增可調參數 1 個**：`MIN_STATES=10000`（判準 §六 P-6 的「第三型安靜量不到」擋門），照實寫、沒假裝是零。
5. **P-R461-3 沒有被掃**（emitter 不同，是 `r447_eq5_offline.py`）⇒ 記 `UNSCANNED_DIFFERENT_EMITTER`，
   **不是綠燈**。它的綠燈基準率 79.45% 見附錄 B.3-1，本輪未重算。
6. 突變體 M2／M3／M4 走檔內 `R492_MUTANT` 旗標 ⇒ 照 r473 的通則，**它們答不了
   「把正式那行整段刪掉會不會紅」**。只有 M1 是真的原始碼突變（另存突變檔、驗 `old in src`）。

## J.5 本附錄**沒有**動的東西

§四 表格、附錄 B.2／B.3／B.4、附錄 C.2／C.3、附錄 D／E／F／G／H／I 的任何一行原文；
`paired_ci.py`／`gain_run.py` 一個 byte；任何門檻、MDE、預測區間、α、n、seed、worker、端點、bank。

## J.6 還沒被普查的是誰（r718 規則，交棒必寫）

附錄 **B.1／B.2 的內文宣稱**（本附錄只用了 B.1 的實測結果，沒有重驗它）、**C.1／C.3**、
**D.1／D.2**、**E.1／E.2**、**F**、**H.2**；認證段落 **C.4／D.4／E.4／H.3** 由 `cert_drift_gate.py` 覆蓋。
**R486／R487／R487B／R488／R489／R490 六份仍然沒有被普查掃過**（R492 §〇.4 具名保留）。
