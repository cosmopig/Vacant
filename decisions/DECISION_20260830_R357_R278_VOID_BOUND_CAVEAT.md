# DECISION 2026-08-30（round357，Sonnet 5 + 一次 Opus 5 子代理覆核）：
R278（179題）flagship 量測用 round77 的 void-proof 區間規則重驗——判定「不可判定」，不是「方向存在但範圍窄」

## 觸發：延伸 round356 的 void-gate 斷言時，順手查到旗艦 run 本身

本輪主線工作是補 round356 留下的欠款——把 void-gate 斷言接進
`analyze_off5_gate_counterfactual.py`／`analyze_reviewer_family.py`
（見同一輪另一筆 commit）。跑 `analyze_reviewer_family.py` 驗證輸出時，
順手把它的 `DEFAULT_RUNS` 清單裡的 `g_het3_r278_20260829` 也算了一次
void 率——這支 run 是 `CONCLUSION_20260830_G_EXPERIMENT.md` 判準 3 引用的
「179 題」那一半量測（另一半是 371 題），也是漏出率顯著性claim的第二個
獨立 run。算出來 ON void=40.78%、OFF5 void=35.75%，遠超
`analyze_fullbank_off.py` 定的 10% 閘門。

## 先查有沒有人已經處理過——有，但處理方式跟 round356 不一樣

`DECISION_20260830_R278_ENDPOINT_VERDICT.md`（round341）早就發現同一件事
（同樣的 40.78%/35.75% 數字），並且做了完整分析：McNemar 的配對分母本來
就排除 void 題目，void 題目在兩臂重疊度（47 實際 vs 26.1 期望）顯示不是
隨機噪音，而更像「同一批題目後端系統性容易 timeout」；round341 的結論是
**保留方向性結論，但把適用範圍收窄到「89 題存活子集」**，明確**沒有**
套用 `analyze_fullbank_off.py` 那條「>10% ⇒ 整條臂作廢，不分類」的硬規則。

同一天，round356 對 `g_r342/g_r345/g_r348` 三個 run 用的是硬規則
（`g_r345` 池化總 void 率只有 11.1% 也被列入作廢），跟 round341 對
R278（35-41%，遠更高）的處理方式不一致。

## 找 Opus 子代理覆核：這是真的不一致，還是我漏看了什麼

派了一個 Opus 子代理（不預設答案，要它自己讀三份文件＋原始資料）獨立判斷。
結論：

1. **不一致沒有我想的那麼嚴重**：`VOID_GATE=0.10` 是 `analyze_fullbank_off.py`
   自己的工具常數，其 docstring 把它限定在「單臂點估計分類」，SPEC_GAIN.md
   §7 本身**沒有寫死 10% 這個數字**（只說「部分臂/部分題的漂亮比例不得拿來
   比較」）。round356 disqualify 的三個 run 用的是單臂比例分析
   （`analyze_off5_gate_counterfactual.py`／`analyze_reviewer_family.py`），
   round341 的 R278 用的是**配對檢定**（McNemar），round341 的「這條規則不
   直接套用在配對分析上」是對規則的一種合理讀法，不是走後門。
2. **新查到的因果知識（400 從沒被重試）反而支持 round341**，不是推翻它：
   瞬時性、成串發生但沒真的重試過的路由雜訊，比「重試 4 次全部失敗」更
   接近隨機刪失，跟 round341 自己查到的距離衰減模式（round342 的驗證）
   吻合；round342 也量過刪失偏誤方向對 ON 有利，ON 仍然沒贏。
3. **但 round341 真正漏掉的一步**：從沒有拿 R278 去跑專案自己最保守的
   `analyze_void_bounds.py` 規則 A（void-proof 區間；round77 訂，
   round341 當時甚至沒有引用它）。

## 本輪獨立驗證（不是照抄子代理的話）

手算區間（`lower=k/T`、`upper=(k+v)/T`，T=179，k=accepted&meets_demand，
v=infra_void，逐 task 恆等式不是估計）：

```
ON    k=77  v=73  measured=106  區間 [43.02%, 83.80%]
OFF5  k=96  v=64  measured=115  區間 [53.63%, 89.39%]
```

