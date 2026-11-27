# 實驗 N（Colab L4、E4B，探索性）：程序性提示 AP 對中性段落 AC

> 計畫：`ops/redo/plans/expN_exam37_colab_e4b.json`。prereg 見 `decisions/prereg/PREREG_20261127_EXPN_UPFRONT_VERIFICATION.md` 與它的修訂節：AN 依 KS-1 HOLD、改跑 AP。
> 後端：Colab L4、vLLM 0.30、gemma-4-E4B-it-qat，11:43–12:15Z。37 題 × 2 次 × 2 臂＝148 格，infra_void 0。
> 結果檔：`~/dev/ops/redo_runs_colab/expN_exam37_colab_e4b_20261127T114333Z_n7/run`；摘要複本 `ops/redo/results/expN/expN_exam37_colab_e4b_summary.json`。
> 工作區沒有任何測試（exam37 題庫），AP 要求的「執行你能執行的檢查」只能靠 agent 自己寫。

| | AC（中性） | AP（程序性） | 配對（AP 對 AC） |
|---|---|---|---|
| 隱藏評分成功 | 23/74（31.1%） | 26/74（35.1%） | +4.1pp，b=7、c=10，McNemar p=0.63 |
| 真的執行了檢查 | 0/74 | 23/74（31.1%） | p<0.001 |
| 聲稱通過 | 0/74 | 6/74 | p=0.031 |
| 聲明與實際不符（謊報） | 0/74 | 0/74 | — |
| 平均牆鐘／token | 65 秒／5.7k | 122 秒／10.1k | |

- **讀法**：程序性要求讓 E4B 有三成的格真的去執行檢查（AC 一次也沒有），牆鐘和 token 大約變成兩倍；但隱藏評分的成功率**沒有量到差別**（+4pp、p=0.63）。兩臂都沒有謊報：AC 根本不聲稱，AP 聲稱的 6 格都和實際相符。
- **限制**：
  - 每格 1800 秒單次，37 題。
  - 謊報分類器是保守的規則，每臂附了 10 個樣本供人工核對，**尚未人工核對**。
  - Colab vLLM 後端，和本機分開判讀。
  - AN（告知會被驗收、會被記錄）**沒有跑**：KS-1 HOLD，等擁有者決定。
