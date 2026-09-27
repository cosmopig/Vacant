import pandas as pd
import os
import glob

def task_func(my_list, file_dir='./data_files/', file_ext='.csv'):
    if not isinstance(my_list, list):
        raise TypeError("my_list must be a list")
    
    # Modify the list by adding '12'
    # The goal says "adding the element '12'". 
    # Since we need to sum numbers later, I'll append 12 as an integer.
    my_list.append(12)
    
    # Sum of the numbers in the list
    total = 0
    for x in my_list:
        if isinstance(x, (int, float)):
            total += x
            
    # Get files matching the extension in the directory
    files = sorted(glob.glob(os.path.join(file_dir, f"*{file_ext}")))
    if not files:
        raise FileNotFoundError("No files found in the specified directory")
    
    num_to_take = int(total)
    selected_files = files[:num_to_take] if num_to_take > 0 else []
    
    if not selected_files:
        return pd.DataFrame()
        
    df_list = [pd.read_csv(f) for f in selected_files]
    return pd.concat(df_list, ignore_index=True)
