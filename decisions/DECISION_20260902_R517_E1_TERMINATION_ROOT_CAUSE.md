# DECISION R517（2026-09-02 21:xx UTC，Sonnet 5）：E1 行程死亡的根因——`loginctl` linger=no，不是 bug、不是資源不足

補 round515/516 留的空格：round515 只記錄「process exited」，round516 §0 只處理
`run_complete` 永遠是 false 的邏輯性質，兩輪都沒查**行程實際是怎麼死的**。本輪查到了。

## 證據

```
$ journalctl _COMM=systemd-logind | grep "session 4218"
Sep 02 09:32:51 user1 systemd-logind[1181]: New session 4218 of user user1.
Sep 02 20:56:35 user1 systemd-logind[1181]: Removed session 4218.

$ journalctl --since "2026-09-02 20:56:30" --until "2026-09-02 20:56:40"
Sep 02 20:56:35 user1 systemd[1]: session-4218.scope: Deactivated successfully.
Sep 02 20:56:35 user1 systemd-logind[1181]: Removed session 4218.

$ loginctl show-user user1 | grep -i linger
Linger=no
```

`runs/g_r441_gemma_only_mbpp_b/calls.jsonl` 最後一筆 `ts_ms=1788382594759`
＝ `2026-09-02 20:56:34.759 UTC`，`summary.json` mtime `20:56:35.333`——
跟 session 4218 被移除的時刻（20:56:35）逐秒對上，不是巧合。

## 結論

E1 是用 `setsid nohup ... &` 起的（LOOP_PROMPT 規定的長跑寫法），理論上應該不受
發起它的 shell 結束影響。但這台主機 `Linger=no`：使用者**最後一個**登入 session
結束時，`systemd-logind` 會把該使用者的整個 user slice/cgroup 收掉，**這個機制在
`setsid`／`nohup`／`disown` 之上**——那三個只防「controlling terminal 消失時的
SIGHUP」，不防「使用者沒有任何登入 session 時 logind 收 cgroup」。session 4218
存活了 11h23m44s（09:32:51→20:56:35），E1 全程正常跑，直到那個 session 結束的
瞬間被收掉，跟行程本身健不健康、後端 8765 通不通完全無關——round516 §0 說「不是
還沒跑完」是對的邏輯結論，這裡補上物理層的「為什麼」。

## 對未來長跑的建議（不是本輪做的，需要人類或有 sudo 的輪次執行）

`loginctl enable-linger user1` 可以讓使用者的 systemd user instance 在沒有登入
session 時繼續活著，長跑就不會被收掉。這需要權限（多半要 sudo 或 polkit 授權）
——照 LOOP_PROMPT「需要 sudo 的安裝」屬於三件要停下來問人類的事之一，本輪
**不自己執行**，只記錄診斷結果與建議。

替代方案（不需要 sudo）：長跑前用 `systemd-run --user --scope --collect
setsid nohup ...` 把行程放進獨立的 transient scope（不掛在登入 session 底下）；
或每輪迴圈開場都確認至少有一個登入 session 存活（目前的 loop.sh 呼叫模式本身
可能就是那個「session」，如果 loop.sh 自己的父 session 也會終止，這個問題會
反覆發生，值得下一個 opus 輪評估）。

## 沒做的事
- 沒有執行 `loginctl enable-linger`（需要權限，且是系統層級持久變更，按規則問人類）。
- 沒有重跑或修改任何實驗資料；E1 的結論本身（round516）不受這個發現影響——
  資料是完整的（537/537 格已處理），只是「為什麼行程恰好在那個時間點停止寫入」
  現在有答案了。
- 沒有嘗試 `systemd-run --user --scope` 的替代寫法（提案，不是本輪執行）。
