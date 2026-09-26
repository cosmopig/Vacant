# 零設定評估（2026-09-25／26）證據索引

> 由 `ops/eval/build_evidence_index.py` 產生；`--check` 驗證索引和檔案一致。**不要手改**。

讀的順序：先看總報告（第一組），要查數字再看結論與正式批次的原始紀錄。
原始紀錄（全部請求／回應、每一跑的 Harbor 目錄）在「證據：正式批次」那一組的兩個 `.xz` 壓縮檔裡；
解壓：`xz -dc formal_io.jsonl.xz > io.jsonl`、`xz -dc formal_jobs.tar.xz | tar -x`。

## 總報告

這一輪的完整報告：為什麼是這個結果、和過去的架構比、Vacant 要不要變成 agent

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md`](../../../docs/ZERO_CONFIG_EVAL_REPORT_2026-09-26.md) | 46.5 KB | `b3b068956334abd4` |

## 裁決、預註冊、結論

設計、評估計畫（含人類裁決）、簽過字的預註冊、結論與更正

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md`](../../../decisions/DECISION_20260925_ZERO_CONFIG_DESIGN.md) | 15.2 KB | `5a2f841528e12817` |
| [`decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md`](../../../decisions/DECISION_20260925_ZERO_CONFIG_EVAL.md) | 52.3 KB | `41738f84ca2c1a7e` |
| [`decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md`](../../../decisions/prereg/PREREG_20260925_ZERO_CONFIG_DABSTEP.md) | 7.5 KB | `8f5506277f9ca229` |
| [`decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md`](../../../decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md) | 9.3 KB | `9aa28e662d782726` |

## 產品程式（C 組本身）

裝了就有作用的零設定 Stop 檢查；正式批次跑的是 8b22c7cc 這一版，之後 efda0d1f 修了兩個誤報

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`vacant_network/adapters/mode.py`](../../../vacant_network/adapters/mode.py) | 1.9 KB | `761514159d6c0344` |
| [`vacant_network/adapters/hook.py`](../../../vacant_network/adapters/hook.py) | 21.1 KB | `0df131471f134ae7` |
| [`vacant_network/adapters/agents.py`](../../../vacant_network/adapters/agents.py) | 38.6 KB | `dd97a424dcbd957d` |
| [`vacant_network/adapters/cli.py`](../../../vacant_network/adapters/cli.py) | 13.8 KB | `0ace9ab51dc78cd1` |
| [`vacant_network/trace/evidence.py`](../../../vacant_network/trace/evidence.py) | 38.6 KB | `6177b3d983abf594` |
| [`vacant_network/trace/review.py`](../../../vacant_network/trace/review.py) | 5.7 KB | `167e90d275a9f594` |
| [`vacant_network/trace/zerostop.py`](../../../vacant_network/trace/zerostop.py) | 20.8 KB | `953dd5646a6f33ee` |
| [`vacant_network/trace/recorder.py`](../../../vacant_network/trace/recorder.py) | 53.2 KB | `b687819272a143d7` |
| [`vacant_network/trace/feedback.py`](../../../vacant_network/trace/feedback.py) | 19.4 KB | `4cff93b0793be633` |

## 測試

零設定的單元與掛鉤測試（含正式批次暴露的誤報回歸）

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`tests/test_zero_mode.py`](../../../tests/test_zero_mode.py) | 4.5 KB | `2da897b70d58a264` |
| [`tests/test_zero_evidence.py`](../../../tests/test_zero_evidence.py) | 19.1 KB | `479560f59b37608e` |
| [`tests/test_zero_stop.py`](../../../tests/test_zero_stop.py) | 11.5 KB | `8a9ebf10ac8f0dc1` |
| [`tests/test_eval_orproxy.py`](../../../tests/test_eval_orproxy.py) | 10.5 KB | `1d6693357ea0341a` |

## 評估工具

