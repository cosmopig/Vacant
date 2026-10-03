# 交接：在另一台算力上重跑「零設定 Vacant v3.6.1 × DABstep、不設回合上限」評測（2026-09-27）

> 讀者：一個**沒看過這個專案**、在**另一台機器**（可能是另一個模型／端點）上工作的 AI agent。
> 從上到下照做就能跑完。`<像這樣>` 的是佔位字，要換成你那台機器的值；標 **〔環境〕** 的是這次評測所在的雲端容器才有、repo 裡沒有、你要自己重建的東西。
> 每個事實後面的 `路徑:行` 是出處（相對 repo 根）。寫這份時 repo 的分支頭是 `6471cd7b`（2026-09-27T11:11Z）；這份文件在其後的 commit 收進 `docs/HANDOFF_EVAL_2026-09-27.md`
> （`git log --format='%h %cI' -- docs/HANDOFF_EVAL_2026-09-27.md` 看得到；它引用的 repo 路徑在那個 commit 都在）。**先讀第 6.6 節**：這個設計在慢的算力上會被 1800 秒時限吃掉。
> **佔位字一律用絕對路徑**（`<REPO>`、`<WORK>`、`<HARBOR_DIR>`、`<PINNED_450>`、`<WHEEL>`、`<JOBS>`、`<LEDGER>`）：`run_local.sh` 先 `cd` 進 Harbor 目錄才用資料集、jobs、wheel 路徑（`ops/eval/local/run_local.sh:21-25,37`；`ops/eval/harbor_vacant.py:68`），相對路徑會解析到 Harbor 底下。`<WORK>` 放在 repo 外面。
> `<P>`＝你這一批的標籤前綴（例 `x274`；**不可以是 `u274`、不可以有 `-`**——分析用「`<P>-` 開頭」比對標籤，`ops/eval/local/analyze_local.py:101`）；前測／重啟探針用 `<P>preflight`、`<P>restartprobe`（不要 `<P>-…`，否則會被算進 `<P>-` 開頭的統計）。

---

## 0. 一段話

Vacant 零設定：使用者只打 `pipx install vacant-network` 和 `vacant install`（`README.md:24-27`），之後照常用 agent；Vacant 記下每一步，
在 agent 說「做完了」時（pi 的 `agent_before_settle`，`vacant_network/adapters/agents.py:404`）只看紀錄做一次檢查，
**只有五類**會退回請 agent 重做——`missing_output`（要求寫的檔不存在）、`failed_step`、`test_claim`、`unsourced`、`unread`（`vacant_network/trace/review.py:37`）——
一個要求內最多 2 回合（`vacant_network/trace/zerostop.py:45`），其他只寫進給人的交件說明；**它不判斷答案對錯**（`CLAUDE.md:196`）。
要測的：同一個 agent（Harbor 裡的 pi 0.87.1）、同一個模型、同一批 DABstep hard 題，**A＝沒裝** 對 **C361＝裝了 v3.6.1（只用使用者的安裝指令）**，
**不設回合上限**（只剩題目自己的 1800 秒時限），主要檢定是配對的 McNemar 精確雙尾（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:59-65`）。
現況：**S36-nocap 判定 GO，但那是篩選不是證據**——36 題是看過正式批次的 A 才選的，p＝0.0074 只是描述（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:194-206`）。
真正的檢定是 **u274 預註冊批次**（274 題沒用過的 hard 題；agent 在 `6ab08c91`〔2026-09-27T10:50:36Z〕凍結、**人類沒有逐條簽字**，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:86-88`），正在**人類自己的兩台 LM Studio** 上跑（10:50:44Z 開跑、11:10Z 觸發並行規則降成 3＋3，`ops/eval/evidence_20260926_local/RUNLOG.md:160-168`），
**還沒有結果，也沒有人看過評分**。你要做的是**另一份新的預註冊批次**（不同算力＝不同實驗），**不是** u274 的一部分，結果不可和 u274 合併或合併分析（除非另一份預註冊事先寫明）。

---

## 1. 必讀與禁區

### 1.1 安全（違反就停）

- **不打開、不印任何憑證檔**：`~/.claude*`、`auth.json`、`.env`、`*.key`、`~/.config/vacant-eval/`（記帳代理預設的金鑰路徑，`ops/eval/orproxy.py:411`）。
  本機模式（設定檔有 `upstreams`）代理**根本不讀**金鑰檔（`ops/eval/orproxy.py:417`）；容器裡的 agent 只拿到假金鑰 `sk-dummy`（`ops/eval/local/run_local.sh:29`）。
- 金鑰、機器主機名、個人資料**不進 repo、不進 log、不進 commit 訊息**。代理本身不記 Authorization 標頭（`ops/eval/orproxy.py:14-15`）。
- **代理沒有任何驗證**（`ops/eval/orproxy.py:224-310` 沒有檢查）：綁 `0.0.0.0` 的機器若有對外介面，別人可以打你的模型；付費模式下可以花你的錢 ⇒ 照 6.1 用防火牆只開給 docker 橋接與本機。
- **付費（OpenRouter）只在人類明確授權、給了額度之後才用**。上一輪整個帳號的付費硬上限是 $4.80（`ops/eval/evidence_20260925/proxy_config.json:2`）；「剩約 $1.10」（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:141`）是**快照回捲之前**的估計，
  而舊帳本回捲後少了約 $0.29（第 0 階，`ops/eval/evidence_20260926_local/RUNLOG.md:136-137`；`ops/eval/evidence_20260926_local/api_tier0/ledger_probe.jsonl`）。新帳本從 0 起算 ⇒ `budget_usd` **絕不是 4.80**，
  而是人類對照 OpenRouter 用量頁確認過的剩餘額度；沒有人類給的數字就不開付費代理。
- **不要把上游指到人類的兩台機器**（u274 正在用、並行數是預註冊釘死的，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:37,52-53`）；不要從 repo 裡已經出現的網址抄（`ops/eval/evidence_20260926_local/RUNLOG.md:4`、`decisions/prereg/PREREG_20260926_ZERO_CONFIG_V3_LOCAL.md:31,78-79`）。你的上游必須是另外的算力；不確定就停下來問人。
- 人類原話裡的網址、主機名、IP、金鑰、帳號，寫進 RUNLOG／預註冊前一律換成代號（如 `<UP1>`）。上游名字、`host_id`、`<算力名>` 也要是代號：它們會隨每一跑的 `config.json`（base URL 裡的 `/up/<名字>/`，`ops/eval/local/run_local.sh:15`）、帳本（`ops/eval/orproxy.py:391-392`）與歸檔（`ops/eval/local/archive_raw.py:75-86`）push 上去。上一輪兩台的主機名就是隨人類原話進了 repo（上面兩處）。
- **批次跑的時候不看任何評分**（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:57`）：不讀 `verifier/reward.txt`、`verifier/test-stdout.txt`（裡面印著標準答案，`<釘死目錄>/dabstep-N/tests/test.sh` 的 `echo "Expected: …"`）、不跑分析腳本。
  上一輪有一次在跑的批次上測新解析器、意外看到中途計數，必須在 RUNLOG 自首（`ops/eval/evidence_20260926_local/RUNLOG.md:101-105`）。
- **不碰 u274**：不寫 `ops/eval/evidence_20260927_nocap/u274/`、不改 `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md` 與 `ops/eval/local/launch_u274.sh`（凍結，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:1`）。
  這個工作階段的歸檔迴圈每 2 小時 push 到 `claude/vacant-verification-redesign-jv7eou`（`ops/eval/local/archive_loop.sh:17`）⇒ **你在自己的分支上工作、push 自己的分支**。
- **不讀 u274 的原始資料**：`ops/eval/evidence_20260927_nocap/u274/raw/chunk_*.tar.xz` 整包收了每一跑的目錄，含 `verifier/reward.txt` 與印著標準答案的 `test-stdout.txt`（`ops/eval/local/archive_raw.py:6,80-84`）。
  在 u274 的 `CONCLUSION` commit 出現之前：不解開、不 `tar -t`、不 grep、不分析，也不 cherry-pick／merge 那些 commit（u274 不准有中途評分，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:51,57`）。
  收進這份文件的 commit 裡 u274 只有 `driver.log`、還沒有任何 chunk ⇒ 從那個 commit 開分支（第 2 節）；之後的 commit 會有 chunk，照樣不打開。

### 1.2 和評測有關的鐵律

| 規則 | 在這裡的意思 | 出處 |
|---|---|---|
| 產品原則 3：安裝最小 | C 組只做使用者會打的安裝指令（`ops/eval/harbor_vacant.py` 已經做好），**不設任何 Vacant 環境變數**（`VACANT_MODE`、`VACANT_TRACE`、`VACANT_HOOK_NO_STOP`、`VACANT_HOME`），不加 `--skill`、不加 `--budget-reminder` | `CLAUDE.md:26`；`ops/eval/harbor_vacant.py:13`；`vacant_network/adapters/cli.py:282-287` |
| 鐵律 1 KS-1 | 退回的字句不准改（改了就是另一個產品）；字句在 `vacant_network/trace/review.py`，匯入時就會檢查 | `CLAUDE.md:339` |
| 鐵律 3 全 I/O 落盤 | 每一通模型呼叫都要經過記帳代理 `ops/eval/orproxy.py`（`io.jsonl` 全文、`ledger.jsonl` 逐通帳）；分析也靠它判 infra_void | `CLAUDE.md:343`；`ops/eval/local/analyze_local.py:33-41` |
| 鐵律 5 | demo／篩選只能說「看得到」；「證明」只留給預註冊批次，而且要人類逐條簽字 | `CLAUDE.md:345`；`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:86-88` |
| 預註冊 | 開跑前寫好、commit＋push 凍結；凍結後不改，要改＝另一份 | `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:1` |
| 用詞 | 用「可究責性／讓依賴有根據」，不用「信任」 | `CLAUDE.md:51` |

### 1.3 口徑

| ✅ 可以說 | ❌ 不可以說 |
|---|---|
| 「沒有退回時，模型收到的每一通請求和沒裝時逐位元組相同」（`CLAUDE.md:193`） | 「Vacant 讓 agent 做得更好」（不帶條件）、「Vacant 沒有用」、「讓成績變差」（`CLAUDE.md:196`） |
| 「預註冊的批次量到／沒量到差別」＋模型、算力、題庫、上限設定、p 值、點估計 | 「Vacant 判斷答案對錯」（它只看每一步有沒有根據、檔在不在）（`CLAUDE.md:196`） |
| 若 C 較好：一定同時說**機制**——agent 說做完卻沒把答案寫進要求的檔，退回後它把**已經說出口的答案**寫進檔；**不是答案變好**（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:69-71`） | 「沒有效果」（不顯著時只能說「這一輪沒有量到差別」）（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:72`） |
| S36-nocap、探針＝「篩選」「機制量測」 | 把 S36-nocap 的 p＝0.0074 當證據；外推到別的模型／題庫／有上限／easy 題／開思考（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:74`） |

⚠ `CLAUDE.md:209` 的「留出批次在跑」已過時（資料遺失，RUNLOG §15）；`CLAUDE.md:193-209` 的所有 ❌ **仍然有效**（包括「外推到沒有上限的互動使用」）。
`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §十一–§十三、RUNLOG §15–§17、u274 預註冊是**加在其上**的（S36-nocap／v3.6.1／u274 的口徑），不取代。

