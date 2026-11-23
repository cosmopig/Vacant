class Base:
    attr1 = None  #: docstring for attr1

    #: docstring for attr2
    attr2 = None

    def __init__(self):
        self.attr3 = None  #: docstring for attr3


class Derived(Base):
    attr4 = None  #: docstring for attr4
