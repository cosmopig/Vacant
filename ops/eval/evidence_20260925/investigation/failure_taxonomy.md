# 正式批次 82 個失敗跑的分類與零設定檢查的上限

> 來源：唯讀 agent `failure-taxonomy`（同上）；讀 scratchpad 裡解開的 318 跑 Harbor 目錄（＝`formal/formal_jobs.tar.xz`）。這一份是 `failure_taxonomy.json` 的可讀版（內容相同、只換排版）；每個數字的 檔:行 在「引用」一節。

## 摘要

我把 2026-09-25 正式 DABstep 批次裡 77 題主要分析的每一個失敗跑都看過一遍，每個「模型×組×題」都取最新的那一跑：gemma A 27 跑、gemma C 33 跑、qwen A 9 跑、qwen C 13 跑，共 82 跑。第 5 題四跑全對，第 70 題四跑全錯，另外列。
最大的一類是「15 回合用完、沒寫答案檔」，共 54 跑（gemma A 24、gemma C 28、qwen 兩組各 1）。另有 1 跑（gemma A 第 66 題）是思考輸出撞到長度上限，所以沒寫檔。
這 55 跑，Vacant 完全沒有機會檢查。Harbor 在第 15 回合就把 pi 中止了，pi 走不到交件前的檢查（Stop），所以 C 組那 28 跑的 stop_reached 全都是 false。
但我讀了模型自己的思考文字：有 15 跑（gemma A 7、gemma C 8）在回合用完之前，其實已經說出一個官方評分會判對的答案，只是一直「再確認一次」，最後沒寫進檔案。另外有 4 跑可能也是這樣，但不確定。
第二類是「讀了資料、答案卻錯」，共 27 跑。真正格式錯的是 0 跑。qwen C 第 1753 題的答案檔是空的，但題目規定清單是空的就回空字串，所以我把它算成推理錯。
錯的地方很集中：
- 7 跑把手冊寫明的「詐欺率＝詐欺金額／總金額」（manual.md 第 225 行）算成筆數的比例。
- 4 跑把「欄位是 null 或空清單＝全部適用」（第 95 行）用錯，或只用了一半。
- 5 跑錯在「每個 email 的平均」和「沒有 email 的列要不要算」這類聚合方式與缺值處理的解讀。
- 4 跑錯在題目範圍：布林欄位算不算「數值增加」、該回區間還是回邊界。
- 2 跑是程式 bug：一跑用字串比大小，日期範圍就錯了；一跑解析「>8.3%」失敗，錯誤被 except 吞掉。
- 2 跑（第 71 題）自己發明了文件裡沒定義的「過度詐欺門檻」，正解是 Not Applicable。
- 3 跑（第 60 題）是標準答案本身，用手冊的定義算不出來。gemma A 和 qwen A 交的其實就是照手冊算出來的答案。
其中 5 跑在自己的工具輸出裡已經算出正確數值，最後卻選了另一種解讀。
目前五類零設定檢查（要求的檔不存在、失敗步驟被略過、測試說法、沒出處的值、點名的檔沒開）在這 27 跑上一跑都抓不到。原因是：每個值都有出處（是它自己算的），手冊也打開了，步驟也沒有失敗。實際情況是 C 組 14 個錯答案全部被放行；唯一一次退回（gemma 第 1753 題），退回的理由本身還是誤報。
便宜的格式或空值檢查，最多只會對 qwen C 第 1753 題的空檔起疑，也不保證改得對。
要抓到其餘 24 跑推理錯（不含第 60 題的標籤問題），需要獨立重算，也就是第二個解題者或正解。拿這一批自己當參考：27 跑裡有 17 跑，同一題的另外三跑至少有一跑是對的；另外 10 跑（第 43、60、71、1273 題）四跑全錯，同一家族的第二個解題者多半會犯同樣的錯。
結論：只看過程證據的零設定檢查器，照現在「交件時才檢查」的設計，在這 82 跑裡能修的是 0 跑。
如果把「答案檔不存在」這一條提前到回合快用完時就提醒，最多碰得到 55 跑，其中約 15 跑（最多 19 跑）答案已經在手上。這是這批資料裡唯一看得到、不需要正解的增益空間，而且全部在 gemma。不過這是改回合預算的處理方式，不是改檢查規則。
其餘 27 個錯答案，過程證據最多再碰到 2 到 3 跑（例如第 71 題，agent 自己搜「excessive」什麼都沒找到）。至少 24 跑需要獨立解題者或正解；第 60 題那 3 跑連正確的解法都救不了。
回到「要不要把 Vacant 做成 agent」：在 DABstep 這類題目上，要讓成果變好只有兩條路。一是處理回合預算（快用完時先把答案寫出來），這不需要做成 agent。二是有能獨立重算的第二個解題者，而那本質上就是再呼叫一次 agent 或模型，已經超出「只看紀錄」的零設定定位。

