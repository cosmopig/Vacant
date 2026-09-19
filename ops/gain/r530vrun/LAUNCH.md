# r530vrun 發射紀錄（2026-09-19，vacant-dev／1003）

⚠ **非預註冊。** 判讀紀律見 `README.md` 最上面那一節。

## 機器與接線

| | |
|---|---|
| 執行機 | `user1@100.124.254.83`（1003），工作目錄 `/var/tmp/vacant_r530vrun/` |
| 模型端點 | `VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions`（LM Studio，`gemma-4-12b-it-qat` Q4_0，`state: loaded`） |
| agent | pi 0.85.1，`/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi` |
| node | `export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH` |
| 沙箱 | `auto` → **bwrap**（`network_isolated: true`、`write_confined: true`、`repo_visible: REPO_ABSENT`） |
| 併發 | **2 串**（`--shard 0:2`／`1:2`，埠 8880／8881）。吞吐 4 串封頂，同時間 Codex 的 L-real 與 Stage C 也在用這台 |

⚠ **不碰**別的 agent 的目錄（`/var/tmp/vacant_codex/`、`/var/tmp/vacant_cc/`、
`/var/tmp/vacant_opencode/`），也**不碰** `ops/gain/r530/`、`ops/gain/r535/`、`vacant/`。

## 逐步

```bash
export PATH=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin:$PATH
export VACANT_GAIN_API=http://100.119.113.56:1234/v1/chat/completions
PI=/home/user1/.local/opt/node-v22.23.2-linux-x64/bin/pi
cd /var/tmp/vacant_r530vrun/repo

# 0. 沙箱探針（量具先講清楚退到哪一級）
python3 -m vacant.vrun.sandbox --backend auto

# 1. 量 --test-timeout（零模型呼叫）
python3 ops/gain/r530vrun/probe_timeout.py \
    --out /var/tmp/vacant_r530vrun/probe --sandbox auto --parallel 2 --include-bad

# 2. 收據量具的**負控制**先跑（乾淨路徑通過不算數）
python3 -m vacant.vrun.verify_receipts --selftest        # → selftest: PASS

# 3. 冒煙一題兩格（接線壞掉不要用 40 格去發現）
python3 ops/gain/r530vrun/run_r530vrun.py \
    --out /var/tmp/vacant_r530vrun/smoke --tasks ow_18_taskorder \
    --stream smoke --pi-port 8880 --pi-bin $PI --test-timeout 20 --agent-timeout 600

# 4. 正式：40 格、兩條流
for i in 0 1; do
  python3 ops/gain/r530vrun/run_r530vrun.py \
    --out /var/tmp/vacant_r530vrun/run --shard $i:2 --stream s$i \
    --pi-port 888$i --pi-bin $PI \
    --test-timeout 20 --test-timeout-source "<probe 的數字＋為什麼不用規則值>" \
    --agent-timeout 900 --load-pause 8 &
done; wait

# 5. 計分＋收官表（零模型呼叫、可離線重跑）
python3 ops/gain/r530vrun/score_r530vrun.py --out /var/tmp/vacant_r530vrun/run

# 6. 收據：負控制已在第 2 步跑過，這裡驗**這一跑**
python3 -m vacant.vrun.verify_receipts \
    --glob '/var/tmp/vacant_r530vrun/run/cells/*/run' \
    --json /var/tmp/vacant_r530vrun/run/receipts_verify.json
```

## 兩個發射前踩到的東西（留著，免得下一個人再踩）

1. **`sha256_dir` 不排除 `__pycache__` ⇒ 旗標會誤報。** 冒煙那兩格的
   `ws_suite_sha256 != suite_sha256`，看起來像「agent 動過驗收」。逐檔 diff 之後
   `test_visible.py` **逐位元相同**，差的是 `tests_visible/__pycache__/`——
   worker 真的去跑了題庫附給他的那組可見驗收。
   ⇒ 雜湊改成排除 `wshash.EXCLUDED_DIRS`；`__pycache__` 本身另外記成
   `ws_suite_pycache`，因為「worker 有沒有用題庫給他的檢查」是**只有這個題庫
   量得到**的觀測（R535 的工作區裡根本沒有驗收）。
   **一個會誤報的旗標比沒有旗標更糟。**
2. **`--test-timeout` 的規則值不穩。** 同一支 probe 連跑兩次，「最慢那一格」
   換了人（`ow_01/hidden/parallel2` → `ow_11/visible/serial`），規則值從 1 秒變 2 秒。
   詳見 `RESULTS.md` 第一節。
