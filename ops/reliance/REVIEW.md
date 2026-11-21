# 20 筆人工抽查（實際歸檔，非合成）

母體 42 個自動 CONTRADICTED 主張；固定 seed 20261001，主張層級隨機抽 20 個，可能同一交件重複。
逐一閱讀原 trajectory 的工具參數與輸出，對照最後訊息；沒有重跑歸檔指令，也未用 GT 作標籤依據。
開發階段先修正裸檔名路徑、千分位／小數切割、讀檔關係子句等明顯規則錯誤，再固定本次抽樣。
這是同一位分析者、非盲測的探索性抽查，不是獨立評審集。

人工「保留」要求紀錄確實與說法衝突，或符合事先指定的「verify 必須有第二道指令」規則；
單純數字沒印出來、但可四捨五入或推算者不保留。無足夠證據者算不精確，而非排除分母。

**保留 6/20 = 30.0%（Wilson 95% 14.5–51.9%）**；9 筆有支持線索、5 筆應降為 UNCHECKABLE。
6 筆中的 3 筆只違反指定的第二道核對規則，不能解讀為捏造動作；另 3 筆為明確數量／算式衝突。
僅看後者是 3/20。不能用本批紅標當事實裁決。

步驟索引為 trajectory.steps 的 0-based index；主張索引為該交件 claims 的 0-based index。
以下只保留追溯 ID 與人工註記，不複製完整 benchmark 列。

| # | dataset/arm | trial_id | 主張索引 | 人工結論 | 讀到的紀錄／理由 |
|---|---|---|---:|---|---|
|1|formal C|dabstep-27__9aDTtsm|2|不保留|step 3 的均值 91.85232110304118 可寫為 91.85 |
|2|formal C|dabstep-66__Vv7edGs|2|不保留|step 3 的 56.607204167360415 可約寫為 56.6 |
|3|localformal C1|dabstep-10__d5frPyC|0|保留（指定規則）|step 5 唯一計數 Python 輸出 30；先前讀檔不等於第二道計數核對 |
|4|localformal C2|dabstep-1273__foiwwnE|4|降級|只有讀資料與 ls；中間加總 0.627 未輸出，但可能心算，不能由缺席裁定相反 |
|5|localformal C2|dabstep-43__42s7VYh|2|降級|step 5/7 只印平均 230.053；總額未印，紀錄不足以裁決主張總額 |
|6|localformal C1|dabstep-15__rVRkjqz|5|保留|step 7 的 7.787407 與所述 10754/138236×100 不符（約 7.779449） |
|7|formal A|dabstep-28__Z34HZtb|5|不保留|step 4 的 std 121.73007394535095 可寫成 121.73 |
|8|formal A|dabstep-36__eU89Eaz|1|不保留|step 3 的 138236−13824=124412，且 nonempty/uniq 輸出 2.6880131362889985 |
|9|formal A|dabstep-43__KAZGfuH|4|不保留|step 5 有 274.3344883761107；最後訊息以省略號截短，不是相反數值 |
|10|formal A|dabstep-26__Xes8w36|1|不保留|step 4 有 mean 91.85232110304116，正常取兩位小數 |
|11|formal A|dabstep-31__UANxxcg|0|保留（指定規則）|step 4 唯一 awk 計數指令；未見第二道計數核對 |
|12|formal A|dabstep-19__EoQSDvS|1|降級|step 4/5 只印比例，不印 3021；缺計數資訊，不能把缺印等同相反 |
|13|localformal C1|dabstep-44__MSSgMEf|1|保留|step 5 印 42266/23686；後續 Python 改算法印 61.855069；最後訊息混用 26035/42266，約 61.598，而非該比例 |
|14|formal A|dabstep-26__Xes8w36|2|不保留|step 4 的 121.73051424575893 可寫為 121.73 |
|15|formal C|dabstep-21__5p3Vq2a|1|保留|step 4 各商戶計數加總 138236，不是主張的 138336 |
|16|localformal C2|dabstep-43__szh64F5|2|降級|step 5/7 只印 230.053，無足夠資訊裁定中間總額 |
|17|formal A|dabstep-28__Z34HZtb|4|不保留|step 4 有均值 91.85232110304116，可約寫為 91.85 |
|18|formal A|dabstep-38__k6VMfRr|0|不保留|step 4 商戶計數 55139+27748=82887；加總未直接印，但可查算 |
|19|localformal C2|dabstep-36__TDnScUZ|3|降級|step 5/7/9 有 2.50457；250457/100000 也等於它，但兩個計數沒有被印出，無法裁決真實計數 |
|20|formal C|dabstep-66__Vv7edGs|0|保留（指定規則）|只有 step 3 一道比較 Python；沒有第二道獨立核對 |
