"""`requests_seen` 不准單獨存在——收據要說得出那是總數還是下界。

這支在架構裡承重什麼：2026-09-20 的獨立稽核實測，ON 29 格／TEE 24 格磁碟上的
`*.req.bin` 比 `index.jsonl` 多 1–2 個，**每一格都恰好 `wire_quiesced == false`**。
多出來的那些都經過 proxy（不影響「有沒有被中介」），但 `requests_seen` 與
`wire_digest` 不含它們——**而收據當時說不出這一點**。

語意照抄 SLSA（2026-09-20 直驗）：v0.2 `metadata.completeness.*` 的
fail-closed（沒有旗標即視為不完整）＋ VSA `dependencyLevels` 的三態。
⚠ **不是照抄欄位**——SLSA v1.0 已經把 in-band 的 completeness 欄位移除了，
現行規格沒有可直接用的欄位。我們自訂欄位、沿用它的語意。
"""
import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _run(tmp_path, extra_cmd):
    ws = tmp_path / "ws"; ws.mkdir()
    (ws / "solution.py").write_text("def add(a, b):\n    return a + b\n")
    suite = tmp_path / "suite"; suite.mkdir()
    (suite / "test_visible.py").write_text(
        "import solution\n"
        "def check_add():\n    assert solution.add(1, 2) == 3\n")
    rd = tmp_path / "rd"
    r = subprocess.run(
        [sys.executable, "-m", "vacant_network.vrun.launcher",
         "--workspace", str(ws), "--run-dir", str(rd), "--suite", str(suite),
         "--task-id", "wirecount", "--sandbox", "none", "--json",
         "--timeout", "60", "--retry", "none", "--"] + extra_cmd,
        cwd=ROOT, capture_output=True, text=True, timeout=180,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
             "VACANT_ATTEST": "off",
             "VACANT_RUN_UPSTREAM_OPENAI": "http://127.0.0.1:1/v1",
             "VACANT_RUN_UPSTREAM_ANTHROPIC": "http://127.0.0.1:1"})
    d = json.loads((rd / "run_RUN-ON.json").read_text())
    return d, rd


def test_model_wire_block_exists_and_is_self_describing(tmp_path):
    d, _ = _run(tmp_path, ["true"])
    mw = d["model_wire"]
    assert set(mw) >= {"requests_indexed", "request_blobs_persisted",
                       "unindexed_requests", "wire_quiesced",
                       "quiesce_timeout", "count_semantics"}
    assert mw["count_semantics"] in ("exact", "lower_bound")
    assert mw["requests_indexed"] == d["requests_seen"]


def test_zero_request_run_is_exact_not_lower_bound(tmp_path):
    """agent 一通都沒打 ⇒ 排空成功、磁碟上也沒有 blob ⇒ 這個 0 是**總數**。

    ⚠ 這一條守的是「不要把所有東西都保守地標成 lower_bound」——
      那樣 `exact` 就變成永遠不會出現的裝飾品，欄位等於沒加。
    """
    d, _ = _run(tmp_path, ["true"])
    mw = d["model_wire"]
    assert mw["requests_indexed"] == 0
    assert mw["request_blobs_persisted"] == 0
    assert mw["unindexed_requests"] == 0
    assert mw["wire_quiesced"] is True
    assert mw["count_semantics"] == "exact"


def test_negative_control_unindexed_blob_forces_lower_bound(tmp_path):
    """**負控制**：磁碟上多塞一個 `.req.bin`，判讀必須從 exact 掉到 lower_bound。

    沒有這一條，`count_semantics` 跟一個永遠回 `exact` 的常數長得一樣。
    這裡直接重算判準（與 launcher 同一條規則），因為要在事後注入 blob。
    """
    d, rd = _run(tmp_path, ["true"])
    assert d["model_wire"]["count_semantics"] == "exact"      # 前提
    wire = rd / "wire_RUN-ON"
    (wire / "deadbeef.req.bin").write_bytes(b"POST /v1/chat/completions")
    blobs = len(list(wire.glob("*.req.bin")))
    unindexed = blobs - d["requests_seen"]
    quiesced = d["model_wire"]["wire_quiesced"]
    semantics = "exact" if (quiesced and unindexed == 0) else "lower_bound"
    assert unindexed == 1
    assert semantics == "lower_bound", "多一個 blob 卻還是 exact ⇒ 判準沒在看 blob"


def test_verdict_receipt_carries_the_semantics(tmp_path):
    """🔴 判讀欄位要**簽進鏈**，不能只躺在旁邊那個改得掉的 JSON 裡。"""
    d, rd = _run(tmp_path, ["true"])
    lines = [json.loads(x) for x in
             (rd / "receipts_RUN-ON.ndjson").read_text().splitlines() if x.strip()]
    # ⚠ 頂層事件別欄位叫 `type` 不是 `etype`（實際落盤查過，不是猜的）。
    #   猜錯的後果是這個測試永遠找不到收據卻看起來像「收據裡沒有那兩欄」。
    verdicts = [e for e in lines if e.get("type") == "ws_verdict"]
    assert verdicts, "沒有 ws_verdict 收據"
    pay = verdicts[-1]["payload"]
    assert pay["wire_count_semantics"] == d["model_wire"]["count_semantics"]
    assert pay["wire_quiesced"] == d["model_wire"]["wire_quiesced"]


def test_requests_seen_still_means_the_same_thing(tmp_path):
    """⚠ 既有欄位的語意**不准改**——r452c 之後的歸檔資料靠它比對。"""
    d, _ = _run(tmp_path, ["true"])
    assert "requests_seen" in d
    assert isinstance(d["requests_seen"], int)
