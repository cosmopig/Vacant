import pandas as pd
import numpy as np

df = pd.read_csv('data/estimated_numbers.csv')
print(f"Total rows: {len(df)}")

# Method 1: Simple to_numeric (will drop ranges)
df2 = df.copy()
df2['No. of cases'] = pd.to_numeric(df2['No. of cases'], errors='coerce')
df2 = df2.dropna(subset=['No. of cases'])
print(f"Rows after to_numeric (dropping ranges): {len(df2)}")
print(f"Mean: {df2['No. of cases'].mean()}")

# Method 2: Extract first number from range strings
def extract_first_number(val):
    if pd.isna(val) or str(val).strip() == "":
        return np.nan
    try:
        return int(float(val))
    except ValueError:
        import re
        match = re.match(r"(\d+)", str(val))
        if match:
            return int(match.group(1))
        return np.nan

df3 = df.copy()
df3['No. of cases'] = df3['No. of cases'].apply(extract_first_number)
df3 = df3.dropna(subset=['No. of cases'])
print(f"Rows after extraction: {len(df3)}")
print(f"Mean: {df3['No. of cases'].mean()}")

