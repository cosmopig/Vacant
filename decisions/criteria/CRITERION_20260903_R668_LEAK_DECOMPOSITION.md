# R668 判準：P-C3 後半（`leaked` 明顯低於 OFF5）的結算算術——**量測前寫死**

（2026-09-03 UTC 20:57，Opus 5，round668。r444 仍在跑（131/179 每臂），本輪不碰它。
判準先 commit 才碰數字；碰的是 `/dev/shm` 的唯讀快照，不是 live 檔。）

## 〇 污染揭露（先寫，因為它決定哪幾條能判 PASS/FAIL）

我在開場讀 `GAIN_STATE.md` 時已看過 round667 的 20:49 中途快照，其中包含
`leak` 欄（OFF5=36／CONFORM=25／OFF=37）、`refus`=7、`md&!acc`=0。
**因此凡是由這四個數字可推導的預測，一律降級成「只報數字、不判 PASS/FAIL」**
（沿用 round667 §〇 的緩解方式）。未被污染的只有「最後 54 題的增量」與
「尺有沒有牙齒」這兩類，那兩類才允許判 PASS/FAIL。

## 一、本輪要解的問題

R440R 的 **P-C3** 有兩半：拒交率 3–10%（有帶、可判），以及
**「`leaked` 明顯低於 OFF5（E1 的 OFF5 是 47）」——沒有門檻、也沒有指定算法。**
round666 問過 P-C4 驗不驗得起來、round667 釘死了 P-C1 的算術；P-C3 後半是
**最後一條還沒釘的主張**，而它偏偏是「機制買到了什麼」的那一條。

## 二、非平凡的碼側事實（讀原始碼確認，不是猜）

| # | 事實 | 位置 |
|---|---|---|
| G1 | `leaked = n_acc - n_acc_ok`＝**逐題**計數（不是逐候選）⇒ **不會**被 calls/task 的 5:1.46 差距直接放大 | `gain_run.py:1280` |
| G2 | `n_acc` 只在 `accepted` 為真時 +1；OFF/OFF5 的 `accepted` 恆為 True（F1，round667）⇒ 這兩臂 `leaked ≡ measured − 正確交付數`＝**答錯題數** | `gain_run.py:1371-1373` |
| G3 | CONFORM 拒交⇒`accepted=False`⇒該題**不進** `n_acc` ⇒ **每拒交一題，`leaked` 至多少 1、且在該題離線候選為錯時剛好少 1** | `gain_run.py:517-521` |
| G4 | `InfraVoid` 走 `continue`、**不寫 rows 列** ⇒ 逐列 `rows` 數 ≡ `measured`，三臂 measured 可不等（void 不對稱） | `gain_run.py:1330-1336` |

⇒ **恆等式**：`leaked = measured − refused − deliv`（deliv＝accepted∧meets_demand）。
兩臂相減：

```
leaked(OFF5) − leaked(CONFORM)
  = [refused(CONFORM) − refused(OFF5)]        ← 拒交驅動（OFF5 恆為 0，G2）
  + [deliv(CONFORM) − deliv(OFF5)]            ← 準確率驅動（＝P-C1 的分子差）
  + [measured(OFF5) − measured(CONFORM)]      ← void 不對稱（G4；不是機制）
```

**這代表 P-C3 後半不是一條獨立主張**：它是 P-C1 的分子差再加上拒交數。
「leaked 比較低」可以完全由「交得比較少」買到，而那對使用者是另一種
「需求≠產出」。所以照字面判 PASS 會把兩件事講成一件事。

## 三、P-C3 後半的結算規則（**先寫死，收官照這個跑**）

收官時 **必須同時報三個數字**，缺一不可：

1. **(a) 字面**：`leaked(CONFORM)` 與 `leaked(OFF5)` 的原始計數。
   R440R 寫的是這個 ⇒ **字面判準＝`leaked(CONFORM) < leaked(OFF5)` 才算方向對**。
   「**明顯**」R440R 沒給門檻、而我已看過中途值 ⇒ **只報數字，不判「明顯」**。
2. **(b) 分解**：§二 的三項各佔多少（拒交驅動／準確率驅動／void 不對稱）。
   若 **拒交驅動 ≥ 50%**，收官文字**必須**寫成
   「CONFORM 漏得少，主要是因為它交得少」，不准只寫「漏得少」。
3. **(c) 等覆蓋率反事實**：`forced_leak(CONFORM) = leaked + (refused − md∧¬acc)`
   ＝**若強迫它把拒交題也交出去**會漏幾題。這是與 OFF5 同覆蓋率的比較。
   `forced_leak < leaked(OFF5)` 才是「閘門選得比較準」的證據。

**這三條不新增旋鈕**：全部是既有欄位的算術，沒有任何可調參數。

## 四、事前預測

| # | 預測 | 可否判 PASS/FAIL |
|---|---|---|
| P-R668-1 | §二 恆等式 `leaked = measured − refused − deliv` 在三臂**逐位成立**（誤差 0） | ✔ 可判（結構，非污染） |
| P-R668-2 | 三項分解的和 **逐位等於** `leaked(OFF5) − leaked(CONFORM)`；且 void 項＝0（三臂 void 至今皆 0） | ✔ 可判 |
| P-R668-3 | 拒交驅動佔 Δleaked 的 **≥50%** | ✘ 已污染（7/11＝63.6% 可由已看過的數推出）⇒ 只報數字 |
| P-R668-4 | **最後 54 題**裡，CONFORM 出現 `meets_demand ∧ ¬accepted` 的題數 = **0**（機制根據：拒交＝沒有任何候選過可見驗收，而可見⊂隱藏 ⇒ 過不了可見幾乎必然過不了隱藏） | ✔ 可判（增量未被污染）。**若 >0**，round667 的「P-C1 對 metric 選擇不敏感」當場失效，收官要改寫 |
| P-R668-5 | `forced_leak(CONFORM) < leaked(OFF5)`（方向仍對，但差距縮小） | ✘ 部分污染（快照可推出 32<36）⇒ 只報數字 |
| P-R668-6 | 尺有牙齒：≥5 種植入缺陷要翻成 **BROKEN**，不准回傳好看的數字 | ✔ 可判 |

## 五、什麼條件下本判準該被推翻

- 若收官時三臂 `measured` 不相等（有 void），§二 的第三項就不是 0，
  **照實列出來**、不要把它塞進另外兩項。
- 若 `md∧¬acc > 0`，(c) 的反事實就不再等於「拒交題全是錯的」，
  `forced_leak` 的公式仍成立（它已經扣掉 `md∧¬acc`），但 (b) 的
  「拒交驅動」要改述成「拒交驅動（其中 k 題本來是對的）」。
- 本判準只管 P-C3 **後半**。前半（拒交率 3–10%）R440R 有帶，照原文判。

## 六、非目標

不改 `gain_run.py`、不碰 r444 的任何檔案、不新增可調參數、不替「明顯」發明門檻。
