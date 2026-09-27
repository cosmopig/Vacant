import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose

def task_func(df, freq='D', decomposition_model='multiplicative'):
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a DataFrame")
    
    if 'value' not in df.columns:
        raise ValueError("DataFrame must contain a 'value' column")
    
    if not pd.api.types.is_numeric_dtype(df['value']):
        raise ValueError("'value' column must contain numeric data")

    valid_models = ['additive', 'multiplicative']
    if decomposition_model not in valid_models:
        raise ValueError("decomposition_model must be 'additive' or 'multiplicative'")

    # The test setup shows that the DataFrame has a 'date' column but it might not be the index.
    df_copy = df.copy()
    if 'date' in df_copy.columns:
        df_copy = df_copy.set_index('date')

    try:
        # Ensure the index has a frequency. 
        if df_copy.index.freq is None:
            df_copy = df_copy.asfreq(freq)
        
        result = seasonal_decompose(df_copy['value'], model=decomposition_model, period=None)
    except ValueError as e:
        raise ValueError(f"Invalid frequency or other value error: {e}")
    except Exception as e:
        # If it's a statsmodels specific error about insufficient data, we should raise ValueError.
        if "NaN" in str(e) or "frequency" in str(e).lower():
            raise ValueError(f"Error during decomposition: {e}")
        raise ValueError(f"Error during decomposition: {e}")

    # result.plot() creates its own figure and axes by default.
    result.plot()
    ax_out = plt.gca()
    
    return result, ax_out
