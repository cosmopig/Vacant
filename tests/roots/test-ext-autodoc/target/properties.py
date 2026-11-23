from abc import abstractmethod


class Foo:
    """docstring"""

    @property
    def prop(self) -> int:
        """docstring"""


class ClassProperties:
    @classmethod
    @property
    def class_prop(cls) -> str:
        """Class property docstring."""
        return 'value'

    @classmethod
    @property
    @abstractmethod
    def abstract_class_prop(cls) -> int:
        """Abstract class property docstring."""
        raise NotImplementedError


class Sub(ClassProperties):
    pass


class Meta(type):
    @classmethod
    @property
    def meta_prop(cls):
        """Metaclass property docstring."""
        return 'value'