記帳代理、Harbor 的 C 組包裝、釘死的 DABstep、試點／正式驅動、分析、重播、模擬使用者、閘門 2

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/orproxy.py`](../../../ops/eval/orproxy.py) | 19.6 KB | `0ad70316f6c3b419` |
| [`ops/eval/harbor_vacant.py`](../../../ops/eval/harbor_vacant.py) | 4.5 KB | `7b93b0e3e5444901` |
| [`ops/eval/dabstep_pin.py`](../../../ops/eval/dabstep_pin.py) | 3.3 KB | `a5efb58e8d436781` |
| [`ops/eval/dabstep_formal.py`](../../../ops/eval/dabstep_formal.py) | 2.8 KB | `81f948f3d2f64ef9` |
| [`ops/eval/pilot/run_one.sh`](../../../ops/eval/pilot/run_one.sh) | 2.3 KB | `937366e8ae3c5180` |
| [`ops/eval/pilot/collect.py`](../../../ops/eval/pilot/collect.py) | 3.1 KB | `c5116884c57bd409` |
| [`ops/eval/pilot/tasks.json`](../../../ops/eval/pilot/tasks.json) | 1.2 KB | `3d30a1c25920422a` |
| [`ops/eval/formal/run_formal.py`](../../../ops/eval/formal/run_formal.py) | 4.6 KB | `9b1bf696df0a0105` |
| [`ops/eval/formal/analyze.py`](../../../ops/eval/formal/analyze.py) | 10.3 KB | `60267f90f85f53ca` |
| [`ops/eval/formal/explore_two_runs.py`](../../../ops/eval/formal/explore_two_runs.py) | 6.1 KB | `3685bc0490128bf3` |
| [`ops/eval/replay_pi_session.py`](../../../ops/eval/replay_pi_session.py) | 6.5 KB | `df3ab1373202aa4c` |
| [`ops/eval/replay_gate.py`](../../../ops/eval/replay_gate.py) | 4.6 KB | `1aaf70bc72b97c93` |
| [`ops/eval/simuser/inside.sh`](../../../ops/eval/simuser/inside.sh) | 2.3 KB | `00ba532c3f29d419` |
| [`ops/eval/simuser/run_simuser.py`](../../../ops/eval/simuser/run_simuser.py) | 6.5 KB | `92e64389336675db` |
| [`ops/eval/gate2/run_gate2.sh`](../../../ops/eval/gate2/run_gate2.sh) | 1.7 KB | `be242b40cc04e0b6` |
| [`ops/eval/build_evidence_index.py`](../../../ops/eval/build_evidence_index.py) | 10.3 KB | `529417e4f298e2d1` |

## 證據：研究與閘門 1、整輪的帳

題庫研究筆記、閘門 1（選模型的冒煙測試）、記帳代理設定；`ledger.jsonl` 是研究階段的 41 通，`ledger_all.jsonl.xz`／`summary_all.json` 是整輪 3,324 通、3.4026 美元

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/README.md`](../../../ops/eval/evidence_20260925/README.md) | 2.8 KB | `42a1171cbee57f6a` |
| [`ops/eval/evidence_20260925/notes/arch.md`](../../../ops/eval/evidence_20260925/notes/arch.md) | 8.6 KB | `9a6a4dab496095c9` |
| [`ops/eval/evidence_20260925/notes/critic-plan.md`](../../../ops/eval/evidence_20260925/notes/critic-plan.md) | 1.6 KB | `d85ce3cbec7352ec` |
| [`ops/eval/evidence_20260925/notes/deep-Aider.md`](../../../ops/eval/evidence_20260925/notes/deep-Aider.md) | 22.4 KB | `0c5a4c496521ad62` |
| [`ops/eval/evidence_20260925/notes/deep-DABstep.md`](../../../ops/eval/evidence_20260925/notes/deep-DABstep.md) | 36.1 KB | `d40feabea0d52263` |
| [`ops/eval/evidence_20260925/notes/deep-GDPval.md`](../../../ops/eval/evidence_20260925/notes/deep-GDPval.md) | 29.4 KB | `8896e165ebdfb7d7` |
| [`ops/eval/evidence_20260925/notes/deep-LiveCodeBench.md`](../../../ops/eval/evidence_20260925/notes/deep-LiveCodeBench.md) | 34.1 KB | `3eaa8fe69c7f9eca` |
| [`ops/eval/evidence_20260925/notes/deep-SpreadsheetBench.md`](../../../ops/eval/evidence_20260925/notes/deep-SpreadsheetBench.md) | 33.5 KB | `28e1d487764675e9` |
| [`ops/eval/evidence_20260925/notes/deep-Terminal.md`](../../../ops/eval/evidence_20260925/notes/deep-Terminal.md) | 13.1 KB | `3c3979972d35bd31` |
| [`ops/eval/evidence_20260925/notes/env-RECIPE.md`](../../../ops/eval/evidence_20260925/notes/env-RECIPE.md) | 10.0 KB | `78e6d143d2939f79` |
| [`ops/eval/evidence_20260925/notes/env.md`](../../../ops/eval/evidence_20260925/notes/env.md) | 2.6 KB | `f8ac5a34be837f99` |
| [`ops/eval/evidence_20260925/notes/plan-v1.md`](../../../ops/eval/evidence_20260925/notes/plan-v1.md) | 42.0 KB | `c0d8117832f8a6b4` |
| [`ops/eval/evidence_20260925/notes/plan.md`](../../../ops/eval/evidence_20260925/notes/plan.md) | 4.0 KB | `407e84db1be3b04b` |
| [`ops/eval/evidence_20260925/notes/scout-coding.md`](../../../ops/eval/evidence_20260925/notes/scout-coding.md) | 21.5 KB | `4e9760742eb0e25e` |
| [`ops/eval/evidence_20260925/notes/scout-data.md`](../../../ops/eval/evidence_20260925/notes/scout-data.md) | 26.2 KB | `3ec7da8b6db54666` |
| [`ops/eval/evidence_20260925/notes/scout-knowledge.md`](../../../ops/eval/evidence_20260925/notes/scout-knowledge.md) | 22.8 KB | `e4e0bb6b9d4f36d0` |
| [`ops/eval/evidence_20260925/notes/scout-selfcheck.md`](../../../ops/eval/evidence_20260925/notes/scout-selfcheck.md) | 31.2 KB | `279f7a5be31a4407` |
| [`ops/eval/evidence_20260925/notes/shortlist.md`](../../../ops/eval/evidence_20260925/notes/shortlist.md) | 1.9 KB | `cb01aae05175630f` |
| [`ops/eval/evidence_20260925/gate1/GATE1.md`](../../../ops/eval/evidence_20260925/gate1/GATE1.md) | 14.8 KB | `5fe2a7079ede6a4a` |
| [`ops/eval/evidence_20260925/gate1/gate1_result.json`](../../../ops/eval/evidence_20260925/gate1/gate1_result.json) | 13.0 KB | `d24c9d45e0a5cd38` |
| [`ops/eval/evidence_20260925/gate1/run_one.sh`](../../../ops/eval/evidence_20260925/gate1/run_one.sh) | 1.4 KB | `9833f87bd79858c7` |
| [`ops/eval/evidence_20260925/proxy_config.json`](../../../ops/eval/evidence_20260925/proxy_config.json) | 545 B | `7d3c6cb8e1fe0aba` |
| [`ops/eval/evidence_20260925/ledger.jsonl`](../../../ops/eval/evidence_20260925/ledger.jsonl) | 42.7 KB | `9dde863ab5177739` |
| [`ops/eval/evidence_20260925/summary.json`](../../../ops/eval/evidence_20260925/summary.json) | 6.5 KB | `41cbef14d9c2f6c1` |
| [`ops/eval/evidence_20260925/study_result.json`](../../../ops/eval/evidence_20260925/study_result.json) | 561.1 KB | `0898e216aea0320c` |
| [`ops/eval/evidence_20260925/ledger_all.jsonl.xz`](../../../ops/eval/evidence_20260925/ledger_all.jsonl.xz) | 135.3 KB | `044518d87fa61a96` |
| [`ops/eval/evidence_20260925/summary_all.json`](../../../ops/eval/evidence_20260925/summary_all.json) | 72.2 KB | `9e24011e05c1f4d6` |

