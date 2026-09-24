import pandas as pd
import json
import os
import shutil
def task_func(path):
    if not os.path.exists(path):
        return pd.DataFrame()
    if not os.path.isdir(path):
        return pd.DataFrame()
    json_files = sorted([f for f in os.listdir(path) if f.endswith('.json') and os.path.isfile(os.path.join(path, f))])
    if not json_files:
        return pd.DataFrame()
    processed_dir = os.path.join(path, 'processed')
    if not os.path.exists(processed_dir):
        os.makedirs(processed_dir)
    all_dfs = []
    for filename in json_files:
        file_path = os.path.join(path, filename)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            if isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                df = pd.DataFrame(data)
            df['Source'] = filename
            all_dfs.append(df)
            shutil.move(file_path, os.path.join(processed_dir, filename))
        except Exception:
            pass
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)
