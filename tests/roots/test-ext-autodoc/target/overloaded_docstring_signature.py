class E:
    """E(foo: int, bar: int, baz: int) -> None
    E(foo: str, bar: str, baz: str) -> None"""

    def __init__(self):
        pass

    def meth(self):
        """meth(FOO, BAR=1) -> BAZ
        meth(FOO, BAR=1, QUX=2) -> BAZ
        meth(FOO) -> BAZ

        First line of docstring

        rest of docstring
        """


def func():
    """func(a: int) -> int
    func(a: str) -> str

    Overloaded function.
    """
