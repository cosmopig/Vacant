import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(df, target_column):
    # Separate features and target
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # Train the random forest classifier
    rf = RandomForestClassifier(random_state=42)
    rf.fit(X, y)

    # Get feature importances and sort them in descending order
    importances = rf.feature_importances_
    features = X.columns
    
    # Create a series to easily sort using pandas which is already imported
    importance_series = pd.Series(importances, index=features).sort_values(ascending=False)
    
    sorted_importances = importance_series.values
    sorted_features = importance_series.index.tolist()

    # Plot the bar plot
    fig, ax = plt.subplots()
    sns.barplot(x=sorted_importances, y=sorted_features, ax=ax)
    ax.set_xlabel('Feature Importance Score')
    ax.set_ylabel('Features')
    ax.set_title('Visualizing Important Features')

    return rf, ax
