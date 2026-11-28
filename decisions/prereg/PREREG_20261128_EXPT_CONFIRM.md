# 預註冊：實驗 T 確認批次（新教材 30 組、沙箱、用紀錄挑初稿）

> 2026-11-28 凍結，在任何確認批次的模型呼叫之前推上遠端。決定者：vacant-hope（11/28 12 小時 review 之後的回覆）。
> 探索批次的結論：`decisions/conclusions/CONCLUSION_20261128_EXPT.md`（T 對 G 未定、T 對 TB 沒過、TE 對 TER 沒過；agent 越界讀取）。
> 固定規則：`ops/SANDBOX_AND_LEAK_SCAN_RULE.md`。

## 資料與模型
- **教材**：realrev3，30 組真實維基百科修訂（公司 10 組 `cc-s01..s10`、足球 20 組 `ff-s01..s20`），manifest sha256 分別是 `3a2a1d6d…`、`39e665bd…`。實驗 1、探索 T、v5.2 調整都沒用過這批。教材與答案在私有目錄，不公開。
- **模型與機器**：qwen3.5-9b，不思考，LM Studio 131072／parallel 2。兩台都用，各 15 組：
  - 1003：cc-s01..05、ff-s01..10。
  - 1004：cc-s06..10、ff-s11..20。
  - 同一組的所有臂、所有初稿都在同一台。
- **沙箱**：受測 agent 一律在 bwrap 裡跑（計畫欄位 `agent_sandbox: bwrap`，`ops/d2/bwrap_expT_agent.sh`），只看得到自己的 live 目錄與輸出目錄。
  - 冒煙在 sc-s01（探索用過的組，不進正式資料）上通過：越界 0；頁面請求經過來源伺服器（c0 8、T 18、G 11 筆，都是 200）；T 兩輪的出口紀錄各記到 36、19 次抓取；標記照常產生。
- **頁面鎖版本、KS-1 模板、作廢規則**：沿用實驗 T（`ops/d2/plans/expT_qwen9b.json` 的 prereg）。

## 第一部分：初稿（`ops/d2/plans/expTc_drafts_qwen9b.json`）
- 每組 5 份初稿（rep 1..5 的 c0，只有 A 臂）。不讀答案、不叫 Haiku。
- 若 11/29 前來不及，**降到 4 份**。這個決定要在看任何結果之前寫進本檔附錄。
- **作廢**：初稿的 agent 有越界讀取（`ops/d2/expT_escape.py`），那份初稿作廢、重跑。

## 第二部分：回饋四臂（`ops/d2/plans/expTc_fb_qwen9b.json`）
- **臂**：A（初稿本身）、G（一般性再檢查，輪數和 T 綁在一起）、T（用紀錄退回特定行）、TB（只退回空白行）。不放 TE／TER、TO。
- **共用初稿**：第一部分的 rep 1、rep 2 初稿。發射前把 `c0` 目錄複製到第二部分的 root，記錄每個檔的 sha256。每臂從自己的副本出發（沙箱裡 agent 看不到 c0 目錄與快照）。
- **主要比較**：配對，以組為群集的 bootstrap，2,000 次，種子 20261127，`python3 ops/d2/expT_metrics.py <root>`。
  - **T 對 TB**：(a) 正確行比例差 ≥5pp 且區間下界 >0，才算紀錄有額外貢獻；否則寫「沒有證據顯示紀錄有額外貢獻」。
  - **T 對 G**：(a) 差 ≥10pp、下界 >0，而且 T 的傷害（C→W/D＋B→W）不多於 G。
- **描述性比較**（事前登記，只描述，不下判定）：
  - TB 對 G。
  - G 對 A：探索發現的「一般性的再檢查有害」會不會重現。
- **三個主指標**：(a) 正確行比例、(b) 已填行精確度、(c) 傷害分開報。
- **無法區分條件**：A 的 (a) >85% 或 <10%，或 T 實際送出回饋的格 <1/4。
- **作廢與排除**：
  - 回饋輪有越界：整對排除，並報「全部」與「排除後」兩個版本。
  - 排除後判定的區間下界不再 >0：主句寫「未定」。

## 第三部分：用紀錄挑初稿（`ops/d2/expTc_select.py`，零額外模型呼叫）
- 每組 5 份初稿，用四種挑法各挑一份：
  1. **record**：紀錄分數最高。分數＝supported_count − flagged_count（flagged 含空白行）；同分取空白較少，再同分取 rep 編號最小。和探索批次次要分析（`expT_metrics.analyze_draft_selection`／`collect_offline_drafts`）**逐字同一個定義**。
  2. **nonblank**：只數非空白行最多（不需要紀錄的對照）；同分取 rep 編號最小。
  3. **random**：5 份的平均（期望值）。
  4. **oracle**：答案鍵挑最好的（上限）。
- **主要比較**（以組為群集的 bootstrap，2,000 次，種子 20261128／20261129）：
  - (1) 對 (3)：正確行比例差 ≥5pp 且下界 >0。
  - **(1) 對 (2)：≥3pp 且下界 >0，才算「紀錄比數空白多帶來東西」。**
- **另報**：各挑法的已填行精確度、(1) 離 (4) 多遠、(1) 和 (2) 挑到同一份的組數。
- 5 份不齊的組不進主要比較，另列。
- **凍結前就知道的事（照實寫）**：在探索批次的資料上（每組只有 2 份初稿），同一支腳本算出：
  - record 63.4%、nonblank 66.2%、random 55.4%、oracle 72.1%。
  - record 對 nonblank −2.7pp，[−9.7, +3.7]；37 組裡有 27 組兩者挑到同一份。
  - 也就是說，在探索資料上，紀錄分數沒有勝過「數空白」。這個比較仍照 vacant-hope 的決定事前登記，用新教材確認。

