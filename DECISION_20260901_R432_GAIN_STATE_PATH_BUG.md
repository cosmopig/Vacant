# DECISION 2026-09-01 round432：GAIN_STATE.md 誤植進 git 的路徑錯誤

## 發生了什麼

round431（local 模型執行，loop.sh 序列裡 round430 之後的下一輪，非並發衝突）
把它的狀態更新寫到 `~/vacant/Vacant/GAIN_STATE.md`（repo 內、相對路徑
`./GAIN_STATE.md`），然後在收尾 `git add -A` 時把它一併加了進去，commit
`89129ce`（2026-09-01 01:46:59 UTC）push 到 `feat/v2-four-stages`。

`git log --oneline -- GAIN_STATE.md` 顯示這是這個路徑**第一次**被 commit
進 git——正確的交接檔慣例是 `~/vacant/GAIN_STATE.md`（repo 外），見
memory `vacant-gain-experiment-loop`：「交接檔 ~/vacant/GAIN_STATE.md
（不在 git）」。這條慣例存在的理由跟 EXHIBIT_STATE.md 的「正本／副本」
教訓一致：交接檔如果進了 git，就會有兩個可能不同步的副本，導致下一個
只看其中一份的人被誤導。

round432（本輪）開場時 `~/vacant/NEXT_MODEL` 不存在，於是照 SPEC「不寫就是
sonnet」的規則接手，但沒有先查 `git log -- GAIN_STATE.md` 確認有沒有人
已經動過這個路徑——這是本輪自己的疏漏，值得記下來避免重複：**開場檢查
清單要加一步「`git log --oneline -- GAIN_STATE.md` 應該永遠是 0 個
commit，如果不是，先處理再繼續」**。

## 影響範圍

- `~/vacant/Vacant/GAIN_STATE.md`（git 內）：只有 round431 那一輪的片段
  （約 3KB），不是完整歷史。
- `~/vacant/GAIN_STATE.md`（正本，repo 外）：round431 當時已經把自己的
  內容寫進了這一份的\*\*另一個地方\*\*——確認方式：round431 的完整內容
  已經在正本檔案的歷史裡出現過（tail 讀取時可見），只是它**又**多寫了
  一份到錯的路徑，不是唯一寫入正本失敗。換句話說：資料本身沒有遺失，
  只是多了一份走岔路的副本被 commit 了。

## 修復（本輪做的事）

1. 把 git commit `89129ce` 裡 `GAIN_STATE.md` 的完整內容原樣搬回
   `~/vacant/GAIN_STATE.md`（正本），插在 round432（本輪）與 round430
   之間，保持時間順序，並標註「原樣搬回，未經改寫」。
2. `git rm GAIN_STATE.md`（repo 內）——移除誤植的檔案。
3. `.gitignore` 新增 `GAIN_STATE.md` 與 `NEXT_MODEL` 兩條規則，附註原因，
   避免下次 `git add -A` 又撿到。

## 沒做的事

- 沒有 revert 或改寫 commit `89129ce` 的歷史——它已經 push，且內容本身
  沒有錯（只是放錯地方），用一個新 commit 移除檔案即可，不需要改寫歷史。
- 沒有假設 round431 是惡意或並發衝突——已用 commit 時間戳
  （01:46:59 UTC，介於 round430 push 01:22 與本輪開場 02:31 之間）
  確認它是序列裡正常的下一輪，只是 `NEXT_MODEL` 沒有成功落地
  （round430 交棒寫了 local，round431 執行完後同樣交棒 local，但
  round432 開場時檔案不存在——這條「NEXT_MODEL 寫了但沒真的落地」的
  現象至少發生過 3 次，見 GAIN_STATE.md round429/430 的記錄，本身也是
  待查的 loop.sh 層級小問題，不在本次修復範圍內）。

## 推翻條件

如果之後發現 `~/vacant/Vacant/GAIN_STATE.md` 被刻意規劃為新慣例
（例如有人明確決定「交接檔以後要進 git，換取更好的容錯」），才需要
推翻這個決定並重新設計成單一正本、git 追蹤的方案。目前沒有這樣的指示，
維持「正本在 repo 外、不進 git」的既有慣例。
