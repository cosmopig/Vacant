# 從零安裝 Vacant —— 逐字紀錄（2026-09-19）

這份文件的用途只有一個：**證明 README 那幾條指令是真的跑得起來的**，並且把
「照著做會在哪裡卡住」逐字留下來。卡住的地方不是失敗，是這份 log 最有價值的部分
——README 的〈你可能會遇到〉那一節就是從這裡長出來的。

- **機器**：`vacant-dev`（Ubuntu VM，本專案裡最接近「外人的機器」的環境；
  展場機器也是 Linux VM）
- **狀態**：**沒有 pip、沒有 `python3-venv`、沒有 `ensurepip`** 的原廠 Ubuntu 24.04
- **裝的是**：PyPI 上的 **`vacant-network` 0.7.0**（⚠ 不是 `vacant`，見 §5）
- **端到端耗時**：**27 秒**（`2026-09-19T12:40:58+00:00` → `12:41:25+00:00`），
  其中安裝本身 6.3 秒、`apt` 補套件 9.4 秒
- **磁碟**：venv 連同 29 個相依套件（共 30 個 wheel）＝ **60 MB**
- **收尾**：全部刪乾淨（`vacant-dev` 只剩 3.5 G 可用，不留東西）

> 逐字規則：下面每一個 `$` 之後都是真的打進去的指令，接下來到 `[exit=… elapsed=…]`
> 為止都是它真的印出來的東西。只做了一件事——把 ssh 客戶端的 OSC 7 轉義序列拿掉，
> 因為那不是程式的輸出。driver 故意**沒有** `set -e`：失敗那幾步要留著。

---

## 0. 這台機器是什麼

```
$ date -Is
2026-09-19T12:40:58+00:00
[exit=0  elapsed=0.0s]

$ uname -a
Linux user1 6.8.0-137-generic #137-Ubuntu SMP PREEMPT_DYNAMIC Fri Jul 17 20:28:23 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux
[exit=0  elapsed=0.0s]

$ grep PRETTY_NAME /etc/os-release
PRETTY_NAME="Ubuntu 24.04.4 LTS"
[exit=0  elapsed=0.0s]

$ python3 -V
Python 3.12.3
[exit=0  elapsed=0.0s]

$ command -v pip pip3 python3 || echo "(pip / pip3 都不在 PATH 上)"
/usr/bin/python3
[exit=0  elapsed=0.0s]

$ df -h / | tail -2
Filesystem                         Size  Used Avail Use% Mounted on
/dev/mapper/ubuntu--vg-ubuntu--lv   38G   33G  3.3G  91% /
[exit=0  elapsed=0.0s]
```

**注意 `command -v` 只回了 `python3` 一行**：這台機器上 `pip` 與 `pip3` 都不存在。
Python 3.12.3 ≥ 3.11，符合 Vacant 的最低需求。

---

## 1. 卡住點 ①：`python3 -m venv` 在原廠 Ubuntu 上直接死

```
$ python3 -m venv /home/user1/vacant-cleanroom-20260919/venv
The virtual environment was not created successfully because ensurepip is not
available.  On Debian/Ubuntu systems, you need to install the python3-venv
package using the following command.

    apt install python3.12-venv

You may need to use sudo with that command.  After installing the python3-venv
package, recreate your virtual environment.

Failing command: /home/user1/vacant-cleanroom-20260919/venv/bin/python3

[exit=1  elapsed=0.2s]
```

這**不是 Vacant 的問題**，是 Debian／Ubuntu 把 `ensurepip` 拆成獨立套件的後果。
但外人照著 README 打第一條指令就會撞到它，所以它必須出現在 README 裡。
`python3 -m venv` 這個 module 本身是在的（`python3 -m venv --help` 有反應），
死的是它底下的 `ensurepip`——所以錯誤訊息會等到**已經建了半個目錄之後**才出現。

---

## 2. 修法：補一次 `python3-venv`（要 root 一次）