## 程式版本（sha256，從現在起不改）
寫在兩份計畫檔的 `prereg.code_sha256`：`run_expT.py`、`bwrap_expT_agent.sh`、`expT_metrics.py`、`expTc_select.py`（`88f743f4…`）、`expT_escape.py`。

## 結論的寫法
- 照控制器複核的標準：差距給區間；寫「沒有證據顯示更好」，不寫「一樣」；分母不同的不並排；事前沒登記判讀規則的只描述；偏離預註冊的地方直接列。
- 稽核包附：逐格表（含時間）、逐行狀態（值只給雜湊）、回饋鏈雜湊結構＋公鑰＋鏈頭、越界掃描的逐筆結果、選擇器的逐組挑選。
- **時程**：判讀在 11/29 06:00Z 前交給 vacant-hope。

## 附錄（發射後的決定，按時間）
- **11/28 01:02Z（看任何結果之前）**：第一次發射兩台共用一個 root，1004 被 root 鎖拒跑，1003 跑了 2 份初稿。已停掉，root 改名 `expTc_drafts_q9_VOID_sharedroot_0102` 保留。
  - 改法：每台一個 root（`expTc_drafts_q9_1003`、`…_1004`），分析時把兩個 root 的格合併（計畫 sha 相同）。
  - 伺服器埠改由系統指定（`server.port: 0`），兩台同時跑不會撞埠。
  - `run_expT.start_server` 加檢查：自己的伺服器行程死了就拒跑。舊版會連到別人的伺服器而誤判成功——第一次撞埠就是這樣。
  - 兩份計畫的 `code_sha256` 已更新。沙箱、臂、判讀規則都沒變。
- **11/28 01:15Z（看任何結果之前）**：第二部分沿用初稿的做法定為：把各台初稿 root 的 `cells/<組>/r1|r2/c0` 整個目錄和 `.live_secret` 複製到同一台的回饋 root（`expTc_fb_q9_1003`、`…_1004`）。
  - 為什麼也要複製 `.live_secret`：live 目錄路徑是由它衍生的，c0 快照裡的 Vacant 紀錄記著那個路徑；路徑不變，紀錄才接得上。
  - 複製後把每個檔的 sha256 寫成 root 裡的 `reused_c0_sha256.json`。
  - runner 看到 `c0/done.json` 就沿用，不重跑 c0。發射前先在一組上確認。
- **11/28 01:40Z，附錄 A：依 vacant-cloud 對探索批次的複核（`decisions/notes/NOTE_20261128_EXPT_EXAM37_AUDIT.md`，分支提交 cf92a6dbc）補的事前規定。在看任何確認批次分臂結果之前寫死。**
  - **先後照實**：寫這段時，確認批次沒有任何評分或分臂彙總被算過或看過。我看過的只有基礎設施檢查：
    - 頭 7 份初稿（cc-s01 r1–r4、cc-s06 r1–r3）報告裡的空白行數，用來確認沙箱裡 agent 有把值填進去；
    - 兩台各自「上下文長度用完」的次數。
    兩者都不涉及答案或任何臂。
  1. ⚠ **本點的判讀已被附錄 B 的 B5 取代**（三段判讀；第一版分析腳本 b33043806 仍是二分，第二版起只輸出 B5）。**整份空白的初稿**：定義為 `c0/report.md` 用 `score_d2.parse_report` 解析後，已填行數＝0。
     - 主分析照原 prereg，用全部格。
     - **同時事前登記分層分析：「初稿非空白」的格**（該對的 c0 已填行數 ≥1），單獨算四個比較（T 對 TB、T 對 G、TB 對 G、G 對 A）。
     - 選擇器的分層：每組的候選只留非空白初稿；非空白初稿 <2 份的組排除；random 取非空白初稿的平均。
     - **判讀規則**：全樣本過、但非空白分層不過 ⇒ 結論寫成「效果來自重寫（或避開）空白初稿」，不寫成退回機制或紀錄有效。
     - 空白初稿的份數，分台、分組報告。
  2. **多重比較**：四個預註冊主要比較（T 對 TB、T 對 G、record 對 random、record 對 nonblank）用 Holm 校正，判定並列報告，**以校正後為主**。
     - p 值：以組為單位的符號翻轉置換檢定（每組的配對差取組平均，10,000 次，種子 20261130，雙尾）。
     - 一個比較要算「過」，必須同時滿足：原本的效果量門檻、區間下界 >0、Holm 校正後 p<0.05。
  3. **少數幾對主導**：每個過關的比較（校正前或後過的都算）都附「拿掉貢獻最大的 2 個單位之後」的差與區間。回饋比較的單位是對（組、次），選擇器的單位是組。這寫進固定輸出。
  4. **評分補一欄**：每一行的最終值除了對照 revision 0 的答案，也對照教材裡後續修訂（cycle_1 以上）的真值。記「和後續修訂相符、但和 revision 0 不符」的行數（偵測從未來版本抄來的值）。確認批次有沙箱，理論上應該是 0；這欄照樣算、照樣報。
  5. **選擇器**：主比較本來就是「紀錄分數對只數空白」，不改。複核在探索資料上重現了：「只數空白」比隨機 +11.8pp，比紀錄分數還高 3.7pp，[−7.8, −0.2]（複核者的 bootstrap；本檔前面寫的 −2.7pp [−9.7, +3.7] 是同一份資料用另一種重抽／定義算的，兩者都照列）。
  - 這些都由一支分析腳本執行：`ops/d2/expTc_confirm_analysis.py`，sha256 `8000b01d1fb26a0ba9d135595322d8c500efa1065f0396c70ae8dbece2c96107`。11/28 02:00Z 提交，當時確認批次還沒有任何結果被看。
    - 先在**探索批次**的資料上驗過，重現了複核的數字：空白初稿 13 份；非空白分層 T−G +8.7pp、T−A −1.5pp；T−G 置換 p=0.015、Holm 後 0.062 不過；拿掉前 2 對 +9.35pp。
    - 驗證時發現一個欄名錯誤（傷害數讀不到，使「T 的傷害不多於 G」恆為否），已修，上面的 sha 是修好後的版本。

