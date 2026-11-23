"""
    test_ext_autodoc_autoproperty
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the autodoc extension.  This tests mainly the Documenters; the auto
    directives are tested in a test source file translated by test_build.

    :copyright: Copyright 2007-2021 by the Sphinx team, see AUTHORS.
    :license: BSD, see LICENSE for details.
"""

import pytest

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


@pytest.mark.sphinx('html', testroot='ext-autodoc')
@pytest.mark.parametrize('classname', ['ClassProperties', 'Sub'])
def test_class_property(app, classname):
    actual = do_autodoc(app, 'property', 'target.properties.%s.class_prop' % classname)
    assert list(actual) == [
        '',
        '.. py:property:: %s.class_prop' % classname,
        '   :module: target.properties',
        '   :classmethod:',
        '   :type: str',
        '',
        '   Class property docstring.',
        '',
    ]


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_class_properties_as_members(app):
    actual = list(do_autodoc(app, 'class', 'target.properties.Sub',
                            {'members': None, 'inherited-members': None}))
    assert '   .. py:property:: Sub.class_prop' in actual
    start = actual.index('   .. py:property:: Sub.abstract_class_prop')
    assert actual[start:start + 8] == [
        '   .. py:property:: Sub.abstract_class_prop',
        '      :module: target.properties',
        '      :classmethod:',
        '      :abstractmethod:',
        '      :type: int',
        '',
        '      Abstract class property docstring.',
        '',
    ]


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_metaclass_property(app):
    actual = do_autodoc(app, 'class', 'target.properties.Meta', {'members': None})
    assert '   .. py:property:: Meta.meta_prop' in actual
    assert '      Metaclass property docstring.' in actual
