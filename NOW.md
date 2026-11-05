# NOW.md — r1044（11/05）

## 本輪完成
- **vq-5nz.21（P1，已關）**：「重複命令每次都失敗」的針對性提示（contrast3 dabstep-23
  localized 歸因：同一行式 ×34 全 SyntaxError、從無結果，舊提示「已得到結果後」前提不成立）。
  5748a6b9（auto/qwen27b，未 push——loop 輪末自動 push）：
  - `detect_tool_loop` 自 `tool_execution_end` 依 toolCallId 關聯執行結果：全敗⇒`all_failed`＋
    `error_class`＋`error_sample`（無 end 事件＝未知、欄位缺省、不造假；至少一次成功⇒`all_failed=False`）。
  - localized 提示全敗分支：點名「每次都失敗（SyntaxError: invalid syntax）」＋具體語法規則
    「把程式碼寫成 .py 檔案後執行（不要一行式拼接多條語句）」＋「確認執行成功、結果正確後直接把結果寫入交付物檔案」；
    不帶「已得到結果」假前提。generic 對照臂定義不變；觀察只進提示，不改裁決／停滯／退出碼。
- **vq-5nz.19（P1，驗收已關）**：auto/worker `4b7a8749` CI 🟢 4827 passed / 71 skipped / 1 xpassed
  （collected 4898 ≥ 4870）、0 failed——15 個 reqloop 紅測試全綠。

## 驗收（本輪）
- 1 TDD 測試先紅後綠（`test_localized_prompt_names_failed_loop_error_class_and_escape`）；
- reqloop 4 檔 **156 passed**（上輪 155）；`python -m vacant_network.reqloop.repair --selftest` **11/11**；
- 真實 log 驗證：dabstep-23 localized r1 log⇒`all_failed=true`、34/34 失敗、`error_class=SyntaxError`、
  提示點名錯誤類＋寫 .py 逃路＋跑通即寫交付物（舊提示該處是假前提）。

## 未做／等
- **vq-6rp**（dabstep-1753 模型側硬缺口）：/srv/vlab/queue 空（0 任務），等點名；未點名＝未發射。
- **vq-5nz.6**（G2 停滯草稿換方法驗證）：未發射（未點名）。
- **auto/qwen27b `5748a6b9` CI**：loop 輪末 push 後查一次（不輪詢；未完成＝UNKNOWN）。
- dabstep-10 generic stalled（contrast3）：n=1 不歸因；未來 effects 再現同型再開票。
- vq-p9g（xpass 除 marker）、vq-ifn（P99 門重設計）：待點名。

## Next（r1045）
1. 查 `5748a6b9` CI（一次；未完成記 UNKNOWN，不輪詢）。
2. vq-6rp 若被點名（/srv/vlab/queue 有任務或 reviewer 點名）→ 按預註冊口徑發射 G2；
   否則待命，不造進度、不寫離線審計腳本充當進度。
3. 紀律：未讀 hidden/scorer；未跑全量 pytest；不 push（loop 自動 push）；不動 main；缺值 UNKNOWN。
