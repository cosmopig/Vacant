"""P20261113_0300-2（D2）：交付物檔名由受信任務契約（原文）決定，不是模型自由填寫。

11-13 人類裁決第 2 條：
- 交付物是任務的事實，不是模型自報；
- 輸入檔永遠不可當交付物；
- 舊行為完全保留：trusted_deliverable=None（預設）與 D2 前逐位元組同路徑。

工單驗收（正／負控制）：
(a) 原文只點一個輸出檔 → deliverable 用它（正）；
(b) 原文無檔名 → UNKNOWN 如前（負）；
(c) 原文點兩個輸出檔 → None → UNKNOWN 如前（負）；
(d) 該檔是輸入檔時，即使唯一點名也不當輸出（負）。

全部純函數＋假 client：零模型、零網路、零寫檔。
"""
from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from vacant_network.reqloop import extract  # noqa: E402
from vacant_network.reqloop.requirements import RequirementItem  # noqa: E402

INPUTS = ["auto-mpg.csv"]
GOAL_SINGLE = "Calculate the mean of the 'mpg' column. Write the final answer to `answer.txt`."
GOAL_NONE = "Calculate the mean of the 'mpg' column and show your work."
GOAL_TWO = ("Calculate the mean of the 'mpg' column. Write the value to `answer.txt` "
            "and the table to `summary.csv`.")
GOAL_INPUT_ONLY = "Inspect `auto-mpg.csv` and summarize what you find in that file."
GOAL_NUMERIC = "Use a tolerance of 0.000001 and pi=3.14; report the result."


class FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _model_items(deliverable: str) -> list[dict]:
    return [{
        "id": "req_answer_kv",
        "quote": "Write the final answer to `answer.txt`.",
        "deliverable": deliverable,
        "verifier": "answer_kv",
        "params": {"keys": [{"key": "mean_mpg", "type": "number"}]},
    }]


# ── 抽層：trusted_deliverable_from_contract（工單驗收 (a)–(d)）────────────────


def test_a_single_named_output_file_is_trusted():
    """(a) 正：原文只點一個輸出檔（非輸入）→ trusted＝它。"""
    assert extract.trusted_deliverable_from_contract(GOAL_SINGLE, INPUTS) == "answer.txt"


def test_a_path_form_candidate_is_kept_verbatim():
    """(a) 補充：子目錄形式 out/answer.txt 照原樣回傳（不做歸一化，呼叫方判定）。"""
    g = "Put the result into `out/answer.txt` when done."
    assert extract.trusted_deliverable_from_contract(g, INPUTS) == "out/answer.txt"


def test_b_no_filename_in_request_stays_unknown():
    """(b) 負：原文無檔名 → None（呼叫方照舊 UNKNOWN，不猜）。"""
    assert extract.trusted_deliverable_from_contract(GOAL_NONE, INPUTS) is None
    assert extract.trusted_deliverable_from_contract("", INPUTS) is None
    assert extract.trusted_deliverable_from_contract(None, INPUTS) is None  # type: ignore[arg-type]


def test_c_two_output_files_named_stays_unknown():
    """(c) 負：原文點兩個輸出檔 → 無法唯一決定 → None。"""
    assert extract.trusted_deliverable_from_contract(GOAL_TWO, INPUTS) is None


def test_d_input_file_never_deliverable():
    """(d) 負：唯一點名的檔是輸入檔 → 永遠不是交付物（裁決明定的界線）。"""
    assert extract.trusted_deliverable_from_contract(GOAL_INPUT_ONLY, INPUTS) is None
    # 全名與 basename 兩口徑都要排除
    g = "Read `data/auto-mpg.csv` and write nothing else."
    assert extract.trusted_deliverable_from_contract(g, INPUTS) is None


def test_numeric_tokens_are_not_files():
    """負：純數值 token（容差 0.000001、pi=3.14）絕不得誤認為檔名（漏判只落 None）。"""
    assert extract.trusted_deliverable_from_contract(GOAL_NUMERIC, INPUTS) is None


