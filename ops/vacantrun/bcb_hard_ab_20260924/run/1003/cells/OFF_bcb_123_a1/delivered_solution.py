import pandas as pd
import os
import glob

def task_func(my_list, file_dir='./data_files/', file_ext='.csv'):
    if not isinstance(my_list, list):
        raise TypeError("my_list must be a list")
    
    # Modify the list by adding '12'
    # We use 12 as an integer because it is more likely to be intended for a sum of numbers.
    my_list.append(12)
    
    # Calculate sum of the numbers in the list
    total = 0
    for x in my_list:
        try:
            # Try to convert each element to a float to see if it's a number
            val = float(x)
            total += val
        except (ValueError, TypeError):
            # If it cannot be converted to a float, it's not considered a number for the sum
            pass
    
    # Get CSV files from the directory
    files = sorted(glob.glob(os.path.join(file_dir, f"*{file_ext}")))
    
    if not files:
        raise FileNotFoundError(f"No files found in {file_dir}")
    
    # The number of files concatenated is determined by the sum of the numbers in the list
    num_to_concat = int(total)
    
    # If total is negative or zero, we might want to return an empty DataFrame.
    if num_to_concat <= 0:
        return pd.DataFrame()
    
    selected_files = files[:num_to_concat]
    
    df_list = []
    for f in selected_files:
        df = pd.read_csv(f)
        df_list.append(df)
    
    if not df_list:
        return pd.DataFrame()
        
    return pd.concat(df_list, ignore_index=True)
