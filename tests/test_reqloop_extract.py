"""G2.5 vq-el4.1：extract.py 的 quote 逐字檢查＋verifier 白名單＋unverified。

全部用假 client（FakeClient），不呼叫任何真實模型。
驗收（bd vq-el4.1）：
- 改寫過的 quote 被丟棄；
- 未知 verifier 變 unverified（且檢查時為 UNKNOWN，不當通過）。
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from vacant_network.reqloop import checks
from vacant_network.reqloop.extract import (
    ExtractError,
    ExtractParseError,
    GlmClient,
    build_requirement_set,
    build_task_prompt,
    csv_preview,
    default_prompt,
    extract_requirements,
    main,
    parse_model_output,
    quote_is_verbatim,
    run_task,
)
from vacant_network.reqloop.requirements import RequirementSet

USER_TEXT = (
    "Task: Calculate the mean of the column 'No. of cases' in data/estimated_numbers.csv.\n"
    "Convert the data type of 'No. of cases' from Object (string) to Int64 before calculating.\n"
    "Ignore records where the value is Null or empty.\n"
    "Answer format: @mean_cases[mean_value] where mean_value is a positive integer."
)


class FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class ExplodingClient:
    def complete(self, prompt: str) -> str:
        raise RuntimeError("endpoint down")


def _valid_items() -> list[dict]:
    return [
        {
            "id": "req_answer_kv",
            "quote": "Answer format: @mean_cases[mean_value] where mean_value is a positive integer.",
            "deliverable": "answer.txt",
            "verifier": "answer_kv",
            "params": {"keys": [{"key": "mean_cases", "type": "integer"}]},
        },
        {
            "id": "req_mean_recomputed",
            "quote": "Calculate the mean of the column 'No. of cases' in data/estimated_numbers.csv.",
            "deliverable": "answer.txt",
            "verifier": "kv_recomputed",
            "params": {
                "key": "mean_cases",
                "data_file": "data/estimated_numbers.csv",
                "recompute": {"type": "mean_int_col", "col": "No. of cases"},
            },
        },
    ]


# ---------------------------------------------------------------- quote 逐字

def test_quote_verbatim_strict_substring_kept():
    assert quote_is_verbatim(
        "Ignore records where the value is Null or empty.", USER_TEXT
    ) is True


def test_quote_paraphrase_rejected():
    assert quote_is_verbatim("Please average the cases column.", USER_TEXT) is False
    assert quote_is_verbatim("Calculate the median of the column 'No. of cases'.", USER_TEXT) is False


def test_quote_whitespace_normalized_kept():
    # 模型把換行正規化成空格——內容逐字即保留（防的是改寫，不是行尾空白）
    q = (
        "Convert the data type of 'No. of cases' from Object (string) to Int64"
        " before calculating."
    )
    assert quote_is_verbatim(q, USER_TEXT) is True


def test_quote_empty_rejected():
    assert quote_is_verbatim("", USER_TEXT) is False
    assert quote_is_verbatim("   ", USER_TEXT) is False


# ---------------------------------------------------------------- 白名單

def test_supported_verifiers_pin():
    # 釘住白名單內容：checks.py 增刪 verifier 時本測試會先紅（防漂移）
    assert checks.SUPPORTED_VERIFIERS == {
        "csv_structure", "table_structure", "monthly_sales_metrics",
        "monthly_top_products", "summary_metrics_consistency", "rowset_filter",
        "group_aggregate", "summary_numbers", "answer_kv", "kv_recomputed",
        "plain_recomputed", "tag_format",
    }


def test_recompute_type_sets_match_dispatch():
    # 守衛：KV/PLAIN_RECOMPUTE_TYPES 必須與 checks.py 的 rtype 分派鏈一致
    src = pathlib.Path(checks.__file__).read_text(encoding="utf-8")

    def _branches(func_name: str) -> set[str]:
        m = re.search(rf"^def {func_name}\(", src, re.MULTILINE)
        assert m, func_name
        rest = src[m.end():]
        m2 = re.search(r"^def ", rest, re.MULTILINE)
        body = rest[: m2.start()] if m2 else rest
        return set(re.findall(r'rtype == "([A-Za-z_0-9]+)"', body))

    assert _branches("check_kv_recomputed") == set(checks.KV_RECOMPUTE_TYPES)
    assert _branches("check_plain_recomputed") == set(checks.PLAIN_RECOMPUTE_TYPES)


# ---------------------------------------------------------------- 核心驗證

def test_happy_path_keeps_valid_items():
    req, report = build_requirement_set("t1", _valid_items(), USER_TEXT)
    assert [i.id for i in req.items] == ["req_answer_kv", "req_mean_recomputed"]
    assert all(not i.unverified for i in req.items)
    assert report.discarded == ()
    assert report.unverified == ()
    assert report.kept == ("req_answer_kv", "req_mean_recomputed")
    assert isinstance(req, RequirementSet)


def test_paraphrased_quote_discarded():
    items = _valid_items()
    items[0]["quote"] = "The answer must be a positive integer in answer.txt."
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert [i.id for i in req.items] == ["req_mean_recomputed"]
    assert len(report.discarded) == 1
    assert report.discarded[0].id == "req_answer_kv"
    assert report.discarded[0].reason == "quote_not_verbatim"


def test_unknown_verifier_becomes_unverified():
    items = _valid_items()
    items[1]["verifier"] = "llm_judge"
    req, report = build_requirement_set("t1", items, USER_TEXT)
    item = req.items[1]
    assert item.unverified is True
    assert item.verifier == "llm_judge"
    assert report.unverified[0].id == "req_mean_recomputed"
    assert report.unverified[0].reason == "unknown_verifier:llm_judge"


def test_unverified_item_is_unknown_at_check_time(tmp_path):
    # unverified ≠ 通過：檢查時一律 UNKNOWN（fail-closed 整合斷言）
    items = _valid_items()
    items[1]["verifier"] = "llm_judge"
    req, _ = build_requirement_set("t1", items, USER_TEXT)
    (tmp_path / "answer.txt").write_text("@mean_cases[2081990]\n", encoding="utf-8")
    results = checks.run_requirement_checks(tmp_path, req, tmp_path)
    by_id = {r.claim_id: r for r in results}
    assert by_id["req_mean_recomputed"].status == "UNKNOWN"
    assert by_id["req_mean_recomputed"].evidence.get("unverified") is True


def test_bad_recompute_type_unverified():
    items = _valid_items()
    items[1]["params"]["recompute"] = {"type": "magic_rule"}
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert req.items[1].unverified is True
    assert report.unverified[0].reason == "unsupported_recompute_type:magic_rule"


def test_plain_recomputed_kv_type_mismatch_unverified():
    items = _valid_items()
    items[1]["verifier"] = "plain_recomputed"
    items[1]["params"] = {
        "data_file": "data/estimated_numbers.csv",
        "recompute": {"type": "mean_int_col", "col": "No. of cases"},
    }
    req, report = build_requirement_set("t1", items, USER_TEXT)
    # mean_int_col 是 kv 系型別，plain 不支援 → unverified
    assert req.items[1].unverified is True
    assert report.unverified[0].reason == "unsupported_recompute_type:mean_int_col"


def test_missing_required_param_unverified():
    items = _valid_items()
    del items[1]["params"]["data_file"]
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert req.items[1].unverified is True
    assert report.unverified[0].reason == "missing_param:data_file"


def test_empty_required_param_unverified():
    items = _valid_items()
    items[0]["params"] = {"keys": []}
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert req.items[0].unverified is True
    assert report.unverified[0].reason == "empty_param:keys"


def test_model_unverified_flag_respected():
    items = _valid_items()
    items[0]["unverified"] = True
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert req.items[0].unverified is True
    assert any(u.id == "req_answer_kv" for u in report.unverified)


def test_non_object_item_discarded():
    items = ["hello", 42, _valid_items()[0]]
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert [i.id for i in req.items] == ["req_answer_kv"]
    reasons = [d.reason for d in report.discarded]
    assert reasons == ["not_an_object", "not_an_object"]


def test_missing_deliverable_discarded():
    items = _valid_items()
    del items[0]["deliverable"]
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert [i.id for i in req.items] == ["req_mean_recomputed"]
    assert report.discarded[0].reason == "deliverable_missing"


def test_invalid_kind_discarded():
    items = _valid_items()
    items[0]["kind"] = "hallucination"
    req, report = build_requirement_set("t1", items, USER_TEXT)
    assert [i.id for i in req.items] == ["req_mean_recomputed"]
    assert report.discarded[0].reason == "invalid_kind:'hallucination'"


def test_extracted_items_never_hidden():
    items = _valid_items()
    items[0]["hidden"] = True
    req, _ = build_requirement_set("t1", items, USER_TEXT)
    assert all(not i.hidden for i in req.items)


def test_non_list_output_is_parse_error_not_pass():
    req, report = build_requirement_set("t1", {"items": "oops"}, USER_TEXT)
    assert req.items == []
    assert report.parse_error is not None


def test_report_to_dict_serializable():
    items = _valid_items()
    items[0]["quote"] = "paraphrase not in text"
    items[1]["verifier"] = "nope"
    req, report = build_requirement_set("t1", items, USER_TEXT)
    d = report.to_dict()
    roundtrip = json.loads(json.dumps(d, ensure_ascii=False))
    assert roundtrip == d
    assert d["discarded"][0]["reason"] == "quote_not_verbatim"
    assert d["unverified"][0]["reason"] == "unknown_verifier:nope"


# ---------------------------------------------------------------- 解析層

def test_parse_bare_json_array():
    assert parse_model_output(json.dumps(_valid_items())) == _valid_items()


def test_parse_fenced_json():
    raw = "好的，以下是需求條目：\n```json\n" + json.dumps(_valid_items()) + "\n```\n（以上）"
    assert parse_model_output(raw) == _valid_items()


def test_parse_items_object():
    raw = json.dumps({"items": _valid_items()})
    assert parse_model_output(raw) == _valid_items()


def test_parse_single_object():
    raw = json.dumps(_valid_items()[0])
    assert parse_model_output(raw) == [_valid_items()[0]]


def test_parse_garbage_raises():
    with pytest.raises(ExtractParseError):
        parse_model_output("我無法完成這個任務，抱歉。")


def test_parse_empty_raises():
    with pytest.raises(ExtractParseError):
        parse_model_output("   ")


# ---------------------------------------------------------------- 編排層

def test_extract_requirements_end_to_end_fake_client():
    client = FakeClient(json.dumps(_valid_items()))
    req, report = extract_requirements(user_text=USER_TEXT, client=client, task_id="dab_055")
    assert [i.id for i in req.items] == ["req_answer_kv", "req_mean_recomputed"]
    assert report.parse_error is None
    assert report.extract_error is None
    assert len(client.prompts) == 1
    assert USER_TEXT in client.prompts[0]


def test_extract_unparseable_output_empty_set_fail_closed():
    client = FakeClient("抱歉，我沒有找到明確的需求。")
    req, report = extract_requirements(user_text=USER_TEXT, client=client)
    assert req.items == []
    assert report.parse_error is not None
    assert report.extract_error is None


def test_extract_client_exception_empty_set_fail_closed():
    req, report = extract_requirements(user_text=USER_TEXT, client=ExplodingClient())
    assert req.items == []
    assert report.extract_error is not None
    assert "RuntimeError" in report.extract_error


def test_extract_custom_build_prompt_injected():
    client = FakeClient(json.dumps(_valid_items()))
    custom = lambda text: "CUSTOM-PROMPT " + text  # noqa: E731
    req, report = extract_requirements(
        user_text=USER_TEXT, client=client, build_prompt=custom
    )
    assert len(req.items) == 2
    assert client.prompts[0].startswith("CUSTOM-PROMPT")


def test_default_prompt_lists_whitelist_and_no_secrets():
    p = default_prompt(USER_TEXT)
    assert "kv_recomputed" in p and "answer_kv" in p
    assert USER_TEXT in p
    # 提示裡不准出現 hidden/scorer 內容或任何金鑰樣式字串
    low = p.lower()
    assert "scorer" not in low and "hidden" not in low
    assert "sk-" not in p and "key=" not in p.lower()


# ------------------------------------------------ vq-el4.2：glm 後端＋任務 CLI（全假 glm，不呼叫模型）

def _fake_glm(tmp_path, *, rc=0, stderr="", response=""):
    """寫一個假 glm shell 指令：記錄參數、拷貝 prompt 檔、回傳固定回應。"""
    script = tmp_path / "fake_glm"
    log = tmp_path / "glm_invocation.txt"
    copy = tmp_path / "prompt_copy.txt"
    lines = [
        "#!/bin/sh",
        f'printf "%s\\n" "$@" > "{log}"',
        f'cp "$6" "{copy}" 2>/dev/null || true',
    ]
    if stderr:
        lines.append(f'printf "%s" "{stderr}" >&2')
    if rc == 0:
        lines.append(f"printf '%s\\n' {json.dumps(response)}")
    else:
        lines.append(f"exit {rc}")
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return script, log, copy


def test_glm_client_passes_model_purpose_prompt_file(tmp_path):
    script, log, copy = _fake_glm(tmp_path, response="[{'id': 'r1'}]")
    client = GlmClient(model="glm53", purpose="orders_monthly 擷取需求", glm_bin=str(script))
    out = client.complete("PROMPT-TEXT-123")
    assert "r1" in out
    args = log.read_text(encoding="utf-8").splitlines()
    assert args[:3] == ["--model", "glm53", "--purpose"]
    assert args[3] == "orders_monthly 擷取需求"
    assert args[4] == "--prompt-file"
    assert copy.read_text(encoding="utf-8") == "PROMPT-TEXT-123"  # prompt 真的經 --prompt-file 交給 glm


def test_glm_client_nonzero_exit_is_fail_closed_no_retry(tmp_path):
    script, _, _ = _fake_glm(tmp_path, rc=3, stderr="今日預算用完")
    client = GlmClient(glm_bin=str(script))
    attempts = 0
    try:
        for _ in range(3):
            client.complete("x")  # 呼叫端不得重試；這裡只驗单次即失敗
    except ExtractError as e:
        attempts = 1
        assert "rc=3" in str(e)
    assert attempts == 1


def test_csv_preview_header_plus_five_rows():
    csv = "\n".join(f"r{i}" for i in range(20)) + "\n"
    assert csv_preview(csv).splitlines() == [f"r{i}" for i in range(6)]


def test_build_task_prompt_whitelist_data_and_user_text_only():
    csv = "a,b\n1,2\n3,4\n5,6\n7,8\n9,10\n11,12\n13,14\n"
    p = build_task_prompt("USER-REQ-TEXT", data_file="orders.csv", data_preview=csv_preview(csv))
    for v in sorted(checks.SUPPORTED_VERIFIERS):
        assert v in p
    assert "orders.csv" in p and "USER-REQ-TEXT" in p
    assert "a,b" in p and "9,10" in p  # 欄位名＋第 5 列資料
    assert "11,12" not in p  # 超過前 5 列的資料不准進 prompt


ORDER_TEXT = (
    "排除狀態為 CANCELLED 的取消訂單。\n"
    "欄位需包含：month、orders_count、net_sales。\n"
    "內文中需明確載明「兩月合計淨銷售總額」（精確數值）。\n"
    "簡述各月銷售成長觀察。\n"
)


def test_run_task_counts_discarded_unverified_and_hands_off(tmp_path):
    t_dir = tmp_path / "orders_monthly"
    t_dir.mkdir()
    (t_dir / "request.md").write_text(ORDER_TEXT, encoding="utf-8")
    (t_dir / "orders.csv").write_text(
        "order_id,status\nA,COMPLETED\nB,CANCELLED\nC,COMPLETED\nD,COMPLETED\nE,COMPLETED\nF,COMPLETED\n",
        encoding="utf-8",
    )
    (t_dir / "requirements.json").write_text('{"task_id": "HANDWRITTEN-SECRET"}', encoding="utf-8")
    items = [
        {"id": "r1", "quote": "排除狀態為 CANCELLED 的取消訂單。", "deliverable": "monthly_sales.csv",
         "verifier": "rowset_filter", "params": {"values": ["COMPLETED"], "identity": "order_id"}},
        {"id": "r2", "quote": "欄位需包含：month、orders_count、net_sales。", "deliverable": "monthly_sales.csv",
         "verifier": "csv_structure", "params": {"required_columns": ["month", "orders_count", "net_sales"]}},
        {"id": "r3", "quote": "內文中需明確載明「兩月合計淨銷售總額」（精確數值）。", "deliverable": "summary.md",
         "verifier": "summary_metrics_consistency", "params": {"metric_keywords": ["合計淨銷售總額"]}},
        {"id": "bad", "quote": "這句是改寫的、原文沒這句話。", "deliverable": "summary.md",
         "verifier": "summary_numbers", "params": {"numbers": [1]}},
        {"id": "unv", "quote": "簡述各月銷售成長觀察。", "deliverable": "summary.md",
         "verifier": "vibes_check", "params": {}},
    ]
    client = FakeClient(json.dumps(items, ensure_ascii=False))
    out = tmp_path / "out.json"
    req, report = run_task(t_dir / "request.md", model="glm53", client=client, out_path=out)
    assert [i.id for i in req.items] == ["r1", "r2", "r3", "unv"]  # 改寫 quote 被丟棄；未知 verifier 保留但 unverified
    assert [d.reason for d in report.discarded] == ["quote_not_verbatim"]
    assert [(u.id, u.reason) for u in report.unverified] == [("unv", "unknown_verifier:vibes_check")]
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["task_id"] == "orders_monthly" and doc["model"] == "glm53"
    assert len(doc["items"]) == 4 and doc["report"]["discarded"][0]["reason"] == "quote_not_verbatim"
    prompt = client.prompts[0]
    assert "HANDWRITTEN-SECRET" not in prompt  # 手寫 requirements.json 不准進 prompt
    assert "order_id,status" in prompt and "B,CANCELLED" in prompt  # 欄位名＋前 5 列進 prompt


def test_run_task_previews_json_data_file_when_no_csv(tmp_path):
    """G1 nested_events 只有 events.json：run_task 須把 JSON 資料檔名與前幾項進 prompt，
    超過前 5 項的不准進；手寫 requirements.json 仍不准進。"""
    t_dir = tmp_path / "nested_events"
    t_dir.mkdir()
    (t_dir / "request.md").write_text(
        "events.json 是 JSON 陣列，產出 event_stats.csv 與 summary.md。",
        encoding="utf-8",
    )
    events = [
        {"event_id": f"e{i:03d}", "event_type": "click", "ts": "2026-10-15T08:01:00Z",
         "payload": {"duration_ms": i * 10}}
        for i in range(1, 8)
    ]
    (t_dir / "events.json").write_text(
        json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (t_dir / "requirements.json").write_text('{"task_id": "HANDWRITTEN-SECRET"}', encoding="utf-8")
    client = FakeClient("[]")
    out = tmp_path / "out.json"
    run_task(t_dir / "request.md", model="glm53", client=client, out_path=out)
    prompt = client.prompts[0]
    assert "events.json" in prompt
    assert "e001" in prompt and "e005" in prompt  # 前 5 項資料
    assert "e006" not in prompt  # 第 6 項起不准進 prompt
    assert "HANDWRITTEN-SECRET" not in prompt


def test_main_success_prints_counts_and_writes(tmp_path, capsys):
    t_dir = tmp_path / "orders_monthly"
    t_dir.mkdir()
    (t_dir / "request.md").write_text(ORDER_TEXT, encoding="utf-8")
    (t_dir / "orders.csv").write_text("order_id,status\nA,COMPLETED\n", encoding="utf-8")
    resp = json.dumps(
        [{"id": "r1", "quote": "排除狀態為 CANCELLED 的取消訂單。", "deliverable": "monthly_sales.csv",
          "verifier": "csv_structure", "params": {"required_columns": ["month"]}}],
        ensure_ascii=False,
    )
    script, log, copy = _fake_glm(tmp_path, response=resp)
    out = tmp_path / "o.json"
    rc = main(["--task", str(t_dir), "--model", "glm53", "--glm", str(script), "--out", str(out)])
    captured = capsys.readouterr().out
    assert rc == 0
    assert "條目 1、丟棄 0、unverified 0" in captured
    assert json.loads(out.read_text(encoding="utf-8"))["items"][0]["id"] == "r1"
    args = log.read_text(encoding="utf-8").splitlines()
    assert args[1] == "glm53" and args[3] == "orders_monthly 擷取需求"
    assert "USER" not in copy.read_text(encoding="utf-8") and "排除狀態" in copy.read_text(encoding="utf-8")


def test_main_fail_closed_on_glm_failure(tmp_path, capsys):
    t_dir = tmp_path / "orders_monthly"
    t_dir.mkdir()
    (t_dir / "request.md").write_text(ORDER_TEXT, encoding="utf-8")
    script, _, _ = _fake_glm(tmp_path, rc=4, stderr="呼叫失敗")
    rc = main(["--task", str(t_dir), "--model", "glm53", "--glm", str(script),
               "--out", str(tmp_path / "o.json")])
    captured = capsys.readouterr()
    assert rc == 20
    assert "條目 0、丟棄 0、unverified 0" in captured.out
    assert "fail-closed" in captured.err
