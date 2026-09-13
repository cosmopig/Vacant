# 1003 換模紀錄（2026-09-11 08:52Z，人類指示、Fable 執行）

人類指示原文：「你把 1003 的模型先記起來然後卸下來，換成跟 1004 一模一樣參數的，這個參數也要記錄以後寫在實驗紀錄裡面。」
目的：讓 1003 與 1004 成為**參數相同**的兩個推論後端，供 R529 跨題庫研究（與之後的 run）使用。
引用本檔的 run，其 `backend.json`／launch notes 應寫明用的是哪一台，因為兩台的 LM Studio **版本不同**（見 §四）。

## 一、換模前的 1003（`lms ps --json`，08:5x Z 之前）

| 欄位 | 值 |
|---|---|
| identifier | `qwen/qwen3.8-27b` |
| path | `qwen/qwen3.8-27b`（variant `qwen/qwen3.8-27b@q4_k_m`） |
| architecture／quantization | qwen35／Q4_K_M（4 bit） |
| sizeBytes | 17,742,040,464（17.74 GB） |
| contextLength／maxContextLength | 100,096／262,144 |
| parallel | 1 |
| ttlMs | 3,600,000（1 小時；卸載前顯示 59m / 1h） |
| status | idle，queued 0 |
| GPU（nvidia-smi） | RTX 3090，VRAM 23,653／24,576 MiB，util 5%，40 W |

（此外 `lms ls` 顯示 1003 磁碟上共 5 個模型、73.15 GB；gemma-4-12b-it-qat 已在其中。）

## 二、換模動作（1003 上，Git Bash，`lms`＝`/c/Users/w401/.cache/lm-studio/bin/lms`）

```
2026-09-11T08:52:25Z
lms unload qwen/qwen3.8-27b            → Model "qwen/qwen3.8-27b" unloaded.（VRAM 降到 128 MiB）
lms load gemma-4-12b-it-qat --context-length 262144 --parallel 4 --gpu max --identifier gemma-4-12b-it-qat -y
                                       → Model loaded successfully in 8.26s. (6.66 GiB)
探針 POST /v1/chat/completions  model=gemma-4-12b-it-qat  "Reply with exactly: OK"  max_tokens=64 temperature=0
                                       → reply="OK"  usage={prompt 21, completion 59 (reasoning 53), total 80}
2026-09-11T08:52:41Z
```

## 三、換模後的 1003 與 1004 對照（兩台皆 `lms ps --json`）

| 欄位 | 1003（100.119.113.56） | 1004（100.86.226.21） | 相同？ |
|---|---|---|---|
| identifier | gemma-4-12b-it-qat | gemma-4-12b-it-qat | ✓ |
| path | google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf | 同左 | ✓ |
| gguf 檔案大小（bytes） | 6,975,877,728 | 6,975,877,728 | ✓ |
| gguf sha256 | faff1a63667fac17ac5e777f47114688fcefea96e220e211aaa8d62c2c4561f1 | 同左 | ✓（逐位元相同） |
| architecture／quantization | gemma4／Q4_0（4 bit） | 同左 | ✓ |
| sizeBytes（lms 報） | 7,150,992,992 | 7,150,992,992 | ✓ |
| contextLength／maxContextLength | 262,144／262,144 | 262,144／262,144 | ✓ |
| parallel | 4 | 4 | ✓ |
| gpu offload | `--gpu max`（顯式） | LM Studio 預設（12B 於 24 GB 卡＝全載） | 行為相同；1004 未顯式指定 |
| ttlMs | null | null | ✓ |
| 載入後 VRAM | 13,326 MiB | 13,213 MiB（3 串生成中） | ≈ |
| GPU | RTX 3090 24 GB | RTX 3090 24 GB | ✓ |
| NVIDIA driver | 591.74 | 591.74 | ✓ |

## 四、兩台**不相同**的地方（必須跟著 run 一起記）

| 項目 | 1003 | 1004 |
|---|---|---|
| LM Studio 版本（`LM Studio.exe` ProductVersion） | **0.4.24.0** | **0.4.17.0** |
| lms CLI commit | ff50809 | 6041ae0 |
| lms 位置 | `C:\Users\w401\.cache\lm-studio\bin\lms.exe` | `C:\Program Files\LM Studio\resources\app\.webpack\lms.exe` |
| SSH | `w401-win`（Git Bash） | `w401@100.86.226.21`（cmd；複雜指令用 `powershell -EncodedCommand`） |

推論引擎版本不同 ⇒ kernel／取樣實作可能有差；**同一個 block 的各臂交錯在同一台**，所以配對比較不受影響，
但跨 block 的絕對值（交付率、token）可能混入版本差。R529 起每個 block 的 `backend.json` 記 endpoint，分析時要能依後端拆開描述。
1004 正在跑 R460R（預註冊條件），**不得為了對齊版本而動 1004**；要對齊只能動 1003，本次未做。

## 五、歷史備註

- 1003 先前兩次崩潰（2026-09-08／09）：一次 262k context 下 bad alloc（當時 qwen 27B 同時佔 VRAM），一次 context 被降到 49k 後三串併發撞 "Context size has been exceeded"（49k/4 < HPI 的 32k）。本次卸掉 qwen 後以 262k／parallel 4 載入，VRAM 13.3 GB，與 1004 相同。
- 1004 吞吐量測（同日）：aggregate completion tok/s 1 串 68 → 3 串 105–123 → 4 串約 136–145 → 6 串約 141；功耗 388/390 W 貼上限。1003 同卡同驅動，預期相同，未另量。