兩個區間**大幅重疊**（ON 上界 83.8% > OFF5 下界 53.6%）。按規則 A
（round77 訂：「只有 lower(X) > upper(Y) 才宣告 X 嚴格優於 Y；區間重疊 ⇒
宣告『以區間法不可判定』，不准改用點估計去補」）——**這個 run 的
ON-vs-OFF5 排序在最保守的意義下是不可判定的**，不是「方向存在、範圍
收窄到 89 題」。round341 的「89 題子集内方向不變」是對的（那是點估計
陳述），但它不等於「void-proof 意義下方向存在」——這兩句話在
round341 交棒裡沒有被分開講清楚，`CONCLUSION` 引用時進一步把它簡化成
跟 371 題那次「同方向、兩次獨立量測」並列，掩蓋了兩者證據強度的落差。

（`analyze_void_bounds.py` 的 CLI 需要 `--off-baseline`——R278 是
ON/OFF5 兩臂 run，沒有配對的 OFF 臂，工具沒法直接跑，上面是照它
docstring 定義的公式手算，跟工具邏輯一致，只是沒有透過 CLI。）

371 題那個 run（`g_onoff5_371_r123_20260825`）獨立查過：ON void=1.62%、
OFF5 void=4.85%，**都在 10% 閘門內**，這條 p=0.5572 的量測本身站得住，
不需要靠區間分析救。

## 對「漏出量」claim 的同一個檢查

179 題那半的漏出率配對（p=0.003418）也來自 R278，同樣帶著 35-41% void。
但這條指標的旁證（ON 拒收的 18 題全部真的是錯的）是對「已接受題目」的
事後核對，跟 void 掉哪些題目無關，所以**方向性結論本身沒被推翻**——
但同樣不該再說成「兩個獨立 run 都乾淨」。

## 修改

`CONCLUSION_20260830_G_EXPERIMENT.md`：

1. 179 題 ON-vs-OFF5 那段之後加註 void 率＋區間分析結果＋更正措辭
   （不再稱「兩次獨立量測」為對等強度，只有 371 題是 void-proof 乾淨的）。
2. 漏出量那段之後加註同樣的措辭更正。
3. 「這個結論會被什麼推翻」加第 6 條：round357 已檢查、部分觸發，
   要等 `g_r356_3arm_20260830`（round356 用修好的 `brain_cline.py` 重開的
   決定性 run）跑出足夠 n 才算真正解除，不能靠重新詮釋舊資料解除。

`ops/gain/analyze_off5_gate_counterfactual.py`、
`ops/gain/analyze_reviewer_family.py`：加 void-gate 斷言（round356 欠款，
同輪另一筆 commit，本文件不重複記）。

## 沒做的事（照實寫）

- 沒有把 `g_het3_r278_20260829` 標記成「void-gate-disqualified」——上面
  Opus 覆核與獨立驗證都認為這樣講太重（配對檢定不是單臂比例分類，
  round341 的方向性結論在 89 題點估計意義上仍然成立）。準確的講法是
  「這個 run 的排序結論在 void-proof 意義下不可判定，但點估計方向不變」，
  兩句話都要，不能只留一句。
- 沒有修改 `analyze_paired.py` 加 void 檢查——Opus 子代理建議加，但建議
  用「warn+標註範圍」而不是 `analyze_off5_gate_counterfactual.py` 那種
  BROKEN 硬擋（因為配對分析的分母本來就會排除 void 題），這是不同的邏輯，
  留給下一輪单独实作與測試，不要在本文件收尾前趕工塞一個沒驗證過的版本。
- 沒有重新計算或撤下 371 題那組數字——它本身乾淨，不受影響。
- 沒有殺掉或重啟任何 run。

## 這個決定會被什麼推翻

- 若下一輪發現 `analyze_void_bounds.py` 規則 A 的公式本身有 bug（例如
  T 應該用「兩臂共同題目數」而不是「單臂 179」），上面手算的區間需要
  重算，結論可能改變。
- 若人類或下一輪認為「189 題點估計方向 15+ 次沒反轉」這個證據，即使
  void-proof 意義下不可判定，仍然足夠支持原本的措辭，可以把這份文件的
  更正撤回、恢復 CONCLUSION 原文——但要另開文件明講理由，不要直接改回去。
