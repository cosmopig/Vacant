# R482 預註冊：把 R481 §3 的缺陷類別（夾具寫死語料事實 ⇒ 安靜衰減）掃到其他量具

**寫於量測之前。** 本檔 commit 之後才寫工具、才跑census。
輪次：round753（2026-09-05 UTC 02:50 起）。模型：Opus 5。

## 一、要答的問題

R481 在 `cert_drift_gate.py` 找到一個**真的、非合成的**缺陷：
`B_realdata_positive_control_stale` 寫死 `pos == ["CERT_STALE"]`，隱含「只有一個附錄引用
`paired_ci.py`」。R478 加了附錄 H（一份**與這條斷言的意圖無關**的新文件）之後，該格
安靜變成**永遠紅**——不是產品壞掉，是夾具衰減。

memory 的通則：「修好一支工具的坑之後要 grep 其他工具有沒有同一份」。
**問題：`ops/gain/*.py` 裡其他 32 支帶 `--selftest` 的量具，有沒有同一份？**

## 二、判別量（不是 grep 字面，是機制導出的）

字面 grep（`== ["`）抓不到這個類別：絕大多數 `== [...]` 的觀測側是**同一個函式裡造出來的
夾具**，不會衰減。真正的判別量是「**這條斷言的真假，取決於測試檔以外會長大的語料**」。

⇒ 用**擾動**量它，不用語法猜它：

**語料增長擾動（corpus-growth perturbation）**＝往量具會掃的語料裡加入一個
**對任何量具的宣稱意圖都不帶訊號**的新項目，然後看 selftest 的判決有沒有翻。

這是「植入缺陷測試」的**反方向**：植入缺陷要求綠→紅；語料增長要求**綠→綠**。

三個擾動（每個都是「那種語料的一個新成員、且不帶訊號」）：

| 代號 | 加什麼 | 為什麼算「不帶訊號」 |
|---|---|---|
| `P_MD` | root 一份 `DECISION_R482_BENIGN_PROBE_DO_NOT_COMMIT.md`，內文只有散文 | 沒有認證標題（`原樣跑過`）、沒有 run 名、沒有 `P-` 預測行 |
| `P_TEST` | `tests/test_r482_benign_probe_DO_NOT_COMMIT.py`，一個 `def test_x(): assert True` | 不 import 任何產品碼、沒有承重牆標記 |
| `P_TOOL` | `ops/gain/r482_benign_probe_DO_NOT_COMMIT.py`，一個 `print` | 沒有 `--selftest`、沒有 `PRED`、沒有 `MUTANT` |

三個檔案**都不 commit**，跑完 `finally` 刪除；名字自帶 `DO_NOT_COMMIT`。

## 三、分類規則（寫死在量測之前）

每支工具跑 **clean 兩次**（分辨不決定性）＋ 每個擾動各一次，只看 `rc`：

- `NONDETERMINISTIC`：兩次 clean 的 rc 不同 ⇒ 該工具**不進**後面的分類（單獨列名）。
- `BROKEN`：任一次 timeout（90s）或 rc 不在 {0,1,2,3} ⇒ 單獨列名，不算 INSENSITIVE。
- `DECAY_PRONE`：clean rc==0，某擾動下 rc!=0 ⇒ **綠→紅**，就是 R481 那一類。
- `MASKING`：clean rc!=0，某擾動下 rc==0 ⇒ **紅→綠**，比 DECAY_PRONE 更糟。
- `SENSITIVE_OTHER`：rc 變了但不是上兩種（例：1→2）。
- `INSENSITIVE`：三個擾動下 rc 與 clean 完全相同。

⚠ **clean rc!=0 的工具本身就是既有紅燈**，要單獨報數（`clean_red`），
不准混進「這個類別不存在」的結論裡。

## 四、量具的牙齒（雙向合成對照，量測之前就寫好）

- **正對照** `_r482_pos_control.py`：selftest 斷言 `len(glob("DECISION_*.md")) == <clean 當下的數>`
  ——R481 缺陷的忠實合成複製（寫死語料基數）。**必須被判 `DECAY_PRONE`**，否則整個 census
  是 `BASELINE_BROKEN`。
- **負對照** `_r482_neg_control.py`：selftest 斷言的是**關係式**（「掃到的每一份文件都出現在輸出裡」），
  同樣讀真語料、同樣會被擾動改變輸入，但**必須被判 `INSENSITIVE`**。
  （只有正對照時，「什麼都判 DECAY_PRONE」也會全綠——這是 r718 的雙向校準規則。）
- 兩個對照都是合成的 ⇒ **牙齒由合成證明，普遍性由真資料證明**，兩件事分開寫。

## 五、預測（落筆時未知，`intent` 先標好）

| 代號 | 預測 | intent |
|---|---|---|
| P-1 | 正對照被判 `DECAY_PRONE`、負對照被判 `INSENSITIVE` | guard（牙齒） |
| P-2 | 真工具裡 **≥1 支**被判 `DECAY_PRONE` 或 `MASKING` | **evidence** |
| P-3 | `P_TEST` 是最會咬的擾動（memory：突變量具曾寫死期望收集數） | evidence |
| P-4 | 多數（>50%）真工具是 `INSENSITIVE` | evidence |
| P-5 | `tools_scanned >= 30` | guard（第三型「掃到 0 個目標」） |
| P-6 | 沒有工具被判 `NONDETERMINISTIC` | evidence（若有，多半是它讀了活著的 run） |

## 六、推翻條件（觸發就照實寫，不准當場補判準去修）

1. **P-2＝0**（真工具一支都沒咬）⇒ 收官只准寫「**今天這 32 支上沒有這個類別**」，
   **不准**寫「已證明其他量具沒有這個缺陷」——擾動只有三種，語料還有別種（`runs/`、題庫）。
2. 正對照沒被判 DECAY_PRONE ⇒ `BASELINE_BROKEN`，本輪所有數字作廢。
3. 負對照被判 DECAY_PRONE ⇒ 判別量太鬆（把「輸入變了」當成「衰減」），數字作廢。
4. `NONDETERMINISTIC` 出現 ⇒ 該工具的 clean 判決本身不可信，**不准**因為它在擾動下翻了
   就記成 DECAY_PRONE。

## 七、具名排除（不是安靜跳過）

- **`runs/` 語料不做擾動**：造一個假 run 目錄有兩個代價——後輪可能誤認它是真 run；
  分析工具在半殘 run 上 crash 是 `BROKEN` 不是衰減。⇒ 這一整類語料**本輪沒量**。
- **題庫（`lcb3`／MBPP+）不做擾動**：同上，且會動到實驗條件。
- **本工具自己**（`r482_corpus_sensitivity_census.py`）排除在受測清單外（會遞迴）。
- **活著的 run `runs/g_r461_lcb3_three_arm` 本輪不讀**（G-LIVE）：本工具不碰它；
  但**受測工具的 selftest 若自己去讀它，那不在我的控制內**，會以 `NONDETERMINISTIC` 現形。
- `~/vacant/GAIN_STATE.md` 在 repo 之外，不是語料的一部分。

## 八、非盲聲明

落筆前我讀過：`GAIN_STATE.md` round752 段（R481 §3 的描述）、
`grep -n '== \[' ops/gain/*.py tests/*.py` 的輸出（60 行）、
四支 selftest 的執行時間。**擾動一次都還沒跑過**，P-1..P-6 落筆時未知。