## 表

### counts_by_class

| model_arm | failures_77 | a_cap_hit_no_answer | b_no_answer_other | c_format | d_reasoning | e_unsourced_or_invented | f_other_label | tasks |
|---|---|---|---|---|---|---|---|---|
| g4 A (gemma-4-26b, no Vacant) | 27 | 24 | 1 | 0 | 1 | 0 | 1 | a: 3,7,10,15,16,17,18,19,39,43,47,48,58,62,65,69,71,72,1273,1305,1464,1681,1753,2697 ／ b: 66 (thinking hit 16384-token output limit) ／ d: 67 ／ f: 60 |
| g4 C (gemma-4-26b, with Vacant) | 33 | 28 | 0 | 0 | 5 | 0 | 0 | a: 3,7,10,12,16,17,19,21,23,28,32,39,40,44,47,48,58,59,60,61,71,72,1273,1305,1464,1681,1871,2697 ／ d: 43,67,68,69,1753 |
| q38 A (qwen3.8-27b, no Vacant) | 9 | 1 | 0 | 0 | 6 | 1 | 1 | a: 2697 ／ d: 18,19,43,49,1273,1464 ／ e: 71 ／ f: 60 |
| q38 C (qwen3.8-27b, with Vacant) | 13 | 1 | 0 | 0 | 10 | 1 | 1 | a: 2697 ／ d: 17,18,36,43,47,49,61,1273,1753(empty file, guideline-permitted),1871 ／ e: 71 ／ f: 60 |
| TOTAL (77-task headline) | 82 | 54 | 1 | 0 | 22 | 2 | 3 | matches analysis.stdout: 77-50=27, 77-44=33, 77-68=9, 77-64=13 |

### excluded_tasks_5_70

| model_arm | detail |
|---|---|
| all four | Task 5: all four runs correct. Task 70 (gold 'Not Applicable'): g4 A = (a) cap hit, no answer; g4 C = 'yes' written on request 15, Stop never reached; q38 A = 'yes'; q38 C = 'yes', allowed by Vacant. The three 'yes' answers all invent a 'high-fraud fine' threshold (the >8.3% fee tier) that is not defined in the documents, same pattern as task 71. |

### signal_by_class

