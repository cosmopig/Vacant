# E1′ 設計紀錄

| 時間（UTC） | 決定 | 依據 |
|---|---|---|
| 11-26 04:30 | 方案經 vacant-hope 同意，六點修改：起始成果是已驗證的正確版本且夠大（程式 8–10 個標準解、文件由真值生成）；先校準；S 臂提示與 B0 相同；加 B0×3（程式）；評測在無網路沙箱；行為變更輪可做才做 | vacant-hope 11-26 |
| 11-26 04:35 | EvalPlus 沒有同一題的變體測試 ⇒ 不做「行為變更」輪（只有新增 r1–r3、改名 r4、確認 r5） | EvalPlus 資料結構 |
| 11-26 04:46 | 第一次校準作廢（`~/dev/ops/e1/cal_*_run_VOID_pi_cfg_readonly`）：沙箱裡 pi 的設定目錄唯讀、pi 要寫 auth.json，agent 0 通呼叫就結束；改成每一跑的去敏副本可寫 | runner log |
| 11-26 04:46 | 文件鏈：值可以含「: 」（例：「Nasdaq: SRPT」）⇒ 標籤／值改用 em dash 之後第一個「: 」切 | build_doc_chains 驗證失敗 |
| 11-26 04:55 | **校準結果（各 3 條校準鏈、只跑 B0、qwen3.5-9b）**：程式整鏈成功 1/3（code_002 在改名輪把 10 個既有函式全弄壞）、文件整鏈成功 1/3。都落在目標 30–70% 內 ⇒ **不調起始檔大小與鏈長**（程式起始 8–10 函式、5 輪；文件 20 條宣稱、4 個真實修訂）。只依據這 6 條校準鏈。 | `~/dev/ops/e1/cal_code_run`、`cal_doc_run` |
| 11-26 05:00 | 程式鏈建構排除遮蔽內建名稱的題目（MBPP 的 `sum` 讓同檔其他函式壞掉）與校準鏈用過的題目（正式 12 條與校準 0 重疊） | build_code_chains 驗證失敗 |
| 11-26 05:00 | 文件類正式 12 條＝批 A 教材的軟體 s01–s06、公司 s08–s13（校準用 s07、s16、s17）；足球員教材還在抓，不進 E1′ | 教材現況 |
| 11-26 05:00 | 文件的獨立評測是整串文字比對（正規化空白與強調符號），比「全部數字」更嚴 | evaluate.py |
| 11-26 05:25 | **Haiku 是否加跑的條件（事前寫下，9B 結果出來之前）**：只有在 9B 上，依預註冊判讀 1，「S 對 B0」的回歸率較低（且新需求完成率不差超過 10 個百分點）**或**整鏈成功率 S 高於 B0 時，才加 Haiku（每類 6 條；Claude Code 在 bubblewrap 裡，唯讀掛登入憑證、網路只放行 Anthropic 與本機來源伺服器，負控制重驗）。9B 上沒有這個訊號就不跑 Haiku。 | vacant-hope 11-26 |
| 11-26 08:45 | **新增 Claude Code（`model.agent: "claude"`）第二種 worker 與真實網路白名單**：worker 跑在 `bwrap --unshare-net`，透過綁入沙箱的單一 UNIX socket 連至宿主 `AllowlistUnixProxy`（沙箱內 `proxy_bridge.py` 轉發 `127.0.0.1:<port>` 並設 `HTTP_PROXY`/`HTTPS_PROXY`、清空 `NO_PROXY`）。實測 Claude Code 2.1.329 在 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`、`DISABLE_TELEMETRY=1`、`DISABLE_AUTOUPDATER=1` 下僅需放行 **HTTPS CONNECT `api.anthropic.com:443`**（零其他外部主機）與**明文 HTTP `*.e1-sources.example`／`*.d2-sources.example`（port 80，轉發至本機 `source_server.py`）**。僅複製 `~/.claude/.credentials.json` 唯讀掛於 `/sandbox_home/.claude/.credentials.json`。`run_claude_negative_controls` 必過才准啟動。 | 實測探針＋`ops/e1/netproxy.py` |
| 11-26 09:13 | **Claude Haiku B0 冒煙驗證（`e1smoke_haiku.json`、`claude-haiku-5-5`、`B0` 單臂）**：`code_001` 5/5 回合全過（0 回歸、`$0.013476`）、`doc_s16` 4/4 回合全過（0 回歸、`$0.019847`），總費用 `$0.033323`。宿主代理 `proxy.jsonl` 共 62 筆請求（`CONNECT api.anthropic.com:443` 27 筆 / `2,364,827 B`、`GET doc_s16.e1-sources.example:80` 35 筆 / `5,776,666 B`），0 筆被拒、零其他外部主機需求。 | `/tmp/claude-1000/agy_e1/smoke_haiku` |
| 11-26 08:50 | **Haiku 範圍縮小（偏離事前條件，vacant-hope 11-26、額度）**：只跑程式類 6 條、三臂 B0／S／B2；文件類不跑。理由：文件類在 9B 上是地板效應（各臂整鏈 0–1/12），而且 S 的範圍來自已被否證的來源推斷（文件類 S 沒有保護效果、範圍內錯 59），跑了也無法判讀。 | vacant-hope 11-26 |