---

## 2. 取得程式碼

```bash
git clone -b claude/vacant-verification-redesign-jv7eou https://github.com/cosmopig/Vacant.git <REPO>
cd <REPO>
git checkout -b <你的分支> $(git log -1 --format=%H -- docs/HANDOFF_EVAL_2026-09-27.md)   # 從收進這份文件的 commit 開分支；不要在 u274 的分支上 commit／push
ls ops/eval/evidence_20260927_nocap/u274/raw/ 2>/dev/null   # 有 chunk_*.tar.xz 也不要打開（1.1）
# 產品＝v3.6.1＝commit c27641c6 的 vacant_network/；之後的 commit 只動評測工具與證據
git diff --quiet c27641c6 HEAD -- vacant_network pyproject.toml && echo "product == v3.6.1"
# 評測工具＝u274 凍結的版本（6ab08c91）；結果寫進你的預註冊
git diff --quiet 6ab08c91 HEAD -- ops/eval/local/{run_pairs.py,run_local.sh,rerun_void.py,analyze_local.py,unseen_analyze.py,s36nc_analyze.py,make_unseen.py,archive_raw.py,archive_loop.sh,monitor.sh,launch_u274.sh} \
  ops/eval/harbor_vacant.py ops/eval/orproxy.py ops/eval/dabstep_pin.py ops/eval/formal/analyze.py && echo "tooling == u274"
# （之後新增的 ops/eval/local/ops_report.py 是運作紀錄，不在 u274 凍結的清單裡，第 9 節）
uv venv -p 3.11 .venv && uv pip install -p .venv/bin/python -e '.[dev]'   # 要 Python ≥ 3.11（pyproject.toml:9）；系統 python3 太舊時 uv 會自己抓
# git 身分與 push 權限（凍結與歸檔都要 commit＋push）
git config user.name '<名字>'; git config user.email '<信箱>'
git remote set-url origin <你有寫入權限的 repo 或 fork>      # 匿名 https clone 推不上去
git push -u origin <你的分支> && git ls-remote origin <你的分支>   # 開跑前就要確認推得上去
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_zero_budget.py tests/test_zero_evidence.py tests/test_zero_mode.py tests/test_zero_stop.py \
  tests/test_adapters_agents.py tests/test_adapters_core.py tests/test_adapters_hardening.py \
  tests/test_trace_stop.py tests/test_eval_run_pairs.py tests/test_eval_orproxy.py
```

- v3.6.1＝`c27641c63625896addb112f2639aedee477cdbd6`，最後一個動到 `vacant_network/` 的 commit（`git log -1 -- vacant_network/`）。
  u274 的預註冊在 `6ab08c9179ac55d66c190cd8dad76363b12c6b6a` 凍結（驅動與分析＝那個 commit 的版本，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:39`）；上面的 `tooling == u274` 在寫這份時成立。你的預註冊要引用 `6ab08c91`。
- 你改的腳本（`run_local.sh` 的 CA／橋接位址／`MODEL` 等；`run_pairs.py` 寫死用這一支，`ops/eval/local/run_pairs.py:36`）只留在你的分支；u274 的結論出來之前**不 merge、不開 PR** 到 `claude/vacant-verification-redesign-jv7eou`。
- 沒有 push 權限就不要開跑：`archive_loop.sh` 不管 push 成不成功都印 "archived and pushed"（`ops/eval/local/archive_loop.sh:17-18`），原始資料會只留在本機——上一輪就這樣整批遺失（`ops/eval/evidence_20260926_local/RUNLOG.md:129-135`）。真的推不上去時，至少定期把 `raw/` 複製到另一顆磁碟／另一台機器，並寫進 RUNLOG。
- 預期：**217 passed**（這台機器 18.4 秒，Python 3.11.15、node v22）。沒有 node 時 `test_zero_budget.py` 有 3 條會 skip（`tests/test_zero_budget.py:89,338,462`）。
  ⚠ 機器很忙時（旁邊在跑 6 個題目容器）`tests/test_eval_orproxy.py::test_local_mode_routes_to_the_named_machine_without_a_key` 3 次裡失敗過 1 次，單獨重跑 6／6 通過（本機測試伺服器的時序，原因沒查）；失敗就單獨重跑那一條。
  `pyproject.toml:105` 已經有 `addopts = "-q"`，不要再加 `-q`（會連總結行都藏起來）。
- 全套 `tests/` 有既存的失敗（約 10 條憑證／展件相關，和零設定無關，`ops/eval/evidence_20260926_local/RUNLOG.md:45-46`）；判準是「失敗集合＝基準」，這一輪沒有重跑全套。
- 分析腳本會 import `vacant_network`（`ops/eval/local/analyze_local.py:28`、`ops/eval/local/s36nc_analyze.py:24-30`）⇒ 一律用 `<REPO>/.venv/bin/python`，並設 `PYTHONDONTWRITEBYTECODE=1`（repo 裡的重播腳本也這樣用，`ops/eval/evidence_20260926_local/v35_given_inline/replay_r530_zero.py:5`）。

---

## 3. 環境需求

| 項目 | 需求 | 這次用的〔環境〕 |
|---|---|---|
| OS | Linux x86_64（只在這上面跑過；macOS／ARM 沒測） | 雲端容器 x86_64，4 CPU、15 GB RAM |
| Docker | 引擎＋`docker compose` v2（Harbor 每題用 compose 建映像、開容器）；預設 `docker0` 橋接，容器從 `172.17.0.1` 連得到主機（`ops/eval/local/run_local.sh:15`） | Docker 29.3.1；`dockerd` 手動啟動、`--data-root` 放在暫存大磁碟；compose 版本沒記錄 |
| uv | 跑 Harbor（`uv run --no-dev harbor …`）與建 wheel | 0.8.17 |
| Python | repo 的 `.venv` ≥ 3.11（`pyproject.toml:9`）；Harbor 自己 ≥ 3.12（uv 會自己抓） | 3.11.15；Harbor venv 是 CPython 3.13 |
| node | 主機上**只有**單元測試的 3 條與模擬使用者要；容器裡的 node 由 Harbor 用 nvm 裝 | v22 |
| 磁碟 | 每個並行位置留 ≥ 0.7 GB（容器可寫層 0.45–0.6 GB，`ops/eval/evidence_20260926_local/RUNLOG.md:161-163`）＋基底與釘死映像＋每題映像（會累積，見第 10 節）＋代理的 `io.jsonl`（新帳本約按「125 KB × 預期通數」估） | 8 並行時掉到 2.5 GB 以下，清掉暫存才回到 5.2 GB（`ops/eval/evidence_20260926_local/RUNLOG.md:161-163`）；〔環境〕帳本目錄是幾批共用的：`io.jsonl` 每通平均 S36-nocap（12k token 提示）72.7 KB、u274（hard 題）約 130 KB |
| 磁碟（docker） | 容器可寫層與每題映像在 docker 的 data-root（`docker info -f '{{.DockerRootDir}}'`），不一定和 `<JOBS>` 同一顆磁碟 | data-root 在暫存大磁碟 |
| 每題資源 | `cpus = 1`、`memory = "4G"`、`storage = "8G"`、agent 時限 1800 秒、驗證 600 秒（每個 `<釘死目錄>/dabstep-N/task.toml:13-23`） | 4 CPU／15 GB 跑過 8 並行 |
| 網路（容器） | 兩組：GitHub／raw.githubusercontent.com（nvm）、nodejs.org、registry.npmjs.org（pi 與它的相依，沒釘版本）；C 組另外要 Ubuntu apt（`pipx`）與 PyPI（`cryptography`、`mcp`、`jsonschema`，沒釘版本）（`ops/eval/harbor_vacant.py:69-78`） | 直連（經過沙箱的 TLS 攔截代理） |
| 網路（主機） | ghcr.io（基底映像）、huggingface.co（資料）、github.com（repo、Harbor、harbor-datasets）、PyPI、uv 的 Python 下載 | 同上 |
| CA bundle | 烤進映像**只有**在 TLS 被攔截的網路才需要（`ops/eval/evidence_20260925/gate1/GATE1.md:87-94`）；但 `run_local.sh` 每一跑都 bind mount `/root/.ccr/ca-bundle.crt`，那個檔一定要存在（第 7 節開頭） | `/root/.ccr/ca-bundle.crt`〔環境〕 |
| 時區 | 驅動用 `TZ=UTC` 跑（`run_pairs.py` 的時間上限換算不處理夏令時間，`ops/eval/local/run_pairs.py:125`） | UTC |

---

## 4. 建 v3.6.1 wheel（可重現）

PyPI 上的 `vacant-network` 最新是 0.7.0（沒有零設定，`CHANGELOG.md:253-256`）⇒ **不要照 README 從 PyPI 裝**；wheel 要自己從 `c27641c6` 建。repo 裡沒有 `.whl`。

```bash
cd <REPO>
W=<WORK>/wheel_v361; mkdir -p "$W"                               # <WORK> 是 repo 外的絕對路徑
export SOURCE_DATE_EPOCH=$(git log -1 --format=%ct c27641c6)      # = 1790490188
git archive c27641c6 | tar -x -C "$W" --one-top-level=src         # 整棵樹約 1.2 GB
echo 'setuptools==84.0.0' > "$W/bc.txt"
(cd "$W/src" && uv build --wheel -b ../bc.txt -o ..)
WHEEL=$W/vacant_network-0.8.0-py3-none-any.whl                   # 之後的 <WHEEL> 就是這個絕對路徑
sha256sum "$WHEEL"
# 預期：4ec156d6648d214baa9bc5be4093f8b8731112f16a6ee61b6118d70b41def0b4
```

- u274 的 wheel 是**不帶**建置限制、直接 `uv build --wheel` 建的（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:38`），當時 setuptools 剛好解析成 84.0.0；
  `pyproject.toml:76` 的 `setuptools>=77` 是浮動的，`-b`（`--build-constraints`）把它釘住，寫這份時在這台機器（uv 0.8.17）重建得到**同一個** sha256（`ops/eval/local/launch_u274.sh:9`）。
- 驗完 sha256（或下面的 114 檔比對）之後 `rm -rf "$W/src"`：上一輪 u274 開跑時磁碟就是靠刪這個樹救回來的（`ops/eval/evidence_20260926_local/RUNLOG.md:161-163`）。
- **版本字串沒有用**：每一版零設定都是 `0.8.0`（`vacant_network/__init__.py:47`）。
- **雜湊對不上時不要硬過**：改做檔案層級的比對，114 個檔、0 個不同才算同一個產品（上一輪 v3.4 就是這樣處理，`ops/eval/evidence_20260926_local/RUNLOG.md:140-141`），
  然後把**新的** sha256 寫進你的預註冊與啟動檔，記成偏差：

```bash
python3 - "$WHEEL" <<'EOF'        # 在 <REPO> 裡跑（用到 git）
import subprocess, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = [n for n in z.namelist() if n.startswith("vacant_network/")]
git = subprocess.run(["git", "ls-tree", "-r", "--name-only", "c27641c6", "vacant_network"],
                     capture_output=True, text=True, check=True).stdout.split()
bad = [n for n in names if z.read(n) != subprocess.run(["git", "show", f"c27641c6:{n}"], capture_output=True, check=True).stdout]
print("wheel", len(names), "git", len(git), "mismatch", len(bad), "missing", sorted(set(git) - set(names)))
EOF
# 預期：wheel 114 git 114 mismatch 0 missing []
```

