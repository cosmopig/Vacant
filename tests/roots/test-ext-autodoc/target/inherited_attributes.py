class Container:
    class Base:
        #: Documentation from the base class.
        class_attr = 1

        #: Documentation for a shadowed attribute.
        shadowed = 2

        def __init__(self):
            #: Documentation for an inherited instance attribute.
            self.instance_attr = 3
