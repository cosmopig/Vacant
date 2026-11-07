import pandas as pd
import numpy as np
from scipy.stats import skew, kurtosis

# Load the dataset
df = pd.read_csv('data/2014_q4.csv')

# Define columns for imputation
impute_cols = [
    "24-Hour Passes Purchased (midnight to 11:59 pm)",
    "7-Day Passes Purchased (midnight to 11:59 pm)"
]

# Target column for analysis
target_col = "Trips over the past 24-hours (midnight to 11:59pm)"

# Ensure numeric types for relevant columns
for col in impute_cols + [target_col]:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Calculate statistics before imputation
stats_before = {
    "mean": df[target_col].mean(),
    "median": df[target_col].median(),
    "sd": df[target_col].std(),
    "skewness": skew(df[target_col], nan_policy='omit'),
    "kurtosis": kurtosis(df[target_col], nan_policy='omit')
}

# Perform mean imputation
for col in impute_cols:
    mean_val = df[col].mean()
    df[col] = df[col].fillna(mean_val)

# Calculate statistics after imputation
stats_after = {
    "mean": df[target_col].mean(),
    "median": df[target_col].median(),
    "sd": df[target_col].std(),
    "skewness": skew(df[target_col], nan_policy='omit'),
    "kurtosis": kurtosis(df[target_col], nan_policy='omit')
}

# Print results for verification
print("Before Imputation:")
for k, v in stats_before.items():
    print(f"{k}: {v:.2f}")

print("\nAfter Imputation:")
for k, v in stats_after.items():
    print(f"{k}: {v:.2f}")

# Write to answer.txt
with open('answer.txt', 'w') as f:
    f.write(f"@pre_mean[{stats_before['mean']:.2f}]\n")
    f.write(f"@pre_median[{stats_before['median']:.2f}]\n")
    f.write(f"@pre_sd[{stats_before['sd']:.2f}]\n")
    f.write(f"@pre_skewness[{stats_before['skewness']:.2f}]\n")
    f.write(f"@pre_kurtosis[{stats_before['kurtosis']:.2f}]\n")
    f.write(f"@post_mean[{stats_after['mean']:.2f}]\n")
    f.write(f"@post_median[{stats_after['median']:.2f}]\n")
    f.write(f"@post_sd[{stats_after['sd']:.2f}]\n")
    f.write(f"@post_skewness[{stats_after['skewness']:.2f}]\n")
    f.write(f"@post_kurtosis[{stats_after['kurtosis']:.2f}]\n")