## 附錄 B（看結果前補充；依 vacant-cloud 對預註冊的方法學審查，`decisions/notes/NOTE_20261128_EXPT_CONFIRM_PREREG_REVIEW.md`，分支提交 4bb7df2d2）
- **全部採用**（vacant-hope 決定）。下面 B1–B12 的條文**逐字取自審查文件**，沒有改寫；條文之後是執行方的補充事實。
- **B5 取代附錄 A 第 1 點的二分判讀**（「全樣本過、分層不過 ⇒ 效果來自空白初稿」改成 B5 的三段）。
- **寫這段時看過什麼**（照實）：確認批次沒有任何評分、沒有任何分臂彙總，回饋四臂還沒發射。我看過的只有基礎設施檢查：
  - 初稿進度與錯誤數；
  - 頭 7 份初稿的空白行數；
  - 兩台各自「上下文長度用完」的次數；
  - 一份初稿 agent 紀錄的結尾（確認空白的原因是上下文長度）。
  這些都不涉及答案或任何臂。

附錄 B（看結果前補充）B1 等價與負向結論。每個主比較事前定一個「最小有意義差」Δ：T 對 TB 5pp、T 對 G 10pp、record 對 random 5pp、record 對 nonblank 3pp（等於各自的效果量門檻）。等價用 TOST：組層級 bootstrap 的 90% 區間（第 5、95 百分位，同一份重抽、同一個種子）完全落在 (−Δ, +Δ) 之內，才可以寫「差小於 Δ」。等價判定不做 Holm 校正，並在報告上標明。沒過門檻也沒過等價時，主句只能用這個格式：「差 d pp，95% 區間 [l, u]；資料仍和最多 +u pp 的效果相容；沒有量到差別」。不准寫「一樣」「沒有效果」「T 不比 TB 好」「紀錄沒有用」「數空白就夠」。事前計算的檢定力（本附錄的表）照列在結論裡。

附錄 B（看結果前補充）B2 網路越界。越界掃描除了 `expT_escape.py` 的路徑類別，再加一類「網路繞過」：任何一次工具呼叫的參數含 `--noproxy`、`-x`／`--proxy`、`unset`／`env -u` 加任何 `*_proxy`、直接指到 `127.0.0.1:`／`localhost:` 的網址（LM Studio 端點除外），或指向 `routes.json` 以外的主機。每一格也要對帳：來源伺服器 `access.jsonl` 裡屬於這一格（host＋arm＋round 中繼資料＋時間窗）的 200 請求，在這一格的 egress 紀錄裡找不到的，記為繞過。網路繞過和讀到工作區外的檔一樣處理：初稿作廢重跑；回饋輪整對排除，並報全部與排除後兩版。越界掃描的敏感度數字以 `expTc_confirm_analysis.py` 為準，`expT_escape.py` 的 `comps()` 輸出不採用。發射前另外記錄每台主機能不能直接連到外部網站（一次 `curl --noproxy '*'` 的結果）。

附錄 B（看結果前補充）B3 未來版本欄的判讀。「和後續修訂相符、但和 revision 0 不符」的行數只當描述，分臂、分台報。越界只依 B2 與 `expT_escape.py` 的紀錄判定，不依這欄；這欄非 0、但紀錄沒有越界時，寫成「可能來自模型的既有知識」，不作廢任何格。若某一臂這欄的組平均比 A 高、且配對區間下界 >0，在結論裡明列，並報「把這些行當成錯」與「從分母拿掉這些行」兩版主指標。

附錄 B（看結果前補充）B4 基礎設施分類（每一次 agent 執行逐一判定，判定只用紀錄，不看分數）。
(i) **infra_void**：這次執行期間，來源伺服器對這一格的 host 沒有任何 200 回應、或有非 200 回應（404／5xx）；或模型端點回連線錯誤／5xx，之後 agent 沒有再成功呼叫就結束；或伺服器行程在執行窗內死掉。初稿 infra_void ⇒ 重跑（最多 2 次，仍失敗就這份初稿缺）。回饋輪 infra_void ⇒ 照 runner 重試，重試仍失敗 ⇒ **整對**從所有比較排除（不是只排除該臂），報全部與排除後兩版，套用「排除後下界不再 >0 ⇒ 未定」。
(ii) **上下文用完**與**逾時（600 秒）**算模型行為，不作廢，報告照磁碟上的樣子評分。但要分臂、分輪、分台報次數。若 T 或 G 任一臂的這兩類合計，比另一臂多出 5 對以上，就加報排除這些對的敏感度。
(iii) 空白初稿再分兩類報：伺服器有 200 回應的（模型行為）與沒有的（依 (i) 已作廢重跑，不應出現在分析裡）。
(iv) 起點檢查：任何一對的 A 臂 `report.md`，或任何一臂的起點 c0，sha256 和 `reused_c0_sha256.json` 不符 ⇒ 該對作廢（探索批次 fb-s11/r1 就是快照被寫壞）。

