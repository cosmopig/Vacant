import json


def shipping_cost(weight, config_path='shipping.json'):
    if weight < 0:
        raise ValueError('negative weight')
    with open(config_path) as stream:
        config = json.load(stream)
    for tier in config['tiers']:
        if weight <= tier['max_weight']:
            return tier['cost']
    return config['overflow_cost']
