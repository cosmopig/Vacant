# VOID：w35_vacantdo_rc4_jspool_colab（W3-5 JS 確認批，Colab）——基礎設施中斷，沒有可引用的數字

- 計畫：`ops/redo/plans/w35confirm_js_vacantdo_rc4_colab.json`（acb9b1dcb，第一通模型呼叫前 commit），30 題 × 5 rep＝150 對，A 對 P（rc4）。
- 發射：2026-11-21 12:58Z，Colab L4（session `redo-w35_vacantdo_rc4_j-125817`，endpoint `…sfdgms`）。
- 中斷：跑到約 100/150 對時，結果沒有取回，VM 被 Colab 回收（session 歷史 `session_terminated, reason: pruned`，00:04:19Z）。
  本機沒有 run/、REPORT、cells；只剩 keepalive 的 poll 行。

## 原因（查證過，責任在操作者）

1. 22:37:48Z 我把這批的 keepalive 從原本的 `colab_keepalive_fetch.sh` 換成新寫的 `colab_keepalive_probe.sh`（多了「跑完先不停機、量 vLLM 並行數」），**在批次進行中換了批次周邊的程式**。
2. 兩份腳本都用「`colab sessions` 一次沒列出就判定 session 消失、結束」的檢查（不重試）。23:07:43Z 新腳本碰上一次暫時性的列表失敗，走 SESSION_GONE 分支結束。
3. Colab CLI 日誌的 assignment 清單顯示這台 VM 在伺服器端一直到 00:01Z 都還在；沒有 keepalive 之後閒置約 57 分鐘，00:04Z 被回收，磁碟上的結果一起消失。

## 已跑到哪（只記錄，不可引用）

最後一次 poll（23:02:38Z）：100/150 對，A 49/101、P 42/102、b=18 c=11、infra_void 0。這是**部分資料、沒有逐格紀錄可查證**，
依預註冊 INCOMPLETE 不下結論；而且沒有原始資料可重算，任何引用都不允許。

## 處置

- 不在 Colab 重跑（vacant-hope 11/22 決定）：這個後端（L4、vLLM、jobs 6，每輪平均約 34 秒）量到的本來就是「產品預設值在慢後端上」；
  JS 的判斷依據是 1003 本機的 hardjs34（快後端、同一個 rc4 產品）。
- 教訓（寫進操作規則）：批次進行中不改 harness，**也不換批次周邊的程式**（keepalive、fetch、量測）；並行數量測另開短命 session。
  keepalive 的「一次沒看到就判定消失」是兩份腳本共有的弱點，之後的新腳本改成連續多次確認、且以伺服器 assignment 清單為準。