附錄 B（看結果前補充）B5 分層判讀。只有在全樣本過關時才看分層，分層不做 Holm、也不單獨成為主張。全樣本過關後：分層的點估計 ≥ 該比較門檻，而且 ≥ 全樣本點估計的一半 ⇒ 寫「非空白初稿上方向一致，分層區間 [l,u]」；分層的點估計 < 門檻的一半，或和全樣本反向 ⇒ 才寫附錄 A 的「效果來自重寫（或避開）空白初稿」；介於兩者之間 ⇒ 寫「分層未定（檢定力不足）」。另報「只有空白初稿的對」的差（描述）。選擇器的非空白分層若剩不到 20 組，標「組數不足、只描述」。

附錄 B（看結果前補充）B6 少數單位主導。「貢獻最大」＝和效果同方向、組平均配對差（選擇器為組差）最大。回饋比較同時報「拿掉前 2 組」與「拿掉前 2 對」，**以拿掉前 2 組為判讀**（和群集單位一致），選擇器拿掉前 2 組。拿掉之後 95% 區間下界 ≤0 ⇒ 主句加「效果由少數組帶動」，不得只寫全樣本的過關。

附錄 B（看結果前補充）B7 傷害條件。「T 的傷害不多於 G」＝`harm_total_rate`（C→W/D＋B→W，除以行數）的組平均配對差 T−G 的**點估計 ≤0**。同時報 C→W/D 與 B→W 分開的差與區間，但判定只用這一個。G 或 T 把整份報告清空（最終已填行數＝0、而起點 c0 已填 ≥1）的對數分臂報，並報「排除整份清空的對」的 T 對 G 敏感度。這個敏感度不改判定；它和主結果方向相反時，主句寫「T 對 G 的差主要來自 G 清空報告」。

附錄 B（看結果前補充）B8 選擇器。(1) k 對所有組一律相同：若任何一組在 11/29 前湊不到 5 份有效初稿，**全部 30 組都改用 rep 1–4**（k=4），不准有些組 5 份、有些組 4 份；若仍有組湊不到 4 份，該組排除並列名，排除超過 5 組 ⇒ 選擇器結論寫「未定」。初稿依 B2／B4 作廢重跑後仍缺，算「湊不到」。(2) 兩台的 root 先合併成 30 組的逐組表，再做一次 bootstrap（2,000 次，種子照原預註冊）與一次置換檢定；不准分台各自報判定。(3) record 對 nonblank 的三種讀法事前寫死：record 過門檻（≥3pp、下界 >0、Holm 後 p<0.05）⇒「紀錄比數空白多帶來東西」；95% 區間上界 <0 ⇒「在這批資料上，只數空白挑得比紀錄分數好」，而且結論第一段要寫：紀錄分數的選擇效果可以完全由空白行數解釋；其他 ⇒ 依 B1 的格式寫「沒有量到差別」，並報 record 和 nonblank 挑到同一份的組數。不准只報 record 對 random 而不並列 record 對 nonblank。

附錄 B（看結果前補充）B9 觸發對齊。(1) 發射後檢查：每一對 G 的實際輪數＝T 的 `rounds_run`；不符的對列出，從 T 對 G 排除（報全部與排除後）。(2) 主比較用全部對（含 T 0 輪、差為 0 的對）。另外事前登記一個描述性的條件化比較：「T 有送回饋（≥1 輪）的對」上的 T 對 G 與 T 對 TB，只描述、不判定。(3) T 對 TB 的結論只能寫成「紀錄引導的退回（含其額外的重寫輪）對只退空白行」，不准寫成「紀錄內容本身的貢獻」；另報 TB 也有 ≥1 輪的對上的 T 對 TB（描述）。(4) 分臂報每對的輪數、token、牆鐘；T 和 G 的牆鐘組平均差若大於 25%，在結論列出。

附錄 B（看結果前補充）B10 時間依據。本預註冊各附錄「看結果之前」的時間，以提交雜湊與遠端分支收到推送的時間為準（附上 `git log --format='%H %cI'` 與推送紀錄）。內文時間 01:15Z、01:40Z 和提交時間 01:07:00Z、01:07:53Z 不一致，照實列出原因（時鐘或手寫）。

附錄 B（看結果前補充）B11 凍結前的使用。列出凍結前所有用到 realrev3 的 root（`expTc_c0_qwen9b` 的每一次發射、`expTc_drafts_q9_VOID_sharedroot_0102`），寫明各自跑了幾格、有沒有人看過報告內容或分數。這些 root 一律不進任何分析，也不拿來替補缺份的初稿。

附錄 B（看結果前補充）B12 分析凍結。`expTc_confirm_analysis.py` 的 sha256 必須在任何初稿 root 被評分之前補進本檔；若提交晚於第一個初稿 root 完成，結論要標「分析碼在初稿完成後凍結」。所有主指標**組加權**（先在組內平均兩對，再在組間平均），對加權只作敏感度。95% bootstrap 區間不做多重比較調整，Holm 只作用於置換檢定的 p；報告上兩者並列。分層分析、條件化比較、敏感度一律不進 Holm 家族，也不單獨成為主張。