- 快速確認是 v3.6 以後：裝進一個暫時的 venv 後 `vacant install --help` 要列出 `--budget-reminder`（`vacant_network/adapters/cli.py:284`）。

---

## 5. 評測框架

### 5.1 Harbor（釘死的 commit）

```bash
git clone https://github.com/laude-institute/harbor <HARBOR_DIR>
git -C <HARBOR_DIR> checkout 6cb9ff3167596c456e0b24622d473b59fc9ab6c7
(cd <HARBOR_DIR> && uv run --no-dev harbor --help)          # 第一次會建 Harbor 自己的 venv
```

- 釘這個 commit 是**承重的**：`ops/eval/harbor_vacant.py:26` import Harbor 的私有名字 `_REMOTE_PI_CONFIG_DIR`（＝`/tmp/harbor-pi-agent`，`<HARBOR_DIR>/src/harbor/agents/installed/pi.py:47`）；
  換 commit 可能 import 失敗，或 pi 的隔離設定目錄搬家、C 組裝錯地方。
- Harbor 不在 repo 裡；一律從 `<HARBOR_DIR>` 裡面、帶 `PYTHONPATH=<REPO>/ops/eval` 跑，`harbor_vacant:PiWithVacant` 才找得到（`ops/eval/local/run_local.sh:23-24`）。這些都已經寫在 `run_local.sh` 裡。

### 5.2 pi 0.87.1 與兩組的差別

- `--ak version=0.87.1`（不給就裝 `@latest`）、`--ak model_api=openai-completions`（自訂端點必須有），兩組都一樣（`ops/eval/local/run_local.sh:36`）。
  Vacant 的 pi 擴充是照 pi 0.87.1 的事件 API 寫的（`vacant_network/adapters/agents.py:179-184`）。
- A 組＝`--agent pi`；**組名不是 `A` 的一律**是 `harbor_vacant:PiWithVacant`（`ops/eval/local/run_local.sh:13`）。
- C 組多做的只有 `install()`：沒有 pipx 就 `apt-get install pipx`；上傳 wheel；`pipx install <wheel> && PI_CODING_AGENT_DIR=/tmp/harbor-pi-agent vacant install`（`ops/eval/harbor_vacant.py:66-78`）。
  `run()` 結束後把 `~/.vacant` 複製到 `<trial>/agent/vacant_home/`，寫 `<trial>/agent/vacant_check.json`（`ops/eval/harbor_vacant.py:30-60,80-88`）。
- 為什麼是 `/tmp/harbor-pi-agent`：Harbor 有自訂 base URL 時讓 pi 用隔離設定目錄，`~/.pi/agent` 的擴充不會被載入（`CLAUDE.md:199`；`<HARBOR_DIR>/src/harbor/agents/installed/pi.py:397-411`）。
  ⇒ **一定要**帶 `--ae OPENROUTER_BASE_URL=…` 與 `--ak model_api=…`，否則 C 組會安靜地變成 A 組。
- `MAX_TURNS=none` ⇒ `run_local.sh` 不帶 `--ak max_turns`（`ops/eval/local/run_local.sh:19-20`），系統提示裡就沒有 Harbor 的「You have a hard budget of N model turns」那一行（`<HARBOR_DIR>/src/harbor/agents/installed/pi.py:316`）。

### 5.3 DABstep 題目：下載、映像、釘死、驗證

來源：Harbor 的 registry 裡 `dabstep@1.0`＝450 題，每題指到 `laude-institute/harbor-datasets` 的 commit `e25eec6e8c2d614d36578ea43f58e5aa5b90859f`（`<HARBOR_DIR>/registry.json` 的 dabstep 條目；`ops/eval/evidence_20260925/gate2/A/result.json:7-8`）。
⚠ **不要**用 Harbor 的 `run_adapter.py` 重新產生 450 題：它抓答案的 `task_scores` 端點 2026-09-25 就回 404 了（`ops/eval/evidence_20260925/study_result.json:799-801`），而且答案是「排行榜上最短的被接受字串」、不是官方標準答案（`ops/eval/evidence_20260925/notes/deep-DABstep.md:125-132`）。

```bash
# (1) 匯出 450 題（推論出來的指令：repo 沒記錄當初用的那一行；下面第 (5) 步的雜湊比對才是驗收）
cd <HARBOR_DIR> && uv run --no-dev harbor datasets download dabstep@1.0 --registry-path registry.json --export -o <WORK>/dabstep_export
ls <WORK>/dabstep_export/dabstep | grep -c '^dabstep-'                                 # 預期 450
sha256sum <WORK>/dabstep_export/dabstep/*/environment/Dockerfile | cut -d' ' -f1 | sort -u
# 預期只有一個：c20a321f2d96924cb750829f2a9d08a317b0365ac914017bdff0350d6f44d14e（ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json:4）

# (2) 釘死的 7 個資料檔（HF adyen/DABstep revision 51884d33…，cc-by-4.0；ops/eval/evidence_20260925/notes/deep-DABstep.md:13,137）
mkdir -p <WORK>/pin && cd <WORK>/pin
for f in acquirer_countries.csv fees.json manual.md merchant_category_codes.csv merchant_data.json payments-readme.md payments.csv; do
  curl -sSfL "https://huggingface.co/datasets/adyen/DABstep/resolve/51884d3339cbc1f05d0e2e02bac7995ea605d69a/data/context/$f" -o "$f"; done
sha256sum *        # 逐一對 ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json:6-12

# (3) 建映像：官方 Dockerfile 原封不動，tag 一定要是 vacant-eval/dabstep-env:1（題目目錄的雜湊包含這個字串）
mkdir -p <WORK>/img && cp <WORK>/dabstep_export/dabstep/dabstep-1/environment/Dockerfile <WORK>/img/
docker build -t vacant-eval/dabstep-env:1 <WORK>/img

# (4) 釘死：驗 Dockerfile 全部相同、映像裡 /app/data 的 7 個檔＝--pin 的檔，然後把每題 Dockerfile 改成 FROM 這個映像
cd <REPO> && python3 ops/eval/dabstep_pin.py --export <WORK>/dabstep_export/dabstep --out <PINNED_450> \
  --image vacant-eval/dabstep-env:1 --pin <WORK>/pin

# (5) 驗收：重算 274 題清單，和 repo 裡凍結的逐位元組相同（順便驗了留出清單的 100 題）
mkdir -p <WORK>/check && python3 ops/eval/local/make_unseen.py --dataset <PINNED_450> --out <WORK>/check/UNSEEN_regen.json
cmp <WORK>/check/UNSEEN_regen.json ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json && echo IDENTICAL
```

- 官方 Dockerfile 從 HF 的 `resolve/main`（浮動分支）抓資料（`<WORK>/dabstep_export/dabstep/dabstep-1/environment/Dockerfile:11-18`）。資料若已經變了，第 (4) 步會拒絕（`ops/eval/dabstep_pin.py:46-54`）。
  那時只把 7 個網址的 `main` 改成 `51884d3339cbc1f05d0e2e02bac7995ea605d69a` 再建，記成偏差。
- 新映像的 image ID **一定**和這次的 `sha256:0e2cbfab…` 不同（`ops/eval/evidence_20260925/pilot/PIN_MANIFEST.json:3`）；可比的是資料 sha256＋題目目錄雜湊。把你的 `PIN_MANIFEST.json` 放進證據目錄。
- 官方 Dockerfile 的基底是 tag（`ubuntu-24-04:20250624`）、`pip3 install pandas` 沒釘版本（`<WORK>/dabstep_export/dabstep/dabstep-1/environment/Dockerfile:1,6-8`）⇒ 新映像的 pandas 可能和這次不同；記進 `env/`（第 12 節）。
- **只有 TLS 被攔截的網路**才需要把 CA 烤進映像。這次的映像〔環境〕是從映像歷史反推的（repo 裡沒有那份 Dockerfile）：先 `cp <你的 CA 檔> <WORK>/img/ca-bundle.crt`（放進 build context），再在官方兩個 `RUN` 之前插入下面四行，和 repo 裡程式題組的做法相同（`ops/eval/evidence_20260926_local/codesuite/base_v2.Dockerfile:6-9`）：
  ```dockerfile
  COPY ca-bundle.crt /usr/local/share/ca-certificates/sandbox-proxy.crt
  RUN update-ca-certificates
  ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
      CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
  ```
  （`ops/eval/evidence_20260926_local/RUNLOG.md:113` 說「`dabstep_pin.py` 把憑證放進信任清單」是錯的：`dabstep_pin.py` 只驗資料、改 Dockerfile，`ops/eval/dabstep_pin.py:42-67`。）
- 若人類能從這個容器把 `<SCRATCH>/dabstep_pinned/dabstep`（18 MB）〔環境〕搬給你，也可以直接用；**一樣要做第 (5) 步**。

### 5.4 題目清單

| 清單 | 內容 | 出處 |
|---|---|---|
| `ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json`（sha256 `43a8f4ee…8ef0`） | 450 − 正式 79 裡在 450 之中的 75 題（另 4 題 1273／1464／1871／2697 只在 dev）− 1716 ＝ 池 374；374 − 留出 100 ＝ **274 題，全部 hard**，每題釘題目目錄雜湊（清單的 `pool_size` 374、`count` 274） | `ops/eval/local/make_unseen.py:1-7,49-55`；`ops/eval/evidence_20260925/pilot/FORMAL_MANIFEST.json`（69 題 `harbor-450`＋10 題 `dev`）；`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:36` |
| `ops/eval/evidence_20260926_local/heldout/HELDOUT_MANIFEST.json` | 留出 100 題（跑過、資料遺失，算用過） | `ops/eval/local/make_unseen.py:3-5` |
| `ops/eval/pilot/tasks.json` 的 `formal_79` | 正式批次 72 easy＋7 hard dev（要另外產生 dev 題；這一輪用不到） | `ops/eval/pilot/tasks.json:6`；`ops/eval/dabstep_formal.py:1-9` |

- 450 題裡**已經沒有別的沒用過的 hard 題**：u274 用掉了剩下的全部。建議你的批次也用這 274 題，但**它們不再是「沒用過的」**：預註冊與結論的標題、說法都**不准**用「沒用過」「unseen」「留出」，
  要寫成「沒有用於設計 v3.6.1、但 u274 已在另一個算力上跑過的 274 題」；模型也是 `gemma-4-12b-it-qat` 時，這一批＝**同一批題在另一個算力上的複製**。
  在預註冊的偏差欄寫明，並**在讀到任何 u274 結果之前凍結**你的預註冊；已經讀過就照實寫。
- 評分：agent 要把答案寫進 `/app/answer.txt`；Harbor 在容器裡跑 `tests/test.sh`：沒有檔＝0 分；有檔就 `head -1 | xargs` 後交給 `tests/scorer.py` 比（`<PINNED_450>/dabstep-1/tests/test.sh:8-41`）。
  **主要檢定的對錯取自每一跑的 `verifier/reward.txt`**（`ops/eval/local/s36nc_analyze.py:42-45,95-96` 經 `ops/eval/local/unseen_analyze.py:44,50-52`）；`result.json` 的 `verifier_result.rewards.reward` 只用來判 infra_void（`ops/eval/local/analyze_local.py:49-51,67-68`）。
  兩者不一致的跑（例如 `reward.txt` 沒寫出來卻不是 infra_void，會被記成 wrong／no_file）要在預註冊寫一條一致性檢查、列出來。

