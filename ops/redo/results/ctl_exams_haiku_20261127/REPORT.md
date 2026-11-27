# Haiku 驗收考卷品質報告（37 題 Exercism；探索性前導）

決定檔：`decisions/DECISION_20261127_HAIKU_EXAMS.md`。考卷凍結於 `ops/redo/exams_haiku_20261127/`（見 MANIFEST.json），量測期間未改。
環境：Python 3.13.18、pytest 9.2.0、bubblewrap 0.9.0（bwrap：無網路、唯讀系統、一次性可寫工作目錄、30 秒時限）。

## 1. 錯解池

候選 151 個（Haiku 寫的 148、Devin 失敗交付 3；沒有 Haiku 的失敗交付——Haiku 校準 37/37 全過）；入選 110（Haiku 107、Devin 3）。丟棄原因：{'passes_none_of_original_tests': 16, 'passes_all_original_tests': 25}。
每題入選數：{0: 4, 1: 2, 2: 6, 3: 6, 4: 17, 5: 2}（鍵＝入選數，值＝題數）。

## 2. 參照點：原始完整 Exercism 測試檔

對參考解：逐測試通過 100.0% (760/760)；平均每題 20.5 個測試。
對入選錯解：**依入選條件＝100% 攔下（循環論證，不是量到的能力）**；另報：入選錯解平均失敗的測試占比 23.6%。

## 3. 每種考卷總表

| 種類 | 有考卷/37 | 無法解析 | none | 平均斷言數 | 平均測試函式數 | 參考解逐測試通過 | 參考解逐斷言通過（unreached 算失敗） | 參考解整份全過 | 錯解拒絕（全部） | 錯解拒絕（只算參考解全過的考卷） |
|---|---|---|---|---|---|---|---|---|---|---|
| XM | 37 | 0 | 0 | 18.6 | 12.9 | 87.9% (421/479) | 88.8% (612/689)（unreached 0） | 75.7% (28/37) | 87.3% (96/110) | 88.0% (81/92) |
| XMV | 37 | 0 | 0 | 13.2 | 10.9 | 86.3% (339/393) | 87.5% (427/488)（unreached 1） | 70.3% (26/37) | 72.7% (80/110) | 73.9% (65/88) |
| PB | 37 | 0 | 0 | 29.9 | 17.6 | 91.8% (597/650) | 89.8% (992/1105)（unreached 40） | 70.3% (26/37) | 84.5% (93/110) | 81.8% (72/88) |
| EX | 0 | 0 | 37 | n/a | n/a | n/a (0/0) | n/a (0/0)（unreached 0） | n/a (0/0) | n/a (0/0) | n/a (0/0) |

「整份全過」分母含無法解析者（算不過）；匯入失敗或逾時的考卷（參考解 collect_error/timeout）：XM 0, XMV 1, PB 0, EX 0。

## 4. 逐題

格式：斷言數／參考解逐測試通過/總數／錯解拒絕數/入選錯解數。

| 題 | 入選錯解 | XM | XMV | PB | EX |
|---|---|---|---|---|---|
| ex_kindergarten_garden | 0 | 13／1/11／0/0 | 14／12/14／0/0 | 19／13/14／0/0 | none |
| ex_ocr_numbers | 0 | 13／5/12／0/0 | 10／2/9／0/0 | 13／2/10／0/0 | none |
| ex_circular_buffer | 1 | 42／4/16／1/1 | 13／2/7／1/1 | 47／10/18／1/1 | none |
| ex_high_scores | 4 | 11／11/11／4/4 | 11／4/4／3/4 | 16／13/13／2/4 | none |
| ex_simple_cipher | 1 | 13／11/11／1/1 | 10／10/10／1/1 | 32／16/16／1/1 | none |
| ex_binary | 0 | 18／13/13／0/0 | 13／10/10／0/0 | 26／31/33／0/0 | none |
| ex_octal | 4 | 16／8/11／2/4 | 12／9/12／1/4 | 33／11/14／4/4 | none |
| ex_yacht | 4 | 26／19/19／3/4 | 19／8/8／1/4 | 34／28/28／2/4 | none |
| ex_luhn | 4 | 15／15/15／3/4 | 0／13/13／0/4 | 30／17/17／4/4 | none |
| ex_sublist | 4 | 18／14/14／4/4 | 11／4/4／3/4 | 27／24/24／4/4 | none |
| ex_say | 3 | 17／12/12／3/3 | 1／11/12／3/3 | 25／16/16／3/3 | none |
| ex_dnd_character | 5 | 15／8/8／4/5 | 10／10/10／4/5 | 20／14/14／5/5 | none |
| ex_twelve_days | 4 | 10／9/9／4/4 | 8／8/8／4/4 | 18／12/13／3/4 | none |
| ex_atbash_cipher | 4 | 16／16/16／4/4 | 11／11/11／4/4 | 22／18/19／4/4 | none |
| ex_queen_attack | 4 | 13／15/15／4/4 | 14／14/14／4/4 | 27／17/17／4/4 | none |
| ex_prime_factors | 4 | 12／12/12／4/4 | 12／12/12／4/4 | 17／11/11／3/4 | none |
| ex_scrabble_score | 2 | 25／13/13／2/2 | 10／10/10／2/2 | 24／15/15／2/2 | none |
| ex_series | 4 | 15／11/11／4/4 | 12／0/0!／4/4 | 21／15/15／4/4 | none |
| ex_binary_search_tree | 3 | 44／13/13／3/3 | 25／10/10／3/3 | 66／15/15／3/3 | none |
| ex_pascals_triangle | 5 | 16／12/12／4/5 | 11／10/10／3/5 | 23／16/16／4/5 | none |
| ex_tournament | 3 | 10／8/8／3/3 | 15／11/11／3/3 | 26／16/16／2/3 | none |
| ex_change | 4 | 19／10/10／2/4 | 10／9/9／2/4 | 14／11/11／2/4 | none |
| ex_killer_sudoku_helper | 4 | 13／9/13／4/4 | 9／9/9／4/4 | 21／14/18／4/4 | none |
| ex_palindrome_products | 3 | 12／9/10／3/3 | 15／8/13／3/3 | 48／13/16／3/3 | none |
| ex_largest_series_product | 2 | 16／12/12／2/2 | 20／17/17／2/2 | 25／17/17／2/2 | none |
| ex_minesweeper | 3 | 14／12/12／3/3 | 9／8/8／2/3 | 23／16/16／3/3 | none |
| ex_bank_account | 2 | 24／13/13／0/2 | 13／13/13／0/2 | 33／25/25／0/2 | none |
| ex_flower_field | 4 | 13／11/11／3/4 | 10／10/10／3/4 | 26／17/17／3/4 | none |
| ex_swift_scheduling | 0 | 19／0/19／0/0 | 17／0/17／0/0 | 40／0/21／0/0 | none |
| ex_all_your_base | 4 | 13／14/14／4/4 | 10／13/13／4/4 | 26／20/20／4/4 | none |
| ex_linked_list | 2 | 43／14/14／2/2 | 15／5/13／0/2 | 55／20/20／2/2 | none |
| ex_word_search | 3 | 13／10/10／2/3 | 8／0/4／2/3 | 28／16/16／3/3 | none |
| ex_camicia | 2 | 24／8/8／1/2 | 18／6/6／1/2 | 18／13/13／1/2 | none |
| ex_custom_set | 4 | 38／28/28／4/4 | 23／23/23／2/4 | 40／21/21／3/4 | none |
| ex_complex_numbers | 4 | 12／12/13／4/4 | 25／10/10／2/4 | 51／27/27／2/4 | none |
| ex_rational_numbers | 2 | 22／13/14／1/2 | 30／21/23／1/2 | 65／17/18／2/2 | none |
| ex_meetup | 4 | 16／16/16／4/4 | 14／6/6／4/4 | 26／20/20／4/4 | none |

