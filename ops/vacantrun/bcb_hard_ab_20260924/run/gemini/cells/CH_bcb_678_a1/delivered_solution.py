import pandas as pd
import json
import os
import shutil

def task_func(path):
    if not os.path.exists(path) or not os.path.isdir(path):
        return pd.DataFrame()
    
    json_files = []
    for f in os.listdir(path):
        if f.endswith('.json') and os.path.isfile(os.path.join(path, f)):
            json_files.append(f)
    json_files.sort()
    
    if not json_files:
        return pd.DataFrame()
    
    data_frames = []
    for filename in json_files:
        file_path = os.path.join(path, filename)
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame(data)
        df['Source'] = filename
        data_frames.append(df)
    
    combined_df = pd.concat(data_frames, ignore_index=True)
    
    processed_path = os.path.join(path, 'processed')
    if not os.path.exists(processed_path):
        os.makedirs(processed_path)
    
    for filename in json_files:
        shutil.move(os.path.join(path, filename), os.path.join(processed_path, filename))
        
    return combined_df