---

## 6. 模型端點：記帳代理 `ops/eval/orproxy.py`

純標準庫（`ops/eval/orproxy.py:51-62`）。網址格式 `/t/<tag>/up/<上游名>/think/<on|off>/api/v1/chat/completions`（`ops/eval/orproxy.py:39-43`）；
`run_local.sh` 送給 pi 的 base URL 是 `http://172.17.0.1:18900/t/$TAG/up/$UP/think/off/api/v1`（`ops/eval/local/run_local.sh:15`）。輸出：`io.jsonl`（全文）、`ledger.jsonl`（逐通帳）、`summary.json`（按標籤加總，分析要讀）、`refusals.jsonl`。

### 6.1 本機／自架 OpenAI 相容端點（不帶金鑰）

`<WORK>/local/proxy.json`（`<MODEL>` 見 6.3；上游名字與 `host_id` 用代號，見 1.1）：

```json
{"models": {"<MODEL>": {}},
 "upstreams": {"<UP1>": "http://<主機1>:<埠>", "<UP2>": "http://<主機2>:<埠>"},
 "host_id": "<這台機器的代號>",
 "retry_waits": [5, 15, 30, 60],
 "budget_usd": 1000000}
```

```bash
cd <REPO> && nohup .venv/bin/python ops/eval/orproxy.py --config <WORK>/local/proxy.json --out <LEDGER> \
  --host 0.0.0.0 --port 18900 > <WORK>/local/proxy.log 2>&1 &
# 代理沒有驗證：只讓 docker 橋接與本機連進來（這一行沒在這裡測過；這次的容器沒有對外介面）
sudo iptables -I INPUT -p tcp --dport 18900 ! -i docker0 ! -i lo -j DROP
```

- 綁 `0.0.0.0`＋防火牆是唯一的建議做法：`monitor.sh` 與第 7 節的前測打 `127.0.0.1:18900`（`ops/eval/local/monitor.sh:14`），只綁 `172.17.0.1` 會讓它們失敗。
- **上游不能要金鑰**：本機模式代理不送 `Authorization`（`ops/eval/orproxy.py:252-253`），設定檔也沒有欄位可以給；要金鑰的端點每一通 401，而 401 不重試（`ops/eval/orproxy.py:66`）。
  上游要嘛不驗證（只聽內網、用防火牆保護），要嘛改 `orproxy.py`（從設定讀每台的金鑰**檔路徑**、加標頭）——那是偏差，先問人、寫進預註冊；**不要**把金鑰寫進 `proxy.json` 或網址（`proxy.json` 會進 `env/`）。
- **上游網址不帶 `/v1`**：代理自己接 `/v1/chat/completions`（`ops/eval/orproxy.py:250`；上一輪重建設定時也是這樣，`ops/eval/evidence_20260926_local/RUNLOG.md:138-139`），網址帶 `/v1` 會變成 `/v1/v1`。
- `budget_usd` 必填；設 0 會讓每一通都 402（`ops/eval/orproxy.py:418`、`ops/eval/orproxy.py:293-295`）。本機沒有費用，設一個用不到的大數（`ops/eval/evidence_20260926_local/RUNLOG.md:138-139`）。
- 上游名字只能用 `[A-Za-z0-9_.-]`（`run_pairs.py` 用這個正則從 `config.json` 讀回機器，`ops/eval/local/run_pairs.py:55-65`），而且要和 `--upstreams` 的名字一致；不認得的名字每一通都 400（`ops/eval/orproxy.py:279-280`）。
- 容器從 `172.17.0.1` 連代理：只綁 `127.0.0.1` 的話容器連不到（同樣的效應在另一個只聽回環的代理上實測過，"Connection refused"，`ops/eval/evidence_20260925/notes/deep-DABstep.md:172-174`）。Docker Desktop／rootless／自訂橋接不是 `172.17.0.1`，要改 `run_local.sh:15`，記成偏差。
- 同一批一直用**同一個 `--out`**：重啟時從 `ledger.jsonl` 重建加總再接著寫（`ops/eval/orproxy.py:124-130`）；換目錄會把帳切成兩半、分析讀不到。
- 這次的部署〔環境〕：`--host 0.0.0.0 --port 18900`、上游是人類自己的兩台 LM Studio（名字 `w401`、`1003`）、`host_id` 是 `ccr-container-local`。

### 6.2 付費（OpenRouter）——只在人類授權後

設定檔**沒有** `upstreams` ＝付費模式：轉到 `https://openrouter.ai`，加 `provider`、`usage.include`、`reasoning`（`ops/eval/orproxy.py:64,92-110`）。

```json
{"budget_usd": <人類授權的額度>,
 "tag_cap_usd": 0.30,
 "models": {"<openrouter 模型 id>": {"provider": {"order": ["<供應商/量化>"], "allow_fallbacks": false, "require_parameters": true}}}}
```

```bash
.venv/bin/python ops/eval/orproxy.py --config <PAID_CFG> --out <PAID_LEDGER> --key-file <金鑰檔路徑，你不打開它> \
  --host 0.0.0.0 --port 18900          # 一樣要 6.1 的防火牆：沒有驗證的付費代理＝別人可以花你的錢
```

- 金鑰只由代理行程讀一次（`ops/eval/orproxy.py:417`）；**你只傳路徑，不 cat、不印**。`tag_cap_usd` 0.30 是上一輪的每跑上限（`ops/eval/pilot/run_one.sh:7`）。
- `run_local.sh` 寫死 18900 埠與 `MODEL`（`ops/eval/local/run_local.sh:12,15`）；付費模型 id（例如 `google/…`）要改 `MODEL`，記成偏差。付費模式會忽略 `/up/<名字>/` 的路由、只記在帳本（`ops/eval/orproxy.py:246-248`），`--upstreams` 隨便取個名字即可。
- OpenRouter 上的模型不是 LM Studio 的 `gemma-4-12b-it-qat` 那一份量化 ⇒ 和本機批次**不可比**。

### 6.3 換模型

模型 id（下文 `<MODEL>`；上一輪 `gemma-4-12b-it-qat`）必須處處一模一樣、代理不改名（`ops/eval/orproxy.py:290-292`）：`run_local.sh:12` 的 `MODEL`、`proxy.json` 的 `models` 鍵、伺服器實際提供的 id、第 7 節 (b) 前測的 curl 本文、你的預註冊。
不一樣 ⇒ 代理回 403 或伺服器報錯。`--model openrouter/$MODEL` 的 `openrouter/` 前綴只是 Harbor 選供應商用的，**保留**（`ops/eval/local/run_local.sh:26`）；
`g12-off` 這個字面值寫死在標籤、目錄和所有分析腳本裡（`ops/eval/local/run_local.sh:14,16`、`ops/eval/local/run_pairs.py:56,61`、`ops/eval/local/analyze_local.py:44,52`），**當成不透明的標籤、不要改**，真正的模型記在預註冊與帳本的 `model` 欄。
換模型＝新問題：u274 的預註冊不准外推到別的模型（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:74`）。

### 6.4 思考開關

`/think/off/` 在本機模式把 `reasoning_effort` 強制成 `"none"`（`ops/eval/orproxy.py:70,96-101`）。這只是請求欄位：人類的 1003 會照做、w401 本來就不思考（`ops/eval/evidence_20260926_local/RUNLOG.md:8-11`）；
**vLLM、llama.cpp、別版 LM Studio 沒測過**，可能忽略或回 400（400 不重試，`ops/eval/orproxy.py:66`）。前測時查帳本的 `usage.reasoning_tokens` 是 0 或 null、`io.jsonl` 的回應裡沒有推理文字。
**伺服器不接受 `reasoning_effort: "none"`**（第 7 節 (b) 回 400）而模型本來就不思考時：把 `run_local.sh:15` 的 `/think/off` 拿掉（代理就不碰那個欄位，`ops/eval/orproxy.py:100-101`），記成偏差寫進預註冊，並用冒煙的 `io.jsonl` 證明回應裡沒有推理內容。模型會思考又關不掉 ⇒ 停下來問人。

### 6.4a 伺服器檢查表（換伺服器／換模型時；寫進預註冊的釘住表）

- **上下文 ≥ 144384**：pi 0.87.1 對 Harbor 寫出的自訂模型預設 `contextWindow` 128000、`maxTokens` 16384〔環境：`@earendil-works/pi-coding-agent@0.87.1` 的 `dist/core/provider-composer.js:93-94`，不在 repo〕，
  每一通都帶 `max_completion_tokens: 16384`（S36-nocap 歸檔的請求，`ops/eval/evidence_20260927_nocap/s36nc/raw/chunk_001.tar.xz` 的 `proxy/io.jsonl`）；hard 題提示中位數 43.7k token（`ops/eval/evidence_20260926_local/RUNLOG.md:165`）；上一輪 262144（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:37`）。太小 ⇒ 長對話 400、不重試。pi 何時壓縮對話沒查證。
- **OpenAI 格式的原生 `tool_calls`**（串流）＋`stream_options.include_usage`＋接受 `max_completion_tokens`。vLLM 要自己開工具呼叫解析（`--enable-auto-tool-choice --tool-call-parser …`，這裡沒測過）；否則會像 `gemma-3-12b` 那樣 0 次真的工具呼叫（`ops/eval/evidence_20260925/gate1/GATE1.md:15-18,31`）。第 7 節 (b2) 前測。

### 6.5 並行

