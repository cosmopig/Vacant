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
    ExtractParseError,
    build_requirement_set,
    default_prompt,
    extract_requirements,
    parse_model_output,
    quote_is_verbatim,
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


# ---------------------------------------------------------------- argon 20261107_0822 回歸

def test_extract_validates_all_verifiers_and_subparams(tmp_path):
    """argon 20261107_0822 回歸：
    1. rowset_filter / group_aggregate / summary_numbers / monthly_* 缺必要參數或子欄位時必須標 unverified=True；
    2. answer_kv 的 keys 元素非 dict 或缺 key / type 非法時標 unverified=True；
    3. kv_recomputed / plain_recomputed 各 rtype 缺子參數（如 col / sel_col / out_col / col_a / col_b / stat / where / num_where / fees_file 等）標 unverified=True；
    4. 模型設 required=False 時強制 required=True（防繞過門禁）；重複 id 自動消歧。
    """
    items = [
        # 0: rowset_filter 缺 values 與篩選條件，且試圖設 required=False 繞過門禁
        {
            "id": "dup_id",
            "quote": "Calculate the mean of the column 'No. of cases' in data/estimated_numbers.csv.",
            "deliverable": "out.csv",
            "verifier": "rowset_filter",
            "params": {"input_csv": "orders.csv", "identity": ["id"]},
            "required": False,
        },
        # 1: answer_kv keys 內為字串而非 dict（且 id 與前一條重複）
        {
            "id": "dup_id",
            "quote": "Answer format: @mean_cases[mean_value] where mean_value is a positive integer.",
            "deliverable": "answer.txt",
            "verifier": "answer_kv",
            "params": {"keys": ["mean_cases"]},
        },
        # 2: group_aggregate 缺 input_csv/input_json
        {
            "id": "req_ga_no_input",
            "quote": "Ignore records where the value is Null or empty.",
            "deliverable": "out.csv",
            "verifier": "group_aggregate",
            "params": {"group_by": ["a"], "aggregates": [{"name": "n", "type": "count"}]},
        },
        # 3: group_aggregate 聚合類型不支援
        {
            "id": "req_ga_bad_agg",
            "quote": "Ignore records where the value is Null or empty.",
            "deliverable": "out.csv",
            "verifier": "group_aggregate",
            "params": {
                "input_csv": "t.csv",
                "group_by": ["a"],
                "aggregates": [{"name": "m", "type": "median"}],
            },
        },
        # 4: summary_numbers numbers 元素 type 不支援
        {
            "id": "req_sn_bad_num",
            "quote": "Ignore records where the value is Null or empty.",
            "deliverable": "summary.md",
            "verifier": "summary_numbers",
            "params": {
                "input_csv": "t.csv",
                "numbers": [{"type": "harmonic_mean", "label": "x"}],
            },
        },
        # 5: kv_recomputed mean_int_col 缺 col
        {
            "id": "req_kv_no_col",
            "quote": "Calculate the mean of the column 'No. of cases' in data/estimated_numbers.csv.",
            "deliverable": "answer.txt",
            "verifier": "kv_recomputed",
            "params": {
                "key": "mean_cases",
                "data_file": "data/estimated_numbers.csv",
                "recompute": {"type": "mean_int_col"},
            },
        },
        # 6: kv_recomputed pearson2 缺 col_b
        {
            "id": "req_kv_no_colb",
            "quote": "Calculate the mean of the column 'No. of cases' in data/estimated_numbers.csv.",
            "deliverable": "answer.txt",
            "verifier": "kv_recomputed",
            "params": {
                "key": "r",
                "data_file": "data/estimated_numbers.csv",
                "recompute": {"type": "pearson2", "col_a": "a"},
            },
        },
        # 7: plain_recomputed cond_rate 缺 num_where
        {
            "id": "req_plain_no_num_where",
            "quote": "Ignore records where the value is Null or empty.",
            "deliverable": "answer.txt",
            "verifier": "plain_recomputed",
            "params": {
                "data_file": "data/estimated_numbers.csv",
                "recompute": {
                    "type": "cond_rate",
                    "where": [{"col": "a", "op": "eq", "value": "1"}],
                },
            },
        },
        # 8: params 非 dict
        {
            "id": "req_params_not_dict",
            "quote": "Ignore records where the value is Null or empty.",
            "deliverable": "out.csv",
            "verifier": "monthly_sales_metrics",
            "params": ["not", "a", "dict"],
        },
    ]
    req, report = build_requirement_set("t_guard", items, USER_TEXT)
    assert len(req.items) == len(items)
    # 重複 id 已消歧，不覆寫
    ids = [i.id for i in req.items]
    assert len(set(ids)) == len(ids)
    assert ids[0] == "dup_id" and ids[1] == "dup_id_1"
    # 所有條目強制 required=True，且因參數殘缺一律 unverified=True
    assert all(i.required is True for i in req.items)
    assert all(i.unverified is True for i in req.items)
    reasons = {u.id: u.reason for u in report.unverified}
    assert reasons["dup_id"] == "missing_param:values"
    assert reasons["dup_id_1"] == "invalid_key_spec"
    assert reasons["req_ga_no_input"] == "missing_param:input_csv_or_json"
    assert reasons["req_ga_bad_agg"] == "unsupported_aggregate_type:median"
    assert reasons["req_sn_bad_num"] == "unsupported_summary_number_type:harmonic_mean"
    assert reasons["req_kv_no_col"] == "missing_recompute_param:col"
    assert reasons["req_kv_no_colb"] == "missing_recompute_param:col_b"
    assert reasons["req_plain_no_num_where"] == "missing_recompute_param:num_where"
    assert reasons["req_params_not_dict"] == "params_not_object"

    # 送入 checks.run_requirement_checks 時一律回傳 UNKNOWN，絕不假 PASS 或拋例外
    (tmp_path / "orders.csv").write_text("id,amt\n1,10\n", encoding="utf-8")
    (tmp_path / "out.csv").write_text("id,amt\n1,999999\n", encoding="utf-8")
    (tmp_path / "answer.txt").write_text("@mean_cases[10]\n", encoding="utf-8")
    results = checks.run_requirement_checks(tmp_path, req, tmp_path)
    assert all(r.status == "UNKNOWN" for r in results)


def test_parse_model_output_handles_multiple_fences_and_braces_in_prose():
    """argon 20261107_0822 回歸：
    模型先輸出說明文字（含 {key: val} 或 [備註]）或多段 code fence 時，
    parse_model_output 必須正確抽出 JSON 陣列，不因貪婪正則跨段而失敗。
    """
    raw_multi_fence = (
        "先看欄位說明：\n```text\n欄位 {No. of cases} 為字串\n```\n"
        "擷取結果如下：\n```json\n"
        + json.dumps(_valid_items())
        + "\n```\n說明 [完]"
    )
    assert parse_model_output(raw_multi_fence) == _valid_items()

    raw_prose_braces = (
        "注意格式 {key: value} 與陣列 [a, b]：\n"
        + json.dumps(_valid_items())
        + "\n附註：以上符合 {schema} 規範 [done]。"
    )
    assert parse_model_output(raw_prose_braces) == _valid_items()