```
$ sudo apt-get update -qq
[exit=0  elapsed=3.9s]

$ sudo apt-get install -y python3-venv 2>&1 | tail -12
No VM guests are running outdated hypervisor (qemu) binaries on this host.
Pending kernel upgrade
----------------------

Newer kernel available

The currently running kernel version is 6.8.0-137-generic which is not the
expected kernel version 6.8.0-139-generic.

Restarting the system to load the new kernel will not be handled automatically,
so you should consider rebooting.

[exit=0  elapsed=5.5s]
```

（那段 kernel 提醒是 `apt` 自己的，跟 Vacant 無關。裝完**不需要重開機**，
下一步立刻就成功了。）

---

## 3. 再試一次：venv 成功

```
$ python3 -m venv /home/user1/vacant-cleanroom-20260919/venv
[exit=0  elapsed=2.2s]

$ /home/user1/vacant-cleanroom-20260919/venv/bin/python -V
Python 3.12.3
[exit=0  elapsed=0.0s]

$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip --version
pip 24.0 from /home/user1/vacant-cleanroom-20260919/venv/lib/python3.12/site-packages/pip (python 3.12)
[exit=0  elapsed=0.2s]
```

---

## 4. 安裝：`pip install vacant-network`

```
$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip install vacant-network 2>&1 | tail -8
Using cached click-8.5.0-py3-none-any.whl (125 kB)
Using cached h11-0.16.0-py3-none-any.whl (37 kB)
Using cached idna-3.20-py3-none-any.whl (69 kB)
Using cached python_dotenv-1.2.3-py3-none-any.whl (22 kB)
Using cached certifi-2026.7.22-py3-none-any.whl (136 kB)
Using cached pycparser-3.0-py3-none-any.whl (48 kB)
Installing collected packages: typing-extensions, rpds-py, python-multipart, python-dotenv, pyjwt, pycparser, idna, httpx-sse, h11, click, certifi, attrs, annotated-types, uvicorn, typing-inspection, referencing, pydantic-core, httpcore, cffi, anyio, starlette, pydantic, jsonschema-specifications, httpx, cryptography, sse-starlette, pydantic-settings, jsonschema, mcp, vacant-network
Successfully installed annotated-types-0.8.0 anyio-4.15.1 attrs-26.1.0 certifi-2026.7.22 cffi-2.1.1 click-8.5.0 cryptography-50.0.1 h11-0.16.0 httpcore-1.0.9 httpx-0.28.1 httpx-sse-0.4.3 idna-3.20 jsonschema-4.26.0 jsonschema-specifications-2025.9.1 mcp-1.30.0 pycparser-3.0 pydantic-2.13.5 pydantic-core-2.46.5 pydantic-settings-2.15.0 pyjwt-2.14.0 python-dotenv-1.2.3 python-multipart-0.0.32 referencing-0.37.0 rpds-py-2026.6.3 sse-starlette-3.4.11 starlette-1.6.0 typing-extensions-4.16.0 typing-inspection-0.4.4 uvicorn-0.53.0 vacant-network-0.7.0
[exit=0  elapsed=6.3s]

$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip show vacant-network | head -4
Name: vacant-network
Version: 0.7.0
Summary: An accountability layer that sits outside any AI agent: runs the customer's executable acceptance tests, gates delivery, and signs every attempt into a verifiable hash chain.
Home-page:
ERROR: Pipe to stdout was broken
Exception ignored in: <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>
BrokenPipeError: [Errno 32] Broken pipe
[exit=0  elapsed=0.4s]

$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip list --format=freeze | wc -l
31
[exit=0  elapsed=0.3s]

$ du -sh /home/user1/vacant-cleanroom-20260919/venv
60M	/home/user1/vacant-cleanroom-20260919/venv
[exit=0  elapsed=0.0s]
```

**這裡量到兩件跟文件不一致的事，兩件都記在這裡：**

1. **`pyproject.toml` 宣告 3 個 runtime 相依**（`cryptography`、`mcp`、`jsonschema`），
   但實際落地是 **30 個 wheel（`vacant-network` ＋ 29 個相依）、60 MB**：`mcp` 一個人就拖進 `pydantic`／`starlette`／
   `uvicorn`／`httpx`／`sse-starlette`／`python-multipart`／`pyjwt` 這一整串。
   「runtime 依賴只有 `cryptography`」那句話**已經不成立**。
   閘門與收據那條路（`vacant_network.vrun.*`）用不到 `mcp`，但目前的 metadata 沒有給
   「只要閘門」的 extras，所以裝了就是全裝。