每台的位置數 ≤ 伺服器的同時預測數；上一輪兩台都是 Max Concurrent Predictions 4、上下文 262144、Unified KV Cache（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:37`）。
同時太多段對話會擠掉 LM Studio 的提示快取，吞吐不升（41.7k token 提示：冷 24 秒、有快取 2.4 秒，`ops/eval/evidence_20260926_local/RUNLOG.md:37-39`）；
hard 題在 4＋4 時延遲中位數 44–47 秒、p90 約 130 秒，1003 超過 5 分鐘沒回應（`ops/eval/evidence_20260926_local/RUNLOG.md:164-166`）。pi 的 HTTP 用戶端約 300 秒沒資料就切斷（`ops/eval/evidence_20260926_local/RUNLOG.md:22-27`）。**從 3 開始**，先看 10–15 分鐘。

### 6.6 吞吐與 1800 秒時限（**最重要的坑**；u274 在人類的機器上就卡在這裡）

- u274 的前 16 跑（有 `result.json` 的）**12 跑碰到 1800 秒的 agent 時限**（`AgentTimeoutError`）；降成 3＋3 之後開始、跑完的 6 跑裡 5 跑碰到（RUNLOG §17）。
  原因是 hard 題的對話很長：每一通的提示中位數 34k–44k token（S36-nocap 的題是 12k–16k），3＋3 時請求延遲中位數 w401 24 秒、1003 85 秒，p90 135／225 秒。
  碰到時限的跑兩組都多半沒交檔 ⇒ 缺檔退回輪不到、兩組差別被時限淹沒——**這個設計在這樣的算力上量不到東西**。
- 你的算力要做得到：**前綴快取**（vLLM 的 automatic prefix caching、SGLang 的 radix cache；LM Studio 在多段對話同時跑時快取會被擠掉，6.5）、夠快的 prefill（一跑常有 20–60 通、每通 30k–50k token 的提示）。
- **在預註冊裡寫一條「可行性規則」**（只看例外類型與時間，不看評分）：例如「前 20 跑（兩組合計）若 ≥ 30% 是 `AgentTimeoutError`，停下、不分析、換算力或改設計（另一份預註冊）」。
  讀例外類型只能兩組合計、只讀 `result.json` 的 `exception_info.exception_type`（不讀 `verifier_result`）；把你怎麼讀的寫進 RUNLOG。
- **不要**為了跑得完而偷偷拉長時限、改題目或設回合上限：那都是另一個設計，要另一份預註冊（時限在每題的 `task.toml`，第 3 節）。

---

## 7. 開跑前的小測試（必做）

```bash
export TZ=UTC
# (0) run_local.sh 每一跑都 bind mount /root/.ccr/ca-bundle.crt（ops/eval/local/run_local.sh:10,28,31-35）：沒有這個檔每一跑都失敗。
#     已經存在就不要覆蓋（在 Claude Code 雲端容器裡它是沙箱自己的 TLS 代理憑證）；不存在才放一份系統 CA：
[ -e /root/.ccr/ca-bundle.crt ] || { sudo mkdir -p /root/.ccr && sudo cp <系統 CA bundle> /root/.ccr/ca-bundle.crt; }
#     Debian／Ubuntu：/etc/ssl/certs/ca-certificates.crt；RHEL 系：/etc/pki/tls/certs/ca-bundle.crt。run_local.sh 保持逐位元組不變
# (a) 代理活著、模型 id 對（GET 原樣轉送、不記帳）
curl -sS http://127.0.0.1:18900/t/<P>preflight/up/<UP1>/api/v1/models
# (b) 每台一通真的請求（會記帳；上一輪用標籤 u274-preflight，RUNLOG.md:160；確切指令 repo 沒記，這是等效的）
curl -sS -H 'Content-Type: application/json' http://127.0.0.1:18900/t/<P>preflight/up/<UP1>/think/off/api/v1/chat/completions \
  -d '{"model":"<MODEL>","messages":[{"role":"user","content":"say ok"}],"max_completion_tokens":16}'
tail -1 <LEDGER>/ledger.jsonl        # status 200、upstream 對、usage.reasoning_tokens 0 或 null；401＝上游要金鑰（6.1）、400＝可能是 reasoning_effort（6.4）
# (b2) 工具呼叫＋串流 usage（6.4a）：回應裡要看得到 tool_calls，帳本這一列的 usage.prompt_tokens 不是 null
curl -sS -N -H 'Content-Type: application/json' http://127.0.0.1:18900/t/<P>preflight/up/<UP1>/think/off/api/v1/chat/completions \
  -d '{"model":"<MODEL>","stream":true,"max_completion_tokens":256,"messages":[{"role":"user","content":"Use the bash tool to run: ls /app"}],
       "tools":[{"type":"function","function":{"name":"bash","description":"Run a shell command","parameters":{"type":"object","properties":{"command":{"type":"string"}},"required":["command"]}}}]}' | grep -c tool_calls
tail -1 <LEDGER>/ledger.jsonl
# (c) 容器連得到代理（官方映像有 curl；代理對 GET / 回 404＝活著）
docker run --rm vacant-eval/dabstep-env:1 curl -s -o /dev/null -w '%{http_code}\n' http://172.17.0.1:18900/
```

**冒煙：一題 A、一題 C361**。用第 9 題（easy、不在 274 題裡；上一輪也拿它冒煙，`ops/eval/evidence_20260926_local/RUNLOG.md:15-18`），jobs 目錄和正式批次**分開**：

```bash
cd <REPO>
# 全部參數用絕對路徑（run_local.sh 會先 cd 進 <HARBOR_DIR>）
DABSTEP_PINNED=<PINNED_450> TAG_PREFIX=<P>smoke MAX_TURNS=none bash ops/eval/local/run_local.sh <HARBOR_DIR> <WORK>/smoke -      9 A    <UP1> 1
DABSTEP_PINNED=<PINNED_450> TAG_PREFIX=<P>smoke MAX_TURNS=none bash ops/eval/local/run_local.sh <HARBOR_DIR> <WORK>/smoke <WHEEL> 9 C361 <UP1> 1
```

逐項確認（冒煙題可以看分數）：

1. 兩跑都有 `<WORK>/smoke/g12-off-<ARM>-s1/<P>smoke-g12-off-<ARM>-9-s1/dabstep-9__*/result.json`，`verifier_result.rewards.reward` 不是 null，`verifier/reward.txt` 存在（主要檢定讀的是它，5.4）。
2. **C 組真的裝上**：`…/g12-off-C361-s1/…/agent/vacant_check.json` 的 `c_arm_ok: true`、`pi_installed: true`、`install_json.mode: "evidence"`、`steps > 0`（`ops/eval/harbor_vacant.py:30-59`）；
   `trial.log` 裡有 pipx 安裝；`agent/vacant_home/adapters/install.json` 沒有 `budget_reminder: true`。`stop_reached` 是 false 不代表壞掉（被時限切斷的跑不會進 Stop，`ops/eval/harbor_vacant.py:16-18`）。
3. 兩個標籤在 `ledger.jsonl` 都有 status 200 的列；`refusals.jsonl` 沒有新列。
4. 沒有回合上限那一行：`grep -c 'hard budget of' <LEDGER>/io.jsonl` → `0`。
5. **不變式：同一題第一通請求兩組相同**（和 `ops/eval/local/analyze_local.py:88-116` 同一種算法）：

```bash
P=<P>smoke python3 - <LEDGER>/io.jsonl <<'EOF'
import hashlib, json, os, sys
first = {}
for ln in open(sys.argv[1]):
    d = json.loads(ln)
    if d.get("status") != 200 or not d["tag"].startswith(os.environ["P"] + "-"):
        continue
    h = hashlib.sha256(json.dumps(d["request_from_agent"], sort_keys=True).encode()).hexdigest()
    if d["tag"] not in first or d["ts"] < first[d["tag"]][0]:
        first[d["tag"]] = (d["ts"], h)
for t, (_, h) in sorted(first.items()):
    print(t, h[:16])          # A 與 C361 的雜湊要一樣
EOF
```

上一輪這個不變式是 237／237（`decisions/conclusions/CONCLUSION_20260926_ZERO_CONFIG_V3_LOCAL.md:60-61`）。新模型時也要確認 pi 真的有工具呼叫（`gemma-3-12b` 曾經把工具呼叫寫成純文字、0 次真的呼叫，`ops/eval/evidence_20260925/gate1/GATE1.md:15-18,31`）：看 `agent/pi.txt` 裡有 `tool_execution_start`。

可選的產品等級閘門（產品原則 4，`CLAUDE.md:27`）：模擬使用者 `ops/eval/simuser/run_simuser.py`（假模型、A/C、`correct` 情境 C 必須和 A 逐位元組相同，`ops/eval/simuser/run_simuser.py:1-15`）。
它要一個已經有 pipx 的題目映像、一個含所有相依 wheel 的目錄（容器不連網，`ops/eval/simuser/inside.sh:13-14`）、node 22 目錄與 pi 的 `node_modules`——**這些的準備步驟 repo 裡沒有**。
`ops/eval/gate3/run_gate3.sh` 寫死 `--ak max_turns`（`ops/eval/gate3/run_gate3.sh:37`），不適用於不設上限的條件。

---

## 8. 正式跑

### 8.1 先寫一份新的預註冊（不要改凍結的那份）

`decisions/prereg/PREREG_<YYYYMMDD>_<名字>.md`（新紀錄一律放 `decisions/`，`CLAUDE.md` 的 decisions 條目；push 前跑 `python3 ops/check_repo_links.py`）。照 `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md` 的一到八節寫，至少要有：

1. 第一行狀態註解（凍結後不准改）。
2. 為什麼：同一個問題換一個算力／模型；引用 u274 預註冊（凍結 commit `6ab08c91`）與本文件。
3. 兩組：A 與 C361（同一個 wheel sha256；不設 Vacant 環境變數、不寫契約、提醒關）。
4. 釘住的東西表：Harbor commit、pi 0.87.1＋兩個 `--ak`、`MAX_TURNS=none`、1800 秒；映像 tag＋**你的** image ID＋資料 7 個 sha256；題目清單 sha256＋`cmp` 的結果；
   模型（確切 id、伺服器軟體與版本、量化、每台同時預測數、上下文、思考怎麼關、怎麼驗證關了）；wheel sha256（或新雜湊＋114 檔相同的證據）；驅動與分析腳本＝`6ab08c91` 的版本（第 2 節 `tooling == u274` 的結果）；**你改過的每一行**（例如 `run_local.sh` 的 CA／橋接位址／`MODEL`／`/think/off`）；伺服器檢查表（6.4a）。
5. 跑法：`run_pairs.py` 的完整指令（新前綴、新種子、未來的時間上限、你的上游名字與位置數）；停止規則（只看時間）；並行的基礎設施規則（只看代理與機器）；**可行性規則（6.6：兩組合計碰到時限的比例）**；infra_void 補跑一次；意向治療；**有 `result.json` 卻沒有 `agent/pi.txt` 的跑怎麼處理**（例：當成 infra_void 拿掉並列出，第 9 節）；`reward.txt` 與 `result.json` 不一致的跑列出（5.4）。
6. 分析：同一個主要檢定（McNemar 精確雙尾 α＝0.05、完整配對）、同一批描述量（見第 9 節）。
7. 事先寫死的說法：照 `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:69-74`，把模型／算力換成你的，並把「沒用過的」換成 5.4 的說法（這 274 題 u274 跑過）。
8. 已知偏差：照 `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:78-82`，另加「不同算力」「同一批 274 題 u274 在別的算力上跑過」「寫這份時有沒有看過 u274 結果」；記下你 clone／開分支的 commit、那時 `u274/raw/` 有幾個 chunk，並寫明一個都沒打開。
9. 授權：人類的原話（網址、主機名、金鑰、帳號換成代號，1.1）；沒有逐條簽字就寫明「只能說預註冊的批次量到／沒量到」。

凍結：`git add` 預註冊＋你的啟動檔＋你改過的腳本 → commit → push → `mkdir -p <JOBS> && echo "frozen at $(git rev-parse HEAD)" > <JOBS>/FROZEN_COMMIT`。**凍結之前不看任何評分**。

### 8.2 啟動檔：從 `launch_u274.sh` 複製成 `ops/eval/local/launch_<P>.sh`

`launch_u274.sh` 的時間上限 `2026-09-28T00:00:00Z` 寫死（`ops/eval/local/launch_u274.sh:16`）：過了之後用新的 jobs 目錄叫它，`run_pairs.py` 會一跑都不開、然後照樣寫 `DONE`，看起來像跑完了（`ops/eval/local/run_pairs.py:85-89,128-135`）。所以一定要自己的啟動檔：

```bash
#!/bin/bash
# 預註冊 decisions/prereg/PREREG_<YYYYMMDD>_<名字>.md 的啟動檔（照 launch_u274.sh；改了前綴、種子、時間上限、上游，加了 realpath 與 TZ）
# 用法：launch_<P>.sh <harbor 目錄> <jobs 目錄> <釘死的 450 題目錄> <C361 wheel> <代理 ledger 目錄>
set -uo pipefail
HARBOR=$(realpath "$1"); JOBS=$(realpath -m "$2"); DATA=$(realpath "$3"); WHEEL=$(realpath "$4"); LEDGER=$(realpath "$5")
REPO=$(cd "$(dirname "$0")/../../.." && pwd)
MAN=$REPO/ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json
[ "$(sha256sum < "$WHEEL" | cut -d' ' -f1)" = <WHEEL_SHA256> ] || { echo "wheel sha256 mismatch"; exit 1; }
[ "$(sha256sum < "$MAN" | cut -d' ' -f1)" = 43a8f4eebd94da98ccdb31822115e5ec64f36c789d7f6807f01094f5baf28ef0 ] || { echo "manifest sha256 mismatch"; exit 1; }
mkdir -p "$JOBS"
export MAX_TURNS=none TZ=UTC            # TZ：run_pairs.py 的時間上限換算要它（ops/eval/local/run_pairs.py:125）
drive() {
  python3 "$REPO/ops/eval/local/run_pairs.py" --harbor "$HARBOR" --jobs "$JOBS" --dataset "$DATA" --manifest "$MAN" \
    --arms A=- "C361=$WHEEL" --samples 1 --upstreams ${UPSTREAMS:-<UP1>:3 <UP2>:3} --seed <SEED> --prefix <P> \
    --deadline <YYYY-MM-DDTHH:MM:SSZ>
}
echo "[$(date -u +%FT%TZ)] start (${UPSTREAMS:-<UP1>:3 <UP2>:3})"
drive >> "$JOBS/driver.log" 2>&1
echo "[$(date -u +%FT%TZ)] driver finished; infra_void rerun"
"$REPO/.venv/bin/python" "$REPO/ops/eval/local/rerun_void.py" --jobs "$JOBS" --ledger "$LEDGER" --dataset "$DATA" --prefix <P> >> "$JOBS/rerun_void.log" 2>&1
drive >> "$JOBS/driver_rerun.log" 2>&1
echo "[$(date -u +%FT%TZ)] all runs finished"
touch "$JOBS/DONE"
```

- `<P>` 見檔頭；組名保持 `A` 與 `C361`（純字母數字，`ops/eval/local/s36nc_analyze.py:111`、`ops/eval/local/analyze_local.py:47`）。
- 時間上限：吞吐參考——S36-nocap 144 跑 06:11→10:37（`w401:3 1003:1`、12k token 提示，`ops/eval/evidence_20260926_local/RUNLOG.md:145-152`）；〔環境，repo 沒有〕u274 hard 題頭兩跑 275／402 秒（8 並行）。S36-nocap 那段不是純 `w401:3 1003:1`：08:45–09:45 1003 多了探針負載、10:05 起最後 12 格改用 `1003:4`（`ops/eval/evidence_20260926_local/RUNLOG.md:147-149`）。548 跑在 6 個位置上大約要以「半天到一天」計；
  題目順序是隨機的，停下時跑完的是隨機子集（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:51`）。上限寫進預註冊，**開跑後不改**。
