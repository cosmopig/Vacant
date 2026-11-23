class Container:
    class BaseAttributes:
        #: Inherited class attribute.
        class_attr = 1

        #: Base documentation for overridden attribute.
        overridden_attr = 1

        #: Base documentation for shadowed attribute.
        shadowed_attr = 1

        def __init__(self):
            self.instance_attr = 1  #: Inherited instance attribute.
