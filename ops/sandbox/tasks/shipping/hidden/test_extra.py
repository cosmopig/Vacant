import json
from shipping import shipping_cost

def test_config(tmp_path):
    assert shipping_cost(2) == 450
    assert shipping_cost(2.1) == 800
    assert shipping_cost(20) == 1500
    path = tmp_path / 'rates.json'
    path.write_text(json.dumps({'tiers': [{'max_weight': 3, 'cost': 99}], 'overflow_cost': 199}))
    assert shipping_cost(3, path) == 99
    assert shipping_cost(4, path) == 199
