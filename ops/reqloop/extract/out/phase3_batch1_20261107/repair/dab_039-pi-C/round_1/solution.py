import pandas as pd
from scipy import stats
import numpy as np

# Load the data
df = pd.read_csv('data/imp.score.ldlr.metabolome.csv')

# Extract importance.score column
scores = df['importance.score']

# Shapiro-Wilk test
shapiro_stat, p_value = stats.shapiro(scores)

print(f"p_value: {p_value:.4f}")

# Check if p-value < 0.05
if p_value < 0.05:
    # Apply natural log transformation (ensure scores are positive)
    transformed_scores = np.log(scores[scores > 0])
    mean_val = transformed_scores.mean()
    std_val = transformed_scores.std()
    print(f"Transformed Mean: {mean_val:.2f}")
    print(f"Transformed Std: {std_val:.2f}")
else:
    # If not normal, we don't transform (or as per instructions, only if p < 0.05)
    # The prompt says "If the p-value ... is less than 0.05, apply a log transformation"
    # It doesn't explicitly say what to do if it's NOT less than 0.05 for mean/std calculation,
    # but usually we calculate them on the result of the conditional branch or the original.
    # Re-reading: "If the p-value ... is less than 0.05, apply a log transformation... Calculate the mean and standard deviation of the transformed 'importance.score' column."
    # This implies if it's NOT < 0.05, there is no "transformed" column to calculate from?
    # Or maybe it means the result of the operation (which might be identity).
    # Let's assume if p >= 0.05, we don't transform and use original scores for mean/std calculation
    # but wait, the prompt says "Calculate ... of the transformed ... column".
    # If no transformation happened, is it still "transformed"?
    # Usually in these tasks, if the condition isn't met, you might not have a value.
    # However, let's look at the answer format: @transformed_importance_score_mean[mean]
    # I will calculate on transformed if p < 0.05, else use original scores but maybe it won't be called?
    # Actually, usually these tasks expect a result. Let's see.
    pass

# Write to answer.txt
with open('answer.txt', 'w') as f:
    f.write(f"@is_normal[{p_value:.4f}]\n")
    if p_value < 0.05:
        f.write(f"@transformed_importance_score_mean[{mean_val:.2f}]\n")
        f.write(f"@transformed_importance_score_std[{std_val:.2f}]\n")
    else:
        # If not transformed, what to write? 
        # The prompt says "If the p-value ... is less than 0.05, apply a log transformation... Calculate the mean and standard deviation of the transformed 'importance.score' column."
        # This suggests if p >= 0.05, we don't do the calculation or it's not required?
        # I'll just write them as None or similar if they are missing, but let's try to see if there's a default.
        # Actually, I'll just skip writing those lines if p >= 0.05.
        pass
