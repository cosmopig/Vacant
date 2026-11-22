import json

import pytest

from shipping import shipping_cost


def write_config(path, tiers, overflow):
    path.write_text(json.dumps({'tiers': tiers, 'overflow_cost': overflow}))
    return str(path)


@pytest.mark.parametrize('weight, expected', [
    (0, 450), (1, 450), (2, 450), (2.0001, 800), (3, 800), (5, 800),
    (5.0001, 1500), (100, 1500),
])
def test_default_config_tiers(weight, expected):
    assert shipping_cost(weight) == expected


def test_negative_rejected():
    with pytest.raises(ValueError):
        shipping_cost(-0.01)


def test_nan_rejected():
    with pytest.raises(ValueError):
        shipping_cost(float('nan'))


@pytest.mark.parametrize('bad', ['3', None, True])
def test_non_number_rejected(bad):
    with pytest.raises(TypeError):
        shipping_cost(bad)


def test_uses_named_config(tmp_path):
    cfg = write_config(tmp_path / 'c.json', [{'max_weight': 1, 'cost': 10}], 99)
    assert shipping_cost(1, cfg) == 10
    assert shipping_cost(1.5, cfg) == 99


def test_reloads_config_each_call(tmp_path):
    cfg = tmp_path / 'c.json'
    write_config(cfg, [{'max_weight': 10, 'cost': 1}], 2)
    assert shipping_cost(5, str(cfg)) == 1
    write_config(cfg, [{'max_weight': 10, 'cost': 7}], 2)
    assert shipping_cost(5, str(cfg)) == 7


def test_tiers_used_in_order(tmp_path):
    cfg = write_config(tmp_path / 'c.json',
                       [{'max_weight': 3, 'cost': 5}, {'max_weight': 10, 'cost': 6}], 9)
    assert shipping_cost(3, cfg) == 5
    assert shipping_cost(3.5, cfg) == 6
    assert shipping_cost(11, cfg) == 9


def test_empty_tiers_use_overflow(tmp_path):
    cfg = write_config(tmp_path / 'c.json', [], 42)
    assert shipping_cost(0, cfg) == 42
