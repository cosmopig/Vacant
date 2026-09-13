"""兩台後端不是同一個推論條件——這一輪補的四件事各自的牙齒。

規格：`DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md` §十一
（2026-09-13 05:50Z，Fable）。一句話：**同一顆 gemma-4 檔案，1003
（LM Studio 0.4.24）跑成 thinking 模式、1004（0.4.17）沒有**；而 1004 在
01:44Z 崩潰後被 JIT 以 TTL 1h 重載，每小時卸載一次，重載要 8–10 秒，
`retry×4` 在幾秒內打完 ⇒ 整格記成 `infra_void`。

本檔對釘的四件事：

1. **退避**：`backoff_s` 預設 5.0 ⇒ 5／10／20／40；重載窗（400 body 帶
   `Model unloaded`）不得變成 `infra_void`。`generate()` 與 `chat()` **同一張表**。
2. **推論模式是實驗條件**：`chat()` 送得出 `reasoning_effort`，送了什麼要落盤；
   `generate()` 被 T12 釘死送不出去，這件事要**被寫出來**而不是被忘記。
3. **探針只記錄不擋**：兩支發射器都送 `reasoning_effort`、都把
   `usage.completion_tokens_details.reasoning_tokens` 記進 `backend_meta.json`，
   `≠0` 只印 WARN。
4. **完成判定不准數 `rows.jsonl` 行數**：作廢列不寫進 `rows.jsonl`
   （`gain_run` 在 void 的格子 `continue`）⇒ 行數 ＝ `processed − infra_void`。
"""
from __future__ import annotations

import io
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain import brain_cline                                 # noqa: E402
from ops.gain.brain_cline import (BACKOFF_SCHEDULE_S,            # noqa: E402
                                  DEFAULT_BACKOFF_S, ClineBrain,
                                  InfraVoid, has_reload_marker, is_retryable)

RELOAD_BODY = json.dumps({"error": {
    "message": "Model unloaded. Please load the model before sending requests.",
    "type": "invalid_request_error"}}).encode()
OK_PAYLOAD = {"model": "gemma-4-12b-it-qat",
              "choices": [{"message": {"content": "def f():\n    return 1\n"},
                           "finish_reason": "stop"}],
              "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                        "total_tokens": 30,
                        "completion_tokens_details": {"reasoning_tokens": 0}}}


class _Resp:
    """urlopen 的回傳（context manager ＋ read()）。"""

    def __init__(self, payload: dict) -> None:
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("http://x/v1/chat/completions", code,
                                  "Bad Request", {}, io.BytesIO(body))


@pytest.fixture()
def fake_backend(monkeypatch):
    """前 `fail_n` 通回 HTTP 400 `Model unloaded`，之後成功。回傳 (sleeps, bodies)。"""
    state = {"fail_n": 3, "calls": 0, "bodies": [], "sleeps": []}

    def _urlopen(req, timeout=None):                       # noqa: ARG001
        state["calls"] += 1
        state["bodies"].append(json.loads(req.data.decode()))
        if state["calls"] <= state["fail_n"]:
            raise _http_error(400, RELOAD_BODY)
        return _Resp(OK_PAYLOAD)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(brain_cline.time, "sleep",
                        lambda s: state["sleeps"].append(s))
    return state


# ══ 一、退避表 ══════════════════════════════════════════════════════════
def test_default_backoff_is_five_seconds_not_two():
    """2／4／8（總和 14 秒）撐不過 8–10 秒的模型重載——那是 r5 void 的成因。"""
    assert DEFAULT_BACKOFF_S == 5.0
    assert BACKOFF_SCHEDULE_S == (5.0, 10.0, 20.0, 40.0)


def test_backoff_delay_matches_the_published_schedule(tmp_path):
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl")
    assert [b.backoff_delay(i) for i in (1, 2, 3, 4)] == list(BACKOFF_SCHEDULE_S)


def test_retry_four_only_uses_the_first_three_steps(tmp_path, fake_backend):
    """誠實邊界：`retries=4` ⇒ 只睡三次（5+10+20＝35 秒），第四格 40 秒用不到。"""
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl", retries=4)
    b.chat([{"role": "user", "content": "hi"}])
    assert fake_backend["sleeps"] == [5.0, 10.0, 20.0]
    assert sum(fake_backend["sleeps"]) == 35.0


