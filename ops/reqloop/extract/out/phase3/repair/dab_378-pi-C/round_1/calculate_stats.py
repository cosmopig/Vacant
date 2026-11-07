import pandas as pd
import numpy as np
from scipy.stats import skew, kurtosis

# Load the dataset
df = pd.read_csv('data/2014_q4.csv')

# Columns to impute
col1 = "24-Hour Passes Purchased (midnight to 11:59 pm)"
col2 = "7-Day Passes Purchased (midnight to 11:59 pm)"
target_col = "Trips over the past 24-hours (midnight to 11:59pm)"

# Ensure columns are numeric, handling potential strings/objects with NaN or non-numeric values
df[col1] = pd.to_numeric(df[col1], errors='coerce')
df[col2] = pd.to_numeric(df[col2], errors='coerce')
df[target_col] = pd.to_numeric(df[target_col], errors='coerce')

# Calculate stats before imputation for target column
pre_mean = df[target_col].mean()
pre_median = df[target_col].median()
pre_sd = df[target_col].std()
pre_skewness = skew(df[target_col], axis=0)
# Fisher's definition is default for scipy.stats.kurtosis (excess kurtosis)
pre_kurtosis = kurtosis(df[target_col], axis=0)

print(f"Pre Mean: {pre_mean:.2f}")
print(f"Pre Median: {pre_median:.2f}")
print(f"Pre SD: {pre_sd:.2f}")
print(f"Pre Skewness: {pre_skewness:.2f}")
print(f"Pre Kurtosis: {pre_kurtosis:.2f}")

# Impute missing values in the specified columns using mean imputation
df[col1] = df[col1].fillna(df[col1].mean())
df[col2] = df[col2].fillna(df[col2].mean())

# Calculate stats after imputation for target column
post_mean = df[target_col].mean()
post_median = df[target_col].median()
post_sd = df[target_col].std()
post_skewness = skew(df[target_col], axis=0)
post_kurtosis = kurtosis(df[target_col], axis=0)

print(f"Post Mean: {post_mean:.2f}")
print(f"Post Median: {post_median:.2f}")
print(f"Post SD: {post_sd:.2f}")
print(f"Post Skewness: {post_skewness:.2f}")
print(f"Post Kurtosis: {post_kurtosis:.2f}")
