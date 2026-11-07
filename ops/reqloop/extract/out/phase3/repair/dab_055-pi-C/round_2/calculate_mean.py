import pandas as pd
import numpy as np

# Load the data
df = pd.read_csv('data/estimated_numbers.csv')

# The 'No. of cases' column contains values like "630308[495000-801000]" or "0"
# We need to extract the first number before any brackets.
def extract_cases(val):
    if pd.isna(val) or val == '':
        return np.nan
    try:
        # Split by '[' and take the first part, then strip whitespace
        s = str(val).split('[')[0].strip()
        return int(float(s))
    except (ValueError, TypeError):
        return np.nan

df['No. of cases_clean'] = df['No. of cases'].apply(extract_cases)

# Drop Null or empty records as per constraints
df_clean = df.dropna(subset=['No. of cases_clean'])

# Calculate the mean
mean_value = df_clean['No. of cases_clean'].mean()

# The requirement asks for a positive integer in the answer format @mean_cases[mean_value]
# Since it's not specified how to round, and 2081990 is the integer part:
print(int(mean_value))
