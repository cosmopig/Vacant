"""個人需求設定層（preference pilot v0.1）的程式入口。

這支在架構裡承重什麼：把「本人通常省略的取捨」收成可凍結的文字規則，
再把新任務的 memo.md／plan.json 送進既有 intake 檢查。它不改寫主線
契約語義，不讀研究分支 reqloop，也不把預測或收據當成本人採用。

誠實邊界：這一包接通的是「個人化產物與 Vacant 驗收流程」。它不是原生
agent 的完成掛鉤，也不提高基礎模型本身的能力。真人回答與 profile
預設放在 Git 工作區外。
"""

from __future__ import annotations

SCHEMA_PACKAGE = "vacant.personal.v1"
BASE_COMMIT = "c097899e768fe049f0b96f6724b219e8530acc10"