- `run_pairs.py` 用系統 `python3`（只用標準庫）；`rerun_void.py` 用 `<REPO>/.venv/bin/python`（會 import `vacant_network`）。
- 一個機器也可以：`--upstreams <UP1>:3`。兩台時同一題兩組一定在同一台、幾乎同時開始（`ops/eval/local/run_pairs.py:1-8`）。

### 8.3 歸檔迴圈：換掉寫死的署名

`ops/eval/local/archive_loop.sh:15-16` 寫死了**這個工作階段**的 `Co-Authored-By`／`Claude-Session` 兩行。複製成 `ops/eval/local/archive_loop_<P>.sh`，換成**你自己的**署名（照你的系統指示），一起凍結；
它每一輪 push 到**目前的分支**、從不 pull（`ops/eval/local/archive_loop.sh:17`），而且不管 push 成不成功都印 "archived and pushed"（`ops/eval/local/archive_loop.sh:18`）⇒ 用 `git log origin/<你的分支> -1` 確認。

### 8.4 開跑、歸檔、監測

```bash
cd <REPO>; export TZ=UTC
mkdir -p <JOBS>
nohup bash ops/eval/local/launch_<P>.sh <HARBOR_DIR> <JOBS> <PINNED_450> <WHEEL> <LEDGER> > <JOBS>/chain.log 2>&1 &
echo $! > <JOBS>/launch.pid
nohup bash ops/eval/local/archive_loop_<P>.sh <JOBS> <LEDGER> <P> ops/eval/evidence_<YYYYMMDD>_<算力名>/<P> 7200 <JOBS>/DONE \
  > <JOBS>/archive_loop.log 2>&1 &
nohup bash ops/eval/local/monitor.sh <JOBS> '[l]aunch_<P>.sh' <JOBS>/DONE > <JOBS>/monitor.out 2>&1 &
echo $! > <JOBS>/monitor.pid       # 背景跑、輪詢 monitor.out；它印一行就結束：處理完再重開
head -1 <JOBS>/driver.log        # {"units": 274, "runs_to_go": 548, …}；runs_to_go 必須 > 0
```

- `monitor.sh` 每 60 秒看：沒有結果的跑變多、磁碟 < 2.5 GB、`127.0.0.1:18900` 沒回應、`dockerd` 不見、驅動死了卻沒 `DONE`（`ops/eval/local/monitor.sh:7-16`）。**第一個問題就結束**，基準在它啟動時取。前景跑會卡住你的工具呼叫到出問題為止 ⇒ 一定背景跑。
  它只看 `<JOBS>` 那顆磁碟（`ops/eval/local/monitor.sh:11`）；吃磁碟的是 docker data-root 裡的容器可寫層（`ops/eval/evidence_20260926_local/RUNLOG.md:161-163`）——`docker info -f '{{.DockerRootDir}}'` 在另一顆磁碟時要另外監測那一顆。
  ⚠ 它的「驅動死了」用 `pgrep -f "$PAT"`（`ops/eval/local/monitor.sh:16`）：樣式會比對到 monitor.sh 自己的命令列，永遠找得到自己——上面用 `[l]aunch_<P>.sh`（啟動檔從開跑活到寫 `DONE`，涵蓋補跑那一段）的寫法避開自己；別的樣式要自己確認。
- 不看評分的進度與代理狀態（只讀 `progress.jsonl` 與帳本；這一段在這台機器上試跑過）：

```bash
J=<JOBS> L=<LEDGER> P=<P> python3 - <<'EOF'
import collections, json, os, time
J, L, P = os.environ["J"], os.environ["L"], os.environ["P"]
try: prog = [json.loads(x) for x in open(f"{J}/progress.jsonl")]
except FileNotFoundError: prog = []
print("progress", len(prog), dict(collections.Counter((r["arm"], r["upstream"], r["has_result"]) for r in prog)))
now = time.time(); by = collections.defaultdict(list)
for x in open(f"{L}/ledger.jsonl"):
    r = json.loads(x)
    if r["tag"].startswith(P + "-") and now - r["ts"] < 3600: by[r["upstream"]].append(r)
for up, rs in sorted(by.items()):
    lat = sorted(r["latency_s"] for r in rs); err = sum(1 for r in rs if r["status"] != 200 or r.get("stream_error"))
    print(up, "calls", len(rs), "errors", err, "p50", lat[len(lat)//2], "p90", lat[int(len(lat)*0.9)],
          "last_call_age_s", round(now - max(r["ts"] for r in rs)))
EOF
```

- `progress.jsonl` 一跑結束才寫一行；停驅動時在跑的那幾跑不會有行（`ops/eval/evidence_20260926_local/RUNLOG.md:149-151`）。完成數以 `result.json` 為準：`ls -d <JOBS>/g12-off-*-s1/*/dabstep-*__*/result.json | wc -l`。

### 8.5 並行規則觸發時（只看代理與機器）

