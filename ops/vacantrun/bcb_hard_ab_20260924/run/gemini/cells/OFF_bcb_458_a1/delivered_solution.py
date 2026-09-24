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

    if not isinstance(data, dict):
        return pd.DataFrame()

    pattern = r'[-+]?\d*\.\d+|[-+]?\d+'

    def replacer(match):
        s = match.group(0)
        try:
            f = float(s)
            doubled = f * 2
            if doubled == int(doubled):
                return str(int(doubled))
            else:
                return str(doubled)
        except ValueError:
            return s

    def process_value(v):
        if isinstance(v, (int, float)):
            return float(v * 2)
        elif isinstance(v, str):
            res = re.sub(pattern, replacer, v)
            try:
                return float(res)
            except ValueError:
                return res
        elif isinstance(v, list):
            return [process_value(item) for item in v]
        else:
            return v

    new_data = {k: process_value(v) for k, v in data.items()}

    if not new_data:
        return pd.DataFrame()

    try:
        return pd.DataFrame(new_data)
    except ValueError:
        try:
            return pd.DataFrame([new_data])
        except Exception:
            return pd.DataFrame()
