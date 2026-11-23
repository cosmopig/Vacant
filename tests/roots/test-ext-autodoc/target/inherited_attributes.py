class Outer:
    class Base:
        alias = str  #: Inherited class alias.
        constant = 1  #: Inherited class attribute.
        overridden = 2  #: Base attribute replaced by the subclass.
        shared = 3  #: Attribute from the first base.

        def __init__(self):
            self.instance = 4  #: Inherited instance attribute.


class OtherBase:
    shared = 5  #: Attribute from the second base.