# ══ 二、重載窗不得變成 infra_void ═══════════════════════════════════════
@pytest.mark.parametrize("path", ["generate", "chat"])
def test_three_model_unloaded_then_success_is_not_infra_void(
        tmp_path, fake_backend, path):
    """假後端前 3 次回 400 `Model unloaded`、第 4 次成功 ⇒ **不得** infra_void。

    `generate()` 與 `chat()` 兩條路都要過：R529 的 OFF／CONFORM 走前者，
    H 臂走後者，而 r5 的 void 兩邊都發生過。
    """
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl", retries=4)
    if path == "generate":
        out = b.generate("寫個函式")
    else:
        out, _info = b.chat([{"role": "user", "content": "寫個函式"}])
    assert "def f" in out
    assert fake_backend["calls"] == 4
    # 三次失敗 ＋ 一次成功都要落盤（鐵律 3）
    recs = [json.loads(x) for x in
            (tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["ok"] for r in recs] == [False, False, False, True]
    assert all("Model unloaded" in r["error"] for r in recs[:3])
    assert fake_backend["sleeps"] == [5.0, 10.0, 20.0]


def test_four_reload_failures_still_become_infra_void(tmp_path, fake_backend):
    """撐不過去就是撐不過去——退避變長**不會**把 void 變不見，那才是誠實的。"""
    fake_backend["fail_n"] = 99
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl", retries=4)
    with pytest.raises(InfraVoid):
        b.chat([{"role": "user", "content": "hi"}])
    assert fake_backend["calls"] == 4


def test_chat_logs_why_it_retried_and_how_long_it_waited(tmp_path, fake_backend):
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl", retries=4)
    b.chat([{"role": "user", "content": "hi"}])
    recs = [json.loads(x) for x in
            (tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()]
    fails = [r for r in recs if not r["ok"]]
    assert [r["retryable"] for r in fails] == [True, True, True]
    assert [r["reload_window"] for r in fails] == [True, True, True]
    assert [r["backoff_s"] for r in fails] == [5.0, 10.0, 20.0]


# ══ 三、可重試的判準是一個具名的純函式 ═════════════════════════════════
@pytest.mark.parametrize("text,want", [
    ("HTTP Error 400 | body=Model unloaded. Please load", True),
    ("HTTP Error 400 | body=Failed to load model 'gemma-4'", True),
    ("HTTP Error 500 | body=The model has crashed without additional "
     "information", True),
    ("HTTP Error 400 | body=invalid 'messages[0].role'", False),
])
def test_reload_markers_are_matched_case_insensitively(text, want):
    assert has_reload_marker(text) is want
    assert has_reload_marker(text.upper()) is want


@pytest.mark.parametrize("code,body,want", [
    (400, "Model unloaded", True),        # 重載窗
    (400, "bad request", True),           # round356：400 一律重試（既有裁決）
    (404, "model not found", True),       # round296：中轉換節點
    (500, "internal", True),              # 5xx：伺服器自己說它壞了
    (503, "overloaded", True),
    (401, "unauthorized", False),         # 認證／額度：不重試
    (402, "quota", False),
    (403, "forbidden", False),
    (403, "Model unloaded behind a proxy", True),   # 代理層改了碼，事實沒變
])
def test_is_retryable_matches_the_frozen_policy(code, body, want):
    assert is_retryable(_http_error(code, body.encode()), body) is want


def test_non_http_errors_stay_retryable():
    """連不上／逾時／RelayError／EmptyResponse 的既有語意一個字沒改。"""
    for exc in (TimeoutError("timed out"),
                brain_cline.RelayError("terminated"),
                brain_cline.EmptyResponse("content 為空"),
                urllib.error.URLError("connection refused")):
        assert is_retryable(exc, str(exc)) is True


def test_auth_failure_still_breaks_immediately(tmp_path, monkeypatch):
    calls = {"n": 0}

    def _urlopen(req, timeout=None):                       # noqa: ARG001
        calls["n"] += 1
        raise _http_error(401, b"unauthorized")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(brain_cline.time, "sleep", lambda s: None)
    b = ClineBrain("t", "sys", key="k", log_path=tmp_path / "c.jsonl", retries=4)
    with pytest.raises(InfraVoid):
        b.chat([{"role": "user", "content": "hi"}])
    assert calls["n"] == 1, "401 不重試（語意不是暫時性路由問題）"


# ══ 四、reasoning_effort：送什麼、不送什麼、落盤什麼 ═══════════════════
def test_chat_sends_reasoning_effort_when_asked(tmp_path, fake_backend):
    fake_backend["fail_n"] = 0
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl",
                   reasoning_effort="none")
    b.chat([{"role": "user", "content": "hi"}])
    assert fake_backend["bodies"][0]["reasoning_effort"] == "none"
    rec = json.loads((tmp_path / "c.jsonl").read_text(encoding="utf-8").strip())
    assert rec["reasoning_effort"] == "none"


@pytest.mark.parametrize("effort", [None, "default"])
def test_default_and_none_omit_the_field_entirely(tmp_path, fake_backend, effort):
    """`default` ＝ 不送這個欄位（＝2026-09-13 之前的行為），不是送字串 default。"""
    fake_backend["fail_n"] = 0
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl",
                   reasoning_effort=effort)
    b.chat([{"role": "user", "content": "hi"}])
    assert "reasoning_effort" not in fake_backend["bodies"][0]
    rec = json.loads((tmp_path / "c.jsonl").read_text(encoding="utf-8").strip())
    assert rec["reasoning_effort"] is None


