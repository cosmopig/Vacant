"""凍結的提示詞。

這支在架構裡承重什麼：四組共用同一段系統規則與同一份輸出契約。
個人資料只換區塊，不換任務事實。gate-off 的客觀回饋是固定句子，
不是空白，這樣「沒有檢查器結果」本身是可核對的。

文字與計畫 §11 的模板一致。改一個字就要換 freeze 版本。
"""

from __future__ import annotations

SYSTEM = """你將處理一個固定資料的試驗任務。
遵守本次任務中的明確條件與提供的事實。
個人資料只代表該使用者過去的回答，不能改寫本次事實或硬條件。
不要從使用者身份猜測未提供的價值觀。
資料不足時保留不確定，不補造本人偏好。
依本次指定的 JSON schema 輸出，不執行工具、不查外部資料。
"""

SUMMARY_BUILD = """只使用下列校準回答，整理最多10條簡短偏好說明。
每條列出支持它的case_id，不添加資料外的人格描述。
保留矛盾與未知。不要讀保留題，不預測具體H/T案例。
輸出一般摘要與來源ID。原始資料：{calibration_cases_joined_with_answers}
"""

STRUCTURED_BUILD = """只使用下列完整校準案例及本人回答建立profile，最多6條規則。
每條規則包含：scope、condition、preference、exceptions、
evidence_case_ids、counterevidence_case_ids、status、evidence_strength。
規則要能被新案例反駁；未被本人確認的狀態為inferred。
不把單一案例推廣為所有場景的固定人格。
矛盾或無來源的內容放unresolved_questions。
原始資料：{calibration_cases_joined_with_answers}
"""

PREDICT = """任務：預測此人在本題較可能選A、B、tie、neither或unsure。
只能使用給定個人資料；輸出case_id、prediction、
evidence_case_ids、applicable_rule_ids、uncertainty。
個人資料：{profile_or_retrieved_cases}
本題：{heldout_case_without_owner_label}
"""

DRAFT = """依本次brief與選項資料提出一份本人可採用的行動方案。
個人規則只作取捨參考；不能覆蓋硬條件與已給事實。
清楚交代選什麼、犧牲什麼、下一步、如何驗證與何時停止。
只輸出指定JSON envelope。
個人資料：{profile}
任務及facts：{task}
輸出schema：{schema}
"""

REVISE = """檢視原稿，確認它符合本次明確要求，且核心理由有根據。
你可以保留或修改；這是最後一輪。
只輸出完整JSON envelope。
原始任務：{task}
個人資料：{profile}
原稿：{draft}
客觀回饋：{gate_on_results_or_fixed_no_checker_feedback}
"""

TEMPLATES = {
    "system": SYSTEM,
    "summary_build": SUMMARY_BUILD,
    "structured_build": STRUCTURED_BUILD,
    "predict": PREDICT,
    "draft": DRAFT,
    "revise": REVISE,
}


def render(name: str, **slots: str) -> str:
    try:
        return TEMPLATES[name].format(**slots)
    except KeyError as exc:
        raise KeyError(f"prompt {name} missing {exc}") from exc
