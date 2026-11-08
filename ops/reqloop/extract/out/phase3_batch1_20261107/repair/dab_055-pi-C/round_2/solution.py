import pandas as pd
import numpy as np

df = pd.read_csv('data/estimated_numbers.csv')

# Convert 'No. of cases' to Int64, ignoring Null or empty values
# Note: The data contains strings like "630308[495000-801000]". 
# However, the instructions say "Convert the data type... from Object (string) to Int64".
# Looking at the CSV, some rows have simple integers as strings, others have ranges.
# If I just use pd.to_numeric(df['No. of cases'], errors='coerce'), 
# it will turn the range ones into NaN.

# Let's see what happens if we try to convert directly.
# The prompt says "Convert... from Object (string) to Int64".
# Usually, this implies that for rows where it is a simple number string, it should become an int.
# For the range ones, they are not standard integers. 

# Let's check the values again.
# Afghanistan, 2017,630308[495000-801000] -> This is definitely a string.
# Algeria, 2017,0 -> This is "0".

# If I use pd.to_numeric(df['No. of cases'], errors='coerce').dropna(), 
# it will only include the ones that are pure numbers.

# Wait, the instructions say: "Convert the data type... to Int64 before performing calculations."
# And "Ignore those records where 'No. of cases' column value is Null or empty."

# Let's try a robust conversion for this specific dataset.
def clean_cases(val):
    if pd.isna(val) or str(val).strip() == "":
        return np.nan
    # If it contains '[', it's a range, we might need to decide how to handle it.
    # But the prompt doesn't say how to handle ranges. 
    # Usually in these tasks, if not specified, we take the first number or ignore them.
    # However, "Convert... to Int64" suggests they should be integers.
    # Let's see if there are any rows that are just numbers.
    try:
        return int(float(val))
    except ValueError:
        # It's a range like 630308[495000-801000]
        # Let's try to extract the first number.
        import re
        match = re.match(r"(\d+)", str(val))
        if match:
            return int(match.group(1))
        return np.nan

df['No. of cases'] = df['No. of cases'].apply(clean_cases)
df = df.dropna(subset=['No. of cases'])
df['No. of cases'] = df['No. of cases'].astype('Int64')

mean_val = df['No. of cases'].mean()
print(int(round(mean_val)))
