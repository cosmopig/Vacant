import pandas as pd
import os
import glob

def task_func(my_list, file_dir='./data_files/', file_ext='.csv'):
    if not isinstance(my_list, list):
        raise TypeError("my_list must be a list")

    # Modify the list by adding '12'
    # The goal says "adding the element '12'". 
    # I will append it to the end of the list.
    my_list.append(12)

    # Determine the number of files to concatenate from the sum of numbers in the list
    total_files = 0
    for item in my_list:
        if isinstance(item, (int, float)):
            total_files += item

    # Get all matching CSV files
    files = glob.glob(os.path.join(file_dir, f"*{file_ext}"))
    
    if not files:
        raise FileNotFoundError(f"No files found in {file_dir}")

    # Sort the files to ensure consistent ordering
    files.sort()

    # Select the number of files specified by total_files
    # If total_files is larger than available files, we take all of them.
    files_to_concat = files[:int(total_files)]

    if not files_to_concat:
        return pd.DataFrame()

    df_list = []
    for f in files_to_concat:
        df_list.append(pd.read_csv(f))

    return pd.concat(df_list, ignore_index=True)