2. **`pip show … | head` 會噴 `BrokenPipeError`**。那是 pip 對 SIGPIPE 的處理，
   不是安裝失敗（`exit=0`）。會嚇到人，所以寫進 README 的〈你可能會遇到〉。

---

## 5. 卡住點 ②：`pip install vacant` 裝到的是**別人的套件**

這一條沒有比喻的空間——下面是真的下載回來的東西：

```
$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip index versions vacant 2>&1 | head -4
WARNING: pip index is currently an experimental command. It may be removed/changed in a future release without prior warning.
vacant (0.4.15)
Available versions: 0.4.15, 0.4.14, 0.4.13, 0.4.12, 0.4.11, 0.4.8, 0.4.7, 0.4.6, 0.4.5, 0.4.4, 0.4.3, 0.4.2, 0.4.1, 0.4.0, 0.3.6, 0.0.1
[exit=0  elapsed=0.9s]

$ /home/user1/vacant-cleanroom-20260919/venv/bin/pip download vacant --no-deps -d /tmp/notours 2>&1 | tail -6
Collecting vacant
  Downloading vacant-0.4.15-cp311-abi3-manylinux_2_28_x86_64.whl.metadata (5.2 kB)
Downloading vacant-0.4.15-cp311-abi3-manylinux_2_28_x86_64.whl (7.5 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7.5/7.5 MB 4.5 MB/s eta 0:00:00
Saved /tmp/notours/vacant-0.4.15-cp311-abi3-manylinux_2_28_x86_64.whl
Successfully downloaded vacant
[exit=0  elapsed=3.9s]
```

`cp311-abi3-manylinux` ＝ 編譯過的原生擴充（別人的 Rust engine bindings），
7.5 MB，**跟本專案毫無關係**。它**不會報錯**，會安安靜靜地裝好。

- **套件名是 `vacant-network`。**
- **指令名是 `vacant`。**
- 這兩個不一樣，而且分別屬於兩個不同的人。README 第一段就要講。

### 5.1 追加實測（macOS，Python 3.13.1）：**兩個名字都撞，而且互相靜靜覆蓋**

上面只證明了「裝到別人的東西」。回頭在 macOS 上補了四個一次性的 venv，量到的比那更糟。
先看對方的 metadata（逐字）：

```
$ pip show -f vacant
Name: vacant
Version: 0.4.15
Summary: Python bindings for the vacant Rust engine — domain availability via authoritative DNS.
Home-page: https://github.com/alltuner/vacant
Author-email: David Poblador i Garcia <david@poblador.com>
License: MIT
Files:
  ../../../bin/vacant
```

**它也裝一支叫 `vacant` 的指令，也佔用 `vacant` 這個 import 名。** 兩個套件寫到同一批路徑。

| 順序 | `vacant --help` 是誰的 | `import vacant_network.__version__` | 有沒有錯誤訊息 |
|---|---|---|---|
| 只裝 `vacant-network` | 我們的（`{init,info,call,demo,…}`） | `0.7.0` | — |
| 只裝 `vacant` | 對方的（`[-o {jsonl,text}] [--concurrency …]`） | `AttributeError` | — |
| 先 `vacant` 後 `vacant-network` | **我們的** | `0.7.0` | **零** |
| 先 `vacant-network` 後 `vacant` | **對方的** | `AttributeError` | **零** |

**後裝的那個靜靜蓋過先裝的**，四種情形一個警告都沒有，`pip list` 兩個都列著。

更難發現的是解除安裝：

```
$ pip uninstall -y vacant
Uninstalling vacant-0.4.15:
  Successfully uninstalled vacant-0.4.15
$ vacant --help
zsh: no such file or directory: …/bin/vacant        ← 指令整個不見了
$ pip list --format=freeze | grep -i vacant
vacant-network==0.7.0                                ← pip 還說我們的裝著
```

