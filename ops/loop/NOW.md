# NOW.md — 現況唯一真源

## 位置
2026-11-09 r1310 redo-2：vq-vyg 重開→再關——redo 審查點出 g25_all_gates_filing.json 未實開；本輪實開＋獨立重算 code 3 sha／sources 3 sha 全一致、0 更正；freeze_check 10/10 OK＋20 passed；三分支已同步。0 模型呼叫。

## 數字（本輪實測著地）
- auto-ci.yml：63 行／2695 B／sha 3f1e05e9（重算、未變）；1 job 4 門（reqloop／FROZEN_SOURCE_SHA／stepchain／repair --selftest）；grep enable/disable＝0→disabled_manually 係服務端狀態、待人類裁決、不翻開關
- effects summary：60228 B／sha a710f7e4（重算、未變）；policy30 w2r g7/l6 r2w0、sessions 19+16=35／API 365+550=915／tokens 33670510；once20 w2r g7/l4 r2w0、sessions 20／API 457／tokens 19503953；與 11-06 指示逐項一致
- repair.py：2795 行／blob 5147f8c3（重算＝anchor pin）；extract 1217／e757aec5；docstring 不變量逐條核實
- g25 filing 實開（4681 B／sha 6e5afb46）：三門全 PASS（g1 39/39·0／real14 9/9·0 good5／phase3 9·fixed7·unres2·r2w0·err0）；code sha 51abfec3/c7589c61/332cd324＋sources 3c6fb35a/6b7cb831/ada235bb 獨立重算全一致（filing 未改聲明著地）
- freeze_check 10/10 OK VERDICT: FROZEN_STATE_OK rc=0；20 passed；in-scope diff 0×2；wt_clean 3/3 clean
- CI 一次讀取（不 poll）：qwen27b@31dbb6c11 running（log 約 19%）；argon@89c378c83／worker@7443c8695 無產出；LATEST 三分支皆 green 5078/0/74

## 待辦（依序）
1. 待人類：G3 --fire（vq-1zf）——不點火、不入 queue
2. 待人類：CI 通道裁決（auto-ci.yml disabled_manually＝服務端狀態；不重診斷、不翻開關）
3. 下輪：三分支 HEAD 之 CI 首一次讀取（qwen27b 31dbb6c11 本輪在跑／argon／worker）；維持審查指示（凍結錨守衛＋CI 合約、fail-closed、輪末 VERDICT: FROZEN_STATE_OK）
4. vq-el4 49/49 全閉；/srv/vlab/queue 空；無新人類指示（ops/ 最新仍 11-07＋附帶審查）

## 紅線
- 不碰 main；不自 push（loop 自推）；.github/workflows/ 只讀；不讀 /srv/eval hidden＋scorer
- 凍結 4 檔＋g2.5 filing 不改；/srv/vlab/queue 不放新任務
- 缺值＝UNKNOWN（None）不填 0；不宣稱 localized 優於 generic；不宣稱等 token
- G3 待人類 --fire；無 reset/rebase；無 sleep poll；0 模型呼叫；不以改文件湊進展
