# 閘門 2：C 組的包裝在 Harbor 裡真的有作用（2026-09-25，L-fake，不花錢）

同一個評測框架（Harbor @ 6cb9ff3）、同一個題目（DABstep `dabstep-5`）、同一組旗標（`--ak max_turns=15
--ak model_api=openai-completions --ak version=0.87.1`），模型換成照劇本回答的假模型（`ops/intake/mock_model.py`，
劇本 `scenario.json`：算出答案、**沒寫答案檔**就說做完；看到退回之後寫 `NL`）。

| | A（`--agent pi`） | C（`--agent harbor_vacant:PiWithVacant`） |
|---|---|---|
| Harbor 評分 | **0.0**（沒有 `/app/answer.txt`） | **1.0** |
| 模型請求數 | 2 | 4（多的兩通＝退回之後的那一輪） |
| `vacant_check.json` | — | `pi_installed: true`、2 個步驟、2 次交件前檢查（`continue` → `allow`）、`c_arm_ok: true` |
| 交件說明 | — | `round 1: answer.txt (asked for in the request) did not exist; it was written afterwards` |

C 組的包裝（`ops/eval/harbor_vacant.py`）只比 A 組多做使用者的安裝指令：沒有 pipx 就用 apt 裝、`pipx install <wheel>`、
`vacant install`（在 Harbor 給 pi 的設定目錄 `PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent` 裡——評測框架的隔離，記在偏差欄）。
不設任何 Vacant 環境變數。重跑：`ops/eval/gate2/run_gate2.sh <harbor 目錄> <jobs 目錄> <wheel> <劇本>`。

⚠ L-fake：劇本決定了模型看到退回之後會寫檔。這一份證明的是「包裝把 Vacant 裝上了、檢查在 Harbor 的 pi 裡真的跑、
退回真的送到模型、Harbor 的評分看得到改過的檔」，不是真模型會不會照做。
