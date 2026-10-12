# v3.5 對抗審查（run `wf_be2c190f-b20`）：10 條都重現，全部修掉

| # | 嚴重度 | 發現 | 怎麼修 | 回歸測試 |
|---|---|---|---|---|
| 0 | high | Line-in-request check is a plain substring test, so a file whose values differ from the pasted text still scores 100% 'given' | 整段連續比對（前後是字的邊界）取代逐行子字串 | `test_v35_a_different_version_pasted_is_not_the_file`（前綴值、前綴結尾） |
| 1 | medium | The 90% threshold marks a file as given when the pasted text is a different version and the task depends on the difference | 同上：全文要整段在請求裡，沒有 10% 的寬容 | 同上（一行不同、多一行） |
| 2 | medium | No size floor and no count of repeated lines: short files and one-token-per-line data count as 'given' when the request mentions the possible values | 至少 80 位元組；整段比對也擋掉重複行與順序 | `test_v35_short_file_matched_by_coincidence_is_not_given` |
| 3 | medium | Line matching is plain substring matching, so short lines count as 'content already in the request' when they only appear inside other text | 整段比對＋字的邊界 | 同上 |
| 4 | medium | The 10% slack treats a stale or partly pasted copy as the file, and the note then says 'content already in the request' | 不再有部分比對；說明只在整段對上時寫「已經在請求裡」 | `test_v35_a_different_version_pasted_is_not_the_file` |
| 5 | low | delivery.json does not record given_in_request, so named ≠ opened ∪ not_opened | `delivery.json` 加 `given_in_request`／`dir_given_in_request` | `test_v35_content_in_the_request_is_told_as_such_in_the_note_json_and_screen` |
| 6 | low | Folder members whose content is in the request vanish from the delivery note and are not explained on screen | 資料夾那一行也寫「已經在請求裡」；畫面上另外數 | 同上 |
| 7 | low | given_inline costs O(lines × prompt) with no early exit: +8 s on every Stop for a 200 KB prompt with 30 candidate files | 每個檔一次 `str.find`：30 個 60 KB 的檔對 200 KB 的請求 0.05 秒（原本約 8 秒） | （量測，見 commit 訊息） |
| 8 | low | Docstring says different line-break positions still match, but a line break inside CJK text in the prompt stops the match | 兩個中日韓字之間的空白拿掉再比；邊界也認中日韓字 | `test_v35_chinese_text_wrapped_differently_still_counts` |
| 9 | low | The new delivery-note wording has no test; the test comment says test_zero_stop covers it, but nothing does | 補真的 Stop 的測試 | `test_v35_content_in_the_request_is_told_as_such_in_the_note_json_and_screen` |

每一個防呆都做過變異：拿掉整段比對、拿掉邊界、最小值改 1、拿掉中日韓換行處理、整個關掉——各自至少一個測試會失敗。