| class | signal_1_current_five_checks | signal_2_format_check | signal_3_independent_recompute | signal_4_correct_solution_only | what_could_help |
|---|---|---|---|---|---|
| (a) cap hit, no answer (54) | 0: 'missing output file' exists but never runs; Harbor aborts at 15 requests and pi never enters Stop (all 28 g4 C cap runs stop_reached=false) | 0 (nothing delivered) | 0 at delivery (nothing delivered) | n/a | Only a pre-cap budget nudge, e.g. the same missing-file check fired near turn 13 to 14. 14 cap-hit runs had already stated a scorer-accepted answer (g4 A: 3,7,18,48,62,65; g4 C: 10,12,19,23,40,44,58,61); 4 more are weak (g4 A 10,17,39; g4 C 39). qwen: 0 of 2. |
| (b) no answer, other reason (1: g4 A 66) | 'missing output file' would fire if Stop runs after a length stop (A arm has no Vacant, so 0 in practice) | same as (1) | not needed | no | The model had already concluded 'is_credit' (= gold). A missing-file prompt would likely fix it. |
| (c) empty/malformed (0) | - | - | - | - | The only empty answer (q38 C 1753) is guideline-compliant (empty list means empty string) and is counted under (d). An emptiness heuristic could raise suspicion there but cannot tell it is wrong. |
| (d) wrong answer after reading data (22) | 0: every value is self-computed, the manual was opened, no failed step was skipped. In practice all C-arm wrong answers that reached Stop were allowed. | 0 (all well-formed; 1 empty-file flag possible) | 22 are candidates; realistic subset = runs where another run on the same task was right: 17 of all 27 wrong-answer runs | The 67/68/69 gold labels are interpretation-sensitive (booleans; range label vs boundary) | Subtypes: count-vs-volume fraud rate 7 (q38 A 18,19,49; q38 C 17,18,49,61); null/empty wildcard misapplied 4 (q38 A 1273,1464; q38 C 1273,1753); aggregation/null-email 5 (g4 C 43; q38 A 43; q38 C 36,43,47); question scope 4 (g4 A 67; g4 C 67,68,69); code bugs 2 (q38 C 1871 string date compare; g4 C 1753 swallowed parse error) |
| (e) invented/unsourced premise (2: q38 A 71, q38 C 71) | 0: 'unsourced value' checks numbers, but the answer is yes/no built on an undefined term | 0 | yes, if the solver answers 'Not Applicable'; but all four runs failed this task | - | A new process check, 'the defining term was searched for and not found, yet the answer is not Not Applicable', could catch it. q38 A 71's own grep for 'excessive' found only unrelated lines. |
| (f) gold label disagrees with the manual-based computation (3: task 60) | 0 | 0 | 0: a manual-following solver reproduces g4 A / q38 A's answer 'Rafa_AI, BE, TransactPlus, Ecommerce' | unfixable except by matching the label | Treat as a benchmark-label issue |

### wrong_answer_detail

