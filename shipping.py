import json
import math
import os


def _load_config(config_path):
    path = os.fspath(config_path)
    if not os.path.isabs(path) and not os.path.exists(path):
        candidate = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        if os.path.exists(candidate):
            path = candidate
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def shipping_cost(weight, config_path='shipping.json'):
    if isinstance(weight, bool) or not isinstance(weight, (int, float)):
        raise TypeError('weight must be a number')
    if math.isnan(weight):
        raise ValueError('weight must not be NaN')
    if weight < 0:
        raise ValueError('weight must not be negative')

    config = _load_config(config_path)
    for tier in config['tiers']:
        if weight <= tier['max_weight']:
            return tier['cost']
    return config['overflow_cost']
