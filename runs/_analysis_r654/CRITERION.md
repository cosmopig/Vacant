# round654 判準（**寫在量測之前**；本檔 commit 完才開始量）

## 問題

`SPEC_GAIN.md:45-61` 把「等預算」定義成 **每題呼叫數**：ON=5、OFF-5x=5。
E3 的頭條結論「ON 等預算打不贏 OFF5」整個掛在這個會計單位上。

但 ON 的 5 次呼叫與 OFF5 的 5 次呼叫**內容量不一樣**：
- OFF5 = 5 次獨立 gen，每次 prompt 只有題目。
- ON = 1 次 gen ＋ 3 次 review（prompt 含題目＋候選碼）＋ 1 次 revise
  （prompt 含題目＋候選碼＋評審意見）。

⇒ **「呼叫數相同」不等於「算力相同」。** 沒有任何一輪量過 E3 的 token 帳。
`calls.jsonl` 每一筆 ok 呼叫都有 `usage.prompt_tokens` / `completion_tokens`
（本輪結構性確認：948 筆全有，ok 但缺 usage = 0），所以這是零 API、精確、可重放的。

## 量什麼

從 `runs/g_r443_gemma_lcb/calls.jsonl` 依 `meta.arm` 與 `meta.task_id` 聚合：

- 每臂**每題**的 prompt_tokens、completion_tokens、total_tokens、latency_ms、呼叫數。
- 只算 **ON 與 OFF5 兩臂都已完成**的 task_id（配對集合），避免半完成題污染分母。
- `ok=False` 的失敗嘗試沒有 usage ⇒ **不進 token 分子**，但**單獨報**次數與 latency，
  因為它們確實燒了牆鐘時間。

主指標 **R = ON 每題 total_tokens 中位數 ÷ OFF5 每題 total_tokens 中位數**
（中位數；平均數同時報，兩個都寫）。

## 事前決策規則

| R | 判定 | 要寫進 STATE 的話 |
|---|---|---|
| **≥ 1.10** | ON 在「等呼叫數」下實際多花算力 | 頭條「ON 等預算打不贏 OFF5」**被加強**：ON 佔了便宜還沒贏。STATE 必須註明「等預算＝等呼叫數，不是等 token」 |
| **≤ 0.90** | ON 實際更省 | 頭條**不完整**：正確寫法是「同呼叫數下分不開，但 ON 少用 X% token」。這是給 fable 收官輪的擋門，必須重寫結論措辭 |
| **0.90 < R < 1.10** | 兩種會計單位一致 | 「等預算」對會計單位穩健，記下數字，主結論措辭不動 |

completion_tokens 單獨再報一次同樣的比值（生成 token 才是 GPU 時間的主要來源），
**若 total 與 completion 落在不同格，以 total 為準判定、但兩個都寫出來**，不事後挑。

## 推翻條件（事前）

1. 若 ok 呼叫缺 `usage` 的比例 > 5% ⇒ 這把尺 **BROKEN**，照實寫「量不到」，
   不准用估算補（鐵律 2 的精神：量不到 ≠ 量到 0）。
2. 若冒出第三類（例如某 task_id 的呼叫數不是 5、或有 arm 為 None 的非 preflight 呼叫）
   ⇒ 照實寫、人眼確認、**不算進分子分母、不當場補判準**。
3. E3 未收官 ⇒ 這是**期中**數字，STATE 必須寫「rows N 行、sha256 前 8 碼」，
   不准寫成最終值。

## 不准做

不改 `ops/gain/gain_run.py`、不改 SPEC_GAIN、不動 E3、不起任何 run、
不寫 NEXT_MODEL=local、不碰展件。純離線分析。
