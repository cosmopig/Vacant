# polyglot3 校準（2026-11-27）：Haiku A 臂 26/30（86.7%），在 25–70% 之外 ⇒ 不跑正式批次

預註冊：`decisions/DECISION_20261127_EVIDENCE_CONTROLLER_HAIKUBAND.md` 候選 2。來源 Aider-AI/polyglot-benchmark（commit 7e0611e7）的 C++／Go／Rust Exercism 練習；Java 因沙箱無 gradle 且依賴要網路而排除。

## 量到的
- 題池：C++ 15、Go 2、Rust 13＝30 題（機械資格＋有效性後；排除原因逐題在 `bank_polyglot3_MANIFEST.json` 的 `excluded`）。每題 ≥10 個原生測試函式，依種子切可見／hidden；參考解兩半全過、空殼兩半全不過。
- Haiku A×1、jobs 4、infra_void 0：**hidden 全過 26/30＝86.7%**（序列重評，`CALIBRATION.md`／`table.json`）。C++ 14/15、Go 1/2、Rust 11/13；費用 $0.190；牆鐘最長約 1 分鐘級（整輪 <15 分鐘）。
- 失敗 4 題：cpp queen_attack（hidden 0/7）、rust luhn_from（0/7）、go simple_linked_list（4/7）、rust acronym（4/5）。
  前兩題的 0/7：可見半驗收放行，但 hidden 半的測試用到可見半沒測到的 API（C++ `board.black()` accessor；Rust `Luhn::from(String)`），整個測試檔編譯失敗 ⇒ 全部失敗。
  這是「依測試函式切半」造成的編譯全有全無效應（**已實測看到編譯訊息**；是否也發生在 simple_linked_list／acronym 只有部分重現，未逐一查）。
- 沙箱：Rust／Go／C++ 工具鏈在沙箱內實跑通過（`toolchain_probe.stream.jsonl`）；負控制（`negctl_poly.json`）第二次 25/25（第一次 worker 拒絕送出 B／T 探針，無效）。
- 憑證掃描（`credscan.json`）：37 個命中全是誤報（30 個是 Claude CLI 自己寫在沙箱 HOME 的 policy-limits signature、7 個 `agent.log` 內的 `\n` 開頭長字串）。是否敏感未驗證。

## 推論（未驗證）
- Aider 選的是「許多模型失敗」的難題，但這個 Haiku 家族在這些 Exercism 題上仍接近天花板；失敗多來自切分造成的 API 缺口，不是演算法難度。
- 與 Python（37/37）、cchard（35/39）、cchard-L（33/37）一致：Haiku 在公開、有自帶測試的練習型題池上都在 85–100%。
