# R530 沙箱：三條路、實測值、裝法與回滾

E-9（Fable 2026-09-14）把沙箱從「事後註解」改成**發射前提**：
`backend_meta.repo_hidden_from_sandbox` 不是 `true` 就不准發射。
這份講怎麼拿到那個 `true`，以及每一條路的實測值。

⚠ **2026-09-18 起實作住在 `vacant/vrun/sandbox.py`**（進 wheel，`pip install` 的人
也要跑得動閘門）。`ops/gain/r530/sandbox.py` 是 re-export：**同一個 module 物件**，
本文所有 `python3 ops/gain/r530/sandbox.py …` 的指令逐字照舊可用。

判準只有三個，而且**三個都是量的不是宣稱的**（`vacant/vrun/sandbox.py::Sandbox.probe`）：

| 欄位 | 量法 | 為什麼它承重 |
|---|---|---|
| `network_isolated` | 沙箱裡 `socket.create_connection(("1.1.1.1", 80))` **必須失敗** | 離線是題目的一部分（`goal.md` 沒有一題要連網），而且觸網會把「模型自己想出來的」與「抄來的」混在一起 |
| `write_confined` | 沙箱裡寫 `<工作區的上一層>/_r530_probe_escape.txt` **必須失敗**，寫工作區內**必須成功** | 寫出界會汙染別格的工作區 ⇒ 樹雜湊不再是那一格的性質 |
| `repo_hidden_from_sandbox` | 沙箱裡 `os.path.isdir(<repo 根>)` **必須是 False** | **V/GT 紅線**：`ops/gain/r530/hidden/` 在 worker 構得到的地方**不存在**，而不是「存在但我們不准它讀」 |

跑一次探針：

```bash
python3 ops/gain/r530/sandbox.py --backend unshare \
  --sandbox-uid 65534 --sandbox-gid 65534 \
  --workdir /var/tmp/vacant_r530_work/_probe
```

---

## 路線 A（現用）：`unshare` ＋ 降權到 `nobody` ＋ 工作區根移出 `$HOME`

**vacant-dev 2026-09-14 實測：三個都 `true`。不需要任何主機政策改動。**

原理是三件事疊起來，全部只用既有的 unix 權限：

1. `sudo -n unshare --net` ⇒ 真的 net namespace（`network_isolated`）。
2. `setpriv --reuid=65534 --regid=65534 --clear-groups` ⇒ 跑成 `nobody`。
   `/home/user1` 是 `drwxr-x---` ⇒ `nobody` **連穿越都不行**
   ⇒ repo、`hidden/`、`~/.cline-keys` 全部看不到（`repo_hidden_from_sandbox`）。
3. 工作區根放 `/var/tmp/vacant_r530_work`（`0755`、user1 擁有），
   單格 `chmod -R a+rwX`（`0777`）⇒ `nobody` 寫得進自己那一格、
   **寫不進工作區根**（`write_confined`）。

實測輸出：

```
network_isolated        true    NET_BLOCKED OSError
write_confined          true    ESCAPE_BLOCKED PermissionError
repo_hidden_from_sandbox true   REPO_ABSENT
sandbox_uid             65534
```

發射時就是：

```bash
python3 ops/gain/r530/run_r530.py … \
  --backend unshare --sandbox-uid 65534 --sandbox-gid 65534
# 工作區根預設已經是 /var/tmp/vacant_r530_work（run_r530.DEFAULT_WORK_ROOT）
```

### 這條路**擋不住**什麼（誠實邊界，不准刪）

- **`/tmp` 與 `/var/tmp` 本身是 world-writable**。`nobody` 寫得進去。
  `write_confined` 量的是「寫不進工作區根」，**不是**「寫不到機器上任何地方」。
  `write_confined=false` 時 `run_r530` 會逐格比對工作區根的直屬項目
  （`row.outside_new_files`），而那是一個**有意的淺檢查**，不准被引用成「沒有外洩」。
- **沒有 mount namespace** ⇒ `/usr`、`/etc` 這些系統目錄照樣看得到（唯讀，因為 `nobody` 沒有權限）。
- **驗收的那幾秒**，隱藏驗收會被複製到 `<work_root>/_verify/_v_hidden_<nonce>/`
  並讓沙箱讀得到——因為驗收本來就要跑它。候選程式碼在那幾秒之內構得到那個目錄。
  這與 `bwrap` 的 `--ro-bind` 是**同一個**殘餘，不是這條路獨有的。
  跑完立刻刪（`acceptance.run_suite` 的 `finally`）。
- `vacant/checks.py` 那句逐字適用：**應用層加固，不是對抗惡意程式碼的完整 OS 安全邊界。**
  本 run 的威脅模型是「意外」不是「攻擊」。

---

## 路線 B（裁定的 S1，**尚未裝，需要人類授權**）：`bwrap` ＋ AppArmor profile

Fable 2026-09-14 授權裝這個 profile。**建置代理的權限層連續兩次擋下這個動作**
（寫 `/etc/apparmor.d/` 屬於主機安全政策變更），所以它**還沒有被執行**。
要裝的話由人類自己跑下面三行。

### 為什麼需要 profile

