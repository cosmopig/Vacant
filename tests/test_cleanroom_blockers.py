"""乾淨室驗證（2026-09-18）找到的三個發布前阻擋項——每一條都配一個負向控制。

這支在架構裡承重什麼
====================
一個只拿 wheel ＋ README、不准看原始碼的外部 agent 在 Ubuntu 上實測 0.7.0，找到三件
**照文件寫就會壞**的事。三件事的共同形狀是「錯誤長得像正常輸出」：

1. `vacant bench` 把「一次都沒量到」渲染成「兩臂各 0%、差 +0%」並 exit 0
   （鐵律 3／09 §3.5 的 `infra_void`：**沒量到 ≠ 量到 0**）。
2. 我們自己列的禁語（「信任」／"trust layer"）出現在我們自己的 CLI 輸出裡
   （CLAUDE.md 鐵律 5：經典定義把「不依賴監督」寫進信任的必要條件，而監督是本系統的全部）。
3. `select_by_quorum` 的 `drafts` 傳反 ⇒ 沒有例外、沒有警告 ⇒ 得到一次
   **三方一致、簽章全過的拒交**——而拒交是本系統的合法輸出，整份文件都在教人相信它。

每一條的測試都成對：一條證明擋門會擋（正向），一條證明**擋門不是永遠都在擋**
（負向控制）。只有前者的話，一個 `return False` 也能讓測試全綠。
"""

from __future__ import annotations

import io
import socket
from contextlib import redirect_stderr, redirect_stdout

import pytest

from vacant.agent import Vacant
from vacant.identity import Identity
from vacant.logbook import Logbook
from vacant.peerexec import (DraftOrderError, Executor, ProbeResult, Selection,
                             select_by_quorum, sha256_hex)
from vacant.suitespec import SuiteSpecError
from vacant import suitespec as ss

BANNED = ("信任", "trust layer", "trusted layer", "信任層")


# ── 共用替身 ────────────────────────────────────────────────────────────────
class DeadBrain:
    """每一次呼叫都炸的腦＝端點是關的。這一格**沒有量到**，不是答錯。"""

    name = "dead"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        raise ConnectionRefusedError("[Errno 61] Connection refused")


class GoodBrain:
    """確定性的好腦：負向控制用——證明擋門在該放行的時候會放行。"""

    name = "good"

    def generate(self, prompt: str) -> str:
        return "RIGHT"


class FlakyBrain:
    """前 `n_dead` 題的**所有**呼叫都死，其餘正常。用來造「部分量到」。"""

    name = "flaky"

    def __init__(self, dead_prompts: set[str]) -> None:
        self.dead_prompts = dead_prompts

    def generate(self, prompt: str) -> str:
        for d in self.dead_prompts:
            if prompt.startswith(d):
                raise TimeoutError("read timed out")
        return "RIGHT"


_CHECK = lambda a: a == "RIGHT"  # noqa: E731


