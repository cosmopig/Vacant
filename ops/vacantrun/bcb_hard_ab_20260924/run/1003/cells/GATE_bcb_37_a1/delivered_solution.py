import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(df, target_column):
    # Separate features and target
    X = df.drop(columns=[target_column])
    y = df[target_column]

    # Train the Random Forest Classifier
    rf = RandomForestClassifier(random_state=42)
    rf.fit(X, y)

    # Get feature importances and sort them in descending order
    importances = rf.feature_importances_
    feature_names = X.columns
    
    # Create a series for plotting
    feature_importance_df = pd.DataFrame({
        'Features': feature_names,
        'Feature Importance Score': importances
    }).sort_values(by='Feature Importance Score', ascending=False)

    # Plotting
    fig, ax = plt.subplots()
    sns.barplot(x='Feature Importance Score', y='Features', data=feature_importance_df, ax=ax)
    ax.set_xlabel('Feature Importance Score')
    ax.set_ylabel('Features')
    ax.set_title('Visualizing Important Features')

    return rf, ax
