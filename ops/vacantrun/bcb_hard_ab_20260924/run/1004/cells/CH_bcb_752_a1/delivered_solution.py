import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import numpy as np

def task_func(data, target_column, test_size=0.2, random_state = 0) -> float:
    if not isinstance(data, pd.DataFrame):
        raise ValueError("If data is not a DataFrame.")
    
    if data.empty:
        raise ValueError("If data is empty.")
    
    if target_column not in data.columns:
        raise ValueError("If target_column ist not a column of data.")
    
    if not np.issubdtype(data[target_column].dtype, np.number):
         # This check might be too strict if it's an object type but contains numbers, 
         # but the goal says "contains values that are not numeric".
         # Let's check if all elements can be converted to numeric and are numeric.
         pass

    if not data.apply(lambda s: pd.to_numeric(s, errors='coerce').notnull().all()).all():
        raise ValueError("If data contains values that are not numeric.")

    if not isinstance(random_state, int):
        raise ValueError("If random_state is not an integer.")
    
    if not (0 <= test_size <= 1):
        raise ValueError("If test_size is not between 0 and 1.")

    X = data.drop(columns=[target_column])
    y = data[target_column]
    
    # Ensure all columns in X are numeric as well
    if not X.apply(lambda s: pd.to_numeric(s, errors='coerce').notnull().all()).all():
        raise ValueError("If data contains values that are not numeric.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state
    )
    
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    return float(model.score(X_test, y_test))
