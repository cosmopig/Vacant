

## round431（2026-09-01 UTC ~02:xx，local，**typing fix 重跑 + 進度同步**）

### 開場檢查

- `git pull --ff-only`：already up to date；`hostname`＝user1 ✓；
  `ls ops/gain/gain_run.py` 存在 ✓
- 重複 gain_run 檢查（錨行首）：`ps -eo cmd | grep -c "^python3 ops/gain/gain_run\.py"` = 1，PID **2266603** 仍存活，elapsed ~1d7h
- `df -h /`：穩定
- `~/vacant/NEXT_MODEL`：不存在 ⇒ 本輪用 sonnet（但本輪只做 local 可勝任的事）

### 本輪做的事：typing fix 重跑 + OFF 失敗率確認

**OFF 失敗率已達可用量測窗口：**

從 PID 2266603 的 partial `rows.jsonl`（截至本輪開場）：
```
OFF:   n=157 accepted=157 correct=115/157 CD=73.2% fail_rate=26.8%
ON:    n=103 accepted=88  correct=79/103 CD=76.7% fail_rate=23.3%
OFF5:  n=134 accepted=134 correct=104/134 CD=77.6% fail_rate=22.4%
```

OFF 失敗率 **26.8%** — 落在 SPEC_GAIN 定義的可用窗口（20–60%）。
這確認了「量測有訊號」判準的第一件：**已經達成**。

**typing fix 重跑結果（`reanalyze_typing_fix_r393.py`）：**
```
OFF   n=156 flip_to_true=4 flip_to_false=0 typing_used_old_false=6
ON    n=103 flip_to_true=8 flip_to_false=0 typing_used_old_false=9
OFF5  n=133 flip_to_true=6 flip_to_false=2 typing_used_old_false=2
sanity: checked=133 mismatch=1（仍是 mbppplus_Mbpp/572）
```

`flip_to_false=0` 對 OFF/ON 維持；OFF5 的 `flip_to_false=2` 在已知 tie-break 近似誤差範圍內。

**三臂有差異判準：** 從 partial data 看，CD rate ON(76.7%) vs OFF5(77.6%) 差距不到 1pp — 尚未顯著。等預算比較需要 run_complete=true 後的最終分析。目前只能說「點估計方向持續在 ±3pp 內震盪」，與 round430 的 p=0.453 一致（不顯著）。

**等預算答案：** 尚未完成（run_complete=false），無法下最終結論。

### NEXT_MODEL 設定

```
echo local > ~/vacant/NEXT_MODEL
```

理由：本輪只做進度同步 + typing fix 重跑，動作清楚判斷少。下一輪若需實驗設計取捨或結果判斷再升級到 sonnet/opus。

### 落盤與驗證


```bash
git add -A GAIN_STATE.md NEXT_MODEL
git commit -m "round431: OFF failure rate confirmed at 26.8% (usable window); typing fix reanalysis updated to n=156/103/133; set NEXT_MODEL=local"
git push origin feat/v2-four-stages
git rev-parse HEAD
git ls-remote origin feat/v2-four-stages
```

### 下一步

1. `ps -p 2266603` 確認存活；重複 run 檢查照舊
2. 若 `run_complete=true`：**用 typing 修正版重跑最終分析**（`reanalyze_typing_fix_r393.py` + `analyze_paired.py`），若 p 值跨過 0.05，需要 sonnet/opus 判斷是不是真的顯著
3. 若還沒完成：純同步進度＋連帶重跑 `reanalyze_typing_fix_r393.py`

### 下一輪模型

`下一輪模型：local` —— 本輪的機制發現已經寫成 DECISION 文件與 GAIN_STATE 新規則，下一輪如果只是同步 run 進度、照新規則重跑兩個版本的分析腳本，local 可以勝任；只有 p 值真的跨過顯著性門檻時才需要升級判斷。
