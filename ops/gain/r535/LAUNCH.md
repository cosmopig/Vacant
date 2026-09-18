# R535 發射手冊（2026-09-19）

預註冊在 `decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md`。
**這一份不重述設計**，只寫「在 vacant-dev 這台機器上，把那份預註冊跑起來要輸入什麼」。
寫下來的理由：下面每一條都是實測踩出來的，不寫就會在發射當下重踩一次。

---

## 〇、發射前必須為真的四件事

| | 怎麼查 |
|---|---|
| 發射 commit 在 `ff28540` 之後 | `git -C <worktree> rev-parse HEAD`，且 `git merge-base --is-ancestor ff28540 HEAD` |
| `state_r535.py` 十條測試綠 | 預註冊寫死「**不准資料出來之後才寫收官器**」 |
| 72 個孤兒清掉（**只有 Stage B 需要**） | `uptime`；S1/S2 微型題在 load 71 下可發，見 `ORPHAN_CLEANUP_NEEDED.md` |
| Fable 核 | 預稽核的 A-1～A-8 全部落地之後 |

---

## 一、環境（**兩條都踩過**）

### 1. `pi` 跑不動，因為 `node` 不在非互動 shell 的 PATH 上

`pi` 是一個 symlink，指向 `…/pi-coding-agent/dist/bundle/cli.js`，
而那支的 shebang 是 `#!/usr/bin/env node`。用 `ssh host 'pi --version'` 會拿到：

```
/usr/bin/env: ‘node’: No such file or directory
```

⇒ **每一條流都要先把 node 的 bin 目錄放進 PATH**：

```bash
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
```

`which pi` 在登入 shell 裡也是空的（它不在 `~/.local/bin`），
所以 `--pi-bin` 要給**絕對路徑**：

```bash
--pi-bin /home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi
```

驗證（應該印 `0.85.1`）：

```bash
ssh user1@100.124.254.83 'export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH; pi --version'
```

### 2. 端點變數是 `VACANT_GAIN_API`，而且要**完整路徑**

```bash
export VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
```

⚠ **不是** `VACANT_ENDPOINT`（那個只管 `substrate.py`）。R532 為此誤發兩次打到
`api.cline.bot` 雲端回 400。

⚠ 但 **pi 不吃環境變數**：它讀 `PI_CODING_AGENT_DIR` 底下的 `models.json`。
驅動會自己寫那份設定（含 `samplingParams: {"reasoning_effort": "none"}`）。
所以這個變數是給**驅動自己**探端點用的，
**真正證明中介發生了的是 `requests_seen > 0`**，不是「我設了變數」。

---

## 二、發射（四條流，各自的埠）

### 1. 釘一個 worktree 在發射 sha 上

```bash
ssh user1@100.124.254.83
cd ~/vacant/Vacant && git fetch origin
LAUNCH_SHA=<發射 sha>
git worktree add --detach /var/tmp/vacant_r535/repo "$LAUNCH_SHA"
```

⚠ **不要用 `~/vacant/Vacant` 本體**——它停在 `feat/v2-four-stages`，
而且跑到一半有人 `git checkout` 就會換掉腳下的程式碼。

### 2. preflight（六門，**跳過任一門一律判 FAIL 不判 PASS**）

```bash
cd /var/tmp/vacant_r535/repo
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
export VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
python3 ops/gain/r535/run_r535.py --out /var/tmp/vacant_r535/run \
  --pi-bin /home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi \
  --preflight
```

六門：① F8 時序門（參考解每題 ≤ 2 s）② 端點活著＋model id＋**`reasoning_tokens == 0`**
③ pi 版本逐字 ④ 題庫 sha ＋ 逐檔 sha ⑤ 樣板 `grep -ril hidden` 零命中
⑥ `--suite` 在工作區外（`resolve()` 之後比）。

### 3. 寫計畫（**只做一次**）

```bash
python3 ops/gain/r535/run_r535.py --out /var/tmp/vacant_r535/run --write-plan
```