def test_per_call_override_beats_the_instance_default(tmp_path, fake_backend):
    fake_backend["fail_n"] = 0
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl",
                   reasoning_effort="none")
    b.chat([{"role": "user", "content": "hi"}], reasoning_effort="high")
    assert fake_backend["bodies"][0]["reasoning_effort"] == "high"


@pytest.mark.parametrize("bad", ["off", "NONE", "true", ""])
def test_an_unknown_effort_is_an_error_not_a_silent_passthrough(tmp_path, bad):
    """打錯字不該變成「送了一個後端看不懂的值然後大家以為關掉了」。"""
    with pytest.raises(ValueError):
        ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl",
                   reasoning_effort=bad)


def test_both_paths_send_the_flag_from_one_source(tmp_path, fake_backend):
    """round529-3（Fable 2026-09-13 授權改 T12）：`generate()` **也**送這個欄位。

    為什麼非改不可：OFF／OFF5／CONFORM／EQ5／ON 五臂全部走 `generate()`，
    只在 `chat()` 送＝只對齊 H 臂，反而在臂之間造出一個 OFF 沒有的推論條件差
    ——那比原本「兩台後端不同」更糟。兩條路的來源必須是**同一個**
    （`self.reasoning_effort`），否則「這個 run 跑在什麼模式」會有兩個答案。
    """
    fake_backend["fail_n"] = 0
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl",
                   reasoning_effort="none")
    b.generate("hi")
    b.chat([{"role": "user", "content": "hi"}])
    assert [x.get("reasoning_effort") for x in fake_backend["bodies"]] == \
        ["none", "none"], "兩條路都要送，而且送的是同一個值"
    recs = [json.loads(x) for x in
            (tmp_path / "c.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["reasoning_effort"] for r in recs] == ["none", "none"], \
        "送了什麼要落盤（鐵律 3）——否則事後查不出這一列跑在哪一種推論條件"


def test_generate_omits_the_field_by_default_so_old_behaviour_is_byte_identical(
        tmp_path, fake_backend):
    """授權的行為差異只有「請求多一個欄位」；不送的時候 body 必須逐位元同舊版。"""
    fake_backend["fail_n"] = 0
    b = ClineBrain("t", "sys", key="", log_path=tmp_path / "c.jsonl")
    b.generate("hi")
    assert "reasoning_effort" not in fake_backend["bodies"][0]
    assert set(fake_backend["bodies"][0]) == {
        "model", "messages", "temperature", "stream"}


def test_the_t12_pin_moved_with_an_explicit_authorisation_note():
    """釘值可以改，但**必須留下誰授權的、為什麼、行為差異是什麼**（round460e 先例）。"""
    src = (ROOT / "tests" / "test_gain_harness_arms.py").read_text(encoding="utf-8")
    for needle in ("round529-3", "Fable 授權", "reasoning_effort",
                   "行為差異＝請求多一個欄位、非 thinking 後端無變化",
                   # 舊值要留著，否則「改過幾次、從哪裡改到哪裡」查不回來
                   "b523c15f43a63476af16395280f7e4763fc6dbf03e30d90f354cc269d469fc18",
                   "DECISION_20260912_R529_FABLE_AUDIT_CROSS_BANK.md"):
        assert needle in src, needle


# ══ 五、gain_run 的旗標與落盤 ═══════════════════════════════════════════
def _gain_run_src() -> str:
    return (ROOT / "ops" / "gain" / "gain_run.py").read_text(encoding="utf-8")


def test_gain_run_exposes_the_flag_with_none_as_the_default():
    src = _gain_run_src()
    assert '"--reasoning-effort", default="none"' in src
    assert "reasoning_effort=args.reasoning_effort" in src


def test_gain_run_backoff_default_comes_from_brain_cline():
    """兩邊各寫一個 5.0 會漂；讓 CLI 的預設直接指向那個常數。"""
    assert "default=brain_cline.DEFAULT_BACKOFF_S" in _gain_run_src()


def test_the_requested_mode_lands_in_summary_and_rows():
    src = _gain_run_src()
    assert '"reasoning_effort": args.reasoning_effort,' in src
    # request_policy 裡那一格＝跨 run 配對的牙齒（pool_precheck C4 比的就是它）
    assert '"reasoning_effort_applies_to": "generate() and chat() (all arms)"' in src


# ══ 六、發射器探針：記錄，不擋 ═════════════════════════════════════════
LAUNCHERS = ("ops/gain/launch_harness_rep_block.sh",
             "ops/gain/launch_r529_block.sh")


@pytest.mark.parametrize("path", LAUNCHERS)
def test_launcher_is_valid_bash(path):
    r = subprocess.run(["bash", "-n", str(ROOT / path)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("path", LAUNCHERS)
def test_probe_sends_the_flag_and_records_what_came_back(path):
    sh = (ROOT / path).read_text(encoding="utf-8")
    assert 'REASONING_EFFORT="${REASONING_EFFORT:-none}"' in sh
    assert 'RE_FIELD=",\\"reasoning_effort\\":\\"$REASONING_EFFORT\\""' in sh
    assert "$RE_FIELD}\"" in sh, "探針的 body 沒有帶上 reasoning_effort"
    assert "reasoning_tokens" in sh
    assert "reasoning_tokens=$rt" in sh, "launch.log 要印得出量到什麼"
    assert '"probe_reasoning_tokens": rt' in sh


@pytest.mark.parametrize("path", LAUNCHERS)
def test_the_reasoning_check_warns_but_never_aborts(path):
    """**不擋**是預註冊的決定，不是疏忽：擋不擋要由預註冊說，不是由發射器說。"""
    sh = (ROOT / path).read_text(encoding="utf-8")
    head, _, tail = sh.partition("reasoning_tokens=$rt ≠ 0")
    assert tail, "沒有那一行 WARN"
    warn_line = tail.split("\n", 1)[0]
    assert "不擋" in warn_line
    # 探針的通過判準仍然只有那三項（HTTP 200／content 非空／三次全過）
    assert '[ "$ok" -eq 3 ]' in sh
    for banned in ("abort_probe_reasoning", "abort_reasoning",
                   "abort_thinking_mode"):
        assert banned not in sh, banned


@pytest.mark.parametrize("path", LAUNCHERS)
def test_probe_reasoning_is_null_not_zero_when_unreported(path):
    """「沒回報 reasoning」與「reasoning 是 0」是兩件事，混掉＝量不到當通過。"""
    sh = (ROOT / path).read_text(encoding="utf-8")
    assert 'rt = None if probe_rt in ("", "-") else int(probe_rt)' in sh


@pytest.mark.parametrize("path", LAUNCHERS)
def test_lmstudio_version_comes_from_a_manual_table_not_a_probe(path):
    """Fable 2026-09-13 裁決第 3 點：`/api/v0/models` 沒有版本欄位（實測過）。

    ⇒ 不再打那一通（永遠回 null 的探針只是多一個失敗面），改端點→版本的
    手動對照表，並把 `source` 逐字落盤：那是**人回報的宣稱**不是量測。
    沒登記的端點 ⇒ 兩格都 null，**不猜**。
    """
    sh = (ROOT / path).read_text(encoding="utf-8")
    # 註解裡**要**寫「為什麼不打 /api/v0」；不准真的還在打它。
    assert not [ln for ln in sh.splitlines()
                if "curl" in ln and "/api/v0" in ln], "版本探針該拿掉了"
    assert 'LMS_VERSION_SOURCE="manual 2026-09-11 lms version"' in sh
    assert '*100.119.113.56*) LMS_VER="0.4.24.0"' in sh
    assert '*100.86.226.21*)  LMS_VER="0.4.17.0"' in sh
    assert 'LMS_VER="-"; LMS_VERSION_SOURCE="-"' in sh, "沒登記的端點要落成 null"
    assert '"lmstudio_version_source"' in sh


def test_the_manual_table_agrees_with_the_analyzer_fallback():
    """兩張表寫在兩個檔案裡 ⇒ 會漂。這條測試是它們之間唯一的接縫。"""
    from ops.gain.analyze_r529 import (LMSTUDIO_VERSION_FALLBACK,
                                       LMSTUDIO_VERSION_SOURCE)
    sh = (ROOT / "ops/gain/launch_r529_block.sh").read_text(encoding="utf-8")
    assert LMSTUDIO_VERSION_FALLBACK == {"1003": "0.4.24.0", "1004": "0.4.17.0"}
    assert LMSTUDIO_VERSION_SOURCE == "manual 2026-09-11 lms version"
    for ver in LMSTUDIO_VERSION_FALLBACK.values():
        assert f'LMS_VER="{ver}"' in sh, ver
    assert f'LMS_VERSION_SOURCE="{LMSTUDIO_VERSION_SOURCE}"' in sh


def test_per_backend_rows_say_out_loud_that_they_are_not_a_test():
    """Fable 2026-09-13 裁決第 2 點：b/c 保留，但欄名與旗標要擋住誤讀。

    被複製進報告的是**列**不是整個區塊 ⇒ note 留在區塊層級會在複製時掉，
    所以每一列（含每一個配對）自己帶 `not_a_test`。
    """
    import json as _json
    a = _json.loads((ROOT / "ops/gain/replay/r529/r529_analyze.json")
                    .read_text(encoding="utf-8"))
    for s_, hosts in a["per_backend"].items():
        for h, row in hosts.items():
            assert row["not_a_test"] is True, (s_, h)
            for k, pr in row["paired"].items():
                assert pr["not_a_test"] is True, (s_, h, k)
                assert pr["b_minus_c_descriptive"] == pr["b"] - pr["c"], (s_, h, k)
                assert "p" not in pr and "p_mcnemar_exact" not in pr, \
                    "逐後端不准出現 p 值——它不是檢定"


def test_the_r460r_launcher_finally_writes_backend_meta():
    """R460R 以前只落 `.endpoint`／`.backend.json` ⇒ 事後查不到版本與推論模式。"""
    sh = (ROOT / "ops/gain/launch_harness_rep_block.sh").read_text(encoding="utf-8")
    assert '.backend_meta.json' in sh
    assert '"slot_host": host' in sh


@pytest.mark.parametrize("path", LAUNCHERS)
def test_launcher_passes_the_flag_through_to_the_runner(path):
    sh = (ROOT / path).read_text(encoding="utf-8")
    assert '--reasoning-effort "$REASONING_EFFORT"' in sh


# ══ 七、完成判定不准數 rows.jsonl 的行數 ═══════════════════════════════
def _summary(processed: int, void: int, terminal: bool = True) -> dict:
    return {"run_terminal": terminal,
            "arms": {"OFF": {"processed": processed, "infra_void": void},
                     "CONFORM": {"processed": processed, "infra_void": 0},
                     "HMIX": {"processed": processed, "infra_void": 0}}}


def test_a_block_with_voids_and_no_rows_file_is_still_DONE():
    """作廢列不寫進 `rows.jsonl` ⇒ 磁碟上根本沒有那一列，判定不准依賴它。"""
    from ops.gain.schedule_harness_reps import classify_summary
    state, why = classify_summary(_summary(20, 2))
    assert state == "DONE", why


def test_void_rate_uses_processed_as_the_denominator_not_the_row_count():
    """行數 ＝ processed − void ⇒ 拿行數當分母會把 void 率系統性算小。

    20 題 2 void：正確 2/20＝10%；若誤用行數 2/18＝11.1%。
    """
    from ops.gain.schedule_harness_reps import void_rates
    assert void_rates(_summary(20, 2))["OFF"] == pytest.approx(0.10)
    assert void_rates(_summary(20, 5))["OFF"] == pytest.approx(0.25)


@pytest.mark.parametrize("name", ["schedule_harness_reps.py", "schedule_queue.py"])
def test_no_scheduler_path_ever_opens_rows_jsonl(name):
    """排程器裡不准出現 `"rows.jsonl"` 這個**字串字面值**——那是檔名。

    散文裡（docstring／註解）寫 `rows.jsonl` 是**要求**的（規則要寫下來），
    所以判準不是「文字有沒有出現」而是「有沒有被當成路徑用」：
    字面值只會出現在 `dir / "rows.jsonl"`／`open("rows.jsonl")` 這種地方。
    """
    src = (ROOT / "ops" / "gain" / name).read_text(encoding="utf-8")
    assert '"rows.jsonl"' not in src, name
    assert "'rows.jsonl'" not in src, name


@pytest.mark.parametrize("name", ["schedule_harness_reps.py", "schedule_queue.py"])
def test_the_rule_is_written_down_where_the_next_person_will_look(name):
    src = (ROOT / "ops" / "gain" / name).read_text(encoding="utf-8")
    assert "作廢列不寫進" in src
    assert "infra_void" in src and "processed" in src


# ══ 八、兩支 analyzer 的新格子 ═════════════════════════════════════════
def test_r529_analyzer_selftest_and_mutations():
    for flag in ("--selftest", "--mutation-check"):
        r = subprocess.run([sys.executable, "ops/gain/analyze_r529.py", flag],
                           capture_output=True, text=True, cwd=str(ROOT))
        assert r.returncode == 0, r.stdout + r.stderr


def test_r529_per_backend_is_reported_and_is_not_an_arbiter():
    from ops.gain.analyze_r529 import (PER_BACKEND_NOTE, analyze,
                                       per_backend_stats)
    import inspect
    assert "不進任何仲裁" in PER_BACKEND_NOTE
    # `decide`／`primary`／`refutation`／`aggregate` 都不准讀 per_backend
    from ops.gain import analyze_r529 as A
    for fn in (A.decide, A.primary, A.refutation, A.aggregate):
        assert "per_backend" not in inspect.getsource(fn), fn.__name__
    assert "per_backend" in inspect.getsource(analyze)
    assert callable(per_backend_stats)


def test_r529_backend_lookup_falls_back_without_inventing_a_host(tmp_path):
    from ops.gain.analyze_r529 import block_backend
    (tmp_path / "runs").mkdir()
    be = block_backend("no_such_block", tmp_path)
    assert be["host"] == "unknown"
    assert be["lmstudio_version"] is None, "查不到版本不准用對照表亂填"


def test_r460r_inference_mode_sits_next_to_co_tenancy():
    from ops.gain.analyze_r460r import INFERENCE_MODE_NOTE, inference_mode
    import inspect

    from ops.gain import analyze_r460r as R
    assert "描述性" in INFERENCE_MODE_NOTE
    src = inspect.getsource(R.run)
    assert '"inference_mode": inference_mode(all_blocks)' in src
    assert '"co_tenancy"' in src
    # 彙總與逐次裁決都不准讀它
    assert "inference_mode" not in inspect.getsource(R.aggregate)
    assert "inference_mode" not in inspect.getsource(R.analyze_rep)


def test_r460r_analyzer_selftest():
    r = subprocess.run([sys.executable, "ops/gain/analyze_r460r.py", "--selftest"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stdout + r.stderr
