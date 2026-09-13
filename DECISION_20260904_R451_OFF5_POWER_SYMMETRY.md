# R451：CONFORM vs OFF5 的 UNINFORMATIVE 目前**沒有** MDE／N₈₀ 陪它落地——收官前補上

（2026-09-04 round712，Opus 5。**本文件在改碼與量測之前寫定。**
對象：`runs/g_r447_conform_lcb2`（發射授權在 `DECISION_20260904_R440Z_LCB2_PREREG.md`）。
本文件**不新開 run、不動 r447 的任何判準、不動任何門檻或窗口**，
只在 `analyze_r447.py` 補一個**新增欄位**，並補一條看得見它的植入缺陷測試。）

## 一、要解的問題（round712 開場查到的具體缺口）

`analyze_r447.py` 的檢定力區塊只算了一半：

```python
if p2 is not None and p2["n_common"]:
    out["power_conform_vs_off"] = {...}      # CONFORM vs OFF   有
#   out["power_conform_vs_off5"]  ← 不存在
```

期中實測（rows=227）：

```
verdict_four_cell_conform_vs_off5 = "UNINFORMATIVE"
power_conform_vs_off5             = null      ← 沒有這個鍵
```

**這正是 r678／R670 已經踩過的那個坑的鏡像。** 記憶鐵律寫得很清楚：

> UNRESOLVED 要分「沒量出來」與「沒有差異」：收官寫 CI 的同時必須寫事前投影的
> MDE／N₈₀，否則下輪會當成「打不贏」引用。

`UNINFORMATIVE` 是 UNRESOLVED 家族裡**最寬**的那一格（區間同時越過 0 與兩側實用線）。
它最需要 MDE 陪著，偏偏它是三個比較裡唯一沒有 MDE 的。若收官輪照現況寫，
`CONFORM vs OFF5 UNINFORMATIVE` 會裸著落地，下一輪引用成「CONFORM 打不贏 OFF5」
——而真正的事實可能只是「n=120 分不出來」（P-Z3 的事前預測本來就是這句）。

## 二、改什麼（**加法式**，先寫死邊界）

1. `analyze()` 新增鍵 `power_conform_vs_off5`，用**與 OFF 那格同一組函式**
   （`mde_at_n` / `n_needed`）、餵 `p3`（CONFORM vs OFF5 的配對結果）。
2. `power_conform_vs_off5` 加進 `TRIPWIRE_FORBIDDEN`（它是 b/c 導出的比率資訊，
   期中監看輪不准看見）。白名單本來就擋得住，這是第二道，且讓 O 條有東西可比。
3. 新增突變體 `M11_power_off5_uses_off_pair` 與指名它的自檢條。

**不准做的（違反就是本文件被推翻）**：
- 不改任何既有欄位的值、名稱、口徑（含 `power_conform_vs_off`）。
- 不改任何窗口、門檻、推翻條件、`pz*_holds` 的定義。
- 不改 `_fixture` 既有四個參數的預設值（新參數必須有「維持原行為」的預設）。

## 三、為什麼這條測試需要新夾具（結構性理由，不是為了好看）

現行 `_fixture` 裡 **OFF5 的交付是從 OFF 抄來的**：

```python
rows.append(_r("OFF",  t, deliv=od, calls=1))
rows.append(_r("OFF5", t, deliv=od, calls=5))     # ← 同一個 od
```

⇒ 乾淨夾具上 `paired_conform_vs_off` 與 `paired_conform_vs_off5` 的 b/c **恆等**。
⇒ 最像的那個 bug——**新區塊複製貼上時餵成 `p2`**——在這個夾具上
**結構上不可能被任何一條看見**（兩邊算出來的數字一模一樣）。

這就是 r695／r699 那條教訓的同型：夾具若把 B 從 A 導出，「檢查 A 與 B 一致」
的擋門結構上沒有夾具看得見。所以本輪必須先讓 OFF5 與 OFF 在夾具上**分岔**，
新測試才有牙齒。新增參數 `o5_flip_tail=k`：把「兩臂都錯」尾段的 k 題翻成
OFF5 交付成功，預設 `0` ＝ 完全維持現行行為。

## 四、判準（**在跑之前寫死**，三條全中才算這輪做成）

- **A（加法性）**：對同一份凍結的 `rows.jsonl` 快照（`/dev/shm/r712/snap`，
  229 行、sha16 `39d3b5dc50a6ba44`），改動前後的輸出中
  **既有 28 個鍵的值逐一相同**，差異**恰好只有** `power_conform_vs_off5` 一個新鍵。
  比對用 `git show HEAD:<path>` 取改動前版本（⛔ 不准 `git stash`）。
- **B（有牙齒）**：`M11_power_off5_uses_off_pair` 讓 selftest 失敗，
  **且**失敗標籤裡出現指名的那一條（不是「有東西紅了」，不是 crash）。
  對照組：乾淨 baseline 那一條必須是 ok。
- **C（不回歸）**：`r447_mutation_check.py` 原本 12 個突變體仍全部 `:Y`，
  `--selftest` 仍 PASS，四支例行尺輸出不變。

## 五、推翻條件（觸發就照實寫，不准當場補判準去修）

1. 若 A 對不上——出現任何既有鍵的值改變——**回退這個改動**，
   在 STATE 寫「加法式宣稱不成立」，不要靠調整比對方式讓它變綠。
2. 若 B 做不到有牙齒（M11 只能靠 crash 或靠沒指名的條抓到），
   照實記 `M11:N`，不要把判準降級成 `rc≠0`。
3. 若補上之後 `power_conform_vs_off5` 的 `n_needed_for_5pp` 大於 LCB2 題庫規模，
   那是**結論**不是失敗：照實寫「這個比較在本題庫上不可能有解析度」，
   而且**不准**因此去放寬 P-Z3 的窗口或改寫 UNINFORMATIVE 的措辭。

## 六、這份文件不做的事

不對 r447 下任何收官判斷。r447 未 terminal（本輪 ETA ~16:1x UTC），
收官仍歸 fable 稽核輪，仲裁者仍是 R440Z §三／§六 與 R450 §四，本文件不參與仲裁。
