"""CI workflow 的七個 job 名字必須逐字對上 main 的分支保護（2026-09-18）。

這支在架構裡承重什麼
────────────────────
`main` 的分支保護要求七個 required status check，而 GitHub **用名字比對**：
沒有任何 workflow 回報那個名字的時候，PR 不會紅、不會綠，會永遠停在
`Waiting for status to be reported`——也就是**合不進去，而且畫面上看不出
是什麼壞了**。2026-09-18 之前 `.github/workflows/` 是空的，整個 repo 就處在
這個狀態。

所以這裡釘的是「名字」不是「有沒有 CI」：把 job 改名（哪怕只是空格）
等於把那個 check 拿掉，而拿掉的後果不是變綠，是回到 Waiting。

⚠ 名單改了要同步改分支保護：
    gh api repos/cosmopig/Vacant/branches/main/protection
本檔只能保證「workflow 這一側有這七個名字」，**保證不了**保護設定那一側
——那份設定不在版控裡（單邊保證，`vacant/suitegauge.py` 的同一句話）。
"""
from __future__ import annotations

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"

#: `gh api repos/cosmopig/Vacant/branches/main/protection` 2026-09-18 讀到的七個。
REQUIRED_CHECKS = (
    "lint + types (3.12, ubuntu)",
    "tests (ubuntu-latest, py3.12)",
    "tests (ubuntu-latest, py3.13)",
    "tests (macos-latest, py3.12)",
    "security scan",
    "build wheel + sdist + smoke install",
    "lint-pr-title",
)

#: 三個 tests check 是同一個 job 的 matrix 展開：GitHub 把 job 的 `name:`
#: 樣板算完之後才拿去比對，所以這裡要驗的是「樣板 ＋ matrix 組合」。
_TESTS_NAME_TEMPLATE = 'name: "tests (${{ matrix.os }}, py${{ matrix.python }})"'


@pytest.fixture(scope="module")
def sources() -> dict[str, str]:
    assert WF.is_dir(), f"{WF} 不存在——七個 check 一個都不會被回報"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(WF.glob("*.yml"))}


#: 承載那七個必要 check 的兩個檔。**缺一個，七個 check 就有一個不會被回報。**
_CHECK_BEARING = {"ci.yml", "pr-title.yml"}


def test_the_check_bearing_workflows_exist(sources):
    missing = _CHECK_BEARING - set(sources)
    assert not missing, f"少了 {sorted(missing)}——必要 check 會變成永遠 pending"


def test_extra_workflows_do_not_impersonate_a_required_check(sources):
    """⚠ 這條取代原本的「集合相等」（2026-09-19）。

    原本寫的是 `set(sources) == {"ci.yml", "pr-title.yml"}`，那把兩件事混在一起：
    「七個必要 check 完好」與「不准有任何別的 workflow」。後者太強——
    加一支 `publish.yml` 就會紅，而它與那七個 check 無關。

    真正要擋的是**冒充**：別的 workflow 宣告了與必要 check 同名的 job，
    分支保護用名字比對 ⇒ 兩個 job 搶同一個名字，綠不綠會變成看誰先跑完。
    """
    for name, blob in sources.items():
        if name in _CHECK_BEARING:
            continue
        for check in REQUIRED_CHECKS:
            assert f'name: "{check}"' not in blob, (
                f"{name} 宣告了必要 check 的名字 {check!r}——"
                f"分支保護會分不清是哪一個 job")


def test_publish_workflow_never_fires_on_push_or_pr(sources):
    """發布流程**只准人手動觸發**。

    它若在 `push`／`pull_request` 上跑，兩件壞事：每個 PR 都會建一次
    artifact（噪音），而且哪天有人把 `publish-pypi` 的條件寫鬆，
    一個 push 就會把東西發出去。
    """
    pub = sources.get("publish.yml")
    if pub is None:
        pytest.skip("這個 repo 沒有 publish.yml")
    head = pub.split("jobs:", 1)[0]
    for bad in ("push:", "pull_request:", "schedule:"):
        assert bad not in head, f"publish.yml 的觸發條件含 {bad}——它只准人手動觸發"
    assert "release:" in head and "workflow_dispatch:" in head


@pytest.mark.parametrize("check", [c for c in REQUIRED_CHECKS
                                   if not c.startswith("tests (")])
def test_non_matrix_checks_are_declared_verbatim(sources, check):
    """非 matrix 的四個：job 的 `name:` 要逐字等於分支保護那個字串。"""
    blob = "\n".join(sources.values())
    assert f'name: "{check}"' in blob, (
        f"沒有 job 叫 {check!r}——那個 required check 會永遠 Waiting")


def test_matrix_covers_exactly_the_three_tests_checks(sources):
    """三個 `tests (...)` 由 matrix 展開，所以要驗 os／python 的組合。"""
    ci = sources["ci.yml"]
    assert _TESTS_NAME_TEMPLATE in ci, "tests job 的名字樣板被改過了"
    combos = set(re.findall(
        r"- os: (\S+)\n\s+python: \"(\S+)\"", ci))
    want = {("ubuntu-latest", "3.12"), ("ubuntu-latest", "3.13"),
            ("macos-latest", "3.12")}
    assert combos == want, combos
    # 樣板展開之後就是保護設定裡的那三個名字。
    rendered = {f"tests ({os_}, py{py})" for os_, py in combos}
    assert rendered == {c for c in REQUIRED_CHECKS if c.startswith("tests (")}


def test_pr_title_job_runs_on_title_edits(sources):
    """標題改對之後要能重跑——少了 `edited` 就是「改了也還是紅的」。"""
    pt = sources["pr-title.yml"]
    assert "pull_request:" in pt
    m = re.search(r"types: \[([^\]]+)\]", pt)
    assert m, "pr-title.yml 沒有寫 types"
    assert "edited" in m.group(1), m.group(1)


def test_pr_title_is_not_interpolated_into_the_shell(sources):
    """PR 標題是外部輸入：只准經環境變數進去。

    `run: python x.py "${{ github.event.pull_request.title }}"` 會讓標題裡的
    `$(...)`／反引號在 runner 上被執行——這是 GitHub Actions 最典型的注入。
    """
    pt = sources["pr-title.yml"]
    assert "PR_TITLE: ${{ github.event.pull_request.title }}" in pt
    for line in pt.splitlines():
        if line.lstrip().startswith(("run:", "- run:")):
            assert "pull_request.title" not in line, line


def test_private_pack_guard_is_wired(sources):
    """CI 上不准出現 `.vacant-private/`（不轉散布），而且要**檢查**它沒出現。"""
    ci = sources["ci.yml"]
    assert "if [ -e .vacant-private ]" in ci
    # 需要私有包的測試在缺席時 skip，而 skip 的理由要被印出來 ⇒ `-rs`。
    assert "python -m pytest tests/ -rs" in ci


def test_gates_are_not_silently_disabled(sources):
    """沒有 `|| true`／`continue-on-error`——那兩個是「空跑」的標準寫法。"""
    blob = "\n".join(sources.values())
    assert "continue-on-error" not in blob
    assert "|| true" not in blob