⇒ **移除對方時把共用的那支指令一起帶走，而 pip 不知道我們的被挖空了。**
救法實測有效：

```
$ pip install --force-reinstall --no-deps vacant-network
$ vacant --help | head -1
usage: vacant [-h] [--root ROOT]
$ python3 -c "import vacant_network; print(vacant_network.__version__)"
0.7.0
```

這一節是**判別式**的來源：`python3 -c "import vacant_network; print(vacant_network.__version__)"`
——我們的印 `0.7.0`，對方丟 `AttributeError`。

---

## 6. CLI 在不在

```
$ /home/user1/vacant-cleanroom-20260919/venv/bin/vacant --help 2>&1 | head -12
usage: vacant [-h] [--root ROOT]
              {init,info,call,demo,selftest,run,bench,audit,verify-att,trace,record,up,toggle,status,scoreboard,resident,verify,ledger}
              ...

Vacant — 先驗證交付，再啟動 AI agent

positional arguments:
  {init,info,call,demo,selftest,run,bench,audit,verify-att,trace,record,up,toggle,status,scoreboard,resident,verify,ledger}
    init                鑄出一個 vacant 身體
    info                檢視一個 vacant
    call                從 caller 對某 niche 發一次 a2a_call
    demo                gate＝30 秒看到閘門擋下交付（預設 eco＝§11 C0/C1/C2/C3 對照實驗）
[exit=0  elapsed=0.1s]
```

---

## 7. `vacant selftest`

```
$ /home/user1/vacant-cleanroom-20260919/venv/bin/vacant selftest
端到端迴圈    : ✓（6 次呼叫無例外，4/6 答對）
expert 鏈驗   : ✓
requester 鏈驗: ✓
暫存目錄      : /tmp/vacant-selftest-_bqraq82
[exit=0  elapsed=0.3s]
```

⚠ **`4/6` 那個數字不是固定的**：同一天在 macOS 上跑同一個版本印的是 `3/6`。
`selftest` 驗的是「端到端迴圈不丟例外」＋「兩條簽章鏈驗得過」，
**答對幾題不是判準**，不要拿它當效能數字。

---

## 8. `vacant demo gate` —— 30 秒看到閘門擋下交付

