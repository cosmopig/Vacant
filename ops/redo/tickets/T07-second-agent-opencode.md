# T07 — 換 agent：OpenCode（S4；迴圈在父行程，理論上不用改 harness）

**前提**：T04 的 state＝EFFECTIVE，T06 已發射或完成。**規模**：只新增計畫檔；0 行 harness 碼。

## 步驟
1. 先手動確認一行 headless 指令在題目工作區裡跑得動、而且用的是本機模型（過去的格子用 `opencode run`；
   看 `ops/vlab/packets/e006_opencode_polyglot.md` 的設定）。
2. 複製 `smoke2_…`／`screen16_…` 成 `…_opencode_gemma12b.json`：改 `id`、`agent.argv`、`agent.env`，
   `agent.config_dir` 拿掉或改成 OpenCode 的，`agent.usage` 設 `"none"`（事件流格式不同，呼叫數記 null，不填 0）、
   `agent.infra_re` 視需要補 OpenCode 的連線錯誤字樣。commit。
3. 冒煙 2 對 → 篩選 16 對 → GO 才上 34×5。結論分開寫，不與 pi 的數字併表。

## 注意
- `usage: "none"` 時「工作區沒動＋0 次呼叫」這條 void 規則不作用，只剩錯誤字樣那條。冒煙時把端點關掉跑一格，
  確認它被記成 infra_void 而不是一次失敗的嘗試；不是的話先補 `infra_re`。

## 票尾（做完填這三行，再把票移到 done）
- commit：
- 驗收指令的實際輸出（逐字貼最後一行）：
- 沒做完的：
