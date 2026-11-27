# Haiku 帶寬搜尋：單次原生基線的探索性校準

範圍：證據導向控制器實驗在 Claude Haiku 上的探索性校準（工作者 `claude-haiku-5-5`，經 Claude Code headless 執行）。雲端工作階段，分支 `claude/wonderful-babbage-0l9zcn`。

## 結論

在我們試過的五個公開題庫上，Haiku 原生單次都在 87–100%，四臂無法區分，控制器沒有可發揮的空間；這不是「控制器在強模型上無效」的證據，而是沒有量得到差別的地方。

## 五個題池（A 臂單次，hidden 半獨立評分）

| 題池 | 內容 | 結果 | 來源 |
|---|---|---|---|
| Exercism Python（修正 3 題池） | 37 題候選 | 37/37（100%） | `ops/redo/results/ctl_haiku_20261127/CALIBRATION_haiku37_A.md` |
| cc40 | Codeforces 1200–3500，附 Python 參考解 | 40/40（100%） | `ops/redo/results/ctl_hardpool_20261127/CALIBRATION_haiku_cc40_A.md` |
| cchard | Codeforces ≥2400，附 C++ oracle | 35/39（89.7%） | `ops/redo/results/ctl_hardpool_20261127/cchard/` |
| cchard-L | cchard 加上大型與最壞情況測資 | 33/37（89.2%） | `ops/redo/results/ctl_haikuband_20261127/cchardL/` |
| polyglot3 | Aider polyglot 的 C++／Go／Rust | 26/30（86.7%） | `ops/redo/results/ctl_haikuband_20261127/polyglot3/` |

預註冊：
- `decisions/DECISION_20261127_EVIDENCE_CONTROLLER.md`（雲端修正 C4–C6）
- `decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HARDPOOL.md`
- `decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md`

## 缺陷與限制

- polyglot3：依測試函式切分可見與 hidden 半，造成兩題（cpp `queen_attack`、rust `luhn_from`）整個測試檔編譯失敗（hidden 半用到可見半沒碰過的 API）。另外兩題失敗（go `simple_linked_list` 4/7、rust `acronym` 4/5）的原因沒有逐一查證。
- cchard-L：大型輸入由 Haiku 生成，只靠兩份 C++ 參考解的結果一致來篩選，沒有對照題目限制獨立驗證。
- 沒有納入 Java（沙箱沒有 gradle，JUnit 需要網路）。
- Exercism 與 2021 年 Codeforces 題目被訓練資料暴露的可能性無法排除。
- Codeforces 題庫的測資是小型變異輸入；cchard 的錯誤解被 hidden 半擋下的中位數只有 0.70，規模與逾時型錯誤大多測不到。
- 沙箱只對 worker 的 shell 做作業系統層級的隔離；檔案工具是靠 CLI 規則限制。

## 沒有做的事

- 不做程序生成題池。
- 不做訓練截止日之後的題池。
理由：方向設定的那次工作階段做了這個決定（時間與成本）。

## 仍在進行中

- Haiku 在 cchard 上的四臂批次（結果將另外回報）。
- Devin 的校準。

## 花費

依各結果檔加總，Haiku 校準約 **$2.4**（Exercism $0.1155、cc40 $0.3611、cchard $0.7197、cchard-L $0.9550、polyglot3 $0.1904；另含 cchard-L 題目生成約 $0.07 與負控制、探針數美分）。
