"""
    test_ext_autodoc_autoproperty
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the autodoc extension.  This tests mainly the Documenters; the auto
    directives are tested in a test source file translated by test_build.

    :copyright: Copyright 2007-2021 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import sys
from abc import abstractmethod

import pytest

from sphinx.ext.autosummary import get_documenter, import_by_name
from sphinx.testing import restructuredtext

from .test_ext_autodoc import do_autodoc


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_properties(app):
    actual = do_autodoc(app, 'property', 'target.properties.Foo.prop')
    assert list(actual) == [
        '',
        '.. py:property:: Foo.prop',
        '   :module: target.properties',
        '   :type: int',
        '',
        '   docstring',
        '',
    ]


class ClassPropertyMeta(type):
    @classmethod
    @property
    @abstractmethod
    def abstract_prop(cls) -> str:
        """An abstract class property."""
        raise NotImplementedError


class ClassPropertyBase(metaclass=ClassPropertyMeta):
    @classmethod
    @property
    def class_prop(cls) -> int:
        """A class property."""
        return 42


class ClassPropertyDerived(ClassPropertyBase):
    pass


@pytest.mark.skipif(sys.version_info < (3, 9), reason='requires classmethod descriptor support')
@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_class_properties(app):
    actual = do_autodoc(app, 'class', __name__ + '.ClassPropertyDerived',
                        {'members': None, 'inherited-members': None})
    assert '   .. py:property:: ClassPropertyDerived.class_prop' in actual
    assert '      :classmethod:' in actual
    assert '      :type: int' in actual
    assert '      A class property.' in actual

    actual = do_autodoc(app, 'property', __name__ + '.ClassPropertyMeta.abstract_prop')
    assert list(actual) == [
        '',
        '.. py:property:: ClassPropertyMeta.abstract_prop',
        '   :module: ' + __name__,
        '   :abstractmethod:',
        '   :classmethod:',
        '   :type: str',
        '',
        '   An abstract class property.',
        '',
    ]
    doctree = restructuredtext.parse(app, '\n'.join(actual))
    assert 'abstract classmethod property ClassPropertyMeta.abstract_prop: str' in doctree.astext()


@pytest.mark.skipif(sys.version_info < (3, 9), reason='requires classmethod descriptor support')
@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_autosummary_class_property(app):
    _, obj, parent, _ = import_by_name(__name__ + '.ClassPropertyBase.class_prop')
    assert get_documenter(app, obj, parent).objtype == 'property'
