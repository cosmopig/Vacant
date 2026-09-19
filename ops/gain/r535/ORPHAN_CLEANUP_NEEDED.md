# vacant-dev 上有 72 個孤兒行程，要 `sudo` 才殺得掉（2026-09-19）

**給人類的一句話**：在 vacant-dev 上跑下面這行，然後才發 Stage B（r530 重量級題庫）。

```bash
sudo -n pkill -9 -u nobody -f "m solution tests_visible"
```

我沒有自己跑。理由有兩層：這台機器的 pkill 需要 `sudo`，而且先前明講過
「未經同意不要 pkill vacant-dev 的失控行程」——「今晚全權交給你」是一般授權，
蓋不過一條具體禁令。

## 現況（2026-09-19 17:06Z 實測）

```
load average: 71.06, 71.03, 71.01      ← 8 核
72 個 nobody 行程，全部是
    python3 -m solution tests_visible/test_visible.py
ppid=1（孤兒）、每個約 13% CPU
起始時間分佈：2 天前 19 個 ／ 3 天前 24 個 ／ 4 天前 29 個
```

來源是 R530／R534 的驗收沙箱子行程。

## 根因（不是「機器忙」，是 bug；已修）

`UnshareSandbox` 的指令鏈是

```
Popen → sudo -n env -i → unshare --net → setpriv --reuid=65534 → bash → python3
```

`Popen` 記到的 pid 是 **`sudo` 的**（root 擁有）。逾時收尾時我們以無特權身分
`os.killpg(proc.pid, SIGKILL)`，核心回 `PermissionError: [Errno 1]`——
2026-09-19 用 `signal 0` 在 vacant-dev 上實測：

```
我的 uid: 1000   目標 uid: nobody(65534)
  killpg(0): PermissionError: [Errno 1] Operation not permitted
  kill(0):   PermissionError: [Errno 1] Operation not permitted
```

舊版 `_kill_group` 把這個例外 `except Exception: pass` 吞掉，於是**逾時什麼都沒殺**。

⚠ 同一個提權轉換也讓第二道防線失效：`_rlimits` 設的 `RLIMIT_CPU` 在 `sudo` 走 PAM
時被重設。**兩道防線是同一個根因**，不是兩個獨立的洞——所以修一個地方就好，
但也代表在這個修法之前，`unshare` 後端的逾時**從來沒有生效過**。

⚠ 它會**自我放大**：孤兒堆高 load ⇒ 後面每一格的逾時虛發 ⇒ 每次虛發再留一批孤兒。

## 修法（`vacant_network/vrun/sandbox.py`）

1. `_kill_group` 從模組函式改成**可覆寫的方法**；`UnshareSandbox` 覆寫成先走
   `sudo -n kill -9 -- -<pgid>`（提權過的行程組只有 root 殺得掉），再直接 `killpg` 一次。
2. 收尾拆成**送**（`_send_kill`）與**確認**（`_verify_reaped`）兩段，中間夾 `communicate`
   把組長收割掉——不先 wait 就驗，殭屍組長會讓每次逾時都被誤判成洩漏。
3. `SandboxResult` 加 `kill_status` 欄位：`""`（沒逾時）／`"reaped"`（確認不見了）／
   `"leaked:<試了什麼>"`。**收尾失敗從此落盤**，不再是一個被吞掉的例外。
   `_group_alive` 對 `PermissionError` 回 **True**——送不到訊號代表「它還在而且我們管不到」，
   那是最糟的情況，不可以樂觀讀成「已經沒了」。

擋門：`tests/test_sandbox_kill.py` 6 條。負控制（把修法拿掉）3 條轉紅。

## 對 R535 的影響（Fable 2026-09-19 裁決）

- **S1／S2 微型題可以帶著 load 71 發**，但要四條件：`--sandbox none`（不降權 ⇒ 不會再造
  跨 uid 孤兒）、`--test-timeout 30`、發射前參考解時序門（每題 ≤ 2 s）、
  以及汙染規則（任一嘗試出現 `kind == "timeout"` ⇒ 孤兒清掉後重算；重算通過 ⇒
  該題三臂一起 `infra_void` 剔除；剔除 > 10% ⇒ 該層 `INVALID`）。
- **Stage B（r530 重量級）在 load < 4 之前不准發**：它的驗收是重量級的
  （`lcb_3686` 要 46 s），而 10 s 是它凍結的常數。

⚠ **單邊保證**：`kill_status` 觀測的是我們**自己新洩**的子行程，不是既有負載對逾時的影響。
後者的觀測點在 `vacant_network/vrun/acceptance.py` 的 `kind == "timeout"`，靠事後在乾淨負載下
重算工作區快照（`_frozen_RUN-ON[_a<n>]/`）來分辨。重算救得回判定，
**救不回「假失敗觸發的那次重試」**——所以要當 `infra_void` 剔題，不是改分。