```
$ /home/user1/vacant-cleanroom-20260919/venv/bin/vacant demo gate

vacant demo gate — 零設定、零模型端點、零 API key、零網路。
               一隻假 agent，一道真閘門，一張真收據。

客戶的需求　：~/.vacant-run/demo-gate/ws_vacant/TASK.md
　　　　　　　  solution.py 要有 add(a, b) 與 mul(a, b)
客戶的驗收　：~/.vacant-run/demo-gate/tests_visible/test_visible.py（2 條）
　　　　　　　  check_add: add(2, 3) == 5
　　　　　　　  check_mul: mul(3, 4) == 12

────────────────────────────────────────────────────────────────────
[1/2] 沒有 Vacant：agent 說完成，就是完成
────────────────────────────────────────────────────────────────────
$ cd ~/.vacant-run/demo-gate/ws_plain && python3 demo_agent.py
  Done. I have created solution.py with add() and multiply().
  All requirements are implemented and the code is ready to use.

  agent 退出碼　　　　：0
  交付　　　　　　　　：出去了（~/.vacant-run/demo-gate/ws_plain/solution.py）
  誰量過　　　　　　　：沒有人
  收據　　　　　　　　：沒有

────────────────────────────────────────────────────────────────────
[2/2] 加上 Vacant：同一隻 agent、同一份交付，這次有人收件
────────────────────────────────────────────────────────────────────
$ python3 -m vacant_network.cli run --workspace ~/.vacant-run/demo-gate/ws_vacant --suite ~/.vacant-run/demo-gate/tests_visible --run-dir ~/.vacant-run/demo-gate/receipts --task-id demo-gate --sandbox auto --vacant 1 -- python3 ~/.vacant-run/demo-gate/demo_agent.py
  （`python3 -m vacant_network.cli` ＝ 你會打的 `vacant`；這裡用模組形式＋明寫 PYTHONPATH，確保跑的是這一份安裝的 vacant）
  ── 以下到空行為止，是 `vacant run` 原樣印出來的 ──
  Done. I have created solution.py with add() and multiply().
  All requirements are implemented and the code is ready to use.
  [vacant run] RUN-ON　拒交（visible_fail）　1/1 次　ws e5241309c23b→76c38272981f　wire 0 通　收據 /home/user1/.vacant-run/demo-gate/receipts
  test_visible.py::check_mul — exception: ImportError: cannot import name 'mul' from 'solution' (/home/user1/.vacant-run/demo-gate/receipts/_frozen_RUN-ON/solution.py) [test_visible.py:7: from solution import mul]

  agent 退出碼　　　　：0　　← agent 自己說它成功了
  客戶的驗收　　　　　：1/2 通過
  沒過的那一條（讀自 run_RUN-ON.json，與上面同一份原文）：
      test_visible.py::check_mul — exception: ImportError: cannot import name 'mul' from 'solution' (/home/user1/.vacant-run/demo-gate/receipts/_frozen_RUN-ON/solution.py) [test_visible.py:7: from solution import mul]
  裁決　　　　　　　　：拒交（visible_fail）
  vacant run 退出碼　 ：20　　← 退出碼反映裁決，不反映 agent 的說法

  工作區雜湊　　　　　：e5241309c23b… → 76c38272981f…（agent 真的動過東西）
  模型通道　　　　　　：requests_seen = 0（這隻假 agent 不呼叫模型，所以離線也跑得完）
  　　　換成你真的 agent 就看這個數字：「我設了環境變數」不是被中介的證據，requests_seen 才是。
  收據　　　　　　　　：2 筆 Ed25519 簽章鏈　~/.vacant-run/demo-gate/receipts/receipts_RUN-ON.ndjson
  　　鏈頭　　　　　　：2e86a37f01a6562200186bf9f19eaf3d…

────────────────────────────────────────────────────────────────────
這張收據任何人都能重算——包括先證明驗章器抓得到壞鏈
────────────────────────────────────────────────────────────────────
$ python3 -m vacant_network.vrun.verify_receipts --selftest
  selftest: PASS
$ python3 -m vacant_network.vrun.verify_receipts --glob ~/.vacant-run/demo-gate/receipts --json ~/.vacant-run/demo-gate/verify.json
  ═══ 收據鏈驗證 /home/user1/.vacant-run/demo-gate/receipts ═══
  run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0

  run                           arm          條數    驗過    失敗 verdict  rows  chain_head
  receipts                      RUN-ON        2     2     0       1     1  2e86a37f01a65622…  OK


────────────────────────────────────────────────────────────────────
一句話：**agent 說它做完了，客戶的驗收說沒有。**
　　　　沒有 Vacant，上面那份 solution.py 已經交出去了。
────────────────────────────────────────────────────────────────────
[exit=0  elapsed=0.9s]
```

（上面截到「一句話」為止；`demo gate` 後面還會印接線提示與三條誠實邊界，
與 README 同文，這裡不重複。）

**實際耗時 0.9 秒**——「30 秒」是給人看的上界，不是量到的值。

---

## 9. `vacant run` 拒交格：`accepted=false` ／ `visible_fail` ／ **exit 20**

這一節與下一節是**直接照 README 那幾行打的**，不是 driver 的改寫版。

```
$ cat ~/vacant-try/tests_visible/test_visible.py
def check_add():
    from solution import add
    assert add(2, 3) == 5

def check_mul():
    from solution import mul
    assert mul(2, 3) == 6

$ vacant run --workspace ~/vacant-try/ws --suite ~/vacant-try/tests_visible \
      --run-dir ~/vacant-try/receipts_refuse -- \
    sh -c 'printf "def add(a, b):\n    return a + b\n" > solution.py; echo "Done. solution.py is complete."'
Done. solution.py is complete.
[vacant run] RUN-ON　拒交（visible_fail）　1/1 次　ws 4f53cda18c2b→c18ac5771908　wire 0 通　收據 /home/user1/vacant-try/receipts_refuse
test_visible.py::check_mul — exception: ImportError: cannot import name 'mul' from 'solution' (/home/user1/vacant-try/receipts_refuse/_frozen_RUN-ON/solution.py) [test_visible.py:6: from solution import mul]
exit=20
```

