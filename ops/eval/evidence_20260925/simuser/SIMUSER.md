# 模擬使用者驗收（2026-09-25，L-fake）

產品原則 4：先用模擬使用者驗過，才准花錢跑公開題庫。這一份回答的是
「**一台已經在用 pi 的機器，只照 README 打兩個指令裝 Vacant，之後照常用 pi，交出來的東西有沒有比沒裝好、對的有沒有被動到**」。

## 怎麼跑

- 機器：DABstep 題目映像（Ubuntu 24.04、Python 3.12、`/app/data/` 七個檔）＋ `apt install pipx`（機器原本就有的東西）＋ node 與 pi 0.87.1。
  一般使用者帳號，每個指令在一個新的登入殼層裡打。容器**不連網**（pipx／pip 讀本機 wheel 目錄，這是唯一和真實安裝不同的地方）。
- 模型：`ops/intake/mock_model.py` 照劇本回答（pi 設定成用它，就像使用者設定自己的模型供應商）。
- 每個情境 A（沒裝）和 C（裝了）各跑一次，都是全新的容器、同一個 `pi -p` 指令、同一份劇本。
- 重跑：`python3 ops/eval/simuser/run_simuser.py --image <映像> --wheels <wheel 目錄> --node /opt/node22 --pi-modules <pi 的 node_modules> --out <輸出>`

## 安裝（C 組做的全部事情）

```
$ pipx install vacant-network
  …（pipx 自己提醒 ~/.local/bin 不在 PATH；新開的登入殼層裡就有）
$ vacant install
  pi: global extension — /home/user/.pi/agent/extensions/vacant.ts
  not found on this machine: claude, codex, opencode (skipped; `vacant install --force` writes their config anyway)
[vacant install] done. Open your agent as usual; …
```

沒有契約、沒有設定檔、沒有金鑰、沒有環境變數。全文：`*_C/install_transcript.txt`。

## 結果

| 情境 | 劇本 | A（沒裝） | C（裝了） |
|---|---|---|---|
| `made_up_number` | 沒讀資料就寫了一個數字 | `87.12`（錯） | 退回 1 次 → 重算 → `91.85`（對） |
| `missing_answer` | 算出答案、沒寫答案檔就說做完 | 沒有答案檔 | 退回 1 次 → 寫了 `NL` |
| `correct` | 算了再寫 | `91.85` | `91.85`，**沒有退回**；4 通模型請求**逐位元組相同**（`correct_bodies_check/sha256.txt`） |

C 組的交件說明（`*_C/delivery.md`）寫出查了什麼、交件前改了什麼（例：`round 1: answer.txt line 1: "87.12" had no source in the record; the value was changed`）、
還沒驗證的（給的資料夾裡沒打開的 6 個檔）。pi 的 `-p` 模式沒有介面，說明只寫檔、不印到畫面。

## 這證明什麼、不證明什麼

- ✅ 只照 README 裝、照常用：退回送得到模型、模型改了之後交出去的是改過的檔、對的作答完全不受影響（模型看到的每一通請求都一樣）。
- ❌ **不證明真模型會照做**：劇本決定了模型看到退回之後的反應。真模型會不會照做、成績有沒有變好，是公開題庫評測要量的。
- 過程中發現並修掉的：Ubuntu 上只有 `pip` 時 `pipx install` 會因為缺 `python3-venv` 失敗（README 要寫「用系統的套件管理器裝 pipx」）；
  `vacant install` 對沒裝的 agent 印三行雜訊（改成一行）；一個 agent 都沒找到時不再說「done」。
