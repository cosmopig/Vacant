# `ops/e1/` — E1′ 實驗基建（「保護已經對的工作」）

檢驗問題：**在多回合任務鏈中，由宿主端只提交允許範圍內的單元並保留基線（`S`／`S+B2`／`O`），相對於無檢查原生 agent（`B0`／`B0x3`）與驗收閘門加回滾（`B2`），能否顯著保護已經正確的既有工作？**

## 模組結構

- [`__init__.py`](__init__.py) — 共用常數、EvalPlus 釘死 sha256、KS-1 防呆與原子寫檔工具
- [`units.py`](units.py) — 單元抽取（程式碼 AST 頂層函式；文件 `": "` 標籤前綴）、任務範圍推導、範圍受限原子提交
- [`sandbox.py`](sandbox.py) — Linux `bwrap` worker 沙箱（pi 模式共用網路＋去敏 `PI_CODING_AGENT_DIR`；Claude 模式強制 `--unshare-net`＋唯讀單檔 `.credentials.json`＋UNIX socket 白名單代理）與 `--unshare-net` 評分沙箱（含 `prlimit` 與逾時強殺）
- [`netproxy.py`](netproxy.py)／[`proxy_bridge.py`](proxy_bridge.py) — 宿主端 UNIX socket 白名單代理（CONNECT 僅放行 `api.anthropic.com:443`、明文 HTTP 僅放行 `*.e1-sources.example`／`*.d2-sources.example` 轉發至本機來源伺服器，逐筆落盤 `proxy.jsonl`）與沙箱內極簡 TCP→UNIX 轉發器
- [`negative_controls.py`](negative_controls.py) — 隔離負控制（支援 `--agent pi` 與 `--agent claude`）：從 worker 沙箱實測禁止路徑皆不可讀、評分沙箱斷網；Claude 模式另驗 `~/.claude` 非憑證檔不可讀、直連外部 IP 失敗、經代理 CONNECT 非白名單主機遭 403 拒絕；任一失敗即拒跑
- [`build_code_chains.py`](build_code_chains.py) — 由公開 EvalPlus（HumanEval+ v0.1.10／MBPP+ v0.2.0）建構 5 回合程式碼鏈（**本實驗延伸，our extension**）
- [`build_doc_chains.py`](build_doc_chains.py) — 由真實修訂維基百科教材（realrev materials）建構 4 週期文件鏈（**本實驗延伸，our extension**）
- [`evaluate.py`](evaluate.py) — 獨立評分器、B2 宿主檢查與文件 S 臂範圍推導（呼叫產品函式 `vacant_network.trace.sources.value_status(..., by_field=True)`）
- [`run_e1.py`](run_e1.py) — 主執行器（未 commit 拒跑、負控制先行、斷點續跑安全、`--calibrate`、JSONL 落盤）
- [`analyze_e1.py`](analyze_e1.py) — 結果彙整（聚類單位＝任務鏈，含主要指標、次要指標、S/S+B2/O 誤拒與範圍內錯誤拆解、對 B0 配對 McNemar）
- [`fake_agent.py`](fake_agent.py)／[`selftest.py`](selftest.py) — 確定性假 agent 與端對端自測

## 使用方式

### 1. 建構任務鏈

```bash
# 程式碼鏈（驗證 ~/dev/ops/ref/evalplus 釘死 sha256；無網路 bwrap 算預期輸出）
python3 ops/e1/build_code_chains.py --seed 42 --n 10 --out /tmp/claude-1000/agy_e1/code_chains

# 文件鏈（讀取 realrev 教材目錄）
python3 ops/e1/build_doc_chains.py --materials /tmp/claude-1000/agy_real/sample --sets set_01 set_02 --out /tmp/claude-1000/agy_e1/doc_chains
```

### 2. 獨立跑隔離負控制

```bash
# 獨立跑隔離負控制（pi 或 claude）
python3 ops/e1/negative_controls.py --agent pi --eval-dir /tmp/claude-1000/agy_e1/run_out
python3 ops/e1/negative_controls.py --agent claude --eval-dir /tmp/claude-1000/agy_e1/run_out
```

### 3. 跑端對端自測（零模型呼叫、真實 bwrap＋真實負控制）

```bash
python3 ops/e1/selftest.py
```

### 4. 正式執行與分析

計畫檔（須先 `git add && git commit`）範例：

```json
{
  "schema": "vacant.e1.plan/1",
  "id": "e1_code_v1",
  "chains_dir": "/tmp/claude-1000/agy_e1/code_chains",
  "arms": ["B0", "B0x3", "B2", "S", "S+B2", "O"],
  "model": {
    "providers": ["lms1003q9", "lms1004q9"],
    "model": "qwen/qwen3.5-9b",
    "pi_cfg_dir": "~/dev/ops/agentcfg/d2v52"
  },
  "jobs": 2,
  "attempt_timeout_s": 600
}
```

```bash
# 先以 B0 校準
python3 ops/e1/run_e1.py --plan plans/e1_code_v1.json --root /tmp/claude-1000/agy_e1/cal --calibrate

# 正式跑全部臂（斷點續跑安全）
python3 ops/e1/run_e1.py --plan plans/e1_code_v1.json --root /tmp/claude-1000/agy_e1/run

# 分析結果
python3 ops/e1/analyze_e1.py /tmp/claude-1000/agy_e1/run --json /tmp/claude-1000/agy_e1/summary.json
```

## 誠實邊界與已知限制

1. **EvalPlus 無法構造「行為變更（behavior-change）」回合**：EvalPlus 僅含單一規格之測資、沒有變體測資，因此程式碼鏈只含 `add`（r1–r3）、`rename`（r4）與 `confirm`（r5），此限制已寫入每條鏈的 metadata。
2. **衍生延伸標註**：所有多回合鏈皆從公開資料（EvalPlus、真實修訂維基百科快照）組裝而來，屬於本實驗延伸（our extension），不可直接等同原基準分數。
3. **隔離範圍**：
   - `pi` 模式 worker 沙箱保證宿主檔案系統（隱藏測資、評分輸出、別臂工作區、教材、`~/dev/ops`、金鑰）不可達，但因須連線本機模型端點與來源伺服器而共用網路。
   - `claude` 模式 worker 沙箱強制 `--unshare-net`，網路出口僅能經單一綁入的 UNIX socket 走宿主白名單代理（CONNECT 僅放行 `api.anthropic.com:443`、明文 HTTP 僅放行來源伺服器虛擬主機），且 `~/.claude` 僅複製 `.credentials.json` 唯讀掛入 `/sandbox_home/.claude/.credentials.json`。
   - 評分與可見測試沙箱一律強制 `--unshare-net`。
4. **機制量具定位**：本套件量的是 harness 端機制，不是安裝產品後的零設定自然表現；`selftest.py` 僅驗證管線正確性，不作為模型效果證據。
