# G3 三臂名實相符修復＋AMEND-1——交接與後續（fix/g3-arms-actually-do-what-they-say）

> 2026-11-11。來源：11/11 日報 P0（「G3 三臂沒有實作成宣稱的三種系統」）。
> 本分支在 origin/auto/qwen27b@506ab8545（r1418）之上修復；未動任務清單、
> 任務輸入 sha256 全部不變。兩個 commit：
> (1) P0 修復（full_rloop 真接 checks 重算／conformance 門／抓假測試）；
> (2) **AMEND-1（2026-11-11 人類裁決，口頭指示：native_pi 接真 pi、模型用
> 本地的 lms1003qwen）**——pi 臂接線本輪完成。

## 一、AMEND-1 之後的三臂（全部有名有實、有測試背書）

1. **native_pi＝真 pi 工具迴圈**：`PiChannel`（`vacant_network/reqloop/g3.py`）。
   每格一次 pi session：`repair.prepare_workspace` 建任務輸入複本（goal/
   contract/data，原任務檔不動）→ `pi_build`（`--provider lms1003qwen
   --model qwen/qwen3.8-27b`，與 G2 CLI 同參數）＋`pin_agent_python`＋
   `run_agent` → 讀回 answer.txt 作為草稿。usage 從 agent stdout raw usage
   讀（`repair.parse_usage_from_log`），缺值＝UNKNOWN 不填 0。agent 失敗
   （rc≠0／逾時／spawn／沒寫 answer.txt）→ G3CallError（該格 error、不重試）。
2. **通道分流**：`_ArmChannelRouter`——pi 臂→PiChannel（本地模型），glm 臂
   與需求擷取→GlmChannel；**兩入口共用同一 QuotaGuard＝同一日額度界**。
   通道注入缺失→拒發（G3ArmsNotConformant、0 模型呼叫）。
3. **預算如實宣告**（`ops/reqloop/g3_gate/manifest.json` AMEND-1 區塊）：
   `model_entry='glm+local_pi'`＋`pi_provider='lms1003qwen'`＋
   `pi_model='qwen/qwen3.8-27b'`。`g3gate.check_budget`：白名單
   'glm'｜'glm+local_pi'；**arms 含 native_pi 而未宣告 local_pi 入口即拒**；
   pi_provider/pi_model 缺失或空字串即拒。**舊核准文件已作廢，發射前須按
   amended manifest 重新核准**（approval_gate 仍 fail-closed）。
4. （前次 P0 修復不變）full_rloop 真接 `checks.run_requirement_checks`
   程式重算＋localized FAIL-only 反饋（不含重算期望值）＋reverify_all＋
   `repair.diff_results` 差異記帳；reqlist_only 不獲得重驗能力（臂間差異
   才可歸因）；`required_answer_names` 修掉範本 placeholder 恆真假缺口。

## 二、發射前置清單（給要真發射的那一輪）

1. `git merge fix/g3-arms-actually-do-what-they-say`（或把分支 rebase 到
   當時 HEAD；凍結 manifest 只有 budget 三欄位＋AMEND-1 區塊，任務 sha 不變，
   不會衝突凍結門）。
2. 跑綠：`tests/test_reqloop_g3.py`、`tests/test_reqloop_g3_conformance.py`、
   `tests/test_reqloop_g3gate.py`、freeze 套件（GUARD_CONTENT_PIN 已依紀律
   顯式更新並留 r1419/r1420 解凍記錄——**不要為了過 pin 把記錄刪掉**）。
3. 本機冒煙：`python3 -m vacant_network.reqloop.g3gate --plan` → PLAN OK；
   `python3 -m vacant_network.reqloop.g3 --dry-run` → 12 格列出、
   `arm conformance: OK`。
4. 真發射：pi 環境必須可用（`pi -p --mode json`＋provider `lms1003qwen`＋
   本地模型服務；G2 repair 已在用同一路徑，同一機器應已具備）。核准文件
   （approved=true、epic=vq-1zf、by=人類）→ `--fire`。三臂＝
   native_pi×4（pi session）＋reqlist_only×4＋full_rloop×4（glm）＋擷取×4。
5. 打分照舊送 /srv/vlab scorer；hidden_after 全 UNKNOWN；full_rloop 的
   content_reverify 記錄（PASS/FAIL/UNKNOWN＋diff）只是 controller 側證據，
   不代替打分。

## 三、驗證記錄（2026-11-11，本機 macOS，repo venv）

- `tests/test_reqloop_g3.py`＋`tests/test_reqloop_g3_conformance.py`＋
  `test_reqloop_g3gate.py`：64 passed（含 12 格三臂假通道發射、
  pi channel 注入缺失拒發、PiChannel workspace／usage／錯誤語義、
  預算門 AMEND-1 負控）。
- `tests/test_reqloop_freeze_check.py`：與乾淨 HEAD 基線**逐項一致**
  （僅本機環境既有 4 紅：queue_empty ×2＝macOS/Python repr 截斷；
  ci_contract＝本 venv 未 `pip install -e .[dev]`；diff_worker/diff_argon＝
  auto/* 分支已前進的跨分支 diff——本機必紅，loop 機上應綠）。
  GUARD_CONTENT_PIN 更新後 guard_content_pin 全綠。

## 四、給 loop agent 的規則（順序即優先級）

1. conformance 門是特性不是故障；**不要為了讓 fire 跑起來而改
   ARM_WIRED／ARM_REQUIRED／GUARD_CONTENT_PIN 的記錄**——那就是
   H-0「同名換內容」假綠燈的入口。
2. 每加一個臂，必須同一輪交付：(a) 接線；(b) ARM_WIRED 如實更新；
   (c) 一個「格式完整但內容錯誤」的抓假測試（抓得到才算接線）。
3. native_pi 的 300s/輪是 pi session 的牆時；agent 沒寫 answer.txt＝
   該格 error，不重試、靜默續跑。
4. 簿記輪次請記 no-op 並設上限；分支同步/狀態鏡像不計入交付。