### 執行方補充（B2、B10、B11、B12）
- **B2**：11/28 01:14Z 在跑 agent 的這台主機（兩台 LM Studio 只提供模型端點；agent、沙箱、來源伺服器、egress 代理都在這台）測試 `curl --noproxy '*' https://en.wikipedia.org/wiki/Main_Page`，回 **200**。也就是說，**沙箱裡的 agent 在技術上可以直連外網、繞過代理**。所以網路繞過的掃描與對帳是必要的，照 B2 處理。
- **B10**：附錄內文的時間是執行方手寫的估計，**不是時鐘**。手寫時把經過的時間估太多，所以內文時間比實際晚。以提交時間為準（`git log --format='%h %cI'`，每次都是提交後在同一個指令裡立刻推送到 `origin/auto/redo`）：
  - 8e5149ee8 `2026-11-28T01:00:54Z`：預註冊主文＋兩份計畫。
  - 0dd266544 `01:02:44Z`：附錄「每台一個 root」，內文寫 01:02Z，一致。
  - 41392b077 `01:07:00Z`：附錄「沿用初稿」，內文寫 01:15Z，手寫錯。
  - d955bc815 `01:07:53Z`：附錄 A，內文寫 01:40Z，手寫錯。
  - b33043806 `01:10:55Z`：分析腳本與 sha，內文寫 02:00Z，手寫錯。
  - 初稿第一份完成於 01:03Z（1003 cc-s01 r1）。到 01:14Z 為止沒有任何初稿被評分。
- **B11**：凍結前用到 realrev3 的 root（都已改名保留，**一律不進任何分析、不替補缺份**）：
  - `expTc_c0_q9_VOID_port_clash_0036`（00:36Z，沒有沙箱、撞埠）：c0 5 份、A 3 格。看過的內容：cc-s01 r1、cc-s02 r1 報告的前幾行（全是空白範本）、一份 agent 紀錄的結尾（404）。
  - `expTc_c0_q9_VOID_nosandbox_0118`（00:40–約 01:00Z，沒有沙箱）：c0 21 份、A 19 格。看過的內容：cc-s01 r1、cc-s02 r1 報告的空白行數（0）。
  - `expTc_drafts_q9_VOID_sharedroot_0102`（01:01Z，沙箱、共用 root）：c0 4 份、A 2 格。看過的內容：cc-s01 r1 的空白行數與 agent 紀錄結尾（上下文長度用完）。
  - 這三個 root 沒有評分，也沒有人看過分數或答案對照。
- **B12**：`expTc_confirm_analysis.py` 第一版（附錄 A 的 sha）在 01:10:55Z 提交，當時沒有任何初稿 root 完成或被評分。依附錄 B 要改的地方（B2 網路繞過、B4 分類、B5 三段、B6 以組為主、B7 傷害定義、B8 k 規則與合併、B9 對齊、B1 等價檢定），會改成第二版，sha256 補在下面，**一樣在任何初稿被評分之前**。

### 檢定力（取自審查文件，結論的限制段要照列）
探索批次的組間變異換算到 30 組時的檢定力：
- T 對 G 要 14–17pp 才有 80% 檢定力；
- T 對 TB 的 5pp 門檻，檢定力約 0.29（全部格）／0.53（非空白分層）；
- 選擇器對數空白的 3pp 門檻，約 0.27。

「沒過」多半只能讀成「沒量到」。

## 附錄 B 補充（B13 起；看結果前；依 vacant-hope 與 vacant-cloud 對沙箱與附錄 B 的追加審查）
- **寫這段時看過什麼**：確認批次**沒有任何評分**、沒有任何分臂彙總。回饋四臂從沒發射過。作廢的初稿只看過：連外指令次數、空白行數、agent 紀錄結尾。

### B13 沙箱的網路隔離（重寫）與重跑
- **為什麼重寫**：01:14Z（晚於 01:02:48Z 的初稿發射）才測出這台主機能直連外網，而 agent 環境只設了 `http_proxy`、沒有 `https_proxy`，所以 https 請求會繞過出口代理。
  - 探索批次的回饋輪確實因此直連過線上維基（196 次 en.wikipedia.org 等，回來的是真 HTML）。
  - 確認初稿用正式掃描重算：**連外指令 0、越界 0**。我先前回報的「43/52」是 grep 到頁面 HTML 裡的連結，是錯的，已更正。