應得 `n_cells: 360`、`plan_sha256: 7a3accf9b1c925fa07fcc79d67ee0a152e776199229f4ef64228f778795c658e`
（題庫 manifest ＝ `5e727b2ee884d80b197ec42f63af2bf73ce939bdd53c48fc8fc29e46e49c0794`）。
sha 會被簽進 `plan_receipt.ndjson` 的第一筆。

### 4. 四條流（**每條不同的埠**）

```bash
for i in 0 1 2 3; do
  ( export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
    export VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
    cd /var/tmp/vacant_r535/repo
    nohup python3 ops/gain/r535/run_r535.py \
      --out /var/tmp/vacant_r535/run \
      --pi-bin /home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi \
      --stream "s$i" --shard "$i:4" --pi-port $((8877 + i)) \
      > /var/tmp/vacant_r535/stream_$i.log 2>&1 &
  )
done
```

⚠ **`--pi-port` 每條流必須不同**。pi 吃設定檔不吃環境變數，埠對不上 ⇒
`requests_seen = 0`，而畫面上只有 pi 自己的 `Connection error.`
（驅動有 flock 擋「同埠兩條流」，但擋不到「人把 `models.json` 想成別的埠」）。

⚠ **四條流吃同一份完整 plan，靠 `--shard` 分。禁止用 `--arms`／`--stratum`／`--limit` 拆流**
（L-9）：一條流一臂 ＝ 臂 × 時間混淆，會把 H2 做壞。

⚠ `--shard` 用的是**計畫裡的列號**，不是過濾後的位置——所以它與 `--tasks` 不可同時用。

### 5. 收官

```bash
python3 ops/gain/r535/run_r535.py --out /var/tmp/vacant_r535/run --reconcile
python3 ops/gain/r535/score_r535.py --out /var/tmp/vacant_r535/run --twice
python3 ops/gain/r535/state_r535.py --out /var/tmp/vacant_r535/run     # 判定
```

`--reconcile` 的五桶（`flags_mismatch`／`bank_mismatch`／`effort_mismatch`／
`f3_violation`／`probe_invalid`）**任一非空即 `INVALID`**。

---

## 三、跑的時候會發生什麼（**不要當成故障**）

| 現象 | 是什麼 |
|---|---|
| 牆鐘差 30 倍（10 s 對 314 s） | 正常。pi 在難題上會一直 `ls -R`。**印分佈不印均值。** |
| `agent_timed_out=true` | **正常的嘗試結果，不 void**（四臂一視同仁）。任一臂-層 > 20% ⇒ 收官必寫「該比較受預算約束」。 |
| `HALT.json` 出現 | 探針測到 model id 變了或 `reasoning_tokens > 0`，**所有流下一格前就停**。人確認後 `--ack-halt "<理由>"`；⚠ 它解的是派工，**洗不掉已落盤的 `probe_invalid`**。 |
| `interim_S1.json` 出現 | 期中看已定案（`O_EXCL` 寫一次）。`STOP` ⇒ 該層收攤；`CONTINUE` ⇒ 續發；`UNEVALUABLE` ⇒ 有 void 格、**不寫檔**。 |
| load > 80 | 驅動自己暫停派工（不砍 run）。 |

---

## 四、這一份證明不了的事

- **只證明 wire 去了 `100.119.113.56:1234`**（`wire_upstreams`／`upstream_matches`），
  **不證明那台載的是哪份 gguf、什麼載入參數**。探針接住「model id 變了」與
  「開始思考了」，接不住「同 id 同模式但檔案或載入參數換了」。**那一段是人的義務。**
- 收據鏈全過**不蘊含沒有格被整格拿掉**（`verify_chain` 無長度承諾，
  見 `vacant audit` 的警語）。那一層靠的是 `plan.jsonl` ↔ `rows.jsonl` 的逐格對帳。
- 機器規格：**8 核／7 GB RAM**，而且發射時 load 已經是 71（72 個跨 uid 孤兒，
  見 `ORPHAN_CLEANUP_NEEDED.md`）。微型題的驗收是毫秒級所以可發；
  **r530 那種重量級題庫（`lcb_3686` 要 46 s，而 10 s 是它凍結的常數）不可發。**
