# NOW（round 1388 收口）

## 狀態
- 分支 auto/qwen27b（tip b4997a07）；r1388：CI 紅燈根因定案（0 產品改動）——qwen27b@50b7023c（r1386）／argon@cc5de0c1（r1386 redo 同步）三紅測＝三 GUARD_CONTENT_PIN 測＝守衛照設計抓到 r1386 未記錄的 ruler 改動（該 commit ruler 已 cfbfba31＝tip 值、pin 仍 r1343 之 4f8f669b）；同 r1384「舊 CI 2 紅閉合」模式、非新缺口、非產品 bug；現 3 tips 皆含 r1387 修復。
- 驗收（本輪 tip 新跑）：守衛 6 檔 88 passed in 4.82s（含三舊紅測）；freeze_check 11/11 OK VERDICT: FROZEN_STATE_OK rc=0。
- CI 一次讀取（不 poll）：現 3 tips（b4997a07/f7115fa6/5f7db930）per-sha json 無→UNKNOWN（H-0、非紅燈）；worker@b056caea（舊 commit、r1386 redo 同步）running（state.json），預期同 pin 族。
- 凍結不變：repair.py 2795 行 blob 5147f8c3、extract.py 1217 行 blob e757aec5、filing 6/6 MATCH、queue 空（含隱藏）、G3 NOT_FIRED。
- vq-el4.71 本輪開→關；vq-1zf（G3）仍等人類 --fire；無其他 open 待辦。

## 下一步（loop 側）
- 下輪開頭一次讀取 CI（不 poll）：3 tips 的 per-sha json（python3 ~/dev/ops/ci_status.py）——綠＝三分支收口；紅＝查因（先核是否本輪 pin 族同型）。
- vq-1zf 仍等人類 --fire；無其他待辦。

## 紅線（不變）
- 不 push（loop 自動推）／不動 main／不 reset-rebase／不讀 hidden+scorer／不 fire G3／不寫 queue／不 full pytest／CI 只讀一次不 poll／0 模型呼叫。