- `bubblewrap 0.9.0-1ubuntu0.1` 的 `dpkg -L` 裡**沒有任何 `/etc/apparmor.d/` 檔案**。
  它只帶 `/usr/lib/sysctl.d/50-bubblewrap.conf`（設 `kernel.unprivileged_userns_clone=1`），
  而 Ubuntu 24.04 的擋門是 **AppArmor** 不是那個 sysctl ⇒ 那個檔案沒有作用。
- `kernel.apparmor_restrict_unprivileged_userns=1` ⇒ 非特權 `bwrap` 建 userns 時
  轉進 `unprivileged_userns` profile，接著寫 `/proc/<pid>/uid_map` 被拒：

  ```
  apparmor="DENIED" operation="open" class="file" info="Failed name lookup - disconnected path"
  error=-13 profile="unprivileged_userns" name="proc/3248817/uid_map" comm="bwrap"
  ```

- `sudo bwrap` 起得來，但**同一條 profile 轉換會拿掉 `dac_override`**
  ⇒ 綁 `/home/user1/**`（`drwxr-x---`）一律 `Permission denied`。
  （走這條就得把工作區根放在世界可穿越的路徑，而那與路線 A 的前提一樣。）

### 裝（三行，root）

```bash
sudo install -m 644 -o root -g root \
  ops/gain/r530/bwrap.apparmor /etc/apparmor.d/bwrap
sudo apparmor_parser -r /etc/apparmor.d/bwrap
sudo aa-status | grep -A1 bwrap        # 應該看得到 profile 已載入
```

profile 的內容就是 `ops/gain/r530/bwrap.apparmor`（Ubuntu 對「某支 binary 需要
userns」的標準寫法）：它**只放行 `/usr/bin/bwrap` 這一支**，其餘 binary 的限制
一格都沒鬆，也**沒有**把 `kernel.apparmor_restrict_unprivileged_userns` 關掉。

### 驗（**非特權** user1，三個都要 true）

```bash
mkdir -p /var/tmp/vacant_r530_work/_probe
python3 ops/gain/r530/sandbox.py --backend bwrap \
  --workdir /var/tmp/vacant_r530_work/_probe
```

`bwrap` 後端用的是**最小 rootfs**（只 ro-bind `/usr /bin /sbin /lib /lib32 /lib64 /etc`）
＋ `--unshare-all` ＋ 只有工作區是 rw，所以三個欄位會一起變 true，
而且 `repo_hidden_from_sandbox` 是**結構性**的（repo 不在那個 mount namespace 裡），
比路線 A 的「uid 讀不到」更強一層。

### 回滾（兩行）

```bash
sudo apparmor_parser -R /etc/apparmor.d/bwrap
sudo rm /etc/apparmor.d/bwrap
```

回滾之後 `bwrap` 會退回「起不來」，`--backend auto` 會自己退到 `unshare`
（退到哪一級寫在 `backend_meta.tried`，不是安靜地換）。

---

## 路線 C（Fable 裁決第 2 點的原案，**沒有採用**）：專用使用者 `r530hidden`

原案是建一個 `r530hidden` 使用者擁有 `hidden/`（mode 700），驗收 runner 以
`sudo -n -u r530hidden` 跑。**沒有採用**，理由兩條：

1. 路線 A 已經拿到三個 `true`，而它**不需要建使用者**——`nobody` 是既有 uid，
   `/home/user1` 的 `0750` 是既有權限。少一個主機狀態就少一個會漂掉的東西。
2. 原案有一個沒有解決的結構問題：驗收 runner 必須**同時**讀得到隱藏測資
   與跑得動候選程式碼，所以候選程式碼會跑在讀得到隱藏測資的那個 uid 底下。
   那與路線 A 的「驗收那幾秒」殘餘是同一個，不是更強。

要真的把那幾秒也關掉，需要的是 mount namespace（路線 B），不是另一個 uid。

---

## 退化的方向

`--backend auto` 依 `bwrap → unshare → none` 的順序試，**第一個起得來的就用**，
試過哪些、為什麼失敗全部寫進 `backend_meta.tried`。
`none` 後端**不是沙箱**（`honest_bound` 逐字這樣寫），而且它一定過不了 E-9
⇒ 真跑不可能安靜地退到它。

---

## 路線 B 已安裝（2026-09-15 01:43Z，人類授權「好裝」）

`/etc/apparmor.d/bwrap`（內容＝本目錄的 `bwrap.apparmor`）已由 `sudo cp` ＋ `sudo apparmor_parser -r` 安裝並載入（`aa-status` 認得 bwrap）。
**非特權 user1 的實測**（`python3 ops/gain/r530/sandbox.py --backend bwrap`，不需 `--sudo-bwrap`）：

| 探針 | 結果 |
|---|---|
| network_isolated | true |
| write_confined | true |
| repo_hidden_from_sandbox | true（mount namespace 裡沒有 repo，比 unshare 版的「uid 讀不到」強一層） |

存證：`ops/gain/r530/smoke9/probe_bwrap_20260915.json`。
⚠ **R530 正式 run 仍以 `unshare` 跑**（AMEND2-F 的四塊補跑中，跑中不換碼）；切換到 bwrap 留到下一次凍結。
回滾：`sudo rm /etc/apparmor.d/bwrap && sudo apparmor_parser -R /etc/apparmor.d/bwrap`（或重開機後自然不載入）。
