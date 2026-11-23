class Base:
    #: docstring for attr1
    attr1 = 1

    attr2 = 2  #: docstring for attr2 in Base


class Derived(Base):
    attr2 = 3  #: docstring for attr2 in Derived
