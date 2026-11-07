import pandas as pd
import numpy as np
from scipy import stats

# Load the data
df = pd.read_csv('data/imp.score.ldlr.metabolome.csv')

# Extract the "importance.score" column
scores = df['importance.score']

# Perform Shapiro-Wilk test
shapiro_stat, p_value = stats.shapiro(scores)

print(f"p_value={p_value:.4f}")

if p_value < 0.05:
    # Apply natural log transformation
    transformed_scores = np.log(scores)
    mean_val = np.mean(transformed_scores)
    std_val = np.std(transformed_scores)
    print(f"mean={mean_val:.2f}")
    print(f"std={std_val:.2f}")