## 證據：C 組設計第 1 版與審查

第 1 版設計、字句、批評（4 blocker、15 major）、驗收規格、安裝稽核

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/cdesign/acceptance_spec.json`](../../../ops/eval/evidence_20260925/cdesign/acceptance_spec.json) | 48.0 KB | `401379efc40475fa` |
| [`ops/eval/evidence_20260925/cdesign/agent_texts_v1.md`](../../../ops/eval/evidence_20260925/cdesign/agent_texts_v1.md) | 6.4 KB | `51056cb644c5c83e` |
| [`ops/eval/evidence_20260925/cdesign/critic_v1.md`](../../../ops/eval/evidence_20260925/cdesign/critic_v1.md) | 27.4 KB | `7a4de7cb01d0558a` |
| [`ops/eval/evidence_20260925/cdesign/design_v1.md`](../../../ops/eval/evidence_20260925/cdesign/design_v1.md) | 40.8 KB | `6eb9e2f809f46e10` |
| [`ops/eval/evidence_20260925/cdesign/install_audit.json`](../../../ops/eval/evidence_20260925/cdesign/install_audit.json) | 18.1 KB | `f9b8d2f5fa523dce` |
| [`ops/eval/evidence_20260925/cdesign/work_packages_v1.json`](../../../ops/eval/evidence_20260925/cdesign/work_packages_v1.json) | 12.4 KB | `4a44c11ce30da802` |

## 證據：真實紀錄重播（誤報門檻）

閘門 1 的 9 個真實 pi 工作階段在題目容器裡重播

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-5__TxRoodQ.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-5__TxRoodQ.json) | 3.3 KB | `47657a0512d16baa` |
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-5__Yqmbch9.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-5__Yqmbch9.json) | 2.4 KB | `a3f7c60833bb131f` |
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-5__zawEaqe.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-5__zawEaqe.json) | 2.6 KB | `bfc662d833da952b` |
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-70__4VtrWRQ.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-70__4VtrWRQ.json) | 2.0 KB | `6585d638a6d4c72c` |
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-70__bryJza5.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-70__bryJza5.json) | 3.6 KB | `49d17a464806cf0a` |
| [`ops/eval/evidence_20260925/replay/out_dab/dabstep-70__g59Domh.json`](../../../ops/eval/evidence_20260925/replay/out_dab/dabstep-70__g59Domh.json) | 3.5 KB | `5eb108ef6c048ace` |
| [`ops/eval/evidence_20260925/replay/out_dab/summary.json`](../../../ops/eval/evidence_20260925/replay/out_dab/summary.json) | 4.1 KB | `edcfcb9038b5b661` |
| [`ops/eval/evidence_20260925/replay/out_sbv/10452__HsdF6hA.json`](../../../ops/eval/evidence_20260925/replay/out_sbv/10452__HsdF6hA.json) | 3.9 KB | `faf4c6b11abf61ae` |
| [`ops/eval/evidence_20260925/replay/out_sbv/10452__YREpPCi.json`](../../../ops/eval/evidence_20260925/replay/out_sbv/10452__YREpPCi.json) | 1.8 KB | `970a2c6ef9c26355` |
| [`ops/eval/evidence_20260925/replay/out_sbv/10452__rRjumd7.json`](../../../ops/eval/evidence_20260925/replay/out_sbv/10452__rRjumd7.json) | 4.1 KB | `255cb9187af882c8` |
| [`ops/eval/evidence_20260925/replay/out_sbv/summary.json`](../../../ops/eval/evidence_20260925/replay/out_sbv/summary.json) | 1.7 KB | `5df38a48100d6ec6` |

## 證據：模擬使用者（L-fake）

乾淨 Ubuntu、只照 README 裝、照常用 pi；A/C 三個情境；請求逐位元組比對

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/simuser/SIMUSER.md`](../../../ops/eval/evidence_20260925/simuser/SIMUSER.md) | 3.1 KB | `e70c3ea132c4a1f1` |
| [`ops/eval/evidence_20260925/simuser/correct_A/answer.txt`](../../../ops/eval/evidence_20260925/simuser/correct_A/answer.txt) | 6 B | `9ca73c56172a2267` |
| [`ops/eval/evidence_20260925/simuser/correct_A/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/correct_A/mock.jsonl) | 838 B | `206a7e57a6c9f350` |
| [`ops/eval/evidence_20260925/simuser/correct_A/pi_exit`](../../../ops/eval/evidence_20260925/simuser/correct_A/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/correct_A/scenario.json`](../../../ops/eval/evidence_20260925/simuser/correct_A/scenario.json) | 321 B | `a3445f98d2eddf45` |
| [`ops/eval/evidence_20260925/simuser/correct_A/task.txt`](../../../ops/eval/evidence_20260925/simuser/correct_A/task.txt) | 615 B | `e791a470ec200f82` |
| [`ops/eval/evidence_20260925/simuser/correct_C/answer.txt`](../../../ops/eval/evidence_20260925/simuser/correct_C/answer.txt) | 6 B | `9ca73c56172a2267` |
| [`ops/eval/evidence_20260925/simuser/correct_C/delivery.json`](../../../ops/eval/evidence_20260925/simuser/correct_C/delivery.json) | 848 B | `263d3c45e1f4a181` |
| [`ops/eval/evidence_20260925/simuser/correct_C/delivery.md`](../../../ops/eval/evidence_20260925/simuser/correct_C/delivery.md) | 810 B | `bb5899514e63097e` |
| [`ops/eval/evidence_20260925/simuser/correct_C/install_transcript.txt`](../../../ops/eval/evidence_20260925/simuser/correct_C/install_transcript.txt) | 1017 B | `de6325b598d382e4` |
| [`ops/eval/evidence_20260925/simuser/correct_C/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/correct_C/mock.jsonl) | 837 B | `b04ce6a50a8724b7` |
| [`ops/eval/evidence_20260925/simuser/correct_C/pi_exit`](../../../ops/eval/evidence_20260925/simuser/correct_C/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/correct_C/scenario.json`](../../../ops/eval/evidence_20260925/simuser/correct_C/scenario.json) | 321 B | `a3445f98d2eddf45` |
| [`ops/eval/evidence_20260925/simuser/correct_C/task.txt`](../../../ops/eval/evidence_20260925/simuser/correct_C/task.txt) | 615 B | `e791a470ec200f82` |
| [`ops/eval/evidence_20260925/simuser/correct_bodies_check/sha256.txt`](../../../ops/eval/evidence_20260925/simuser/correct_bodies_check/sha256.txt) | 592 B | `eae04ea105430c6b` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_A/answer.txt`](../../../ops/eval/evidence_20260925/simuser/made_up_number_A/answer.txt) | 6 B | `9d79b1f64611afb5` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_A/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/made_up_number_A/mock.jsonl) | 628 B | `0b162bc208be8d6e` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_A/pi_exit`](../../../ops/eval/evidence_20260925/simuser/made_up_number_A/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_A/scenario.json`](../../../ops/eval/evidence_20260925/simuser/made_up_number_A/scenario.json) | 458 B | `bb83005acdc15446` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_A/task.txt`](../../../ops/eval/evidence_20260925/simuser/made_up_number_A/task.txt) | 615 B | `e791a470ec200f82` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/answer.txt`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/answer.txt) | 6 B | `9ca73c56172a2267` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/delivery.json`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/delivery.json) | 943 B | `7484ac87b3fd48ab` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/delivery.md`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/delivery.md) | 927 B | `0c0ac26f788f8ad4` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/install_transcript.txt`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/install_transcript.txt) | 1017 B | `de6325b598d382e4` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/mock.jsonl) | 3.6 KB | `fb7504ec7aa37b45` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/pi_exit`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/scenario.json`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/scenario.json) | 458 B | `bb83005acdc15446` |
| [`ops/eval/evidence_20260925/simuser/made_up_number_C/task.txt`](../../../ops/eval/evidence_20260925/simuser/made_up_number_C/task.txt) | 615 B | `e791a470ec200f82` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_A/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/missing_answer_A/mock.jsonl) | 416 B | `6248ca566d7ebde0` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_A/pi_exit`](../../../ops/eval/evidence_20260925/simuser/missing_answer_A/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_A/scenario.json`](../../../ops/eval/evidence_20260925/simuser/missing_answer_A/scenario.json) | 320 B | `702ce03e4f765df0` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_A/task.txt`](../../../ops/eval/evidence_20260925/simuser/missing_answer_A/task.txt) | 586 B | `6505bd6d9a84efb6` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/answer.txt`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/answer.txt) | 3 B | `41b602a7dcbcba75` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/delivery.json`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/delivery.json) | 942 B | `0f6434831c609cfe` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/delivery.md`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/delivery.md) | 709 B | `028b863be721f4fd` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/install_transcript.txt`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/install_transcript.txt) | 1017 B | `de6325b598d382e4` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/mock.jsonl`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/mock.jsonl) | 2.4 KB | `d4e5c593377a446e` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/pi_exit`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/pi_exit) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/scenario.json`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/scenario.json) | 320 B | `702ce03e4f765df0` |
| [`ops/eval/evidence_20260925/simuser/missing_answer_C/task.txt`](../../../ops/eval/evidence_20260925/simuser/missing_answer_C/task.txt) | 586 B | `6505bd6d9a84efb6` |