- **處理**：01:23Z 停掉初稿。兩個 root 改名 `expTc_drafts_q9_1003_VOID_https_direct_0123`、`…_1004_VOID_https_direct_0123` 保留（c0 共 56 份），**不評分、不替補、不進任何分析**。為了設定一致，初稿在新沙箱裡從頭重跑。
- **新沙箱**（計畫欄位 `agent_sandbox: bwrap_netns`；`ops/d2/bwrap_expT_agent.sh`、`ops/d2/sockfwd.py`、`run_expT.run_agent`）：
  - `--unshare-net`：沙箱裡只有 loopback，沒有 DNS、沒有路由。
  - 唯一的出口：runner 在外面把出口代理的埠接成 `<live>/tmp/egress.sock`，沙箱裡把 `127.0.0.1:<埠>` 接回去。
  - 外面的轉送器用 HTTP/1.1 請求串流剖析器檢查**每一個請求**：連線的第一個、keep-alive／管線化的後續、CONNECT 通道裡的明文請求。只放行：
    - 這一格自己的來源主機 `<組>-r<次>.d2-sources.example:80`；
    - cfg/models.json 裡 LM Studio 端點的 `IP:埠`。這是唯一允許直接用 IP 的例外，執行時讀，不寫進 repo。模型端點上只放行 `/v1/chat/completions`、`/v1/completions`、`/v1/models`；`/v1/responses` 刻意不放，因為它可在 body 帶 remote MCP 工具。pi 用的是 openai-completions，即 `/v1/chat/completions`。
  - 其他一律 403 或斷線，並記到每一輪輸出目錄的 `net_blocked.jsonl`。Transfer-Encoding 與 Content-Length 並存、重複標頭、格式不合，一律斷線（防請求走私）。
  - 代理變數 `http_proxy`、`https_proxy`、`HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY` 全設成轉送器，清掉 `NO_PROXY`。
  - `/tmp` 是沙箱自己的 tmpfs；不掛主機的 `/tmp`、`/run`、`/var/run`；沙箱裡唯一的 socket 是轉送器那一個。
  - 來源伺服器只能經轉送器到達（沙箱的 127.0.0.1 是它自己的）。伺服器只提供 revision 0 的凍結頁面；私有教材目錄不掛進沙箱。