# ── 套用層：extract_requirements(trusted_deliverable=…) ───────────────────────


def test_trusted_applied_claimed_recorded_old_stays_unverified():
    """正：模型自報的假檔名 → 舊路徑 unverified（deliverable_not_in_request）；
    trusted 路徑 → deliverable 換成原文點名的 answer.txt，模型原字串只留紀錄。"""
    user_text = "Calculate the mean of the 'mpg' column. Write the final answer to `answer.txt`."

    # 舊行為（預設 trusted_deliverable=None）：假檔名照樣 unverified，claimed 空
    old_req, old_rep = extract_requirements_(user_text, "output_9x7z.csv")
    assert any(u.id == "req_answer_kv" for u in old_rep.unverified)
    assert old_rep.unverified[0].reason.startswith("deliverable_not_in_request:")
    assert all(i.deliverable_claimed == "" for i in old_req.items)  # 舊行為無 claimed

    # D2：trusted 由契約抽出 → deliverable 用 trusted，原字串只紀錄、不參與判定
    trusted = extract.trusted_deliverable_from_contract(user_text, INPUTS)
    assert trusted == "answer.txt"
    new_req, new_rep = extract_requirements_(user_text, "output_9x7z.csv", trusted)
    item = next(i for i in new_req.items if i.id == "req_answer_kv")
    assert item.deliverable == "answer.txt"
    assert item.deliverable_claimed == "output_9x7z.csv"
    assert item.unverified is False
    assert all(u.id != "req_answer_kv" for u in new_rep.unverified)


def test_trusted_none_is_exactly_old_behavior():
    """負：trusted=None（預設）時，逐條目 deliverable／unverified 與 D2 前同。"""
    user_text = "Calculate the mean of the 'mpg' column. Write the final answer to `answer.txt`."
    a_req, a_rep = extract_requirements_(user_text, "ghost_123.out")
    b_req, b_rep = extract_requirements_(user_text, "ghost_123.out", None)
    assert a_rep.unverified and all(
        u.reason.startswith("deliverable_not_in_request:") for u in a_rep.unverified)
    assert [i.deliverable for i in a_req.items] == [i.deliverable for i in b_req.items]
    assert [u.id for u in a_rep.unverified] == [u.id for u in b_rep.unverified]


def test_apply_trusted_fail_closed_when_trusted_not_named():
    """負：trusted 本身沒在原文點名 → 什麼都不改（fail-closed，不製造交付物）。"""
    user_text = "Calculate the mean of the 'mpg' column. Write the final answer to `answer.txt`."
    req, rep = extract_requirements_(user_text, "ghost_123.out", trusted="ghost_123.out")
    assert all(i.deliverable == "ghost_123.out" for i in req.items)
    assert any(u.id == "req_answer_kv" for u in rep.unverified)


# ── 序列化：deliverable_claimed 只留紀錄、空值不進 dict（舊組 digest 穩定）────


def _item(**kw) -> RequirementItem:
    base = dict(id="r1", quote="Write the final answer to `answer.txt`.",
                deliverable="answer.txt", verifier="answer_kv")
    base.update(kw)
    return RequirementItem(**base)


def test_to_dict_omits_empty_claimed_and_roundtrips_set_value():
    d = _item().to_dict()
    assert "deliverable_claimed" not in d  # 舊行為組：序列化與 D2 前同（digest 穩定）
    d2 = _item(deliverable_claimed="output_9x7z.csv").to_dict()
    assert d2["deliverable_claimed"] == "output_9x7z.csv"
    assert RequirementItem.from_dict(d).deliverable_claimed == ""
    assert RequirementItem.from_dict(d2).deliverable_claimed == "output_9x7z.csv"


def extract_requirements_(user_text: str, claimed: str, trusted: str | None = None):
    client = FakeClient(json.dumps(_model_items(claimed)))
    return extract.extract_requirements(
        user_text=user_text, client=client, task_id="d2_test",
        trusted_deliverable=trusted,
    )