## 證據：閘門 2（Harbor 裡，L-fake）

Harbor 裡 A=0.0、C=1.0（沒寫答案檔被退回、補寫）

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/gate2/GATE2.md`](../../../ops/eval/evidence_20260925/gate2/GATE2.md) | 1.6 KB | `820949909a00f12d` |
| [`ops/eval/evidence_20260925/gate2/mock.jsonl`](../../../ops/eval/evidence_20260925/gate2/mock.jsonl) | 2.9 KB | `954844de2d0c1116` |
| [`ops/eval/evidence_20260925/gate2/scenario.json`](../../../ops/eval/evidence_20260925/gate2/scenario.json) | 265 B | `9dbca2232fbd694f` |
| [`ops/eval/evidence_20260925/gate2/A/pi.txt`](../../../ops/eval/evidence_20260925/gate2/A/pi.txt) | 25.3 KB | `2ca182714f4d8a68` |
| [`ops/eval/evidence_20260925/gate2/A/result.json`](../../../ops/eval/evidence_20260925/gate2/A/result.json) | 5.2 KB | `c4ff9d1e832f1af9` |
| [`ops/eval/evidence_20260925/gate2/A/reward.txt`](../../../ops/eval/evidence_20260925/gate2/A/reward.txt) | 2 B | `9a271f2a916b0b6e` |
| [`ops/eval/evidence_20260925/gate2/A/test-stdout.txt`](../../../ops/eval/evidence_20260925/gate2/A/test-stdout.txt) | 64 B | `4ce2ffe5489a6362` |
| [`ops/eval/evidence_20260925/gate2/C/delivery.json`](../../../ops/eval/evidence_20260925/gate2/C/delivery.json) | 942 B | `e033440ce4b4d43d` |
| [`ops/eval/evidence_20260925/gate2/C/delivery.md`](../../../ops/eval/evidence_20260925/gate2/C/delivery.md) | 709 B | `0e4088f354ef4d2c` |
| [`ops/eval/evidence_20260925/gate2/C/pi.txt`](../../../ops/eval/evidence_20260925/gate2/C/pi.txt) | 30.6 KB | `3deb014395dd1295` |
| [`ops/eval/evidence_20260925/gate2/C/result.json`](../../../ops/eval/evidence_20260925/gate2/C/result.json) | 5.2 KB | `bcf5cedd5b4d5eff` |
| [`ops/eval/evidence_20260925/gate2/C/reward.txt`](../../../ops/eval/evidence_20260925/gate2/C/reward.txt) | 2 B | `4355a46b19d348dc` |
| [`ops/eval/evidence_20260925/gate2/C/test-stdout.txt`](../../../ops/eval/evidence_20260925/gate2/C/test-stdout.txt) | 67 B | `aaaf2b8f1ddc2734` |
| [`ops/eval/evidence_20260925/gate2/C/vacant_check.json`](../../../ops/eval/evidence_20260925/gate2/C/vacant_check.json) | 177 B | `d4531704c4b7a605` |

## 證據：校準與題目清單

校準（困難題 1716）、釘死環境與正式 79 題的清單

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json`](../../../ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json) | 11.6 KB | `ddf4a962f612b582` |
| [`ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json`](../../../ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json) | 907 B | `88426617d2499b27` |
| [`ops/eval/evidence_20260925/pilot/calibration/CALIBRATION.md`](../../../ops/eval/evidence_20260925/pilot/calibration/CALIBRATION.md) | 1.2 KB | `94770794deccdf04` |
| [`ops/eval/evidence_20260925/pilot/calibration/gemma_on_1716.json`](../../../ops/eval/evidence_20260925/pilot/calibration/gemma_on_1716.json) | 1.5 KB | `1c9635df3ca2d1e4` |
| [`ops/eval/evidence_20260925/pilot/calibration/ledger_by_tag.json`](../../../ops/eval/evidence_20260925/pilot/calibration/ledger_by_tag.json) | 1.4 KB | `9c4e2fed96ee28a4` |
| [`ops/eval/evidence_20260925/pilot/calibration/qwen_on_1716_r2.json`](../../../ops/eval/evidence_20260925/pilot/calibration/qwen_on_1716_r2.json) | 1.6 KB | `275ce33e0aff9393` |

