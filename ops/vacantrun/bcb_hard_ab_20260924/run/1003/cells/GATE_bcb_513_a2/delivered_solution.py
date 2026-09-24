import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def task_func(column, data):
    if not data:
        raise ValueError("The data list is empty.")

    df = pd.DataFrame(data)

    # Identify the column to use and the date column
    target_col_data = None
    date_data = None
    default_cols = ['Date', 'Steps', 'Calories Burned', 'Distance Walked']

    if column in df.columns:
        # Case 1: Column name is directly in the DataFrame columns
        target_col_data = df[column]
        date_col_name = 'Date' if 'Date' in df.columns else df.columns[0]
        date_data = df[date_col_name]
    elif all(isinstance(c, (int, float)) or str(c).isdigit() for c in df.columns):
        # Case 2: Columns are integers, use default names
        if column in default_cols:
            idx = default_cols.index(column)
            target_col_data = df.iloc[:, idx]
            date_data = df.iloc[:, 0]
        else:
            raise KeyError(f"Column '{column}' is not valid.")
    else:
        # Case 3: Column name not found and columns are not integers
        raise KeyError(f"Column '{column}' is not valid.")

    # Validation of numeric columns
    numeric_cols_to_check = ['steps', 'calories burned', 'distance walked']
    for nc in numeric_cols_to_check:
        found_nc_col = None
        for c in df.columns:
            if str(c).lower() == nc.lower():
                found_nc_col = c
                break
        
        if found_nc_col is not None and found_nc_col in df.columns:
            # Check if any value is negative
            # We use pd.to_numeric to ensure we are comparing numbers, 
            # but only for the check of negativity.
            series = pd.to_numeric(df[found_nc_col], errors='coerce')
            if (series < 0).any():
                raise ValueError(f"Numeric values for {nc} must be non-negative.")

    # Calculate stats
    stats = {
        "sum": float(target_col_data.sum()),
        "mean": float(target_col_data.mean()),
        "min": float(target_col_data.min()),
        "max": float(target_col_data.max())
    }

    # Plotting
    fig, ax = plt.subplots()
    ax.plot(date_data, target_col_data)
    ax.set_title(f"Line Chart of {column}")
    ax.set_xlabel("Date")
    ax.set_ylabel(column)

    return stats, ax