「!」＝參考解下該考卷匯入失敗或逾時（0 個測試）。

## 5. 考卷錯誤（參考解沒過的斷言／測試）
共 251 個斷言錯誤（逐斷言口徑，不含整份無法執行者）；逐項如下。

### XM / ex_kindergarten_garden
- 行 14（fail）：`assert garden.plants("Alice") == [ "violets", "radishes", "violets", "radishes" ]` → AssertionError("assert ['Violets', '...', 'Radishes'] == ['violets', '...', 'radishes']\n  \n  At index 0 diff: 'Violets' != 'violets'\n  Use -v to get more dif
- 行 21（fail）：`assert garden.plants("Bob") == [ "clover", "grass", "clover", "clover" ]` → AssertionError("assert ['Clover', 'G...er', 'Clover'] == ['clover', 'g...er', 'clover']\n  \n  At index 0 diff: 'Clover' != 'clover'\n  Use -v to get more diff"
- 行 30（fail）：`assert result == ["violets", "violets", "clover", "grass"]` → AssertionError("assert ['Violets', '...ver', 'Grass'] == ['violets', '...ver', 'grass']\n  \n  At index 0 diff: 'Violets' != 'violets'\n  Use -v to get more dif
- 行 35（fail）：`assert garden.plants("Ginny") == [ "clover", "grass", "grass", "clover" ]` → AssertionError("assert ['Clover', 'G...ss', 'Clover'] == ['clover', 'g...ss', 'clover']\n  \n  At index 0 diff: 'Clover' != 'clover'\n  Use -v to get more diff"
- 行 42（fail）：`assert garden.plants("Harriet") == [ "violets", "radishes", "radishes", "violets" ]` → AssertionError("assert ['Violets', '...s', 'Violets'] == ['violets', '...s', 'violets']\n  \n  At index 0 diff: 'Violets' != 'violets'\n  Use -v to get more dif
- 行 49（fail）：`assert garden.plants("Kincaid") == [ "grass", "clover", "clover", "grass" ]` → AssertionError("assert ['Grass', 'Cl...ver', 'Grass'] == ['grass', 'cl...ver', 'grass']\n  \n  At index 0 diff: 'Grass' != 'grass'\n  Use -v to get more diff")
- 行 56（fail）：`assert garden.plants("Larry") == [ "grass", "violets", "clover", "violets" ]` → AssertionError("assert ['Grass', 'Vi...r', 'Violets'] == ['grass', 'vi...r', 'violets']\n  \n  At index 0 diff: 'Grass' != 'grass'\n  Use -v to get more diff")
- 行 73（fail）：`assert garden.plants("Valorie") == [ "violets", "radishes", "violets", "clover" ]` → AssertionError("assert ['Clover', 'C...ass', 'Grass'] == ['violets', '...ts', 'clover']\n  \n  At index 0 diff: 'Clover' != 'violets'\n  Use -v to get more diff
- 行 80（fail）：`assert garden.plants("Raven") == [ "clover", "clover", "grass", "grass" ]` → AssertionError("assert ['Violets', '...ts', 'Clover'] == ['clover', 'c...ass', 'grass']\n  \n  At index 0 diff: 'Violets' != 'clover'\n  Use -v to get more diff
- 行 87（fail）：`assert garden.plants("Alice") == [ "radishes", "grass", "clover", "violets" ]` → AssertionError("assert ['Radishes', ...r', 'Violets'] == ['radishes', ...r', 'violets']\n  \n  At index 0 diff: 'Radishes' != 'radishes'\n  Use -v to get more d
- 失敗的測試：`test_alice_gets_first_two_cups_of_each_row`, `test_bob_gets_second_pair_of_cups`, `test_charlie_result_is_a_list_of_four_plants`, `test_ginny_plants_from_middle_of_roster`, `test_harriet_plants_with_radishes_in_second_row`, `test_kincaid_plants`, `test_larry_is_last_child_on_default_roster`, `test_custom_roster_overrides_default_first_student`, `test_custom_roster_second_student`, `test_single_student_roster_with_one_cup_pair_per_row`

### XM / ex_ocr_numbers
- 行 31（fail）：`assert convert(_grid(_block([" _ "], ["| |"], ["|_|"]))) == "0"` → ValueError('Number of input columns is not a multiple of three')
- 行 35（fail）：`assert convert(_grid(_block([" "], [" |"], [" |"]))) == "1"` → ValueError('Number of input columns is not a multiple of three')
- 行 39（fail）：`assert convert(_grid(_block(ALL_TOP, ALL_MID, ALL_BOT))) == "1234567890"` → ValueError('Number of input columns is not a multiple of three')
- 行 58（fail）：`assert convert(_grid(block_1, block_2, block_3)) == "123,456,789"` → ValueError('Number of input columns is not a multiple of three')
- 行 63（fail）：`assert convert(_grid(one, one)) == "1,1"` → ValueError('Number of input columns is not a multiple of three')
- 行 73（fail）：`assert convert(_grid(block)) == "1?"` → ValueError('Number of input columns is not a multiple of three')
- 行 78（fail）：`assert convert(_grid(block)) == "?"` → ValueError('Number of input columns is not a multiple of three')
- 失敗的測試：`test_recognizes_zero`, `test_recognizes_one`, `test_recognizes_all_digits_in_one_row`, `test_multiple_rows_are_separated_by_commas`, `test_two_rows_of_single_digits`, `test_unrecognized_cell_becomes_question_mark`, `test_only_unrecognized_cell_becomes_question_mark`

### XM / ex_circular_buffer
- 行 19（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43f02f0>.read")
- 行 26（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43c6350>.read")
- 行 27（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43c6350>.read")
- 行 35（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43c6350>.read")
- 行 36（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43c6350>.read")
- 行 37（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43c6350>.read")
- 行 64（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a4424830>.read")
- 行 65（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a4424830>.read")
- 行 74（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43d4d10>.read")
- 行 75（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43d4d10>.read")
- 行 76（fail）：`assert buf.read() == 4` → AssertionError("assert '\\x04' == 4\n +  where '\\x04' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43d4d10>.read")
- 行 83（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43d4d10>.read")
- 行 84（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43d4d10>.read")
- 行 90（fail）：`assert buf.read() == 7` → AssertionError("assert '\\x07' == 7\n +  where '\\x07' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 102（fail）：`assert buf.read() == 5` → AssertionError("assert '\\x05' == 5\n +  where '\\x05' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 103（fail）：`assert buf.read() == 6` → AssertionError("assert '\\x06' == 6\n +  where '\\x06' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 107（fail）：`assert buf.read() == 7` → AssertionError("assert '\\x07' == 7\n +  where '\\x07' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 108（fail）：`assert buf.read() == 8` → AssertionError("assert '\\x08' == 8\n +  where '\\x08' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 109（fail）：`assert buf.read() == 9` → AssertionError("assert '\\t' == 9\n +  where '\\t' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 110（fail）：`assert buf.read() == 10` → AssertionError("assert '\\n' == 10\n +  where '\\n' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 111（fail）：`assert buf.read() == 11` → AssertionError("assert '\\x0b' == 11\n +  where '\\x0b' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 112（fail）：`assert buf.read() == 12` → AssertionError("assert '\\x0c' == 12\n +  where '\\x0c' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 113（fail）：`assert buf.read() == 13` → AssertionError("assert '\\r' == 13\n +  where '\\r' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43b9f50>.read")
- 行 121（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43e5130>.read")
- 行 124（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43e5130>.read")
- 行 125（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a43e5130>.read")
- 行 143（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a4482b30>.read")
- 行 153（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a4482b30>.read")
- 行 160（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fb5a464bad0>.read")
- 失敗的測試：`test_write_then_read_returns_element`, `test_read_returns_oldest_first`, `test_spec_example_removing_two_leaves_three`, `test_full_buffer_still_yields_original_elements_after_failed_write`, `test_overwrite_on_full_buffer_replaces_oldest`, `test_overwrite_on_non_full_buffer_acts_like_write`, `test_overwrite_on_empty_buffer_stores_element`, `test_spec_overwrite_example_reuses_freed_slots`, `test_wraparound_after_reads_keeps_fifo_order`, `test_buffer_is_usable_after_clear`, `test_clear_frees_full_buffer_for_writes`, `test_capacity_one_overwrite_keeps_latest`

### XM / ex_octal
- 行 39（fail）：`assert parse_octal("8") == 0` → ValueError('Invalid octal digit: 8')
- 行 40（fail）：`assert parse_octal("18") == 0` → ValueError('Invalid octal digit: 8')
- 行 44（fail）：`assert parse_octal("9") == 0` → ValueError('Invalid octal digit: 9')
- 行 45（fail）：`assert parse_octal("79") == 0` → ValueError('Invalid octal digit: 9')
- 行 49（fail）：`assert parse_octal("1a") == 0` → ValueError('Invalid octal digit: a')
- 行 50（fail）：`assert parse_octal("17x") == 0` → ValueError('Invalid octal digit: x')
- 失敗的測試：`test_digit_8_is_invalid_and_treated_as_zero`, `test_digit_9_is_invalid_and_treated_as_zero`, `test_letters_are_invalid_and_treated_as_zero`

### XM / ex_killer_sudoku_helper
- 行 36（fail）：`assert _normalized(combinations(4, 2, [])) == [[1, 3]]` → AssertionError('assert [] == [[1, 3]]\n  \n  Right contains one more item: [1, 3]\n  Use -v to get more diff')
- 行 40（fail）：`assert _normalized(combinations(3, 2, [])) == [[1, 2]]` → AssertionError('assert [] == [[1, 2]]\n  \n  Right contains one more item: [1, 2]\n  Use -v to get more diff')
- 行 48（fail）：`assert _normalized(combinations(3, 1, [3])) == []` → AssertionError('assert [[3]] == []\n  \n  Left contains one more item: [3]\n  Use -v to get more diff')
- 行 57（fail）：`assert _normalized(combinations(17, 2, [])) == [[8, 9]]` → AssertionError('assert [[1, 16], [2,... [6, 11], ...] == [[8, 9]]\n  \n  At index 0 diff: [1, 16] != [8, 9]\n  Left contains 7 more items, first extra item: [2,
- 失敗的測試：`test_repeated_digit_pair_is_not_allowed`, `test_digit_cannot_repeat_in_cage_sum_three`, `test_single_cell_cage_excluded_digit_gives_no_combinations`, `test_largest_pair_sum_has_single_combination`

### XM / ex_palindrome_products
- 失敗的測試：`test_largest_min_factor_defaults_to_zero`

### XM / ex_swift_scheduling
- 行 8（fail）：`assert delivery_date(start, "NOW") == datetime.datetime(2012, 12, 21, 12, 0)` → TypeError('fromisoformat: argument must be str')
- 行 13（fail）：`assert delivery_date(start, "NOW") == datetime.datetime(2012, 12, 22, 1, 30)` → TypeError('fromisoformat: argument must be str')
- 行 18（fail）：`assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 21, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 23（fail）：`assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 21, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 28（fail）：`assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 22, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 33（fail）：`assert delivery_date(start, "ASAP") == datetime.datetime(2012, 12, 22, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 38（fail）：`assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 43（fail）：`assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 48（fail）：`assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 28, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 53（fail）：`assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 30, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 58（fail）：`assert delivery_date(start, "EOW") == datetime.datetime(2012, 12, 30, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 63（fail）：`assert delivery_date(start, "5M") == datetime.datetime(2012, 5, 1, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 68（fail）：`assert delivery_date(start, "5M") == datetime.datetime(2013, 5, 1, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 73（fail）：`assert delivery_date(start, "3M") == datetime.datetime(2013, 3, 1, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 79（fail）：`assert delivery_date(start, "9M") == datetime.datetime(2012, 9, 3, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 84（fail）：`assert delivery_date(start, "Q4") == datetime.datetime(2012, 12, 31, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 90（fail）：`assert delivery_date(start, "Q2") == datetime.datetime(2012, 6, 29, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 95（fail）：`assert delivery_date(start, "Q2") == datetime.datetime(2012, 6, 29, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 101（fail）：`assert delivery_date(start, "Q1") == datetime.datetime(2013, 3, 29, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 失敗的測試：`test_now_is_two_hours_after_meeting_start`, `test_now_crosses_midnight`, `test_asap_before_13_is_today_at_17`, `test_asap_just_before_13_is_today_at_17`, `test_asap_at_13_is_tomorrow_at_13`, `test_asap_after_13_is_tomorrow_at_13`, `test_eow_monday_is_friday_at_17`, `test_eow_tuesday_is_friday_at_17`, `test_eow_wednesday_is_friday_at_17`, `test_eow_thursday_is_sunday_at_20`, `test_eow_friday_is_sunday_at_20`, `test_month_before_n_uses_this_year`, `test_month_in_n_uses_next_year`, `test_month_after_n_uses_next_year`, `test_month_first_day_on_weekend_uses_first_workday`, `test_quarter_in_n_uses_this_years_last_workday`, `test_quarter_before_n_uses_this_years_last_workday`, `test_quarter_same_quarter_is_this_years_last_workday`, `test_quarter_after_n_uses_next_years_last_workday`

### XM / ex_complex_numbers
- 行 13（fail）：`assert abs(diff) < TOL` → AssertionError('assert 1.718281828459045 < 1e-09\n +  where 1.718281828459045 = abs(<complex_numbers.ComplexNumber object at 0x7f0e98eb3170>)')
- 失敗的測試：`test_exp_of_general_complex_number`

### XM / ex_rational_numbers
- 行 68（fail）：`assert Rational(1, 4) ** 0.5 == pytest.approx(0.5)` → TypeError("'float' object cannot be interpreted as an integer")
- 失敗的測試：`test_power_real_exponent_returns_real_number`

### XMV / ex_kindergarten_garden
- 行 73（fail）：`assert _norm(garden.plants("Valorie")) == ["violets", "radishes", "violets", "clover"]` → AssertionError("assert ['clover', 'c...ass', 'grass'] == ['violets', '...ts', 'clover']\n  \n  At index 0 diff: 'clover' != 'violets'\n  Use -v to get more diff
- 行 79（fail）：`assert _norm(garden.plants("Raven")) == ["clover", "clover", "grass", "grass"]` → AssertionError("assert ['violets', '...ts', 'clover'] == ['clover', 'c...ass', 'grass']\n  \n  At index 0 diff: 'violets' != 'clover'\n  Use -v to get more diff
- 失敗的測試：`test_custom_students_override_default_roster`, `test_custom_students_second_child`

### XMV / ex_ocr_numbers
- 行 34（fail）：`assert convert(make_grid([digit])) == str(digit)` → ValueError('Number of input columns is not a multiple of three')
- 行 39（fail）：`assert convert(make_grid([1, 2, 3, 4, 5, 6, 7, 8, 9, 0])) == "1234567890"` → ValueError('Number of input columns is not a multiple of three')
- 行 44（fail）：`assert convert(make_grid([1, 2, 3])) == "123"` → ValueError('Number of input columns is not a multiple of three')
- 行 49（fail）：`assert convert(make_grid([1, 2, 3], [4, 5, 6], [7, 8, 9])) == "123,456,789"` → ValueError('Number of input columns is not a multiple of three')
- 行 54（fail）：`assert convert(make_grid([1, 0], [0, 1])) == "10,01"` → ValueError('Number of input columns is not a multiple of three')
- 行 59（fail）：`assert convert(make_grid([1, "X", 2])) == "1?2"` → ValueError('Number of input columns is not a multiple of three')
- 行 64（fail）：`assert convert(make_grid(["X"])) == "?"` → ValueError('Number of input columns is not a multiple of three')
- 失敗的測試：`test_recognises_each_digit_alone`, `test_all_digits_in_one_row`, `test_three_digits_in_one_row`, `test_multiple_rows_are_separated_by_comma`, `test_two_rows_of_two_digits`, `test_unrecognised_cell_becomes_question_mark`, `test_single_unrecognised_cell`

### XMV / ex_circular_buffer
- 行 12（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a35c2f0>.read")
- 行 14（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a35c2f0>.read")
- 行 16（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a35c2f0>.read")
- 行 24（unreached）：`with pytest.raises(BufferFullException): buf.write(7)`
- 行 38（fail）：`assert buf.read() == 5` → AssertionError("assert '\\x05' == 5\n +  where '\\x05' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a3225d0>.read")
- 行 64（fail）：`assert buf.read() == 5` → AssertionError("assert '\\x07' == 5\n +  where '\\x07' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a5db1d0>.read")
- 行 66（fail）：`assert buf.read() == 6` → AssertionError("assert '\\x08' == 6\n +  where '\\x08' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a5db1d0>.read")
- 行 83（fail）：`assert buf.read() == 7` → AssertionError("assert '\\t' == 7\n +  where '\\t' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7f9c0a3406b0>.read")
- 失敗的測試：`test_elements_are_read_oldest_first`, `test_buffer_of_length_seven_holds_seven_elements`, `test_write_to_full_buffer_raises_and_keeps_contents`, `test_overwrite_on_full_buffer_replaces_oldest_elements`, `test_overwrite_after_reads_reuses_freed_slots_and_keeps_order`

### XMV / ex_octal
- 行 51（fail）：`assert parse_octal('8') == 0` → ValueError('Invalid octal digit: 8')
- 行 56（fail）：`assert parse_octal('9') == 0` → ValueError('Invalid octal digit: 9')
- 行 61（fail）：`assert parse_octal('abc') == 0` → ValueError('Invalid octal digit: a')
- 失敗的測試：`test_invalid_digit_eight_is_zero`, `test_invalid_digit_nine_is_zero`, `test_non_numeric_input_is_zero`

### XMV / ex_say
- 行 65（fail）：`assert str(excinfo.value) != ""` → NameError("name 'excinfo' is not defined")
- 失敗的測試：`test_out_of_range_error_includes_message`

### XMV / ex_series
- 整份考卷在參考解下無法執行（collect_error=True, timeout=False）：`no tests ran in 0.01s`

### XMV / ex_palindrome_products
- 行 17（fail）：`assert _sorted_factors(largest(min_factor=1, max_factor=9)) in {(1, 9), (3, 3)}` → AssertionError('assert ((1, 9), (3, 3), (9, 1)) in {(1, 9), (3, 3)}\n +  where ((1, 9), (3, 3), (9, 1)) = _sorted_factors((9, [(1, 9), (3, 3), (9, 1)]))\n +    
- 行 27（fail）：`assert _sorted_factors(smallest(min_factor=1, max_factor=9)) == (1, 1)` → AssertionError('assert ((1, 1),) == (1, 1)\n  \n  At index 0 diff: (1, 1) != 1\n  Right contains one more item: 1\n  Use -v to get more diff')
- 行 37（fail）：`assert _sorted_factors(smallest(min_factor=10, max_factor=99)) == (11, 11)` → AssertionError('assert ((11, 11),) == (11, 11)\n  \n  At index 0 diff: (11, 11) != 11\n  Right contains one more item: 11\n  Use -v to get more diff')
- 行 47（fail）：`assert _sorted_factors(largest(min_factor=10, max_factor=99)) == (91, 99)` → AssertionError('assert ((91, 99), (99, 91)) == (91, 99)\n  \n  At index 0 diff: (91, 99) != 91\n  Use -v to get more diff')
- 行 59（fail）：`assert largest(max_factor=9)[0] == 9` → TypeError("largest() missing 1 required positional argument: 'min_factor'")
- 失敗的測試：`test_largest_over_range_1_to_9_factors_are_a_valid_pair`, `test_smallest_over_range_1_to_9_factors_are_1_and_1`, `test_smallest_over_range_10_to_99_factors_are_11_and_11`, `test_largest_over_range_10_to_99_factors_are_91_and_99`, `test_min_factor_defaults_to_zero_for_largest`

### XMV / ex_swift_scheduling
- 行 8（fail）：`assert delivery_date(datetime(2024, 1, 1, 10, 0), "NOW") == datetime(2024, 1, 1, 12, 0)` → TypeError('fromisoformat: argument must be str')
- 行 13（fail）：`assert delivery_date(datetime(2024, 1, 1, 23, 30), "NOW") == datetime(2024, 1, 2, 1, 30)` → TypeError('fromisoformat: argument must be str')
- 行 18（fail）：`assert delivery_date(datetime(2024, 1, 1, 10, 0), "ASAP") == datetime(2024, 1, 1, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 23（fail）：`assert delivery_date(datetime(2024, 1, 1, 12, 59), "ASAP") == datetime(2024, 1, 1, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 28（fail）：`assert delivery_date(datetime(2024, 1, 1, 13, 0), "ASAP") == datetime(2024, 1, 2, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 33（fail）：`assert delivery_date(datetime(2024, 1, 31, 14, 0), "ASAP") == datetime(2024, 2, 1, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 38（fail）：`assert delivery_date(datetime(2024, 1, 1, 9, 0), "EOW") == datetime(2024, 1, 5, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 43（fail）：`assert delivery_date(datetime(2024, 1, 3, 9, 0), "EOW") == datetime(2024, 1, 5, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 48（fail）：`assert delivery_date(datetime(2024, 1, 4, 9, 0), "EOW") == datetime(2024, 1, 7, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 53（fail）：`assert delivery_date(datetime(2024, 1, 5, 9, 0), "EOW") == datetime(2024, 1, 7, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 58（fail）：`assert delivery_date(datetime(2024, 2, 10, 9, 0), "6M") == datetime(2024, 6, 3, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 63（fail）：`assert delivery_date(datetime(2024, 6, 15, 9, 0), "6M") == datetime(2025, 6, 2, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 68（fail）：`assert delivery_date(datetime(2024, 7, 1, 9, 0), "3M") == datetime(2025, 3, 3, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 73（fail）：`assert delivery_date(datetime(2024, 2, 1, 9, 0), "Q1") == datetime(2024, 3, 29, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 78（fail）：`assert delivery_date(datetime(2024, 6, 30, 9, 0), "Q2") == datetime(2024, 6, 28, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 83（fail）：`assert delivery_date(datetime(2024, 7, 15, 9, 0), "Q2") == datetime(2025, 6, 30, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 88（fail）：`assert delivery_date(datetime(2024, 4, 1, 9, 0), "Q1") == datetime(2025, 3, 31, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 失敗的測試：`test_now_is_two_hours_after_meeting_start`, `test_now_crosses_midnight`, `test_asap_before_13_is_today_at_17`, `test_asap_one_minute_before_13_is_today_at_17`, `test_asap_at_13_is_tomorrow_at_13`, `test_asap_after_13_is_tomorrow_at_13_across_month_end`, `test_eow_on_monday_is_friday_at_17`, `test_eow_on_wednesday_is_friday_at_17`, `test_eow_on_thursday_is_sunday_at_20`, `test_eow_on_friday_is_sunday_at_20`, `test_month_before_nth_month_is_first_workday_this_year`, `test_month_in_nth_month_is_first_workday_next_year`, `test_month_after_nth_month_is_first_workday_next_year`, `test_quarter_before_nth_quarter_is_last_workday_this_year`, `test_quarter_in_nth_quarter_is_last_workday_this_year`, `test_quarter_after_nth_quarter_is_last_workday_next_year`, `test_quarter_after_nth_quarter_for_q1_from_q2`

### XMV / ex_linked_list
- 行 30（fail）：`assert values(ll) == [1, 2, 3]` → AssertionError('assert [(1, <linked_...f214a5c6350>)] == [1, 2, 3]\n  \n  At index 0 diff: (1, <linked_list.Node object at 0x7f214a5c6350>, None) != 1\n  Use -v
- 行 37（fail）：`assert values(ll) == [0, 1, 2, 3]` → AssertionError('assert [(0, <linked_...f214a5b4770>)] == [0, 1, 2, 3]\n  \n  At index 0 diff: (0, <linked_list.Node object at 0x7f214a5b4510>, None) != 0\n  Use
- 行 46（fail）：`assert values(ll) == [0, 1, 2]` → AssertionError('assert [(0, <linked_...f214a5b9b50>)] == [0, 1, 2]\n  \n  At index 0 diff: (0, <linked_list.Node object at 0x7f214a5b9b50>, None) != 0\n  Use -v
- 行 53（fail）：`assert values(ll) == [1, 2]` → AssertionError('assert [(1, <linked_...f214a67cad0>)] == [1, 2]\n  \n  At index 0 diff: (1, <linked_list.Node object at 0x7f214a67cbb0>, None) != 1\n  Use -v to
- 行 60（fail）：`assert values(ll) == [1, 3]` → AssertionError('assert [(1, <linked_...f214a84b860>)] == [1, 3]\n  \n  At index 0 diff: (1, <linked_list.Node object at 0x7f214a5bcdd0>, None) != 1\n  Use -v to
- 行 67（fail）：`assert values(ll) == [2, 3]` → AssertionError('assert [(2, <linked_...f214a993cd0>)] == [2, 3]\n  \n  At index 0 diff: (2, <linked_list.Node object at 0x7f214a68c910>, None) != 2\n  Use -v to
- 行 74（fail）：`assert values(ll) == [1, 2]` → AssertionError('assert [(1, <linked_...f214a68cb90>)] == [1, 2]\n  \n  At index 0 diff: (1, <linked_list.Node object at 0x7f214a7e2060>, None) != 1\n  Use -v to
- 行 81（fail）：`assert values(ll) == [2, 1, 3]` → AssertionError('assert [(2, <linked_...f214a5e95c0>)] == [2, 1, 3]\n  \n  At index 0 diff: (2, <linked_list.Node object at 0x7f214a5e95c0>, None) != 2\n  Use -v
- 失敗的測試：`test_push_adds_stations_to_end_of_route`, `test_unshift_adds_station_to_beginning_of_route`, `test_pop_removes_station_from_end_of_route`, `test_shift_removes_station_from_beginning_of_route`, `test_delete_removes_station_in_the_middle`, `test_delete_removes_station_at_beginning`, `test_delete_removes_station_at_end`, `test_delete_removes_only_first_occurrence`

### XMV / ex_word_search
- 行 34（fail）：`assert start == Point(1, 10)` → AssertionError('assert Point(0:9) == Point(1:10)\n +  where Point(1:10) = Point(1, 10)')
- 行 36（fail）：`assert end == Point(7, 10)` → AssertionError('assert Point(6:9) == Point(7:10)\n +  where Point(7:10) = Point(7, 10)')
- 行 43（fail）：`assert start == Point(6, 5)` → AssertionError('assert Point(5:4) == Point(6:5)\n +  where Point(6:5) = Point(6, 5)')
- 行 45（fail）：`assert end == Point(1, 5)` → AssertionError('assert Point(0:4) == Point(1:5)\n +  where Point(1:5) = Point(1, 5)')
- 行 52（fail）：`assert start == Point(10, 1)` → AssertionError('assert Point(9:0) == Point(10:1)\n +  where Point(10:1) = Point(10, 1)')
- 行 54（fail）：`assert end == Point(10, 10)` → AssertionError('assert Point(9:9) == Point(10:10)\n +  where Point(10:10) = Point(10, 10)')
- 行 61（fail）：`assert start == Point(8, 6)` → AssertionError('assert Point(7:5) == Point(8:6)\n +  where Point(8:6) = Point(8, 6)')
- 行 63（fail）：`assert end == Point(5, 9)` → AssertionError('assert Point(4:8) == Point(5:9)\n +  where Point(5:9) = Point(5, 9)')
- 失敗的測試：`test_horizontal_left_to_right`, `test_horizontal_right_to_left`, `test_vertical_top_to_bottom_full_height`, `test_diagonal_down_left`

### XMV / ex_rational_numbers
- 行 119（fail）：`assert Rational(1, 4) ** 0.5 == pytest.approx(0.5)` → TypeError("'float' object cannot be interpreted as an integer")
- 行 124（fail）：`assert Rational(4, 9) ** 0.5 == pytest.approx(2 / 3)` → TypeError("'float' object cannot be interpreted as an integer")
- 失敗的測試：`test_power_with_real_exponent_returns_real_number`, `test_power_with_real_exponent_on_square_rational`

### PB / ex_kindergarten_garden
- 行 103（fail）：`assert _norm(garden.plants("Valorie")) == [ "violets", "radishes", "violets", "clover" ]` → AssertionError("assert ['clover', 'c...ass', 'grass'] == ['violets', '...ts', 'clover']\n  \n  At index 0 diff: 'clover' != 'violets'\n  Use -v to get more diff
- 行 106（fail）：`assert _norm(garden.plants("Raven")) == ["clover", "clover", "grass", "grass"]` → AssertionError("assert ['violets', '...ts', 'clover'] == ['clover', 'c...ass', 'grass']\n  \n  At index 0 diff: 'violets' != 'clover'\n  Use -v to get more diff
- 失敗的測試：`test_custom_student_list_overrides_roster`

### PB / ex_ocr_numbers
- 行 57（unreached）：`assert isinstance(result, str)`
- 行 66（fail）：`assert convert(grid) == "1234567890"` → ValueError('Number of input columns is not a multiple of three')
- 行 75（fail）：`assert convert(grid) == "123,456,789"` → ValueError('Number of input columns is not a multiple of three')
- 行 84（fail）：`assert convert(grid) == "000,111"` → ValueError('Number of input columns is not a multiple of three')
- 行 93（fail）：`assert convert(_block(digit)) == digit` → ValueError('Number of input columns is not a multiple of three')
- 行 103（fail）：`assert convert(grid) == "?"` → ValueError('Number of input columns is not a multiple of three')
- 行 118（fail）：`assert convert(grid) == "1?2"` → ValueError('Number of input columns is not a multiple of three')
- 行 158（unreached）：`assert result == "4?7,09?"`
- 行 159（unreached）：`assert set(result) <= set("0123456789?,")`
- 失敗的測試：`test_returns_string_for_valid_grid`, `test_single_row_example_converts_to_expected_digits`, `test_multi_row_example_separates_rows_with_comma`, `test_two_rows_are_separated_by_single_comma`, `test_each_digit_zero_to_nine_is_recognized`, `test_unrecognizable_cell_outputs_question_mark`, `test_unrecognizable_cell_inside_row_outputs_question_mark_in_place`, `test_output_contains_only_digits_question_marks_and_commas`

### PB / ex_circular_buffer
- 行 72（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c116490>.read")
- 行 82（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c116490>.read")
- 行 95（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1050f0>.read")
- 行 96（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1050f0>.read")
- 行 97（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1050f0>.read")
- 行 170（fail）：`assert [buf.read() for _ in range(7)] == [5, 6, 7, 8, 9, "A", "B"]` → AssertionError("assert ['\\x05', '\\x0...\\t', 'A', ...] == [5, 6, 7, 8, 9, 'A', ...]\n  \n  At index 0 diff: '\\x05' != 5\n  Use -v to get more diff")
- 行 198（fail）：`assert buf.read() == 5` → AssertionError("assert '\\x05' == 5\n +  where '\\x05' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c14be30>.read")
- 行 199（fail）：`assert buf.read() == 6` → AssertionError("assert '\\x06' == 6\n +  where '\\x06' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c14be30>.read")
- 行 204（fail）：`assert [buf.read() for _ in range(7)] == [7, 8, 9, "A", "B", "C", "D"]` → AssertionError("assert ['\\x07', '\\x0...'B', 'C', ...] == [7, 8, 9, 'A', 'B', 'C', ...]\n  \n  At index 0 diff: '\\x07' != 7\n  Use -v to get more diff")
- 行 216（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 217（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 230（fail）：`assert buf.read() == 1` → AssertionError("assert '\\x01' == 1\n +  where '\\x01' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 233（fail）：`assert buf.read() == 2` → AssertionError("assert '\\x02' == 2\n +  where '\\x02' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 234（fail）：`assert buf.read() == 3` → AssertionError("assert '\\x03' == 3\n +  where '\\x03' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 235（fail）：`assert buf.read() == 4` → AssertionError("assert '\\x04' == 4\n +  where '\\x04' = read()\n +    where read = <circular_buffer.CircularBuffer object at 0x7fae5c1acf30>.read")
- 行 265（unreached）：`assert first == 42 and isinstance(first, int)`
- 行 266（unreached）：`assert second == "text" and isinstance(second, str)`
- 行 267（unreached）：`assert third == 2.5 and isinstance(third, float)`
- 失敗的測試：`test_read_returns_written_element`, `test_read_removes_element_so_next_read_is_empty`, `test_reads_remove_oldest_values_first`, `test_overwrite_on_full_buffer_replaces_oldest_values`, `test_overwrite_reuses_freed_slots_and_refills_buffer`, `test_overwrite_when_space_available_keeps_existing_data`, `test_fifo_order_holds_across_wrap_around`, `test_read_returns_value_unchanged_in_type`

### PB / ex_binary
- 行 101（unreached）：`with pytest.raises(ValueError): parse_binary("")`
- 失敗的測試：`test_rejects_empty_string`, `test_error_carries_nonempty_message[]`

### PB / ex_octal
- 行 95（fail）：`assert parse_octal("8") == 0` → ValueError('Invalid octal digit: 8')
- 行 96（fail）：`assert parse_octal("9") == 0` → ValueError('Invalid octal digit: 9')
- 行 97（fail）：`assert parse_octal("18") == 0` → ValueError('Invalid octal digit: 8')
- 行 98（fail）：`assert parse_octal("79") == 0` → ValueError('Invalid octal digit: 9')
- 行 99（fail）：`assert parse_octal("90") == 0` → ValueError('Invalid octal digit: 9')
- 行 107（fail）：`assert parse_octal("abc") == 0` → ValueError('Invalid octal digit: a')
- 行 108（fail）：`assert parse_octal("x") == 0` → ValueError('Invalid octal digit: x')
- 行 109（fail）：`assert parse_octal("17a") == 0` → ValueError('Invalid octal digit: a')
- 行 110（fail）：`assert parse_octal("12.3") == 0` → ValueError('Invalid octal digit: .')
- 行 111（fail）：`assert parse_octal("-7") == 0` → ValueError('Invalid octal digit: -')
- 行 129（unreached）：`assert isinstance(result, int)`
- 行 130（unreached）：`assert not isinstance(result, bool)`
- 行 131（unreached）：`assert result == 0`
- 失敗的測試：`test_digits_8_and_9_are_invalid_and_give_zero`, `test_non_digit_characters_are_invalid_and_give_zero`, `test_invalid_input_result_is_int`

### PB / ex_twelve_days
- 行 93（unreached）：`assert result.strip("\n") == "\n\n".join(EXPECTED)`
- 失敗的測試：`test_string_output_separates_verses_with_blank_line`

### PB / ex_atbash_cipher
- 行 73（fail）：`assert decode("gsvjf rxpyi") == "thequickbrown"` → AssertionError("assert 'thequickbr' == 'thequickbrown'\n  \n  - thequickbrown\n  ?           ---\n  + thequickbr")
- 行 74（fail）：`assert decode("gsvjfrxpyi") == "thequickbrown"` → AssertionError("assert 'thequickbr' == 'thequickbrown'\n  \n  - thequickbrown\n  ?           ---\n  + thequickbr")
- 失敗的測試：`test_decode_ignores_spaces_in_ciphertext`

### PB / ex_killer_sudoku_helper
- 行 22（fail）：`assert 1 <= digit <= 9` → AssertionError('assert 12 <= 9')
- 行 103（fail）：`assert list(combinations(10, 1, [])) == []` → AssertionError('assert [[10]] == []\n  \n  Left contains one more item: [10]\n  Use -v to get more diff')
- 行 109（fail）：`assert [list(c) for c in combinations(17, 2, [])] == [[8, 9]]` → AssertionError('assert [[1, 16], [2,... [6, 11], ...] == [[8, 9]]\n  \n  At index 0 diff: [1, 16] != [8, 9]\n  Left contains 7 more items, first extra item: [2,
- 行 141（fail）：`assert result == expected` → AssertionError('assert [[1, 2, 12], ..., 3, 10], ...] == [[1, 5, 9], [...3, 4, 8], ...]\n  \n  At index 0 diff: [1, 2, 12] != [1, 5, 9]\n  Left contains 4 more 
- 失敗的測試：`test_combination_digits_are_standard_sudoku_digits`, `test_single_digit_cage_boundaries`, `test_largest_two_digit_cage`, `test_result_is_complete_against_rule_based_enumeration`

### PB / ex_palindrome_products
- 行 40（unreached）：`assert isinstance(result, tuple)`
- 行 41（unreached）：`assert len(result) == 2`
- 行 43（unreached）：`assert isinstance(value, int)`
- 行 44（unreached）：`assert iter(factors) is not None`
- 行 45（unreached）：`assert _factors_are_well_formed(factors)`
- 行 51（unreached）：`assert isinstance(result, tuple)`
- 行 52（unreached）：`assert len(result) == 2`
- 行 54（unreached）：`assert isinstance(value, int)`
- 行 55（unreached）：`assert iter(factors) is not None`
- 行 56（unreached）：`assert _factors_are_well_formed(factors)`
- 行 138（fail）：`assert largest(max_factor=9) == largest(min_factor=0, max_factor=9)` → TypeError("largest() missing 1 required positional argument: 'min_factor'")
- 行 140（unreached）：`assert value == 9`
- 行 141（unreached）：`assert _pairs(factors) == {(1, 9), (3, 3)}`
- 失敗的測試：`test_largest_returns_value_and_iterable_of_factors`, `test_smallest_returns_value_and_iterable_of_factors`, `test_min_factor_defaults_to_zero`

### PB / ex_swift_scheduling
- 行 12（fail）：`assert isinstance(delivery_date(start, "NOW"), datetime)` → TypeError('fromisoformat: argument must be str')
- 行 13（fail）：`assert isinstance(delivery_date(start, "ASAP"), datetime)` → TypeError('fromisoformat: argument must be str')
- 行 14（fail）：`assert isinstance(delivery_date(start, "EOW"), datetime)` → TypeError('fromisoformat: argument must be str')
- 行 15（fail）：`assert isinstance(delivery_date(start, "3M"), datetime)` → TypeError('fromisoformat: argument must be str')
- 行 16（fail）：`assert isinstance(delivery_date(start, "Q2"), datetime)` → TypeError('fromisoformat: argument must be str')
- 行 26（unreached）：`assert result == datetime(2026, 1, 15, 11, 30)`
- 行 27（unreached）：`assert result - start == timedelta(hours=2)`
- 行 36（fail）：`assert delivery_date(start, "NOW") == datetime(2026, 1, 16, 1, 30)` → TypeError('fromisoformat: argument must be str')
- 行 45（fail）：`assert delivery_date(start, "ASAP") == datetime(2026, 1, 15, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 54（fail）：`assert delivery_date(start, "ASAP") == datetime(2026, 1, 15, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 63（fail）：`assert delivery_date(start, "ASAP") == datetime(2026, 1, 16, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 72（fail）：`assert delivery_date(start, "ASAP") == datetime(2026, 1, 16, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 81（fail）：`assert delivery_date(start, "ASAP") == datetime(2026, 2, 1, 13, 0)` → TypeError('fromisoformat: argument must be str')
- 行 89（fail）：`assert delivery_date(datetime(2026, 1, 5, 0, 0), "EOW") == datetime(2026, 1, 9, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 90（fail）：`assert delivery_date(datetime(2026, 1, 6, 12, 0), "EOW") == datetime(2026, 1, 9, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 91（fail）：`assert delivery_date(datetime(2026, 1, 7, 23, 59), "EOW") == datetime(2026, 1, 9, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 99（fail）：`assert delivery_date(datetime(2026, 1, 5, 0, 0), "EOW") == datetime(2026, 1, 9, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 100（fail）：`assert delivery_date(datetime(2026, 1, 5, 23, 59), "EOW") == datetime(2026, 1, 9, 17, 0)` → TypeError('fromisoformat: argument must be str')
- 行 108（fail）：`assert delivery_date(datetime(2026, 1, 8, 8, 0), "EOW") == datetime(2026, 1, 11, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 109（fail）：`assert delivery_date(datetime(2026, 1, 9, 17, 30), "EOW") == datetime(2026, 1, 11, 20, 0)` → TypeError('fromisoformat: argument must be str')
- 行 119（fail）：`assert delivery_date(start, "3M") == datetime(2026, 3, 2, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 120（fail）：`assert delivery_date(start, "8M") == datetime(2026, 8, 3, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 129（fail）：`assert delivery_date(start, "2M") == datetime(2026, 2, 2, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 138（fail）：`assert delivery_date(datetime(2026, 6, 10, 12, 0), "6M") == datetime(2027, 6, 1, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 139（fail）：`assert delivery_date(datetime(2026, 11, 27, 12, 0), "5M") == datetime(2027, 5, 3, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 148（fail）：`assert delivery_date(datetime(2026, 2, 28, 23, 59, 59), "3M") == datetime(2026, 3, 2, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 149（fail）：`assert delivery_date(datetime(2026, 3, 1, 0, 0), "3M") == datetime(2027, 3, 1, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 158（fail）：`assert delivery_date(datetime(2026, 1, 1, 0, 0), "Q1") == datetime(2026, 3, 31, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 159（fail）：`assert delivery_date(datetime(2026, 11, 27, 12, 0), "Q4") == datetime(2026, 12, 31, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 168（fail）：`assert delivery_date(datetime(2026, 3, 31, 23, 59), "Q2") == datetime(2026, 6, 30, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 169（fail）：`assert delivery_date(datetime(2026, 7, 1, 0, 0), "Q3") == datetime(2026, 9, 30, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 178（fail）：`assert delivery_date(datetime(2026, 4, 1, 0, 0), "Q1") == datetime(2027, 3, 31, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 179（fail）：`assert delivery_date(datetime(2026, 11, 27, 12, 0), "Q3") == datetime(2027, 9, 30, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 188（fail）：`assert delivery_date(datetime(2028, 11, 1, 0, 0), "Q4") == datetime(2028, 12, 29, 8, 0)` → TypeError('fromisoformat: argument must be str')
- 行 207（unreached）：`assert result.hour == 8, description`
- 行 208（unreached）：`assert result.minute == 0, description`
- 行 209（unreached）：`assert result.second == 0, description`
- 行 210（unreached）：`assert result.microsecond == 0, description`
- 行 211（unreached）：`assert result.weekday() < 5, description`
- 行 232（fail）：`assert delivery_date(start, description) > start, description` → TypeError('fromisoformat: argument must be str')
- 失敗的測試：`test_output_is_datetime_for_fixed_and_variable_descriptions`, `test_now_is_two_hours_after_meeting_start`, `test_now_two_hours_after_start_crosses_midnight`, `test_asap_before_1300_is_today_at_1700`, `test_asap_one_second_before_1300_is_today_at_1700`, `test_asap_at_exactly_1300_is_tomorrow_at_1300`, `test_asap_after_1300_is_tomorrow_at_1300`, `test_asap_after_1300_on_last_day_of_month_rolls_into_next_month`, `test_eow_monday_tuesday_wednesday_is_friday_at_1700`, `test_eow_on_monday_is_independent_of_time_of_day`, `test_eow_thursday_friday_is_sunday_at_2000`, `test_nM_before_month_is_first_workday_of_this_years_month`, `test_nM_first_workday_skips_weekend_at_start_of_month`, `test_nM_in_or_after_month_is_first_workday_of_next_years_month`, `test_nM_boundary_at_start_of_month_switches_to_next_year`, `test_Q_before_or_in_quarter_is_last_workday_of_this_years_quarter`, `test_Q_boundary_one_minute_before_next_quarter_still_uses_this_years_quarter`, `test_Q_after_quarter_is_last_workday_of_next_years_quarter`, `test_Q_last_workday_skips_weekend_when_quarter_ends_on_weekend`, `test_variable_results_are_at_0800_on_a_workday`, `test_delivery_is_strictly_after_meeting_start_for_all_examples`

### PB / ex_all_your_base
- 行 148（unreached）：`assert False, f"input base {bad_base} did not raise ValueError"`
- 行 162（unreached）：`assert False, f"output base {bad_base} did not raise ValueError"`
- 行 175（unreached）：`assert False, "digit 2 in base 2 did not raise ValueError"`
- 行 181（unreached）：`assert False, "digit 10 in base 10 did not raise ValueError"`
- 行 194（unreached）：`assert False, "negative digit did not raise ValueError"`
- 行 208（unreached）：`assert False, "input base 1 did not raise ValueError"`

### PB / ex_rational_numbers
- 行 219（unreached）：`assert isinstance(r, numbers.Real)`
- 行 220（unreached）：`assert r == pytest.approx(2 / 3, rel=1e-9)`
- 行 223（unreached）：`assert isinstance(r, numbers.Real)`
- 行 224（unreached）：`assert r == pytest.approx(8 / 27, rel=1e-9)`
- 失敗的測試：`test_power_to_real_float_exponent`


## 6. 補充量測（`measure.json` 直接算出）

- 沒有任何入選錯解的題（4 題）：ex_kindergarten_garden、ex_ocr_numbers、ex_binary、ex_swift_scheduling（候選不是全過原測試就是全不過）；
  這 4 題的考卷仍計入「參考解」各欄，但對錯解攔截欄貢獻 0 個分母。
- 錯解來源分開：Haiku 錯解（107）拒絕數 XM 94、XMV 78、PB 91；Devin 失敗交付（3）拒絕數 XM 2、XMV 2、PB 2。Devin 只有 3 個樣本，不能拆開下結論。
- 以 k（Haiku 被要求的錯誤類型）分，XM 拒絕 k1 27/29、k2 30/30、k3 18/23、k4 19/25；XMV k1 21/29、k2 26/30、k3 16/23、k4 15/25；
  PB k1 23/29、k2 29/30、k3 19/23、k4 20/25。（k2＝讀歪一條寫明規則最容易被擋；k3 輸出格式／k4 少見情況較容易漏。樣本小，僅描述。）
- 參考解下「半數以上測試失敗」的考卷：XM 4、XMV 5、PB 2（這些考卷對錯解的「拒絕」大多是誤拒因素造成，所以才另報「只算參考解全過的考卷」那欄）。

## 7. 缺陷與限制（量到的事實）

1. **EX 全部 none（37/37）。** 預註冊的確定性抽取器只認 doctest 與同行 `呼叫(...) == / => / -> 值` 且呼叫根名須是存根名字；
   37 份 goal.md 沒有一條符合。Exercism 的範例多半寫在散文、表格或圖示裡，抽取器照規則不處理，也沒有手寫補。
   所以 **EX 這一欄沒有任何資料**，不是「EX 沒用」的證據。
2. **XMV 的 SRC 位置**：提示詞要求 SRC 註解在每個 assert 正上方；Haiku 在 ex_luhn 與 ex_say 把 SRC 放在 `def` 上方。按預註冊的確定性規則，
   這兩題的斷言因此被刪（luhn 13/13 全刪，XMV 0 個斷言、拒絕不了任何錯解；say 12/13 刪）。全 37 題共 519 個斷言單位刪 31 個，其中 25 個來自這兩題；
   其餘 6 個見 `xmv_deletions.json`。這是後處理規則與模型實際格式不合，**不是**「這兩題需求沒有出處」。不事後改規則（凍結），要改就放新版本目錄。
3. **XMV ex_series 是模組層級 assert（沒有 `test_` 函式）**：pytest 收集到 0 個測試，算參考解下無法執行（逐題表的「!」）。
   逐斷言（模組層級）參考解全過，所以斷言本身沒錯，但作為 pytest 考卷沒有功能；對錯解它因匯入時 assert 失敗而被「拒絕」。
4. **PB 的 unreached 40 個**：發生在 9 題（palindrome_products 12、swift_scheduling 7、all_your_base 6、rational_numbers 4、其餘各 1–3），
   是同一個測試函式裡前面的敘述就丟例外，後面的斷言沒跑到；算失敗。
5. **「錯誤」的定義是相對於參考解**：參考解與 Haiku 對需求的詮釋不一致（例：Garden 的植物名大小寫、ocr 的欄寬輸入格式、palindrome 的因數對順序）都算考卷錯誤；
   其中一部分可能是需求文字本身有歧義，本報告沒有逐條判斷誰對。
6. **錯解攔截率的分母是 110 個**（Haiku 寫 107＋Devin 3），分布不明：錯誤由 Haiku 在指定類型下寫出，與真實小模型的錯誤分布不同；4 題沒有錯解。
   原始完整測試檔的 100% 是入選條件決定的，不是量到的。
7. 入選條件要求「至少通過 1 個原測試」：全不過的 16 個與全過的 25 個被丟棄（`qualify.json`）。
8. Haiku 可能看過 Exercism 測試（訓練資料）；輸入只給需求＋存根是約束，不是保證。所有 Haiku 呼叫使用 CLI 預設取樣（無溫度設定）；Claude Code 自己的系統提示仍在請求裡。
9. 每種考卷每題只生成一次，沒有重複，沒有變異量估計。

## 8. 推論（沒有直接量到）

- 未修改的 Haiku 考卷對參考解有約 8–14% 的逐測試誤拒、約 24–30% 的考卷至少有一個誤拒測試；若拿它當閘門驗收一個正確的小模型解，
  約四分之一至三成的題可能被誤退（推論：假設正確解行為等同參考解）。
- XMV 攔得比 XM 少，主要是它的斷言更少（平均 13.2 對 18.6）加上 luhn 被刪空；不是「帶出處的考卷比較差」的證據。
- PB 攔下率與 XM 無法區分（單次生成、110 個錯解、題間相依）；本前導不做檢定。