## 10. `vacant run` 交付格：`accepted=true` ／ `visible_pass` ／ **exit 0**

**同一份驗收、同一條指令，只有假 agent 寫出來的東西不一樣。**

```
$ vacant run --workspace ~/vacant-try/ws --suite ~/vacant-try/tests_visible \
      --run-dir ~/vacant-try/receipts_deliver -- \
    sh -c 'printf "def add(a, b):\n    return a + b\n\ndef mul(a, b):\n    return a * b\n" > solution.py; echo "Done. solution.py is complete."'
Done. solution.py is complete.
[vacant run] RUN-ON　交付（visible_pass）　1/1 次　ws 4f53cda18c2b→bf906ec43e3b　wire 0 通　收據 /home/user1/vacant-try/receipts_deliver
exit=0
```

兩格的 `run_RUN-ON.json`：

```
$ python3 -c "import json;d=json.load(open('$HOME/vacant-try/receipts_refuse/run_RUN-ON.json'));print({k:d[k] for k in ('accepted','stop_reason','agent_rc','visible_passed','visible_total','requests_seen')})"
{'accepted': False, 'stop_reason': 'visible_fail', 'agent_rc': 0, 'visible_passed': 1, 'visible_total': 2, 'requests_seen': 0}

$ python3 -c "import json;d=json.load(open('$HOME/vacant-try/receipts_deliver/run_RUN-ON.json'));print({k:d[k] for k in ('accepted','stop_reason','agent_rc','visible_passed','visible_total','requests_seen')})"
{'accepted': True, 'stop_reason': 'visible_pass', 'agent_rc': 0, 'visible_passed': 2, 'visible_total': 2, 'requests_seen': 0}
```

**兩格都要量，這是規格不是完整性。** 只演拒交格的話，量不出「這個閘門會不會
永遠回同一個答案」——而**一個永遠拒交的閘門跟沒有閘門一樣沒用**。
注意兩格的 `agent_rc` 都是 `0`：agent 兩次都說自己成功了，
裁決的差別完全來自客戶的驗收。

---

## 11. 驗收據（負控制先過）

```
$ python3 -m vacant_network.vrun.verify_receipts --selftest
selftest: PASS

$ python3 -m vacant_network.vrun.verify_receipts --glob ~/vacant-try/receipts_deliver
═══ 收據鏈驗證 /home/user1/vacant-try/receipts_deliver ═══
run 1　鏈 1　entries 2　驗過 2　失敗 0　壞鏈 0

run                           arm          條數    驗過    失敗 verdict  rows  chain_head
receipts_deliver              RUN-ON        2     2     0       1     1  9a3abd1bd71c31cd…  OK

總判：OK
每一列＝一個 run 的一條臂鏈。`verified_n` 數的是**逐筆都過**的 entry；`failures` 是原文（seq／type／原因），不是摘要。`chain_ok` 是本檔逐筆重跑的結論、`logbook_verify_chain` 是 `vacant_network/logbook.py` 那支的 bool——兩者必須一致，不一致算 BROKEN。
```

`--selftest` 要**先**跑：它證明這把尺抓得到壞鏈。沒過負控制的驗章器，
拿去驗真鏈只會得到一個沒有內容的 `OK`。

---

## 12. 現場量到的一條誠實邊界：**零請求的跑照樣 `chain_ok=true`**

```
$ python3 -c "import json;d=json.load(open('.../receipts_deliver/run_RUN-ON.json'));print('requests_seen =', d['requests_seen'])"
requests_seen = 0
[exit=0  elapsed=0.0s]
```

上面那條鏈 `entries 2 / 驗過 2 / 失敗 0 / chain_ok=true`，而這一跑的
**模型通道一通都沒有發生**（假 agent 不呼叫模型）。