## 證據：正式批次

執行紀錄、逐通帳、分析輸出、全部請求／回應本文與 318 跑 Harbor 目錄的壓縮檔

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/formal/ARCHIVES.sha256`](../../../ops/eval/evidence_20260925/formal/ARCHIVES.sha256) | 170 B | `ee3dfc5efecc1b3c` |
| [`ops/eval/evidence_20260925/formal/RUNLOG.md`](../../../ops/eval/evidence_20260925/formal/RUNLOG.md) | 1.8 KB | `261b0956ef25c19c` |
| [`ops/eval/evidence_20260925/formal/formal_io.jsonl.xz`](../../../ops/eval/evidence_20260925/formal/formal_io.jsonl.xz) | 3.7 MB | `075bb8690ab7ad5a` |
| [`ops/eval/evidence_20260925/formal/formal_jobs.tar.xz`](../../../ops/eval/evidence_20260925/formal/formal_jobs.tar.xz) | 3.1 MB | `14d1dbdd6cedcd22` |
| [`ops/eval/evidence_20260925/formal/ledger_formal.jsonl`](../../../ops/eval/evidence_20260925/formal/ledger_formal.jsonl) | 1.3 MB | `8c37960fccf1c143` |
| [`ops/eval/evidence_20260925/formal/ledger_summary.json`](../../../ops/eval/evidence_20260925/formal/ledger_summary.json) | 72.2 KB | `9e24011e05c1f4d6` |
| [`ops/eval/evidence_20260925/formal/progress.jsonl`](../../../ops/eval/evidence_20260925/formal/progress.jsonl) | 20.9 KB | `955a986a4ec69ab2` |
| [`ops/eval/evidence_20260925/formal/reruns.json`](../../../ops/eval/evidence_20260925/formal/reruns.json) | 80 B | `c0fac18c21d15606` |
| [`ops/eval/evidence_20260925/formal/result.json`](../../../ops/eval/evidence_20260925/formal/result.json) | 3.0 KB | `18b090745a61cc6a` |
| [`ops/eval/evidence_20260925/formal/runs.json`](../../../ops/eval/evidence_20260925/formal/runs.json) | 210.4 KB | `5aa19273fa96b9b7` |

## 證據：調查（2026-09-26）

為什麼沒有差別：過去實驗對照、失敗分類、文獻、兩跑的探索性估計；先讀 README

| 檔案 | 大小 | sha256（前 16 碼） |
|---|---:|---|
| [`ops/eval/evidence_20260925/investigation/README.md`](../../../ops/eval/evidence_20260925/investigation/README.md) | 3.3 KB | `899131d0b7d78e4c` |
| [`ops/eval/evidence_20260925/investigation/factcheck_report.md`](../../../ops/eval/evidence_20260925/investigation/factcheck_report.md) | 9.1 KB | `bf6badd2d9bf31f4` |
| [`ops/eval/evidence_20260925/investigation/failure_taxonomy.json`](../../../ops/eval/evidence_20260925/investigation/failure_taxonomy.json) | 28.9 KB | `731fbdfd4cdc8f5d` |
| [`ops/eval/evidence_20260925/investigation/failure_taxonomy.md`](../../../ops/eval/evidence_20260925/investigation/failure_taxonomy.md) | 22.6 KB | `e3ac9c179e7aace4` |
| [`ops/eval/evidence_20260925/investigation/literature.json`](../../../ops/eval/evidence_20260925/investigation/literature.json) | 28.3 KB | `9afeb3fb66dc5709` |
| [`ops/eval/evidence_20260925/investigation/literature.md`](../../../ops/eval/evidence_20260925/investigation/literature.md) | 24.1 KB | `e0eddc1dad8afa05` |
| [`ops/eval/evidence_20260925/investigation/past_results.json`](../../../ops/eval/evidence_20260925/investigation/past_results.json) | 31.0 KB | `50fdd55d7e0c31af` |
| [`ops/eval/evidence_20260925/investigation/past_results.md`](../../../ops/eval/evidence_20260925/investigation/past_results.md) | 26.7 KB | `33ecede8815e6a11` |
| [`ops/eval/evidence_20260925/investigation/two_runs.json`](../../../ops/eval/evidence_20260925/investigation/two_runs.json) | 36.9 KB | `cc1c7dbe869a0314` |
| [`ops/eval/evidence_20260925/investigation/verify_dabstep_results.json`](../../../ops/eval/evidence_20260925/investigation/verify_dabstep_results.json) | 43.2 KB | `022944035b440b3d` |
| [`ops/eval/evidence_20260925/investigation/workflow_verify-dabstep-results.js`](../../../ops/eval/evidence_20260925/investigation/workflow_verify-dabstep-results.js) | 6.8 KB | `b6a66eb1d7ec69de` |
| [`ops/eval/evidence_20260925/investigation/workflow_why-zero-config-null.js`](../../../ops/eval/evidence_20260925/investigation/workflow_why-zero-config-null.js) | 6.9 KB | `944ded130e81b293` |
| [`ops/eval/evidence_20260925/investigation/helpers/caps.py`](../../../ops/eval/evidence_20260925/investigation/helpers/caps.py) | 3.4 KB | `7ca182c346c9005b` |
| [`ops/eval/evidence_20260925/investigation/helpers/conv.py`](../../../ops/eval/evidence_20260925/investigation/helpers/conv.py) | 1.5 KB | `48e40dd6cb031840` |
| [`ops/eval/evidence_20260925/investigation/helpers/conv2.py`](../../../ops/eval/evidence_20260925/investigation/helpers/conv2.py) | 2.1 KB | `bec36e48b1a1e179` |
| [`ops/eval/evidence_20260925/investigation/helpers/ctx.py`](../../../ops/eval/evidence_20260925/investigation/helpers/ctx.py) | 971 B | `354b73680e585485` |
| [`ops/eval/evidence_20260925/investigation/helpers/dump.py`](../../../ops/eval/evidence_20260925/investigation/helpers/dump.py) | 1.4 KB | `b7a384a2e2c24b2b` |

## 這一輪的提交（依時間）

從 `a80a295a`（評測計畫第 2 版）到索引產生時的 HEAD，只列觸及這一輪程式、測試、評估工具、裁決、文件的提交。

| commit | 時間（UTC） | 說明 |
|---|---|---|
| `a80a295a` | 2026-09-25 12:15 | docs(eval): 零設定可究責的評測計畫（第 2 版，草稿待核准）＋研議證據 |
| `42bb5d1e` | 2026-09-25 12:17 | docs(eval): 計畫裡的「老闆」改成「人類」（和其他裁決文的稱呼一致） |
| `01f30fa8` | 2026-09-25 13:04 | docs(eval): 閘門 1——三個小模型在 Harbor＋pi 上各跑 4 題官方題（A 組，不裝 Vacant） |
| `5c9c0309` | 2026-09-25 13:25 | feat(eval): 記帳代理加思考開關、每一跑上限、主機 id；計畫記下人類的裁決 |
| `9331309a` | 2026-09-25 13:25 | docs(eval): 預算不加值；放不下就只跑 DABstep，開思考優先 |
| `b217186c` | 2026-09-25 13:30 | fix(trace): 誰說了這個值——vacant do 的回饋不再洗掉 agent 自己的錯、任務訊息只對那一跑算數、排程／信封只認真形狀 |
| `b8b78304` | 2026-09-25 13:40 | docs: 產品原則寫進 CLAUDE.md 與 LOOP.md——裝一次照常用、零設定、安裝最小、先產品等級再評測 |
| `5e32ae96` | 2026-09-25 13:49 | fix(trace): 後果要是文件說的意思、完整性要程式對得出來（審查 §10 第 7、8、10、16 列） |
| `6cf8b8f6` | 2026-09-25 14:53 | merge xpath/sources: 跨路徑審查的修正（xpath/sources） |
| `630e3b9f` | 2026-09-25 14:53 | merge xpath/consequences: 跨路徑審查的修正（xpath/consequences） |
| `5a99cb91` | 2026-09-25 15:12 | 零設定 C 組設計 v2＋回饋字句：整檔新建的那一步寫成「建立它的那一步」 |
| `a86743c2` | 2026-09-25 15:00 | feat(zero): 第 1 步——裝了就有作用：模式開關、沒有契約也記錄、預設不裝技能 |
| `3bfecc17` | 2026-09-25 15:13 | feat(zero): 第 2–4 步——交件前檢視的字句、pi 帶最後訊息、證據檢查 |
| `8f8f4c7e` | 2026-09-25 15:36 | feat(zero): 第 6–7 步——沒有契約的回合結束：證據檢查、退回、交件說明；真實紀錄重播 |
| `145f1873` | 2026-09-25 15:43 | feat(zero): 第 8 步——模擬使用者驗收（只照 README 裝、照常用 pi，A/C 對照） |
| `c3f9f6bd` | 2026-09-25 15:48 | feat(eval): 第 9 步——C 組的 Harbor 包裝＋閘門 2（Harbor 裡 A/C 對照，假模型） |
| `0b125a56` | 2026-09-25 15:54 | feat(eval): 試點工具——釘死的 DABstep 環境、每一跑的驅動、彙整 |
| `0150902e` | 2026-09-25 15:57 | eval: 正式 79 題的組法＋DABstep 預註冊草稿（未簽） |
| `def0c8ee` | 2026-09-25 16:03 | fix(eval): 記帳代理——串流裡的供應商錯誤（200＋data 裡的 429）要重試，不當成回答轉給 agent |
| `c9a7ee1b` | 2026-09-25 16:14 | eval: C 組檢查分開「裝上了」與「走到交件前檢查」；重跑用獨立標籤 |
| `58bf3ea7` | 2026-09-25 17:00 | eval: 校準紀錄——gemma 困難題 15 回合用完（約 0.04 美元／跑）；qwen 的 darkbloom/fp4 幾乎每一通限流 |
| `8b22c7cc` | 2026-09-25 17:05 | eval: 正式批次的驅動（種子順序、同題 A/C 同時、看花費停、可續跑）＋正式 79 題的清單 |
| `49310aec` | 2026-09-25 17:06 | prereg: DABstep 零設定 A/C 預註冊——人類簽字、凍結 |
| `dd836318` | 2026-09-25 17:08 | eval: 正式批次的分析腳本（在看任何正式結果之前寫好） |
| `ebcb959d` | 2026-09-25 20:07 | eval: 正式批次——容器重啟後的紀錄；補跑取時間上最後一跑、成本讀補跑標籤 |
| `90102c38` | 2026-09-25 20:13 | eval: RUNLOG——gemma 的兩跑補跑完成，續跑 qwen |
| `3c0ad49f` | 2026-09-25 21:37 | eval: 正式批次的原始紀錄（全部請求／回應本文、318 跑的 Harbor 目錄）與分析輸出 |
| `efda0d1f` | 2026-09-25 21:41 | 結論：零設定 Vacant 在 DABstep 正式批次沒有量到差別；修正正式批次暴露的兩個誤報 |
| `faa452cb` | 2026-09-26 00:40 | 結論更正：獨立重算（三個 agent＋批評者）之後的更正與補充 |
| `386d37d4` | 2026-09-26 01:11 | 調查：零設定 Vacant 在 DABstep 為什麼沒有量到差別——總報告＋證據索引 |

## 不在 git 裡的東西

- OpenRouter 金鑰：只在記帳代理的行程裡讀，從未寫進任何檔（所有證據檔都掃過 `sk-or-v1`）。
- 題目容器映像 `vacant-eval/dabstep-env:1`（ID 在 `pilot/PIN_MANIFEST.json`）：可用 `ops/eval/dabstep_pin.py` 從官方 Dockerfile＋釘死的資料重建。
- 這台雲端機器的暫存區（scratchpad）：原始工作目錄在評估結束後不保證存在；需要的都已壓縮進 `formal/`。
