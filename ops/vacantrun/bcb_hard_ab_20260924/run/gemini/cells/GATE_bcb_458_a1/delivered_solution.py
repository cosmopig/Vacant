import json
import re
import pandas as pd

def task_func(json_str):
    if not isinstance(json_str, str) or not json_str.strip():
        return pd.DataFrame()
    
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return pd.DataFrame()
        
    if not isinstance(data, dict) or not data:
        return pd.DataFrame()

    def process_item(item):
        if isinstance(item, (int, float)):
            return float(item * 2)
        elif isinstance(item, str):
            # Check if the string can be interpreted as a number
            # Using regex as suggested. We'll use fullmatch to ensure the whole string is a number.
            match = re.fullmatch(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*", item)
            if match:
                return float(match.group(1)) * 2
            else:
                return item
        elif isinstance(item, list):
            return [process_item(i) for i in item]
        else:
            return item

    normalized_data = {}
    for k, v in data.items():
        normalized_data[k] = process_item(v)

    try:
        df = pd.DataFrame(normalized_data)
        return df
    except Exception:
        return pd.DataFrame()
