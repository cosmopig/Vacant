import pandas as pd
import numpy as np

df = pd.read_csv('data/cost_data_with_errors.csv')
# The CSV seems to have a leading comma or some weird structure based on 'head' output
# Let's check the columns first
print("Columns:", df.columns.tolist())

# Count null values in "min_p" column
null_count = df['min_p'].isna().sum()
print(f"Null count: {null_count}")