開跑 20 分鐘內代理錯誤 > 10% 或任一台 5 分鐘沒回應 ⇒ 降位置（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:52-53`；你的預註冊寫你自己的數字）：
1. **用 PID、照這個順序**停（上一輪也是用 PID，`ops/eval/evidence_20260926_local/RUNLOG.md:166`；`pkill -f` 會比對到自己的殼層）：先 `kill $(cat <JOBS>/monitor.pid)`；再 `kill $(cat <JOBS>/launch.pid)`，確認它不在了；
   最後 `kill $(pgrep -f "[r]un_pairs.py .*--jobs <JOBS> ")`。**順序是承重的**：先殺 `run_pairs.py` 的話，啟動檔會照樣往下跑 `rerun_void`、用舊的 `UPSTREAMS` 再開驅動、然後寫 `DONE`（`ops/eval/local/launch_u274.sh:19-24`）——歸檔迴圈看到 `DONE` 做最後一次就結束（`ops/eval/local/archive_loop.sh:21`），還可能同一格跑兩次。
2. **等在跑的跑完**：`while pgrep -f '[r]un_local.sh .*<JOBS> ' >/dev/null; do sleep 30; done`。
3. 同一組參數、只改位置：`cd <REPO>; export TZ=UTC; UPSTREAMS='<UP1>:2 <UP2>:2' nohup bash ops/eval/local/launch_<P>.sh …（同上）> <JOBS>/chain.log 2>&1 & echo $! > <JOBS>/launch.pid`，再重開 monitor。已經有 `result.json` 的格子會跳過，接了一半的題排回原來那台（`ops/eval/local/run_pairs.py:90-97`）。寫進 RUNLOG。

### 8.6 infra_void、工作階段被砍、原始資料

- infra_void＝沒有評分，或那個標籤的每一通代理請求都失敗（`ops/eval/local/analyze_local.py:67-68`）。啟動檔結束時自動 `rerun_void.py` 移到 `<JOBS>/_void_first/`（不刪）再補跑一次；過了時間上限也只補開始過的單位（`ops/eval/local/run_pairs.py:9-11`）。補跑也壞 ⇒ 分析時拿掉並列出。
- `archive_raw.py` 不會收 `rerun_void.log` 與 `_void_first/moved.json`（`ops/eval/local/archive_raw.py:134-138`）⇒ `DONE` 之後手動複製進證據目錄。
- **開跑時就起保險絲** `nohup setsid bash ops/eval/local/guard.sh <JOBS> &`：dockerd 或代理連續兩次（10 秒）不在就依序停啟動檔與驅動。u274 在 18:18 UTC 的重啟裡，dockerd 與代理停了、驅動還活著，28 秒內把 27 題、54 格都秒敗（RUNLOG §17）。dockerd 與代理也用 `setsid` 起。
- 背景行程可能整批被砍（dockerd、代理、驅動、監測；上一輪兩次，`ops/eval/evidence_20260926_local/RUNLOG.md:83-92,117-126`）：重開 dockerd（同一個 data-root、清掉死容器）→ 代理（**同一個 `--out`**）→ 每台一通 `<P>restartprobe`（第 7 節 (b) 的 curl）→ 同一組參數重開啟動檔與 monitor（照 8.5 第 3 步：`TZ=UTC`、更新 `launch.pid`）。
- 容器可能回到**舊快照**，沒 push 的東西全丟（留出批次就這樣整批遺失，`ops/eval/evidence_20260926_local/RUNLOG.md:129-135`）⇒ 歸檔迴圈從第一分鐘就開；不要把原始資料只放在暫存區。

### 8.7 每 3 小時給人類的報告（繁體中文）

只報**進度與運作**，不報任何中途評分（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:57`）：已完成跑數／總數（每組、每台）、預估完成時間與時間上限、代理錯誤率與延遲 p50／p90、有沒有機器沉默、磁碟、infra_void 數、做過的處置（附 RUNLOG 節號）、最近一次歸檔的 commit（`git ls-remote origin <你的分支>`）。
infra_void 數只用不帶評分值的來源算：`progress.jsonl` 的 `has_result: false`，或 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ops/eval/local/rerun_void.py … --dry-run`（只印 `reward_missing` 等欄位、不移動，`ops/eval/local/rerun_void.py:33,40-42,54`）。
`DONE` 之前**不准**跑 `analyze_local.py`、`unseen_analyze.py`、`s36nc_analyze.py`，也不讀 `result.json` 的 `verifier_result`（它們都讀評分，`ops/eval/local/analyze_local.py:49-51,61-66`）。
上一輪用例行觸發排程（`ops/eval/evidence_20260926_local/RUNLOG.md:146`）；怎麼排的 repo 裡沒有。

---

## 9. 分析（`DONE` 之後跑一次）

先確認沒有「有 `result.json` 卻沒有 `agent/pi.txt`」的跑（`s36nc_analyze.one` 沒有 try，遇到會讓整個分析崩，`ops/eval/local/s36nc_analyze.py:50`）：

```bash
for d in <JOBS>/g12-off-*-s1/*/dabstep-*__*; do [ -f "$d/result.json" ] && [ ! -f "$d/agent/pi.txt" ] && echo "$d"; done
```

有的話照你的預註冊處理並寫明；**不要安靜地改凍結的腳本**。然後：

```bash
cd <REPO>
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ops/eval/local/unseen_analyze.py --jobs <JOBS> --ledger <LEDGER> --io <LEDGER>/io.jsonl \
  --dataset <PINNED_450> --prefix <P> --c-arm C361 --out ops/eval/evidence_<YYYYMMDD>_<算力名>/<P>/analysis
# 一致性檢查（退回：病歷 vs pi 事件流）
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python ops/eval/local/s36nc_analyze.py --jobs <JOBS> --dataset <PINNED_450> --c-arm C361 \
  --out ops/eval/evidence_<YYYYMMDD>_<算力名>/<P>/analysis/s36nc_view.json
```

運作紀錄（不含評分；人類 2026-09-27 要求「超時等最後一併記錄」）：
```bash
python3 ops/eval/local/ops_report.py --jobs <JOBS> --ledger <LEDGER> --prefix <P> \
  --manifest ops/eval/evidence_20260927_nocap/unseen/UNSEEN_MANIFEST.json \
  --period <並行時期名>=<開始時間 UTC> [--period …] --out ops/eval/evidence_<YYYYMMDD>_<算力名>/<P>/ops
```
每一跑的機器、並行時期、牆鐘、時限、請求數與串流錯誤、驅動有沒有記到；組別 × 時期 × 機器的時限次數；沒開始的題。和主要分析一起交。

`unseen_analyze.py` 的 `summary.json` 怎麼讀（`ops/eval/local/unseen_analyze.py:67-83`）：

| 欄位 | 意思 |
|---|---|
| `primary.pairs`、`primary.C361_only_right`、`primary.A_only_right`、`primary.p`、`primary.right` | **主要檢定**：完整配對數、C 單獨對、A 單獨對、McNemar 精確雙尾（`vacant_network/research.py:142`）、每組答對 |
| `tally`、`extra_wrong` | 每組 `right`／`wrong`（有檔、0 分）／`no_file`；C 比 A 多出來的錯 |
| `infra_void_tasks`、`half_pairs_not_analysed` | 拿掉的題、只有一組的題（都要列出） |
| `C_runs_with_a_sendback`、`C_missing_output_sendback_runs`、`sendback_kinds_runs`、`end_state_after_sendback_kind` | 退回幾跑、哪一類、之後的結果 |
| `harm` | **傷害**：第一次退回那一刻答案檔已經是評分器會收的值、最後卻錯（`ops/eval/local/unseen_analyze.py:57`） |
| `sendback_ended_wrong_value_before_unknown` | 退回時有檔但重建不出值、最後錯的（要列出） |
| `A_said_done_without_file`、`timeouts`、`by_machine` | A 說做完卻沒寫檔；每組 1800 秒時限次數；每台機器 |
| `invariants.first_request_differs` | **必須是空的**（第一通請求兩組相同）。`runs_over_15_requests` 是有上限那幾輪留下來的檢查，不設上限時不是違規（`ops/eval/local/analyze_local.py:88-116`） |

- `s36nc_view.json` 只看 `sendback_chain_vs_stream_mismatch`（必須是空的：病歷裡有退回的跑＝事件流裡找得到退回的跑，`ops/eval/local/s36nc_analyze.py:137,148`）。它的 `mcnemar_p_descriptive` 不是主要檢定；`decision` 只在 `--c-arm C36` 時輸出。
- 對錯取自容器寫出的 `verifier/reward.txt`（5.4）；主機上的重算（`ops/eval/formal/analyze.py:39-45`）只用來重建「第一次退回那一刻的答案」，它用 `.strip()`、容器用 `xargs`，引號答案可能不一致。
- **只描述、不分配功勞**：依 C 的路徑（有沒有退回）拆開的數字只描述（`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:65`；分組會偏，`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:212`）。
- 寫結論：`decisions/conclusions/CONCLUSION_<YYYYMMDD>_<名字>.md`，只用預註冊寫死的句型；顯著且 C 較好時一定附機制（見 1.3）。

---

## 10. 已知的坑

| 症狀 | 原因 | 解法 |
|---|---|---|
| C 組裝的是 0.7.0、沒有零設定 | 照 README 從 PyPI 裝 | 用第 4 節自己建的 wheel（`CHANGELOG.md:253-256`） |
| `launch_…` 印 `wheel sha256 mismatch` | uv／setuptools 版本不同、zip 位元組不同 | `-b` 釘 `setuptools==84.0.0`（第 4 節）；還不同就做 114 檔比對、把新雜湊寫進**新**預註冊（`ops/eval/evidence_20260926_local/RUNLOG.md:140-141`） |
| C 組 `c_arm_ok: false`、`steps: 0` | 沒自訂 base URL ⇒ Harbor 沒用隔離設定，擴充裝在 pi 不讀的目錄 | 保留 `--ae OPENROUTER_BASE_URL` 與 `--ak model_api`（`<HARBOR_DIR>/src/harbor/agents/installed/pi.py:397-411`）；照算 C（意向治療，`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:55`） |
| C 組安裝步驟失敗（`NonZeroAgentExitCodeError`，0 通模型請求） | 容器連不到 apt／PyPI／GitHub／npm，或 TLS 被攔截卻沒信任 CA | 開放那些網域；TLS 攔截就把 CA 烤進映像（5.3）（`ops/eval/evidence_20260926_local/RUNLOG.md:112-115`） |
| `vacant install` 回 1（no supported agent found） | 殼層裡找不到 `pi` | `harbor_vacant.py` 的 `. ~/.nvm/nvm.sh; export PATH=…` 前綴不能動（`vacant_network/adapters/cli.py:146-149`；`ops/eval/harbor_vacant.py:76`） |
| docker 報 bind mount 來源不存在，每跑都 infra_void | `run_local.sh` 寫死 `/root/.ccr/ca-bundle.crt`（`ops/eval/local/run_local.sh:10,28`） | 第 7 節 (0)：**不存在時才**放一份系統 CA（存在就不要覆蓋：雲端容器裡它是沙箱自己的 TLS 代理憑證），`run_local.sh` 保持逐位元組不變；或刪 `run_local.sh:28` 與 `:31-35`，記成偏差 |
| 每跑都 infra_void、帳本沒有那個標籤 | 容器連不到 `172.17.0.1:18900`（代理只綁 127.0.0.1、橋接位址不同） | `--host 0.0.0.0`＋防火牆；第 7 節 (c) 檢查；必要時改 `run_local.sh:15` |
| 每一通 400／403／404 | 上游名字不在設定、模型 id 不在 `models`、路徑錯 | 名字與 id 處處一致（6.3）；**這些拒絕不寫進帳本**（`ops/eval/orproxy.py:279-292`），所以要前測 |
| 每一通 402 | `budget_usd` 是 0 | 本機模式設大數（`ops/eval/orproxy.py:293-295`） |
| 每一通失敗、路徑 `/v1/v1/…` | 上游網址帶了 `/v1` | 拿掉（`ops/eval/orproxy.py:250`） |
| `driver.log` 第一行 `runs_to_go` > 0 但什麼都沒跑、馬上 `DONE` | 時間上限已過（沿用 `launch_u274.sh`） | 自己的啟動檔、未來的時間上限（`ops/eval/local/run_pairs.py:85-89`） |
| 時間上限早一小時觸發 | 主機時區有夏令時間 | `TZ=UTC`（`ops/eval/local/run_pairs.py:125`） |
| 系統提示裡出現「hard budget of」 | 忘了 `MAX_TURNS=none` | 啟動檔 `export MAX_TURNS=none`；`grep -c 'hard budget of' io.jsonl` 應為 0 |
| 裝了 pi 最新版 | 沒給 `--ak version=0.87.1` | 別改 `run_local.sh:36` |
| 磁碟掉到 2.5 GB 以下 | 容器可寫層每個 0.45–0.6 GB；每題映像累積（這裡觀察到，Harbor 預設 `docker compose down --rmi local`，`<HARBOR_DIR>/src/harbor/environments/docker/docker.py:1165-1168`，原因沒查證） | 每個位置留 ≥ 0.7 GB；批次之間只清**名字以 `dabstep-` 開頭、沒有在跑的容器用的**每題映像與已停的容器（先 `docker image ls` 看清楚）；**不要**刪 `vacant-eval/dabstep-env:1` 與基底，**不要** `docker system prune -a` |
| 某台機器 5 分鐘沒回應、延遲 p90 上百秒 | hard 題提示大（中位數 43.7k token）、位置太多擠掉快取 | 降位置（8.5）；pi 約 300 秒沒資料就切斷 |
| 大多數跑碰到 1800 秒時限（`AgentTimeoutError`） | 算力的 prefill 太慢／沒有前綴快取；hard 題的對話長 | 6.6：預註冊的可行性規則觸發就停，換算力；不要偷改時限 |
| 分析說傷害 0 但其實沒查 | pi 把擴充送的訊息記成 `entry_appended`（`custom_message`、`customType=vacant-check`），不是 `message_end` | 用現成的 `s36nc_analyze.one`，並看 `sendback_chain_vs_stream_mismatch` 為空（`ops/eval/local/s36nc_analyze.py:70-75`） |
| 找不到 Vacant 介入過 | 退回字句裡沒有 "Vacant"；`action` 在 `payload` 裡 | 讀 `chain.ndjson` 的 `review` 事件 `payload.action`（`decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:143-145`） |
| 分析整個崩掉 | 有 `result.json` 卻沒有 `agent/pi.txt` 的跑 | 第 9 節開頭的檢查 |
| 同一格跑兩次 | 停驅動後在跑的還沒結束就重開 | 8.5 的步驟 2 |
| 兩個 pusher 互相 non-fast-forward | 和這個工作階段推同一個分支 | 自己的分支 |
| `stop_reached: false` 被當成 Vacant 壞掉 | 被 1800 秒時限切斷或 pi 中止的跑不會進 Stop | 只有 `c_arm_ok: false` 是 C 組失敗；時限每組分開報（`ops/eval/harbor_vacant.py:16-18`） |
| 文件說法互相矛盾 | `vacant_network/trace/zerostop.py:25` 說四類、`README.md:86` 說裝技能 | 以程式為準：五類（`vacant_network/trace/review.py:37`）、技能要 `--skill` 才裝（`vacant_network/adapters/cli.py:282`） |

---

## 11. 目前狀態與數字

| 批次 | 設定 | 結果 | 出處 |
|---|---|---|---|
| 付費正式批次（2026-09-25，預註冊、人類簽字；和「第 0 階」探針是兩回事） | 77 題、15 回合上限、gemma-4-26b／qwen3.8-27b 開思考 | **沒有量到差別**（p＝0.21／0.29）；8 次退回全是誤報（之後修掉） | `decisions/conclusions/CONCLUSION_20260925_ZERO_CONFIG_DABSTEP.md:3,10-15`；`CLAUDE.md:193-197` |
| 本機正式批次 | 77 題 × 3 次、15 回合上限、gemma-4-12b 關思考；A／C1／C2(v3) | C2（v3，回合預算提醒開、15 回合上限）51.9%→59.3%（Wilcoxon 精確 p＝0.021）；提醒只在被告知上限時作用、v3.6.1 預設關 ⇒ **不適用於 C361／不設上限**；集中 6 題、兩跑翻過來就不顯著；提醒後寫的 63 跑 25 對 38 錯；Vacant 把對的改成錯 0 次；v3 看過同一批題設計。C1 沒有差別（p＝0.75） | `decisions/conclusions/CONCLUSION_20260926_ZERO_CONFIG_V3_LOCAL.md:10-18,26-28,46-55`；`CLAUDE.md:187,205-209` |
| 留出批次（v3.4） | 100 題 | **原始資料遺失**，做不了分析 | `ops/eval/evidence_20260926_local/RUNLOG.md:129-135` |
| S36-nocap（篩選） | 36 題 × 2 次、不設上限、A vs C36(v3.6) | A 40/72 vs C36 51/72；C 單獨對 13、A 單獨對 2；傷害 0；缺檔退回 9 跑 ⇒ **GO（不是證據）** | `decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:194-214`；`ops/eval/evidence_20260927_nocap/s36nc/analysis.json` |
| 缺檔退回探針（機制） | 15 個「說做完沒寫檔」的時刻 × 3 | 下一個回覆 45/45 寫檔、21 對 24 錯；36/45 寫的值逐字就在「做完了」那一則裡 | `decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md:186-192` |
| **u274（預註冊；agent 凍結、人類沒有逐條簽字）** | 274 題 hard、不設上限、A vs C361、人類的兩台 LM Studio | **在跑，沒有結果、沒有人看過評分**。10:50:44Z 開跑 4＋4；11:10Z 並行規則觸發；11:28Z 以 3＋3 接續；**12:15Z 前 16 跑有 12 跑碰到 1800 秒時限**（6.6），要不要停由人類決定；代理的串流錯誤 w401 5 通（`failed to decode`）、1003 3 通（`Engine protocol predict stream returned an error`），都是 LM Studio 那一側 | RUNLOG §17；`decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md:86-88` |

### 檔案地圖

| 路徑 | 做什麼 |
|---|---|
| `vacant_network/trace/{evidence,review,zerostop,budget}.py` | 零設定的檢查、退回字句、Stop／回合／交件說明、回合預算提醒（預設關） |
| `vacant_network/adapters/{cli,install,agents,hook,mode}.py` | `vacant install`／`uninstall`、pi 擴充（`agents.py` 裡的 JS）、掛鉤分派、模式開關 |
| `ops/eval/harbor_vacant.py` | Harbor 的 C 組 agent（A＋使用者的安裝指令＋`vacant_check.json`） |
| `ops/eval/orproxy.py` | 記帳代理（本機／付費兩種模式） |
| `ops/eval/dabstep_pin.py`、`ops/eval/local/make_unseen.py` | 釘死 450 題；產生／驗證 274 題清單 |
| `ops/eval/local/run_local.sh` | 一跑（A 或 C）；`MAX_TURNS=none` 不設上限 |
| `ops/eval/local/run_pairs.py` | 共用佇列驅動（`tests/test_eval_run_pairs.py`） |
| `ops/eval/local/launch_u274.sh` | u274 的啟動檔（**凍結，只當範本**） |
| `ops/eval/local/rerun_void.py` | 把 infra_void 移開以便補跑 |
| `ops/eval/local/archive_raw.py`、`archive_loop.sh` | 原始資料打包進 repo、定期 commit＋push |
| `ops/eval/local/monitor.sh` | 每分鐘監測、第一個問題就結束 |
| `ops/eval/local/unseen_analyze.py`、`s36nc_analyze.py`、`analyze_local.py`、`ops/eval/formal/analyze.py` | 主要分析、退回／傷害重建、每格整理、主機端重算 |
| `decisions/prereg/PREREG_20260927_NOCAP_UNSEEN.md` | u274 預註冊（範本） |
| `decisions/DECISION_20260926_BIGGER_EFFECT_REVIEW.md` §十一–§十三 | 篩選判準、探針、S36-nocap 結果 |
| `ops/eval/evidence_20260926_local/RUNLOG.md` | 執行紀錄格式的範例（§15–§17 是最近的） |
| `ops/eval/evidence_20260927_nocap/{unseen,s36nc,missing_probe,u274}/` | 274 題清單、S36-nocap 原始資料與分析、探針、u274（別碰） |

---

## 12. 交回來的東西

放在你的分支、**新目錄** `ops/eval/evidence_<YYYYMMDD>_<算力名>/`（不要寫進 `evidence_20260927_nocap/`）：

| 路徑 | 內容 |
|---|---|
| `decisions/prereg/PREREG_<YYYYMMDD>_<名字>.md` | 開跑前凍結的預註冊（commit 早於第一跑） |
| `ops/eval/local/launch_<P>.sh`、`archive_loop_<P>.sh`，以及你改過的任何腳本 | 和預註冊同一個 commit |
| `ops/eval/evidence_<…>/RUNLOG.md` | 執行紀錄（格式見下） |
| `ops/eval/evidence_<…>/env/` | `PIN_MANIFEST.json`、`UNSEEN_regen.json` 的 `cmp` 結果、wheel sha256（與 114 檔比對輸出）、代理設定（**不含金鑰與主機名**，主機用代號）、`docker version`、`uv --version`、Harbor commit、一跑 C 組裡的 `pipx runpip vacant-network freeze`（相依沒釘版本，`pyproject.toml:39-43`；u274 拿到的是 cryptography 50.0.1、mcp 1.30.0、jsonschema 4.26.0、Python 3.12.3〔環境觀察，repo 裡沒有、沒驗證〕——記你自己的）、`docker run --rm vacant-eval/dabstep-env:1 python3 -c 'import pandas,sys;print(pandas.__version__, sys.version)'` 的輸出、基底映像的 digest（`docker image inspect ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624 -f '{{.RepoDigests}}'`） |
| `ops/eval/evidence_<…>/<P>/raw/` | `archive_loop` 產生的 `chunk_NNN.tar.xz`＋`MANIFEST.jsonl`（只有這兩種） |
| `ops/eval/evidence_<…>/<P>/` | `progress.jsonl`、`driver*.log`（`archive_raw.py` 寫在這一層，`ops/eval/local/archive_raw.py:134-138`）；`rerun_void.log`、`moved.json`（手動複製）、`FROZEN_COMMIT` |
| `ops/eval/evidence_<…>/<P>/analysis/` | `cells.json`、`summary.json`、`s36nc_view.json` |
| `decisions/conclusions/CONCLUSION_<YYYYMMDD>_<名字>.md` | 只用預註冊寫死的說法 |

RUNLOG 格式（照 `ops/eval/evidence_20260926_local/RUNLOG.md`）：開頭一行寫人類的要求原話（網址、主機名、IP、金鑰、帳號換成代號——上一輪的第 4 行就是反例）；之後 `## N. 標題（HH:MM–HH:MM UTC）`，每節幾個條列——發生了什麼、量到的運作數字（延遲、錯誤、磁碟）、做了什麼決定與依據哪一條規則、**偏差**明寫、「沒有看任何評分」明寫；換並行、重啟、補跑各自一節。

commit：一行中文摘要（例：`原始資料歸檔：<P>（<時間>）`、`預註冊：<名字>（凍結）`），結尾用**你自己的**署名行（依你的系統指示）；**不要**抄這個工作階段的 `Co-Authored-By`／`Claude-Session` 兩行。push 前跑 `python3 ops/check_repo_links.py`。

---

## 附：這份文件沒能驗證的事

- `harbor datasets download dabstep@1.0 --registry-path registry.json --export -o …` 是從 Harbor 原始碼推出來的（`<HARBOR_DIR>/src/harbor/cli/datasets.py:167-230`），當初用的那一行沒有記錄；以 `make_unseen.py`＋`cmp` 驗收。
- wheel 雜湊只在這台機器（uv 0.8.17、setuptools 84.0.0）重現過；別的 uv 版本沒試。
- `vacant-eval/dabstep-env:1` 的 CA 版 Dockerfile 是從映像歷史反推的；官方原版（無 CA）在新機器上會不會建出同樣的 `/app/data` 取決於 HF `main` 有沒有變。
- 每題映像為什麼會累積、確切命名（這裡看到 `dabstep-<id>__<亂碼>…`）沒查證；docker compose／buildx 版本、是否需要 containerd 映像儲存沒記錄。
- 前測指令（`u274-preflight`、`restart-probe*`）當初的確切寫法不在 repo；第 7 節是等效重寫。
- 非 LM Studio 的伺服器（vLLM、llama.cpp）是否接受 pi 0.87.1 的請求欄位、`reasoning_effort: "none"`、回 OpenAI 格式的 `tool_calls` 與串流 usage：沒測過；pi 在多長的對話時壓縮上下文：沒查。
- 6.1 的 `iptables` 規則、要金鑰的上游（`orproxy.py` 不支援）：這裡都沒用過。
- 代理全部拒絕時 Harbor 會給 `reward` null（infra_void）還是 0：repo 沒記錄；靠前測與看帳本避免。
- `harbor_vacant.py` 只在 Harbor `6cb9ff31`＋pi 0.87.1 上用過；容器裡 PyPI／npm 相依沒釘版本，換日期可能解析出新版。
- 每 3 小時報告當初怎麼排程：repo 沒有。u274 的結果：還沒有。
