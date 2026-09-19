"""收據要說得出 **bytes 去了誰的伺服器，以及那個位址是誰指定的**。

這支在架構裡承重什麼
────────────────────
`vacant run` 的全部意義是中介。但收據原本**只記了「有幾通」**（`requests_seen`），
沒記「去了哪裡」，更沒記「那個位址是我指定的，還是程式自己挑的預設值」。

於是這件事發生了而沒有人看得到（2026-09-19，Claude Code 升 L-real 時量到）：

> Claude Code 啟動會探 `$ANTHROPIC_BASE_URL/api/hello`。
> `wireproxy.route()` 只把 `/v1/messages`／`/v1/complete` 判給 anthropic，
> **其餘一律落到 openai** ⇒ 那一通用的是 openai 的上游。
> 而那一跑只指定了 anthropic（→ 本機 1003），openai 沒指定
> ⇒ 它走 `DEFAULT_UPSTREAM["openai"]` ＝ **`https://api.openai.com`**，
> **真的出網，去了一家那一跑根本沒在用的廠商。**

那一通是空的 HEAD、金鑰是 sentinel，所以沒有洩漏內容。
⚠ **但「這次沒洩漏」與「這條路不會洩漏」是兩件事**——
明天 agent 換一個**帶 body** 的診斷端點，同一個機制就會把東西送出去。

這支不修那個路由（`route()` 按 path 猜家族是 V0 的設計邊界，
結構性補法是 `block_egress.sh`）。它修的是**看不見**：
`defaulted: true` 讓「沒有人指定這個位址」在收據上寫得出來。

## 2026-09-19：從「看得見」改成「擋得住」（門檻三）

`upstreams_defaulted` **只修了看不見，路還在**——而看得見沒有擋住任何東西。
現在沒指定的 wire 解析到 `envmap.SINK_UPSTREAM`（一個 `.invalid` 主機名），
`wireproxy` 在**開任何連線之前**就回 502。要走公開 API 得明講。

本檔因此分成兩組，**兩組都要在**：

  · `test_negative_control_*` ——**證明那條路還在**（明講之後照樣走得到
    `https://api.openai.com`）。沒有這一組，「擋住了」就沒有對照。
  · 其餘 ——證明預設擋得住，而且**兩條上游都釘死的跑完全不受影響**
    （五 agent 矩陣 20 格、`runs/v1_five_agent_matrix_20260919/controls.sh`）。
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from vacant_network.vrun import envmap

SUITE = "def check_add():\n    from solution import add\n    assert add(2, 3) == 5\n"


def test_named_upstream_records_which_variable_named_it():
    d = envmap.describe_upstreams(
        {"VACANT_RUN_UPSTREAM_ANTHROPIC": "http://127.0.0.1:1234",
         "VACANT_RUN_UPSTREAM_OPENAI": "http://127.0.0.1:5678"})
    assert d["anthropic"]["url"] == "http://127.0.0.1:1234"
    assert d["anthropic"]["source"] == "env:VACANT_RUN_UPSTREAM_ANTHROPIC"
    assert d["anthropic"]["defaulted"] is False
    assert d["openai"]["defaulted"] is False


ONLY_ANTHROPIC = {"VACANT_RUN_UPSTREAM_ANTHROPIC": "http://127.0.0.1:1234"}


def test_negative_control_the_road_to_the_public_api_is_still_there():
    """**負控制：修改前真的會落到公開 API。**

    這一條刻意不驗「擋住了」，它驗的是**那條路存在**——只指定 anthropic
    的那一跑，openai 這條路由在明講放行之後解析到 `https://api.openai.com`。
    不送任何 bytes，只看解析結果（`describe_upstreams` 是純函式）。

    ⚠ 沒有這一條，「擋住了」就沒有對照：一個永遠解析不到公開 API 的系統
      與一個被擋住的系統，在只驗後者的測試底下長得一模一樣。
    """
    d = envmap.describe_upstreams(ONLY_ANTHROPIC, allow_public=True)
    assert d["openai"]["url"].startswith("https://api.openai.com"), (
        "公開 API 的位址變了——那不一定是壞事，但這條負控制的前提要跟著改")
    assert d["openai"]["defaulted"] is True
    assert d["openai"]["fallback"] == "public"
    # 逐字重現 2026-09-19 量到的那一通：Claude Code 的啟動探測
    from vacant_network.vrun import wireproxy
    assert wireproxy.route("/api/hello") == "openai"
    assert wireproxy.join_upstream(d["openai"]["url"], "/api/hello") == \
        "https://api.openai.com/api/hello"


def test_unspecified_wire_goes_to_a_refusing_local_sink():
    """**預設**：沒人指定的 wire 指到本機 sink，不是公開 API。"""
    d = envmap.describe_upstreams(ONLY_ANTHROPIC)
    assert d["anthropic"]["defaulted"] is False
    assert d["anthropic"]["fallback"] is None
    assert d["openai"]["defaulted"] is True, "沒人指定卻沒被標出來"
    assert d["openai"]["source"] == "default", "`source` 的形狀凍結，不准變"
    assert d["openai"]["fallback"] == "sink"
    assert d["openai"]["url"] == envmap.SINK_UPSTREAM
    assert envmap.is_sink(d["openai"]["url"])
    # `.invalid` 是 RFC 2606 保留的 TLD：就算有人繞過 wireproxy 的檢查拿
    # 這個字串去連，結果也是**連不上**而不是**連到別人家**。
    assert d["openai"]["url"].split("/")[2].endswith(".invalid")
    assert not d["openai"]["url"].startswith("https://api.openai.com")


def test_pinned_upstreams_are_completely_untouched():
    """五 agent 矩陣那批（兩條上游都釘死）**一個欄位都不准變**。"""
    env = {"VACANT_RUN_UPSTREAM_OPENAI": "http://100.86.226.21:1234/v1",
           "VACANT_RUN_UPSTREAM_ANTHROPIC": "http://100.86.226.21:1234"}
    for allow in (False, True):
        d = envmap.describe_upstreams(env, allow_public=allow)
        assert [d[w]["defaulted"] for w in d] == [False, False]
        assert [d[w]["fallback"] for w in d] == [None, None]
        assert not any(envmap.is_sink(v["url"]) for v in d.values())
        assert d["openai"]["url"] == env["VACANT_RUN_UPSTREAM_OPENAI"]


def test_escape_hatch_is_explicit_only():
    """逃生口有兩個入口，**兩個都要明講**；預設一律 sink。"""
    assert envmap.public_upstream_allowed({}) is False
    assert envmap.public_upstream_allowed({envmap.ALLOW_PUBLIC_VAR: "1"}) is True
    assert envmap.public_upstream_allowed({envmap.ALLOW_PUBLIC_VAR: "true"}) is True
    # 空字串／0／隨便一個值都不算明講
    for v in ("", "0", "no", "maybe"):
        assert envmap.public_upstream_allowed({envmap.ALLOW_PUBLIC_VAR: v}) is False


def test_discover_upstreams_keeps_its_old_shape():
    """既有呼叫端只要 `{wire: url}`，形狀不准變。"""
    env = {"VACANT_RUN_UPSTREAM_OPENAI": "http://x:1/v1"}
    old = envmap.discover_upstreams(env)
    assert old == {w: v["url"]
                   for w, v in envmap.describe_upstreams(env).items()}
    assert all(isinstance(v, str) for v in old.values())


@pytest.mark.parametrize("named,expect_defaulted", [
    ({"VACANT_RUN_UPSTREAM_ANTHROPIC": "http://127.0.0.1:1"}, ["openai"]),
    ({"VACANT_RUN_UPSTREAM_OPENAI": "http://127.0.0.1:1/v1"}, ["anthropic"]),
    ({}, ["anthropic", "openai"]),
])
def test_summary_lists_every_defaulted_wire(tmp_path, named, expect_defaulted):
    """`upstreams_defaulted` 是給人一眼看的那一行，要**逐跑落盤**。"""
    ws, suite = tmp_path / "ws", tmp_path / "suite"
    ws.mkdir()
    suite.mkdir()
    (suite / "test_visible.py").write_text(SUITE, encoding="utf-8")
    (ws / "solution.py").write_text("def add(a, b):\n    return a + b\n",
                                    encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), **named}
    r = subprocess.run(
        [sys.executable, "-m", "vacant_network.vrun.launcher",
         "--workspace", str(ws), "--suite", str(suite),
         "--run-dir", str(tmp_path / "rd"), "--sandbox", "none", "--json",
         "--", "bash", "-lc", "true"],
        capture_output=True, text=True, timeout=300, env=env)
    assert r.returncode == 0, r.stderr[-400:]
    d = json.loads(r.stdout)
    assert d["upstreams_defaulted"] == expect_defaulted
    for w in expect_defaulted:
        assert d["upstreams"][w]["source"] == "default"
