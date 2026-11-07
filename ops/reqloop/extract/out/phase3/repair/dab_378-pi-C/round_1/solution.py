import pandas as pd
import numpy as np
from scipy.stats import skew, kurtosis

# Load data
df = pd.read_csv('data/2014_q4.csv')

# Columns to impute - ensure they are numeric
col1 = "24-Hour Passes Purchased (midnight to 11:59 pm)"
col2 = "7-Day Passes Purchased (midnight to 11:59 pm)"
target_col = "Trips over the past 24-hours (midnight to 11:59pm)"

# Convert columns to numeric, coercing errors to NaN
df[col1] = pd.to_numeric(df[col1], errors='coerce')
df[col2] = pd.to_numeric(df[col2], errors='coerce')
df[target_col] = pd.to_numeric(df[target_col], errors='coerce')

def get_stats(series):
    # Drop NaNs for calculation as per standard pandas/scipy behavior unless specified
    s = series.dropna()
    if len(s) == 0:
        return {
            "mean": 0.0, "median": 0.0, "sd": 0.0, "skewness": 0.0, "kurtosis": 0.0
        }
    return {
        "mean": round(float(s.mean()), 2),
        "median": round(float(s.median()), 2),
        "sd": round(float(s.std()), 2),
        "skewness": round(float(skew(s)), 2),
        "kurtosis": round(float(kurtosis(s, fisher=True)), 2) # scipy kurtosis defaults to Fisher (excess)
    }

# Stats before imputation for target column
stats_before = get_stats(df[target_col])

# Perform imputation on col1 and col2
df[col1] = df[col1].fillna(df[col1].mean())
df[col2] = df[col2].fillna(df[col2].mean())

# Stats after imputation
stats_after = get_stats(df[target_col])

print(f"pre_mean={stats_before['mean']}")
print(f"pre_median={stats_before['median']}")
print(f"pre_sd={stats_before['sd']}")
print(f"pre_skewness={stats_before['skewness']}")
print(f"pre_kurtosis={stats_before['kurtosis']}")
print(f"post_mean={stats_after['mean']}")
print(f"post_median={stats_after['median']}")
print(f"post_sd={stats_after['sd']}")
print(f"post_skewness={stats_after['skewness']}")
print(f"post_kurtosis={stats_after['kurtosis']}")