def _closed_port() -> int:
    """綁一個 port 再放掉——拿到一個幾乎確定沒人聽的位址（connection refused）。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ══════════════════════════════════════════════════════════════════════════
# 阻擋項一：bench 不准把「沒量到」講成「量到 0%」
# ══════════════════════════════════════════════════════════════════════════
def test_solve_result_separates_not_measured_from_wrong():
    """三種結局要分得開：答對 / 答錯 / 沒量到。"""
    dead = Vacant(DeadBrain(), k=3).solve("x", _CHECK)
    assert dead.verified is False
    assert dead.infra_void is True and dead.measured is False
    assert dead.ok_calls == 0 and dead.failed_calls == 3
    assert "Connection refused" in (dead.first_error or "")

    wrong = Vacant(GoodBrain(), k=3).solve("x", lambda a: a == "NEVER")
    assert wrong.verified is False
    assert wrong.infra_void is False and wrong.measured is True   # 負向控制：答錯≠沒量到


def test_a_cell_with_one_successful_call_is_measured():
    """誠實邊界：`infra_void` 是「**一次**成功的呼叫都沒有」，不是「有任何失敗」。

    這條釘住的是分母的定義。放寬成「有失敗就作廢」會把一次真的量測丟掉；
    收緊成「有成功就算數」才是 09 §3.5 的語意。
    """
    class HalfDead:
        name = "half"

        def __init__(self) -> None:
            self.n = 0

        def generate(self, prompt: str) -> str:
            self.n += 1
            if self.n == 1:
                return "WRONG"
            raise ConnectionRefusedError("boom")

    r = Vacant(HalfDead(), k=3).solve("x", _CHECK)
    assert r.ok_calls == 1 and r.failed_calls == 2
    assert r.infra_void is False and r.measured is True


def test_bench_report_marks_every_cell_void_when_the_endpoint_is_down():
    rep = Vacant(DeadBrain(), k=3).bench([("a", _CHECK), ("b", _CHECK)])
    assert rep["n"] == 2
    assert rep["plain_void"] == 2 and rep["vacant_void"] == 2
    assert rep["plain_measured"] == 0 and rep["vacant_measured"] == 0
    assert rep["paired_measured"] == 0
    assert rep["infra_void"] is True
    # 分母為 0 ⇒ **None**，不是 0.0。0.0 會被下游當成一個量到的數字。
    assert rep["plain_acc"] is None and rep["vacant_acc"] is None
    assert rep["gain"] is None
    assert rep["plain_calls_per"] is None and rep["vacant_calls_per"] is None


def test_bench_report_is_normal_when_everything_is_measured():
    """負向控制：腦活著的時候，`infra_void` 必須是 False、數字必須印得出來。"""
    rep = Vacant(GoodBrain(), k=3).bench([("a", _CHECK), ("b", _CHECK)])
    assert rep["infra_void"] is False
    assert rep["plain_void"] == 0 and rep["vacant_void"] == 0
    assert rep["plain_measured"] == 2 and rep["vacant_measured"] == 2
    assert rep["paired_measured"] == 2
    assert rep["plain_acc"] == 1.0 and rep["vacant_acc"] == 1.0
    assert rep["gain"] == 0.0
    assert rep["first_error"] is None


def test_bench_denominator_excludes_the_void_cells():
    """部分量到：void 的格子既不進分子也不進分母，而且格數單獨回報。"""
    cases = [(f"q{i}", _CHECK) for i in range(4)]
    rep = Vacant(FlakyBrain({"q0", "q1"}), k=3).bench(cases)
    assert rep["plain_void"] == 2 and rep["vacant_void"] == 2
    assert rep["plain_measured"] == 2 and rep["vacant_measured"] == 2
    assert rep["paired_measured"] == 2
    assert rep["infra_void"] is False
    # 分母是 2 不是 4：兩格沒量到的題目不准把正確率稀釋成 50%。
    assert rep["plain_acc"] == 1.0 and rep["vacant_acc"] == 1.0
    assert "timed out" in (rep["first_error"] or "")


def _run_cli(argv: list[str]) -> tuple[int, str, str]:
    from vacant.cli import main

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


def test_cli_bench_refuses_to_print_comparison_numbers_when_nothing_was_measured():
    """阻擋項一的核心證明：零成功量測 ⇒ 不輸出比較數字 ⇒ exit 非 0。

    外部使用者第一次跑 `vacant bench` 用的是預設 `--base`（localhost:1234），
    端點沒開是**最可能**的第一次體驗。發一個「可究責層」的套件，而它的 demo 指令
    把「沒量到」講成「量到 0%」，比不發還糟。
    """
    port = _closed_port()
    rc, out, err = _run_cli(["bench", "--model", "definitely-not-real",
                             "--base", f"http://127.0.0.1:{port}", "-n", "2"])
    assert rc != 0, "一次都沒量到卻 exit 0"
    # 比較數字一個都不准出現
    for forbidden in ("正確率", "讓你的模型", "算力"):
        assert forbidden not in out, f"沒量到卻印了 {forbidden!r}：\n{out}"
    assert "%" not in out
    # 診斷要說人話：端點、分母、第一個錯誤原文
    assert "infra_void" in err
    assert f"127.0.0.1:{port}" in err
    assert "量到 0/2" in err
    assert "Connection refused" in err or "URLError" in err


def test_cli_bench_still_prints_numbers_when_the_brain_answers(monkeypatch):
    """負向控制：擋門不是永遠都在擋——腦活著就要照印，而且 exit 0。"""
    import vacant.brains as brains

    class FakeLMStudio:
        name = "lmstudio:fake"

        def __init__(self, *a, **kw) -> None:
            pass

        def generate(self, prompt: str) -> str:
            return "whatever"          # 一定答錯，但**量到了**

    monkeypatch.setattr(brains, "LMStudioBrain", FakeLMStudio)
    rc, out, err = _run_cli(["bench", "--model", "m", "--base", "http://x", "-n", "2"])
    assert rc == 0
    assert "正確率" in out and "讓你的模型" in out
    assert "infra_void" not in err
    # 「量到 0%」是合法輸出——它跟「沒量到」的差別正是這一整條測試的主題。
    assert "0%" in out


def test_cli_bench_prints_the_void_count_separately_when_partial(monkeypatch):
    """部分故障：數字可以印，但 void 的格數要**單獨印**、分母要講清楚。"""
    import vacant.brains as brains

    class HalfDeadLMStudio:
        name = "lmstudio:halfdead"

        def __init__(self, *a, **kw) -> None:
            self.seen: set[str] = set()

        def generate(self, prompt: str) -> str:
            if "reverse" in prompt:
                raise ConnectionResetError("connection reset by peer")
            return "whatever"

    monkeypatch.setattr(brains, "LMStudioBrain", HalfDeadLMStudio)
    rc, out, err = _run_cli(["bench", "--model", "m", "--base", "http://x", "-n", "6"])
    assert rc == 0
    assert "⚠ infra_void" in out
    assert "connection reset" in out
    assert "正確率" in out


# ══════════════════════════════════════════════════════════════════════════
# 阻擋項二：我們自己列的禁語不准出現在我們自己的輸出裡
# ══════════════════════════════════════════════════════════════════════════
def _scan(text: str, where: str) -> list[str]:
    """回傳 `text` 裡踩到禁語的行。獨立成函式，好讓負向控制能餵它假資料。"""
    hits = []
    for ln in text.splitlines():
        for w in BANNED:
            if w in ln:
                hits.append(f"{where}: {ln.strip()}")
    return hits


def test_the_banned_word_scanner_actually_catches_something():
    """負向控制（先驗掃描器）：擋門自己要會響，否則下面三條全是空的。"""
    assert _scan("這是 C3 +Vacant 信任組合", "fake") != []
    assert _scan("do not call it a trust layer", "fake") != []
    assert _scan("這是可究責組合", "fake") == []


def test_no_banned_term_in_any_cli_help_text():
    """`--help` 是使用者可見輸出，而且是 argparse 直接渲染的，最容易漏掉。"""
    from vacant.cli import build_parser

    hits: list[str] = []

    def walk(parser, path):
        hits.extend(_scan(parser.format_help(), path))
        for a in parser._actions:
            ch = getattr(a, "choices", None)
            if isinstance(ch, dict):
                for name, sp in ch.items():
                    walk(sp, f"{path} {name}")

    walk(build_parser(), "vacant")
    assert hits == [], "CLI --help 出現禁語：\n" + "\n".join(hits)


def test_no_banned_term_in_demo_init_and_up_output(tmp_path):
    """`demo` 是外部使用者最可能截圖的畫面；`init`／`up` 是第一次跑的兩步。"""
    hits: list[str] = []
    for argv, where in (
        (["demo"], "vacant demo"),
        (["--root", str(tmp_path / "bodies"), "init", "probe"], "vacant init"),
        (["up", "--root", str(tmp_path / "eco"), "--no-dashboard"], "vacant up"),
    ):
        rc, out, err = _run_cli(argv)
        assert rc == 0, f"{where} exit {rc}"
        hits.extend(_scan(out, where))
        hits.extend(_scan(err, where + " (stderr)"))
    assert hits == [], "CLI 輸出出現禁語：\n" + "\n".join(hits)


def test_no_banned_term_in_the_bench_void_diagnostic():
    port = _closed_port()
    rc, out, err = _run_cli(["bench", "--model", "m",
                             "--base", f"http://127.0.0.1:{port}", "-n", "1"])
    assert rc != 0
    assert _scan(out, "bench stdout") == [] and _scan(err, "bench stderr") == []


# ══════════════════════════════════════════════════════════════════════════
# 阻擋項二之二（2026-09-18 裁決，`DECISION_20260918_MCP_WORDING.md`）：
# 禁語的第四個出口——MCP 工具 description，也就是**模型**看的輸出
# ══════════════════════════════════════════════════════════════════════════
def _mcp_tool_descriptions() -> dict[str, str]:
    """FastMCP 實際會送進 `tools/list` 的那份文字（不是原始碼，是 client 看到的）。"""
    from vacant import mcp_server

    return {t.name: (t.description or "")
            for t in mcp_server.mcp._tool_manager.list_tools()}


def test_no_banned_term_in_any_mcp_tool_description():
    """禁語的第四個出口：MCP 工具的 description。

    `--help`／`demo`／`init`／`up` 是**人**看的輸出，這一條掃的是**模型**看的輸出。
    `AGENTS.md:59` 把 MCP 這個形態定性為 persuasion only——整個形態就只有這段文字在
    出力，所以它比 CLI 的字串更該守禁語，不是更寬鬆。2026-09-18
    （`DECISION_20260918_MCP_WORDING.md`）把 `delegate` 的 `trusted` 拿掉、模組
    docstring 的「信任閘道／信任生態」改成「究責閘道／究責生態」之後，這一條防回流。
    """
    hits: list[str] = []
    for name, desc in _mcp_tool_descriptions().items():
        hits.extend(_scan(desc, f"mcp tool {name}"))
    assert hits == [], "MCP 工具 description 出現禁語：\n" + "\n".join(hits)


def test_the_word_trusted_alone_is_not_and_must_not_be_in_the_banned_list():
    """**誤殺防線**：`trusted` 單獨一個字**不准**進 `BANNED`。

    本 repo 對 `trusted` 有一個精確且正當的用法——TCB 語意的「不驗、直接假設」：
    `vacant/peerexec.py:186,196` 的 `the executor's own trusted renderer` 與
    `the renderer and the sandbox ... remain a trusted input`，以及 `AGENTS.md:451`
    的 H-8。那是誠實邊界句，是規格的一部分（CLAUDE.md 慣例第三條），機械掃字會把它
    一起殺掉，而殺掉它會讓收據看起來比實際乾淨。

    所以 `delegate` 那一處只能用**逐點釘子**（下一條），不能用整字黑名單。
    """
    assert "trusted" not in BANNED, (
        "把 `trusted` 整字加進 BANNED 會誤殺 peerexec 的 TCB 用法——"
        "那不是行銷詞，是誠實邊界句"
    )
    from vacant import peerexec

    # 負向控制：正當用法還活著。掃字黑名單一旦上場，這一行會先燒起來。
    assert "trusted renderer" in peerexec.SUITE_FIXED_POINT_NOTE
    assert "remain a trusted input" in peerexec.SUITE_FIXED_POINT_NOTE


def test_delegate_docstring_does_not_call_the_ecosystem_trusted():
    """逐點釘子（2026-09-18 裁決）：`delegate` 的 description 不准出現 `trusted`。

    範圍只有這一支 docstring。理由不是禁語表，是**同字反義**：同一個 repo 用
    `trusted` 表示「不驗、直接假設」，而居民生態恰恰是唯一被路由、互審、稽核、
    簽章綁定的東西——寫 `trusted, accountable` 等於讓 docstring 對它自己描述的機制
    說錯話，而且與同一片語裡的 `accountable` 自相矛盾（所以當時是**刪**不是換）。
    """
    desc = _mcp_tool_descriptions()["delegate"]
    assert "trusted" not in desc, f"delegate description 又出現 trusted：\n{desc}"
    # 負向控制：這一條釘的是形容詞，不是整段文案——該留的都還在。
    assert "accountable resident" in desc
    assert "accountable, accountable" not in desc      # 當初若「換」而不是「刪」的樣子
    assert "trust card" in desc                        # `trust_card` 工具名的自然語言寫法


# ══════════════════════════════════════════════════════════════════════════
# 阻擋項三：三個「照文件寫會壞」的地方
# ══════════════════════════════════════════════════════════════════════════
SPEC = ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                    "tests": [{"args": "[1]", "expected": "2"}], "cmp": {"atol": None}})
GOOD_CODE = "def f(x):\n    return x + 1\n"
TASK = {"task_id": "t1", "entry_point": "f",
        "visible_check": {"type": "run_python", "code": "assert f(1) == 2\n", "timeout": 8}}


def _probe(code, _task):
    """真沙箱的確定性替身：認得出的碼就過，其餘（例如一個 worker id）不過。"""
    return ProbeResult(sha256_hex(code) == sha256_hex(GOOD_CODE), None, 1, True, None)


def _execs(n=3):
    return [Executor(f"x{i}", Identity.generate(), Logbook(), _probe) for i in range(n)]


# --- 3a：drafts 的順序 ------------------------------------------------------
def test_reversed_drafts_raise_instead_of_silently_refusing():
    """傳反 ⇒ 當場吵。不吵的話會得到一次與「機制正確拒絕」一模一樣的拒交。"""
    with pytest.raises(DraftOrderError) as e:
        select_by_quorum(TASK, [("w_good", GOOD_CODE)], _execs(), suite=SPEC)
    msg = str(e.value)
    assert "(code, worker_id)" in msg
    assert "啟發式" in msg          # 誠實邊界要在訊息裡，不只在 docstring 裡


def test_correct_draft_order_ships():
    """負向控制：正確順序不准被這道檢查擋住，而且要真的出貨。"""
    out = select_by_quorum(TASK, [(GOOD_CODE, "w_good")], _execs(), suite=SPEC)
    assert isinstance(out, Selection)
    assert out.refused is False and out.shipped_index == 0
    assert out.shipped_worker == "w_good"


def test_empty_drafts_do_not_trip_the_heuristic():
    """負向控制：沒有草稿就沒有順序可言——拒交，但不是 `DraftOrderError`。"""
    out = select_by_quorum(TASK, [], _execs(), suite=SPEC)
    assert out.refused is True and out.shipped_index is None


def test_the_draft_order_check_is_a_heuristic_and_has_false_negatives():
    """**偽陰性要被釘住**，不然 docstring 的誠實邊界就只是一句話。

    這裡的 worker id 自己含換行 ⇒ 兩格都「像碼」⇒ 檢查不吵 ⇒ 使用者拿到的仍然是
    那一次「長得像機制正確運作」的拒交。這正是我們**沒有**修好的那一半：
    不可以因為加了這道檢查就宣稱「順序錯一定會被抓到」。
    """
    weird_worker = "w_good\n"        # 名字裡有換行 ⇒ 看起來像碼
    out = select_by_quorum(TASK, [(weird_worker, GOOD_CODE)], _execs(), suite=SPEC)
    assert out.refused is True and out.shipped_index is None   # 安靜的拒交，沒有例外


# --- 3b：SuiteSpec 的 v: 1 --------------------------------------------------
def test_missing_version_says_what_the_field_is_and_what_to_put_in_it():
    with pytest.raises(SuiteSpecError) as e:
        ss.validate({"dialect": "mbpp", "entry_point": "f",
                     "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                    entry_point="f")
    exc = e.value
    assert exc.code == "bad_version:None"        # wire 面不准漂
    msg = str(exc)
    assert "`v`" in msg and "1" in msg
    assert "'v': 1" in msg                       # 抄得走的最小合法形狀
    assert "整個欄位漏了" in msg


def test_a_correct_version_still_validates():
    """負向控制：`v: 1` 給對了就過——擋門不是對所有 mapping 都吵。"""
    spec = ss.validate({"v": 1, "dialect": "mbpp", "entry_point": "f",
                        "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                       entry_point="f")
    assert spec.entry_point == "f" and spec.n_tests == 1


def test_wrong_version_number_reports_the_value_it_got():
    with pytest.raises(SuiteSpecError) as e:
        ss.validate({"v": 2, "dialect": "mbpp", "entry_point": "f",
                     "tests": [{"args": "[1]", "expected": "2"}], "cmp": {}},
                    entry_point="f")
    assert e.value.code == "bad_version:2"
    assert "整個欄位漏了" not in str(e.value)     # 有給但給錯 ≠ 沒給


# --- 3c：task["entry_point"] ------------------------------------------------
def test_attest_without_task_entry_point_explains_where_the_field_goes():
    """文件說會是 `OpsRunnerUnavailable`，實際是這一個——訊息至少要說得出怎麼修。"""
    ex = Executor("x0", Identity.generate(), Logbook(), _probe)
    with pytest.raises(SuiteSpecError) as e:
        ex.attest({"task_id": "t1"}, GOOD_CODE, suite=SPEC)
    exc = e.value
    assert exc.code == "entry_point_unbound"
    msg = str(exc)
    assert "task['entry_point']" in msg
    assert "'f'" in msg                    # 直接把套件宣告的那個名字唸出來
    assert "屬於題目不屬於套件" in msg
    assert ex.book.entries == []           # 不該存在的證言不准先上鏈


def test_attest_with_task_entry_point_works():
    """負向控制：題目帶了 entry_point 就照跑，而且證言上鏈。"""
    ex = Executor("x0", Identity.generate(), Logbook(), _probe)
    att = ex.attest(TASK, GOOD_CODE, suite=SPEC, ts_ms=1_700_000_000_000)
    assert att.payload["visible_ok"] is True
    assert len(ex.book.entries) == 1


def test_the_wire_facing_refusal_reason_did_not_drift():
    """`.code` 是會上鏈的字串——加了人讀提示之後它必須**逐字不變**。

    收據上的理由若隨文案改動而漂，歷史 run 的 `refusal_reason` 就對不回來了
    （CLAUDE.md 鐵律 6 的同一條紀律）。
    """
    out = select_by_quorum({"task_id": "t1"}, [(GOOD_CODE, "w")], _execs(), suite=SPEC)
    assert out.refused is True
    assert out.refusal_reason == "entry_point_unbound"   # 不是 "entry_point_unbound — …"
    assert out.n_sandbox_runs == 0
