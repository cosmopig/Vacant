def turn_lookup_inside_out(lookup):
    new_lookup = {}
    for key, value in lookup.items():
        new_lookup[value] = key
    return new_lookup

if __name__ == "__main__":
    import sys
    import json

    input_data = json.load(sys.stdin)
    result = turn_lookup_inside_out(input_data)
    print(json.dumps(result))