| class | model | arm | task | got | expected | mistake | vacant | peer_correct |
|---|---|---|---|---|---|---|---|---|
| f | g4 | A | 60 | Rafa_AI, BE, TransactPlus, Ecommerce | Belles_cookbook_store, ES, SwiftCharge, Ecommerce | None under the manual: volume-based worst segment per manual.md:225. The gold matches neither the volume-based nor the count-based rate. | A arm | no (all 4 wrong) |
| d | g4 | A | 67 | capture_delay, monthly_volume, intracountry | monthly_volume,capture_delay | Included boolean intracountry as 'value increased means cheaper' (defensible from manual.md:89); scope interpretation | A arm | yes (q38 A/C) |
| d | g4 | C | 43 | 247.300 | 90.70 | Used sum of amounts over rows with email / unique emails; its own output printed 'Average of the averages: 90.696' and it rejected that | answer written on request 15; Stop never reached | no (all 4 wrong) |
| d | g4 | C | 67 | capture_delay, monthly_volume, intracountry | monthly_volume,capture_delay | Same as g4 A 67 | reached Stop, allowed | yes |
| d | g4 | C | 68 | monthly_fraud_level, is_credit | monthly_fraud_level | Included boolean is_credit (manual.md:85); scope interpretation | reached Stop, allowed | yes |
| d | g4 | C | 69 | 1m-5m | 5m | Answered the range label instead of the boundary volume | written on request 15; Stop never reached | yes (q38) |
| d | g4 | C | 1753 | 33 IDs (missing 939) | 34 IDs incl. 939 | check_fraud_match could not parse '>8.3%'; a bare except returned False and silently dropped fee 939 | Sent back as 'unsourced 868', which is a false positive (868 is in its tool output); the cap was then hit; final answer unchanged | yes (q38 A) |
| d | q38 | A | 18 | SwiftCharge | TransactPlus | Count-based fraud rate. Its grep output contained manual.md:225 (volume definition) but it declared the count definition. | A arm | yes (g4 C) |
| d | q38 | A | 19 | 8.024467 | 9.676954 | Computed both the count rate and the volume rate (9.6769539488) and chose the count rate | A arm | yes (q38 C) |
| d | q38 | A | 43 | 274.334 | 90.70 | Computed 90.69560832225704 as an alternative and chose total amount / unique emails (numerator includes rows without email) | A arm | no |
| d | q38 | A | 49 | A. NL | B. BE | Ranked by raw count of fraudulent transactions, not by rate; read only the first 3000 chars of manual.md, never saw line 225 | A arm | yes (g4) |
| f | q38 | A | 60 | Rafa_AI, BE, TransactPlus, Ecommerce | Belles_cookbook_store, ES, SwiftCharge, Ecommerce | Explicitly used the manual's volume definition; gold not reproducible | A arm | no |
| e | q38 | A | 71 | no | Not Applicable | Invented 'excessive fraud threshold' = top fee tier >8.3%; its grep for 'excessive' found no definition | A arm | no |
| d | q38 | A | 1273 | 0.117667 | 0.120132 | Printed both 0.117667 (is_credit==True only) and 0.12013194 (True+null); chose strict, against manual.md:95 | A arm | no |
| d | q38 | A | 1464 | partial list | long list starting 1, 2, 5, 6, 8, 9 ... | Treated empty account_type as wildcard but empty aci as non-matching (inconsistent null/empty rule) | A arm | yes (q38 C) |
| d | q38 | C | 17 | 7.683437 | 8.91 | Computed the volume value 8.907926 in its own output, then chose the count-based value | allowed | yes (q38 A) |
| d | q38 | C | 18 | SwiftCharge | TransactPlus | Quoted 'fraudulent volume over total volume', then computed the mean of the boolean (a count) | allowed | yes (g4 C) |
| d | q38 | C | 36 | 2.986691 | 2.7 | Divided all 138236 rows (incl. rows without email) by unique non-empty emails | allowed | yes |
| d | q38 | C | 43 | 274.334 | 90.70 | Same aggregation choice as q38 A 43 | allowed | no |
| d | q38 | C | 47 | 87.687 | 78.04 | value_counts(dropna=False) grouped all missing emails into one 'repeat customer' | allowed (an earlier Traceback step was retried, so not 'skipped') | yes (q38 A) |
| d | q38 | C | 49 | A. NL | B. BE | Raw fraud count, although its grep showed manual.md:225 | allowed | yes (g4) |
| f | q38 | C | 60 | Martinis_Fine_Steakhouse, BE, SwiftCharge, Ecommerce | Belles_cookbook_store, ES, SwiftCharge, Ecommerce | Count-based rate (also not the manual's definition); gold not reproducible either way | allowed | no |
| d | q38 | C | 61 | Martinis_Fine_Steakhouse | Rafa_AI | Std of monthly count-based fraud rate; the volume-based std gives Rafa_AI (g4 C 61 stated both) | allowed | yes (g4 A, q38 A) |
| e | q38 | C | 71 | yes | Not Applicable | Invented threshold (>8.3% tier = 'excessive') | allowed | no |
| d | q38 | C | 1273 | 0.117667 | 0.120132 | Strict is_credit==True, 'not null' written in its own code comment | allowed | no |
| d | q38 | C | 1753 | (empty file) | 34 IDs | Treated empty merchant_category_code [] as 'matches nothing' (while treating empty account_type as wildcard), concluded no rule applies | allowed; 'missing output file' does not catch an empty file | yes (q38 A) |
| d | q38 | C | 1871 | -8.01008000000000 | -0.94810300000017 | String comparison row['day_of_year']<='31' let non-January days in; also invented 'most specific rule wins' | allowed | yes (g4 A, q38 A) |

### ceiling

| item | fixable |
|---|---|
| Zero-config process-evidence checks as designed (at Stop) | 0 of 82 in this batch (C arms: 0 of 46; the one wrong-answer send-back had a false reason) |
| Same missing-file check moved before the turn cap | Reaches 55 (54 a + 1 b); 15 strong (g4 A 3,7,18,48,62,65,66; g4 C 10,12,19,23,40,44,58,61) + 4 weak (g4 A 10,17,39; g4 C 39) had an accepted answer in hand; qwen 0 |
| New process checks (undefined term; definition section unread) | at most 2 to 3 of 27 wrong answers (q38 A/C 71; maybe q38 A 49) |
| Needs an independent solver or oracle | at least 24 of 27 wrong answers; 17 of 27 had a correct peer run on the same task; 10 (tasks 43, 60, 71, 1273) had none |
| Unfixable even by a correct solver (label) | 3 (task 60) |

## 注意事項（agent 自己寫的限制）

- Runs chosen = latest job dir per (model, arm, task), as instructed. For g4 C 43 that is the r2 rerun (reward 0). CONCLUSION:79-80 notes that a literal reading of the prereg would drop the task-43 pair (n=76). This does not change any class count except removing one g4 C (d) run.
- The 'answer already in hand' judgment for cap-hit runs comes from regex extraction of the model's own stated conclusions (answer is / I'll go with / I will output ...). Each candidate was scored with the task's own scorer.py, and context was read by hand for about 15 of them. Strong = 15 (includes g4 A 66, which is class b); weak = 4 (hypothetical or one of two alternatives). Nothing was re-run.
- Transcripts read: all 27 headline wrong-answer runs plus the 3 task-70 wrong answers, read for key steps (not every token). The 55 no-answer runs were characterized automatically (stated conclusions, error counts), with manual context checks on a subset.
- Some supporting numbers are my own read-only recomputation on the pinned data copy (D; hashes match PIN_MANIFEST) and do not come from archived files. They are: count vs volume fraud rates per scheme, merchant and country; that task 60's gold matches neither definition but coincides with the fewest fraudulent transactions in 3 of 4 segments; that q38 C 1871's string compare admits 235 distinct day values; and that a numeric January filter with aci C/B reproduces -0.948103. Treat them as verification aids, not archived evidence.
- Classifying 67/68/69 as (d) and 60 as (f) is my judgment. Those gold labels are interpretation-sensitive, so part of the 'wrong answers' may be benchmark-label noise rather than agent error.
- The 'independent solver' proxy (17 of 27 wrong-answer runs have a correct peer run) uses the other three runs in this batch. It is not a real second-solver experiment, and it ignores how a system would decide which of two disagreeing answers to trust.
- g4 A 72's 15th request ended with 'Stream ended without finish_reason'. I still counted it as a cap hit, because it used 15 requests.
- The g4 C 1753 'unsourced 868' false positive is already recorded in CONCLUSION:81. The cause (a script's output was treated as re-reading the deliverable) was fixed after the batch (evidence.py:386-388), so the current evidence.py differs from the frozen version that was measured.
- Out of scope here: the part of the user's request about matching earlier paper-like experimental results. This output covers only the failure taxonomy and the zero-config ceiling.
- No repo or data files were modified. I created only helper scripts in the session scratchpad: /tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/taxonomy_readonly/{dump.py,caps.py,conv.py,conv2.py,ctx.py}. They are read-only extractors and can be deleted, or kept for reproducing the tallies.

## 引用

- J=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/formal ; T=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/dabstep_pinned/formal ; D=/tmp/claude-0/-home-user-Vacant/95e2b6b6-418f-504c-a59e-fd594ef13041/scratchpad/study/pin (data copy; sha256 of manual.md bb7f4ca6... equals /home/user/Vacant/ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json:8, payments.csv equals :12)
- J/analysis.stdout:8-9 (g4 A_correct 50, C_correct 44 of 77)
- J/analysis.stdout:141-142 (q38 A_correct 68, C_correct 64)
- J/analysis.stdout:111,116 (g4 c_stop_reached 41, c_sent_back 7); :204,:206 (q38 78, 1)
- /home/user/Vacant/decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md:24 (max_turns=15), :33 (15-turn cap; after a Harbor abort pi does not enter Stop)
- J/analysis/runs.json:5122 (g4 C 43 stop_reached false), :4426 (g4 C 69), :1702 (g4 C 70), :4031 and :4035 (g4 C 1753 stop_reached true, sent_back true)
- J/jobs/<model>-on-<arm>/<job>/<trial>/verifier/test-stdout.txt:2 ('Error: /app/answer.txt not found' for all 54 cap-hit runs and g4 A 66) and :2-3 (Expected/Got for wrong answers)
- T/dabstep-<task>/tests/test.sh:20 (expected answers: 17 '8.91', 18 'TransactPlus', 19 '9.676954', 36 '2.7', 43 '90.70', 47 '78.04', 49 'B. BE', 60 'Belles_cookbook_store, ES, SwiftCharge, Ecommerce', 61 'Rafa_AI', 66 'is_credit', 67 'monthly_volume,capture_delay', 68 'monthly_fraud_level', 69 '5m', 70/71 'Not Applicable', 1273 '0.120132', 1753 list incl. 939, 1871 '-0.94810300000017')
- D/manual.md:225 ('Fraud is defined as the ratio of fraudulent volume over total volume'); :82 (monthly_fraud_level as volume ratio); :85 (is_credit); :89 (intracountry); :95 (null means applies to all values)
- J/jobs/g4-on-A/2026-09-25__19-53-35/dabstep-66__Q8tZK3y/agent/pi/sessions/*.jsonl:18 (stopReason length, output 16384 tokens, concluded is_credit)
- J/jobs/g4-on-A/2026-09-25__17-06-50/dabstep-7__zzihBVQ/agent/pi/sessions/*.jsonl:24,34 (89.999711 computed, never written)
- J/jobs/g4-on-A/2026-09-25__17-35-37/dabstep-3__qw7iUME/agent/pi/sessions/*.jsonl:34 ('confident with 27647')
- J/jobs/g4-on-C/2026-09-25__18-21-48/dabstep-19__dgKckR4/agent/pi/sessions/*.jsonl:18 (9.676954 computed, cap hit)
- J/jobs/g4-on-C/2026-09-25__18-36-59/dabstep-58__wUuL5NK/agent/pi/sessions/*.jsonl:24,28
- J/jobs/q38-on-A/2026-09-25__20-34-24/dabstep-18__nEgrSaC/agent/pi/sessions/*.jsonl:12 (grep output includes manual.md:225), :13 (declares count definition), :20 (count-based rates)
- J/jobs/q38-on-C/2026-09-25__20-34-24/dabstep-18__FzWYy7x/agent/pi/sessions/*.jsonl:13-14
- J/jobs/q38-on-A/2026-09-25__20-51-25/dabstep-19__EoQSDvS/agent/pi/sessions/*.jsonl:14 (volume rate 9.6769539488), :17 (writes 8.024467)
- J/jobs/q38-on-C/2026-09-25__21-30-24/dabstep-17__xQeJ26J/agent/pi/sessions/*.jsonl:18 (8.907926 printed), :19 (writes 7.683437)
- J/jobs/q38-on-A/2026-09-25__21-31-01/dabstep-43__KAZGfuH/agent/pi/sessions/*.jsonl:16 (90.69560832225704), :17 (writes 274.334)
- J/jobs/g4-on-C/2026-09-25__20-10-15/dabstep-43__NLrZee5/agent/pi/sessions/*.jsonl:23 ('Average of the averages: 90.696'), :32 (writes 247.300)
- J/jobs/q38-on-C/2026-09-25__20-47-14/dabstep-36__jYRKCfs/agent/pi/sessions/*.jsonl:11,15
- J/jobs/q38-on-C/2026-09-25__20-20-21/dabstep-47__uuBvjAS/agent/pi/sessions/*.jsonl:15 (value_counts(dropna=False)), :22 (87.687)
- J/jobs/q38-on-A/2026-09-25__21-02-11/dabstep-49__xcfqwz9/agent/pi/sessions/*.jsonl:8 (head -c 3000 manual.md), :20-21 (raw counts NL 2955 > BE 2493)
- J/jobs/q38-on-C/2026-09-25__21-02-11/dabstep-49__EaJ7ZjB/agent/pi/sessions/*.jsonl:12 (manual.md:225 visible), :22
- J/jobs/g4-on-A/2026-09-25__18-35-17/dabstep-60__fdkDzhC/agent/pi/sessions/*.jsonl:32 (volume-based: Rafa_AI 0.0939, BE 0.1226, TransactPlus 0.0968, Ecommerce 0.1002)
- J/jobs/q38-on-C/2026-09-25__20-56-59/dabstep-60__oSkkKHj/agent/pi/sessions/*.jsonl:15 (count-based: Martinis 8.00%, BE 10.78%, SwiftCharge 8.02%, Ecommerce 8.55%)
- J/jobs/q38-on-C/2026-09-25__20-28-49/dabstep-61__UtyGPmT/agent/pi/sessions/*.jsonl:15,17
- J/jobs/g4-on-C/2026-09-25__17-45-07/dabstep-61__uJiJZ6V/agent/pi/sessions/*.jsonl:34 (amount-based gives Rafa_AI, count-based Martinis)
- J/jobs/q38-on-A/2026-09-25__20-28-42/dabstep-71__VrxPVc3/agent/pi/sessions/*.jsonl:11 (grep 'excessive' only hits manual.md:196-197), :18
- J/jobs/q38-on-A/2026-09-25__21-26-46/dabstep-1273__BeY9wLh/agent/pi/sessions/*.jsonl:14 (0.117667 vs 0.12013194), :15 (writes 0.117667)
- J/jobs/q38-on-A/2026-09-25__20-37-52/dabstep-1464__umGA94x/agent/pi/sessions/*.jsonl:13-17
- J/jobs/q38-on-C/2026-09-25__21-09-20/dabstep-1753__dJ4T2uN/agent/pi/sessions/*.jsonl:25 (5942 in no fee list), :27 (writes empty file)
- J/jobs/q38-on-C/2026-09-25__21-03-33/dabstep-1871__6FrPtoU/agent/pi/sessions/*.jsonl:29 (row['day_of_year']<='31' string compare; 83 tx), :31
- J/jobs/g4-on-C/2026-09-25__19-01-18/dabstep-1753__SktQCfh/agent/pi/sessions/*.jsonl:18 (check_fraud_match with bare except), :21 (output includes 868), :33 (vacant-check: '868 was not found')
- J/jobs/g4-on-C/2026-09-25__17-37-39/dabstep-68__yakzHps/agent/pi/sessions/*.jsonl:16 ; J/jobs/g4-on-C/2026-09-25__19-25-41/dabstep-69__hy8gnaD/agent/pi/sessions/*.jsonl:32 ; J/jobs/g4-on-A/2026-09-25__19-38-40/dabstep-67__Rpk7eGp/agent/pi/sessions/*.jsonl:18
- /home/user/Vacant/decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md:44-46 (two false-positive root causes), :51-55 (failures are reasoning and cap), :79-80 (task 43 rerun twice), :81-85 (all 8 send-backs false; 14 wrong answers allowed; C 28 vs A 25 no-answer)
- /home/user/Vacant/vacant_network/trace/evidence.py:386-388 (post-batch fix: running one's own script counts as a source)
