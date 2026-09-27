# Colab A100 上複製 1003／1004 的 gemma 後端（2026-09-27）

`colab` CLI（google-colab-cli 0.7.4）＋ LM Studio 無介面版（llmster）。**只在 VM 裡打本機端點量測**，沒有開公開網址。

## 對齊的四樣（全部量過）

| 項目 | 值 | 怎麼確認 |
|---|---|---|
| GGUF | `google/gemma-4-12B-it-qat-q4_0-gguf` **revision `f6e7774e6148`**（06-05 首發） | 主模型 sha256 `faff1a63…c4561f1`、mmproj `e70b0e5c…` 在 VM 上逐位元 MATCH；與 1004 `Get-FileHash` 相同 |
| 引擎 | LM Studio `llama.cpp-linux-x86_64-nvidia-cuda12-avx2@2.46.0` | 與 1004 同版號（1004 是 win 版的 2.46.0；1003 是 2.34.0） |
| 載入參數 | context 262144、parallel 4、GPU max、identifier `gemma-4-12b-it-qat`、vision 開 | `lms ps --json`；顯存 13,390 MiB（1004 約 13.2GB） |
| 思考 | 預設**會思考**；`reasoning_effort:"none"` 關掉後 17 隻羊那題 completion 31 token（與 1004 當年量到的一樣） | 探針 |

⚠ **HF `main` 已經不是這個檔**（07-15 換 chat template、07-17 換「修正版」權重）。一定要指定 revision。
⚠ 權重、引擎版本、參數對得上；**輸出不會逐位元相同**（不同 GPU 的數值差異）。

## 吞吐（A100 40GB，Colab Standard，12 vCPU；關思考；每條 512 token）

| 同時 | 總輸出 | 1004（3090，09-11） |
|---|---|---|
| 1 | 64 tok/s | 68 |
| 2 | 93 tok/s | 98 |
| 4 | 106 tok/s | 136–145 |
| 8 | 98 tok/s（超過 parallel 4 就排隊） | — |

約 2 萬 token 提示首字 11.1 秒。**A100 沒有比 3090 快**：4 條同時時 GPU 使用率只有 34–40%、功耗 100–160 W／400 W，
LM Studio 的推論行程 CPU 約 110%——瓶頸在 LM Studio 這一層，不在卡。要用滿 A100 得換引擎或加平行度，
那就不再是「與 1003／1004 一模一樣」。

## 費用

實際耗用 **5.30 CU／小時**（`colab usage`；不是第三方網站寫的 15）。這次設定＋量測共 0.96 CU。
⚠ Colab 條款：所有方案都禁止「與互動式運算無關的網頁服務」與「連到遠端代理」——開公開端點給外面的批次打是灰色地帶。

## 重跑

```
colab new -s gemma-a100 --gpu A100
colab upload -s gemma-a100 setup_gemma_lmstudio.py /content/setup_gemma_lmstudio.py
echo 'import subprocess; subprocess.Popen("nohup python3 /content/setup_gemma_lmstudio.py > /content/setup.stdout 2>&1 &", shell=True)' | colab exec -s gemma-a100
# 約 5 分鐘後 /content/setup.log 出現 SETUP_DONE；用完一定要 colab stop -s gemma-a100
```