- **自我測試**（`ops/d2/netns_selftest.py`，報告 `ops/redo/audit/netns_selftest_20261128.json`）：先負控制、後正控制，在同一個沙箱設定裡逐項跑。**全部通過**；白名單記到 9 筆被擋（預期 9 筆）；經代理連維基的那一筆被擋並有紀錄；自己那一頁出現在出口紀錄。

  | 項目 | 指令（模型端點 IP 遮成 <lms>） | 預期 | 結果 | 判定 |
  |---|---|---|---|---|
  | N01 curl --noproxy direct https wikipedia | `curl -sS -m 8 --noproxy '*' https://en.wikipedia.org/wiki/Main_Page -o /dev/null -w '%{http_code}'` | fail | rc=6；000curl: (6) Could not resolve host: en.wikipedia.org  | 過 |
  | N02 python urllib direct (ignore proxy env) | `python: import urllib.request as u; u.build_opener(u.ProxyHandler({})).open('https://en.wikipedia.org/', timeo` | fail | rc=1；URLError: <urlopen error [Errno -3] Temporary failure in name resoluti | 過 |
  | N03 node fetch (node ignores proxy env) | `node -e "fetch('https://en.wikipedia.org/').then(r=>{console.log(r.status);process.exit(0)}).catch(e=>{console` | fail | rc=1；TypeError: fetch failed  | 過 |
  | N04 raw socket to an IP | `python: import socket; socket.create_connection(('1.1.1.1', 443), timeout=5)` | fail | rc=1；OSError: [Errno 101] Network is unreachable | 過 |
  | N05 DNS lookup | `python: import socket; socket.getaddrinfo('en.wikipedia.org', 443)` | fail | rc=1；gaierror: [Errno -3] Temporary failure in name resolution | 過 |
  | N06 host source server port directly (127.0.0.1 is the sandbox's own) | `python: import socket; socket.create_connection(('127.0.0.1', 57185), timeout=5)` | fail | rc=1；ConnectionRefusedError: [Errno 111] Connection refused | 過 |
  | N07 host /run is not visible | `ls -A /run 2>&1 ／ head -5; test ! -e /run/user && test ! -e /run/dbus && test ! -e /var/run/docker.sock` | pass_cmd | rc=0；ls: cannot access '/run': No such file or directory  | 過 |
  | N08 host /tmp is a private tmpfs (empty) | `test -z "$(ls -A /tmp)"` | pass_cmd | rc=0； | 過 |
  | N09 only the forwarder socket exists | `find / -xdev -type s 2>/dev/null ／ grep -v '^/proc' ／ sed 's#.*/##' ／ sort ／ tr '\n' ' '; test "$(find / -xdev` | pass_cmd | rc=0； | 過 |
  | N10 curl -x proxy https wikipedia (must be 403/blocked) | `curl -sS -m 10 -x http://127.0.0.1:35483 https://en.wikipedia.org/ -o /dev/null -w '%{http_code}'` | fail | rc=56；000curl: (56) CONNECT tunnel failed, response 403  | 過 |
  | N11 other set's source host via proxy | `curl -sS -m 10 http://selftest-s02-r1.d2-sources.example/index.html -o /dev/null -w '%{http_code}' ／ grep -qx ` | fail | rc=1； | 過 |
  | N12 LM Studio host on another port via proxy | `curl -sS -m 10 http://<lms>:22/ -o /dev/null -w '%{http_code}' ／ grep -qx 200` | fail | rc=1； | 過 |
  | N13 LM Studio admin API via proxy (/api/v0/models) | `curl -sS -m 10 http://<lms>:1234/api/v0/models -o /dev/null -w '%{http_code}' ／ grep -qx 200` | fail | rc=1； | 過 |
  | N14 LM Studio /v1/responses via proxy | `curl -sS -m 10 -X POST -H 'Content-Type: application/json' -d '{}' http://<lms>:1234/v1/responses -o /dev/null` | fail | rc=1； | 過 |
  | N15 pipelined: allowed request + /api/v0/models in one send (2nd must be blocked) | `GET http://selftest-s01-r1.d2-sources.example/index.html HTTP/1.1` | blocked_logged | rc=0；HTTP/1.1 403 Forbidden | 過 |
  | N16 CONNECT tunnel to LM Studio, then /api/v0/ inside the tunnel | `CONNECT <lms>:1234 HTTP/1.1 ／ GET /api/v0/models HTTP/1.1` | second_closed | rc=0；HTTP/1.0 200 Connection Established ／／ <closed> | 過 |
  | N17 smuggling: Transfer-Encoding and Content-Length together | `POST http://selftest-s01-r1.d2-sources.example/index.html HTTP/1.1` | first_closed | rc=0；HTTP/1.1 403 Forbidden | 過 |
  | N18 malformed request line | `GARBAGE` | first_closed | rc=0；HTTP/1.1 403 Forbidden | 過 |
  | P01 own source host revision-0 page via env proxy | `curl -sS -m 10 http://selftest-s01-r1.d2-sources.example/index.html ／ grep -q SELFTEST_OK` | pass_cmd | rc=0； | 過 |
  | P02 model endpoint /v1/models via proxy CONNECT tunnel (how pi connects) | `curl -sS -m 15 -p http://<lms>:1234/v1/models -o /dev/null -w '%{http_code}' ／ grep -qx 200` | pass_cmd | rc=0； | 過 |
  | P03 keep-alive inside the LM Studio tunnel: two /v1/models requests | `CONNECT <lms>:1234 HTTP/1.1 ／ GET /v1/models HTTP/1.1 ／ GET /v1/models HTTP/1.1` | all_answered | rc=0；HTTP/1.0 200 Connection Established ／／ HTTP/1.1 200 OK ／／ HTTP/1.1 200 | 過 |

- **正式路徑冒煙**（真 pi、真模型、sc-s01，探索用過的組，不進正式資料；root `expTc_smoke_netns`）：
  - c0 填了 20/20 行、標記 7 行。
  - 來源伺服器有 c0 8 筆、T 6 筆、G 6 筆，都是 200；T、G 各兩輪照常。
  - 白名單 0 筆被擋，新掃描判越界 0。
- **每次發射前必須先跑自我測試、全部通過才發射**；這次的結果在上表。

### B14 附錄 A 第 1 點已被 B5 取代
已在附錄 A 第 1 點加註。第二版分析腳本只輸出 B5 的三段判讀。

### B15 檢定力表（原樣取自審查文件 4bb7df2d2）
| 比較 | 組間 SD（pp） | MDE α=.05 | MDE α=.0125 | 在預註冊門檻或探索效果下的檢定力 |
|---|---|---|---|---|
| T−G 全部 | 27.7 | 14.2 | 16.9 | 效果 11.7：0.64／0.43；效果 10：0.51／0.30 |
| T−G 非空白 | 28.7 | 14.9 | 17.7 | 效果 8.7（探索的非空白值）：0.38／0.20 |
| T−TB 全部 | 19.5 | 10.0 | 11.9 | 門檻 5：0.29／0.14 |
| T−TB 非空白 | 13.5 | 7.0 | 8.3 | 門檻 5：0.53／0.32 |
| record−nonblank（選擇器） | 12.1 | 6.2 | 7.4 | 門檻 3：0.27 |
| record−random（選擇器） | 23.5 | 12.0 | 14.3 | 門檻 5：0.21；效果 8：約 0.46 |

### B16 越界與網路繞過的判定規則（第二版分析腳本 `scan_runs` 的定義；只用紀錄、不看分數）
- **越界**，處理方式：初稿作廢重跑；回饋輪整對排除，並報全部與排除後兩版。以下任一項成立即算：
  - (a) 參數含教材根目錄或 run root 的絕對路徑（agent 自己掛在沙箱裡的輸出目錄除外）。
  - (b) 參數命中相對路徑、`~`、`$HOME`、萬用字元、`find`／`ls /`、`os.path.join`／`glob`／`pathlib` 等樣式，而且工具回傳（去掉 agent 自己的 live 與輸出目錄後）出現教材或別格的特徵；命中次數照報。
  - (c) 繞過代理的參數：`--noproxy`、`-x`／`--proxy`、`--no-proxy`、`unset`／`env -u` 加任何 `*proxy`、`env -i`、把 `http(s)_proxy` 設空、Python `proxies={}`／`trust_env=False`、node 腳本。
  - (d) curl／wget／requests／urlopen／fetch 指令直接指向 localhost／127.0.0.1 或別組的來源主機。
  - (e) **正向對帳**：指令裡抓的每一個網址，在執行窗內都要對到一筆出口紀錄（`egress.jsonl` 的 GET／CONNECT），或一筆白名單擋下的紀錄；對不到就算繞過。另外，來源伺服器的 200 網址必須出現在這一臂的 `egress.jsonl`。
  - 只出現在 grep 樣式、文字或頁面 HTML 裡的網址不算。
- **LM Studio 例外**：主機名 `w1003`、`w1004`，以及 cfg 裡的端點，不算繞過。
- **「與後續修訂相符」的行**：出現在有 (c)–(e) 的格裡，就算繞過，不適用 B3 的寬鬆讀法。
- **探索批次的正控制**：同一支掃描在探索批次判出 **108 次執行有越界**（c0 1 次；TO 45、G 37、TB 14、T 11）。前面口頭說的 109，含一筆「agent 讀自己的輸出目錄」的誤判，已修。舊掃描（只看絕對路徑）是 45。名單會進稽核包。
- **掃描的限制**：用程式拼接、間接讀檔，只能靠 (b) 的回傳特徵去抓。沙箱讓檔案越界讀不到東西；網路有白名單與正向對帳。

### B17 凍結前的三個 root（B11 的補充）
- **誰看的**：都是執行方（本 session）看的，vacant-hope、vacant-cloud 都沒有看過這些 root。
- port_clash、nosandbox 兩個 root 沒有沙箱，共 26 份初稿碰過同一批教材。對它們的 agent 紀錄跑了寫入掃描（專查寫進教材目錄或 template.md）：
  - port_clash 有 9 次呼叫碰到 realrev3 目錄，都是 `cat`／`ls` cc-s01 的 cycle_1 頁面（讀，不是寫；掃描初判的「寫」是 `2>/dev/null` 的重導向符號造成的誤判）；
  - nosandbox 0 次。
- **教材完整性比對**：
  - 兩份 manifest.json 的 sha256 和計畫記的相同（`3a2a1d6d…`、`39e665bd…`），也和教材自帶的 manifest.sha256 相同；
  - 550 個各修訂頁面的 sha256 全部和 manifest 的 `page_sha256` 相符；
  - 30 份 template.md 都含全部行；
  - 736 個教材檔沒有任何一個的修改時間晚於 00:36Z。
  - **教材沒有被寫壞。**

### B18 時間證明
- **作廢的初稿**：RUN.json 記 runner sha `5559a148…`，和 0dd266544 的 run_expT.py 逐位元相同；head 0dd266544；啟動 01:02:48Z，提交後 4 秒（提交與推送在同一個指令裡）。
- **重跑的初稿**：用本補充提交後的 runner（sha 見計畫的 `prereg.code_sha256`），RUN.json 會記 head、runner sha、啟動時間；稽核包附每個 root 的 RUN.json 與逐格時間戳。

### B19 B4 的兩處補充定義（看結果前；只用紀錄判定）
1. 來源伺服器回 404：
   - 那一頁確實在這一格的凍結站裡 ⇒ 基礎設施（路由壞了，例如撞埠）；
   - 頁面本來就不存在（模型亂猜網址）⇒ 模型行為，不作廢。
   - 探索批次有 110 筆 404 都是後者，存在的頁面拿到 404 的是 0 筆。照 B4 字面會把它們全部作廢，所以補這條。
2. 整次執行沒有抓任何頁面 ⇒ 模型行為，不作廢，照報次數。只有「agent 發了請求、伺服器在執行窗內卻沒有任何紀錄」才算伺服器沒在聽（基礎設施）。

### B20 「標記可疑」分層（vacant-hope 定案，回饋臂發射前生效）
1. **主訊號＝量具缺口，不碰答案鍵**：某份 c0 的缺口＝agent 指令裡字面出現的本格頁面網址數 − 出口紀錄到的本格 200 頁面數。缺口 >0 ⇒「標記可疑」。
   - 若診斷找到具體 bug，主訊號改成「符合該 bug 觸發條件的格」，同樣不碰答案鍵。
   - 第二個描述版本：「被標的有值行 ≥80%，且出口頁數 ≤4」（這是看探索資料定的）。
2. **只用 c0 判、整對排除**：只用共用初稿 c0 的紀錄判定，排除單位是整對（A／G／T／TB 一起）。名單在回饋臂發射前算完，sha256 寫進本附錄。
3. **比例上限**：
   - 可疑對 >25% ⇒ 主比較結論加註「紀錄裝置在相當比例的格上不可靠，T 的退回內容可能帶假標記」，T 相關比較一律降為描述性。
   - ≤25% ⇒ 另報排除版，只描述、不進 Holm。
4. **方向**：可疑的格裡 T 會退回本來就對的行，對 T 不利。所以排除版若比主分析好看，**不得用來升級結論**，只准寫「若紀錄裝置正確，T 的表現可能較高」。
5. **裝置精確度**（評分後算、只描述）：每臂每輪「被標的有值行裡真的錯的比例」，分可疑、不可疑兩層。
- 執行方對原因的初步猜測（未驗證）：足球的「出場（進球）」在頁面上是兩個表格儲存格，報告寫成 `32 (1)`，純文字比對找不到，會把對的值標成「讀過的頁裡找不到」。

### B21 值雜湊一律加鹽 HMAC
從本補充起，所有進 repo 或稽核包的值雜湊一律用 HMAC-SHA256。鍵只放本機（`~/.config/vacant/audit_hmac.key`，權限 600，不進 git），等值比對仍然可做。已推上的舊雜湊檔不動，記進歷史清理待辦。

### B22 分析碼第二版
- `ops/d2/expTc_confirm_analysis.py` 第二版，sha256 見計畫的 `prereg.code_sha256`。在任何確認批次的初稿或回饋格被評分之前提交。
- 實作了：
  - B1：等價判定（90% 區間）。
  - B2、B16：越界與網路對帳。
  - B4、B19：基礎設施分類。
  - B5：三段判讀。
  - B6：拿掉前 2 組為判讀，並報前 2 對。
  - B7：傷害率點估計 ≤0、整份清空與其敏感度。
  - B8：k 一律相同、兩台合併一次檢定、「數空白贏」的寫法。
  - B9：G 與 T 輪數對齊、條件化比較只描述、分臂的輪數／token／牆鐘、牆鐘差 >25% 標出。
  - B12：組加權、Holm 只作用於 p。
  - B20：標記可疑分層與裝置精確度。
- 驗證：在 sc-s01 冒煙 root 上跑過；在探索批次上當正控制（越界 108 次）。