⇒ **鏈保證的是「我記下來的沒被動過」，不是「該發生的都發生了」。**
所以「我設了環境變數」不是被中介的證據，**`requests_seen > 0` 才是唯一能證明
中介真的發生過的欄位**。這跟 Ma & Tsudik 2009 的 truncation／omission attack
是同一件事的兩個面向：`verify_chain` 沒有長度承諾，也沒有外部錨。

同一支指令也量到**一個文件與實作的落差**：

```
$ python3 -c "... print('upstreams_defaulted =', d.get('upstreams_defaulted','<這個版本沒有這個欄位>'))"
upstreams_defaulted = <這個版本沒有這個欄位>
```

`upstreams` / `upstreams_defaulted` 兩個欄位在 **repo HEAD 有**
（`vacant_network/vrun/launcher.py:586-590`，commit `9eeb1d9e`），
**PyPI 上的 `vacant-network` 0.7.0 沒有**——版本號沒有跟著 bump，
所以 `0.7.0` 這個字串同時指兩份不同的碼。這件事寫進 README 的〈你可能會遇到〉，
並列為待處理事項。

---

## 13. 卡住點 ③：驗收目錄放進工作區底下 ⇒ fail-closed

```
$ vacant run --workspace .../try/ws_bad --suite .../try/ws_bad/tests_visible --run-dir .../try/receipts_bad -- sh -c 'true'
--suite 不可以在工作區底下（/home/user1/vacant-cleanroom-20260919/try/ws_bad/tests_visible ⊂ /home/user1/vacant-cleanroom-20260919/try/ws_bad）：agent 改得到的驗收不是驗收。權威的那一份放工作區外，要給 agent 看就複製一份進去。停。
[exit=1  elapsed=0.1s]
```

這是**正確行為**，而且它是 fail-closed（停下來，不是安靜跑錯）。
但第一次打的人會以為自己的路徑寫錯了，所以要寫進 README。

---

## 14. 收尾

```
$ du -sh /home/user1/vacant-cleanroom-20260919
60M	/home/user1/vacant-cleanroom-20260919
[exit=0  elapsed=0.0s]

$ df -h / | tail -1
/dev/mapper/ubuntu--vg-ubuntu--lv   38G   33G  3.4G  91% /
[exit=0  elapsed=0.0s]

$ date -Is
2026-09-19T12:41:25+00:00
[exit=0  elapsed=0.0s]
```

收工後 `vacant-cleanroom-20260919`、`~/vacant-try`、`~/.vacant-run/demo-gate`、
`/tmp/notours` 全部刪除（`vacant-dev` 只有 ~3.5 G 可用，不留東西）。

---

## 這份 log **沒有**證明的事

鐵律 3：「沒量到」≠「量到 0」。下面每一條都是**沒量**，不是量到不行。

1. **沒有量真模型。** 這一整份從頭到尾 `requests_seen = 0`，假 agent 是
   `sh -c printf`。它證明的是**安裝、閘門、退出碼、收據鏈**，
   **不是**「某個 agent 用 Vacant 做得好」。真模型的五個 agent 逐格實測在
   [`docs/AGENT_COMPAT.md`](AGENT_COMPAT.md)。
2. **沒有量 macOS 與 Windows 的完整路徑。** macOS（Python 3.13.1）上只跑過
   `pip install` ／ `selftest` ／ `demo gate` ／ 兩格 `vacant run`（都過）
   ＋ §5.1 的套件撞名四格，**沒有做 clean-room**。Windows **完全沒量**，而且
   `vacant_network/checks.py` 本來就沒有可用的 Windows 沙箱分支。
3. **沒有量「裝了之後跑 repo 的測試套件」。** 那需要 clone ＋ `pytest`，
   不在「外人照著 README 裝起來用」這條路徑上。
4. **沒有量出網封鎖。** `ops/vacantrun/block_egress.sh` 要 root、改整台機器的
   網路規則，而且**不在 wheel 裡**。這份 log 裡的 proxy 只有 L3
   （records，不 prevents）。
5. **沒有量那 29 個相依套件的供應鏈。** 只記下它們被裝進來了。
