# NOW.md — r1267（2026-11-08，第 1267 輪）

## 現在在哪（一句）
Redo#2 落地：「1910 B」以本輪命令重算（`git show 684e2ba2:loop/NOW.md | wc -c`＝1910）並只寫重算值；
補開審查點名、此前未開的 2 個給定檔（g25_all_gates_filing.json、extract.py），filing 三 sha256 重算 3/3 MATCH。
無代碼改動；主線 G2.5 完結全綠，G3 仍阻塞等人類核准。

## 實測記錄（全部直接開啟／重跑）
【r1267】
- `g25_all_gates_filing.json`：4681 B；開啟讀全文；code 段三 sha256（extract.py `51abfec3`／checks.py `c7589c61`／
  run_eval.py `332cd324`）本輪逐一 sha256 重算 → **3/3 MATCH**（備案與 repo 100% 吻合）。
- `extract.py`：1217 行／57363 B；git blob `e757aec50c16`（anchor 一致）、sha256 `51abfec3…`（filing 一致）；
  docstring fail-closed：quote 非逐字→丟棄、SUPPORTED_VERIFIERS 閉集、unverified→UNKNOWN 不當通過、
  解析失敗→空集、GlmClient（subprocess `glm`）＝擷取模型唯一入口。
- 「1910 B」重算：`git show 684e2ba2:loop/NOW.md | wc -c`＝**1910**（r1266 覆寫前的 r1252 舊版）；
  現行 NOW.md／loop/NOW.md＝1996 B（本輪 wc -c）。
【r1266】
- `auto-ci.yml`：name「auto CI」、job「auto core (reqloop + frozen hash + stepchain)」，
  觸發僅 auto/**/PR/dispatch、`contents: read`；worktree clean，本輪只讀。
- `repair.py`：2795 行／blob `5147f8c3ea1b`（與 anchor 一致）；docstring 含權威快照、
  來源改寫→exit 20、FAIL→UNKNOWN≠修好、regressed、session≠model_calls、缺值=None；
  `test_reqloop_frozen_anchors.py`+`test_reqloop_ci_contract.py` 7 passed。
- `effects_20261105_summary.json`：60228 B／sha `a710f7e4…`；程式重算 8/8 條聲明 PASS：
  50 cells、current_code 50/50（0 分歧）、local 45/50（5 分歧）、policy30 w2r13（g7/l6）
  r2w0 pg10 sw7、once20 w2r11（g7/l4）r2w0 sw9、api_calls 915+457、sessions 35+20。
- repo `loop/NOW.md`：原停滯 r1252（**1910 B**——本輪自 git 重算 `git show 684e2ba2:loop/NOW.md | wc -c`＝1910；
  11-08 10:38）vs 根 NOW.md r1265——13 輪未同步；r1266 已覆寫（即本檔），與根 NOW.md／STATE.md 一致。
- bd：vq-el4 27/27 closed；唯一 open＝vq-1zf（G3，等人類核准）。HEAD 13151d72（r1266 commit）。

## 下一步（次輪，按序）
1. **需人類**：G3（`--fire`）核准或指派其他 in-scope 工作；未核准前禁 fire／入 queue／
   未授權模型呼叫（紅線#5）。
2. 三分支 CI 綠燈確認（一次、不 poll）；紅燈僅在與本輪變更相關時才修。
3. 每輪守：anchors 5 passed＋in-scope diff 0（簿記鏡像同步 worker/argon）。

## 紅線（本輪全守）
0 model calls・無 push（迴圈自推）・`.github/workflows/` 只讀・無 reset/rebase/branch -f・
repair.py／extract.py／checks.py／run_eval.py／filing 未改・未讀 /srv/eval hidden 與
scorer.py・無 sleep 輪詢。
