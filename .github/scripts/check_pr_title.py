"""PR 標題的 conventional-commit 格式檢查（CI 的 lint-pr-title job）。

這支在架構裡承重什麼：本 repo 的歷史就是實驗紀錄——`git log --oneline` 是
「哪一輪做了什麼」的第一手索引，`prereg:` 與 `audit:` 這兩個 type 更是直接
對應「量測之前寫的判準」與「另一雙眼睛複核」這兩件在紀律上完全不同的事。
標題一旦退化成 `update` / `fix stuff`，那個索引就沒了，而**沒有人會回頭補**。

型別清單不是抄來的，是從本 repo 實際用過的挑出來的（`git log --format=%s`
的前 300 筆：prereg 18、feat 15、docs 15、fix 11、ops 7、audit 7、
sched／amend 各若干）。所以這道門擋的是「新造一個沒人看得懂的 type」，
不是「照著別的 repo 的規矩重來」。

⚠ 標題是**外部輸入**：workflow 用環境變數把它交進來，不做 shell 內插。

用法：
    PR_TITLE='feat(ci): …' python .github/scripts/check_pr_title.py
    python .github/scripts/check_pr_title.py --selftest
"""
from __future__ import annotations

import argparse
import os
import re
import sys

#: 本 repo 實際在用的 type（見模組 docstring 的出處）。
TYPES = (
    "feat",      # 新功能／新機制
    "fix",       # 修壞掉的東西
    "docs",      # 文件、README、裁決文
    "test",      # 只動測試
    "refactor",  # 不改行為的重寫
    "perf",      # 效能
    "build",     # 打包、依賴
    "ci",        # CI／workflow
    "chore",     # 雜務
    "revert",    # 回退
    "ops",       # 發射器、佇列、運維腳本
    "prereg",    # **量測之前**寫的預註冊
    "audit",     # 獨立稽核／收官
    "amend",     # 對既有預註冊／裁決的修訂
    "sched",     # 排程
    "merge",     # 合併
)

#: `type(scope)!: subject`。scope 與 `!` 都可省；subject 至少 6 個字元。
_RE = re.compile(
    r"^(?P<type>[a-z]+)"
    r"(?:\((?P<scope>[^()\n]+)\))?"
    r"(?P<breaking>!)?"
    r": (?P<subject>.+)$"
)

MAX_LEN = 120


def check(title: str) -> list[str]:
    """回「哪裡不合格」的清單；空清單＝過。"""
    bad: list[str] = []
    title = title.rstrip("\n")
    if not title.strip():
        return ["標題是空的"]
    if len(title) > MAX_LEN:
        bad.append(f"標題 {len(title)} 個字元，超過 {MAX_LEN}")
    m = _RE.match(title)
    if not m:
        return bad + [
            "格式要是 `type(scope): 說明` 或 `type: 說明`"
            "（冒號後面要有一個半形空格）"]
    if m["type"] not in TYPES:
        bad.append(f"不認得 type={m['type']!r}；可用：{'／'.join(TYPES)}")
    if m["scope"] is not None and not m["scope"].strip():
        bad.append("scope 的括號是空的")
    subject = m["subject"].strip()
    if len(subject) < 6:
        bad.append(f"說明太短（{len(subject)} 個字元）：{subject!r}")
    if subject.endswith((".", "。")):
        bad.append("說明結尾不要句點")
    if re.match(r"^(wip|tmp|temp|test)\b", subject, re.I):
        bad.append("說明不要以 WIP／tmp 開頭——那不是說明，是狀態")
    return bad


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("title", nargs="?", default=None)
    args = ap.parse_args(argv)
    if args.selftest:
        return _selftest()

    title = args.title if args.title is not None else os.environ.get("PR_TITLE", "")
    bad = check(title)
    print(f"PR 標題：{title!r}")
    if not bad:
        print("OK")
        return 0
    for b in bad:
        print(f"  × {b}")
    print("\n本 repo 近期的實例：\n"
          "  prereg(r533): 12B 全部用不思考重做 R529 四題組（716 題/37 塊）\n"
          "  ops(r533): 佇列 37 塊逐塊照抄 R529 參數\n"
          "  docs(lit): 109 筆文獻缺口調查")
    return 1


def _selftest() -> int:
    ok = [
        "feat(ci): 補上七個 status check 的 workflow",
        "fix: build_runs_index 吃得下 R530 的 list 版 arms",
        "prereg(r533): 12B 全部用不思考重做 R529 四題組（716 題/37 塊）",
        "docs(lit): 109 筆文獻缺口調查——對著做出來的東西找",
        "amend(r533): 1003 可用，改兩台八流",
        "feat(logbook)!: wire-format 換版",
    ]
    bad = [
        "",                                   # 空
        "update",                             # 沒有 type
        "更新一些東西",                        # 沒有 type
        "feat:沒有空格",                       # 冒號後沒空格
        "wibble(x): 不認得的 type",             # type 不在清單
        "feat(): 空的 scope",                  # 空 scope
        "feat: 短",                            # 說明太短
        "feat: 結尾有句點。",                   # 句點
        "fix: WIP 先推上去再說",                # WIP
        "feat: " + "字" * 200,                 # 太長
    ]
    for t in ok:
        assert check(t) == [], (t, check(t))
    for t in bad:
        assert check(t) != [], f"這個應該被擋下來卻過了：{t!r}"
    print(f"selftest OK（{len(ok)} 個該過的過、{len(bad)} 個該擋的擋住）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
