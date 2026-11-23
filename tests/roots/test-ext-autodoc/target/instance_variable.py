class Foo:
    #: docstring for attr1
    attr1 = 1

    def __init__(self):
        self.attr2 = None  #: docstring for attr2


class Bar(Foo):
    def __init__(self):
        self.attr3 = None  #: docstring for attr3
