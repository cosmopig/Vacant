import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.seasonal import seasonal_decompose

def task_func(df, freq='D', decomposition_model='multiplicative'):
    if not isinstance(df, pd.DataFrame):
        raise ValueError("df must be a DataFrame")
    
    if 'value' not in df.columns:
        raise ValueError("DataFrame must contain a 'value' column")
    
    if not pd.api.types.is_numeric_dtype(df['value']):
        raise ValueError("'value' column must contain numeric data types")

    valid_models = ['additive', 'multiplicative']
    if decomposition_model not in valid_models:
        raise ValueError("decomposition_model must be 'additive' or 'multiplicative'")

    # Validate freq string (basic check)
    try:
        pd.infer_freq(df.index) # This doesn't really validate the string 'freq' directly as a parameter
        if not isinstance(freq, str):
            raise ValueError("freq must be a string")
    except Exception:
        pass

    # seasonal_decompose requires the index to have a frequency.
    # If df.index is datetime-like but has no freq, we set it.
    df_copy = df.copy()
    if pd.api.types.is_datetime64_any_dtype(df_copy.index):
        if df_copy.index.freq is None:
            try:
                # We need to make sure the index has a frequency for seasonal_decompose
                df_copy.index = pd.DatetimeIndex(df_copy.index).asfreq(freq)
            except Exception as e:
                raise ValueError(f"Invalid frequency string: {e}")
    else:
        # If it's not datetime, we might need to handle it or assume the user provided a proper index.
        pass

    try:
        result = seasonal_decompose(df_copy['value'], model=decomposition_model)
    except Exception as e:
        raise ValueError(f"Error during decomposition: {e}")

    fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
    result.plot().set_axis_objects(axes)
    plt.tight_layout()
    
    return result, fig.get_axes()
