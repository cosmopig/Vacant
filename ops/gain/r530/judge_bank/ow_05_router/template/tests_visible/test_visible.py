"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_match_and_params():
    """Visible check 1: a path finds its pattern and hands back the named pieces."""


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/users/{id}/posts/{slug}", "user_post")
        got = router.match("/users/42/posts/hello")
        want = ("user_post", {"id": "42", "slug": "hello"})
        assert got == want, "args=%r got=%r want=%r" % ("/users/42/posts/hello", got, want)
    _bank_entry(solution)


def check_v02_more_specific_wins():
    """Visible check 2: when two patterns fit, the more specific one answers."""


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/users/{id}", "show")
        router.add("/users/new", "create_form")
        got = router.match("/users/new")
        assert got == ("create_form", {}), (
            "args=%r got=%r want=%r" % ("/users/new", got, ("create_form", {})))
        got = router.match("/users/7")
        assert got == ("show", {"id": "7"}), (
            "args=%r got=%r want=%r" % ("/users/7", got, ("show", {"id": "7"})))
    _bank_entry(solution)


def check_v03_catch_all_and_miss():
    """Visible check 3: the rest-of-path pattern, and a path that belongs to nobody."""


    def _bank_entry(solution):
        router = solution.Router()
        router.add("/static/{rest:*}", "assets")
        got = router.match("/static/css/site/main.css")
        want = ("assets", {"rest": "css/site/main.css"})
        assert got == want, "args=%r got=%r want=%r" % ("/static/css/site/main.css", got, want)
        got = router.match("/nothing/here")
        assert got is None, "args=%r got=%r want=%r" % ("/nothing/here", got, None)
    _bank_entry(solution)
