from .inherited_attributes import Container


class Base(object):
    def inheritedmeth(self):
        """Inherited function."""

    @classmethod
    def inheritedclassmeth(cls):
        """Inherited class method."""

    @staticmethod
    def inheritedstaticmeth(cls):
        """Inherited static method."""


class Derived(Base):
    def inheritedmeth(self):
        # no docstring here
        pass


class DerivedAttributes(Container.BaseAttributes):
    #: Subclass documentation.
    overridden_attr = 2

    shadowed_attr = 2
