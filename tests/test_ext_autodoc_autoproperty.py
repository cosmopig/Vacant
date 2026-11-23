"""
    test_ext_autodoc_autoproperty
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the autodoc extension.  This tests mainly the Documenters; the auto
    directives are tested in a test source file translated by test_build.

    :copyright: Copyright 2007-2021 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

from abc import abstractmethod

import pytest

from sphinx import addnodes
from sphinx.ext.autosummary import get_documenter, import_by_name
from sphinx.testing import restructuredtext

from .test_ext_autodoc import do_autodoc


class ClassPropertyBase:
    @classmethod
    @property
    def label(cls) -> str:
        """The label for this class."""
        return cls.__name__


class ClassPropertyChild(ClassPropertyBase):
    pass


class ClassPropertyMeta(type):
    @classmethod
    @property
    @abstractmethod
    def required(cls) -> int:
        """The required class property."""
        raise NotImplementedError


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


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_class_property_members(app):
    actual = do_autodoc(app, 'class', __name__ + '.ClassPropertyChild',
                        {'members': None, 'inherited-members': None})
    assert '   .. py:property:: ClassPropertyChild.label' in actual
    assert '      :type: str' in actual
    assert '      The label for this class.' in actual


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_abstract_class_property(app):
    actual = do_autodoc(app, 'property', __name__ + '.ClassPropertyMeta.required')
    assert '.. py:property:: ClassPropertyMeta.required' in actual
    assert '   :abstractmethod:' in actual
    assert '   :type: int' in actual
    assert '   The required class property.' in actual
    doctree = restructuredtext.parse(app, '\n'.join(actual))
    signature, = doctree.traverse(addnodes.desc_signature)
    assert signature.astext() == 'abstract class property ClassPropertyMeta.required: int'


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_autosummary_class_property(app):
    _, obj, parent, _ = import_by_name(__name__ + '.ClassPropertyBase.label')
    assert get_documenter(app, obj, parent).objtype == 'property'
