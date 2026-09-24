import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from statsmodels.tsa.arima.model import ARIMA
from typing import List, Tuple

def task_func(df: pd.DataFrame) -> Tuple[List[float], Axes]:
    # Identify the price column
    price_col = None
    if 'closing_price' in df.columns:
        price_col = 'closing_price'
    else:
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            price_col = numeric_cols[0]
            
    if price_col is None:
        raise ValueError("No suitable column for price found in DataFrame.")

    # Prepare the series
    series = df[price_col]
    
    # Fit ARIMA model with order (5, 1, 0)
    model = ARIMA(series, order=(5, 1, 0))
    model_fit = model.fit()
    
    # Forecast next 7 days
    forecast = model_fit.forecast(steps=7)
    forecast_list = forecast.tolist()
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(series, label='Historical')
    
    if isinstance(series.index, pd.DatetimeIndex):
        last_date = series.index[-1]
        forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7)
        ax.plot(forecast_dates, forecast_list, label='Forecast', color='red')
    else:
        # If it's a range index or something else, we can use the next 7 integers.
        last_idx = series.index[-1]
        if isinstance(last_idx, (int, float)):
            forecast_indices = [last_idx + i for i in range(1, 8)]
            ax.plot(forecast_indices, forecast_list, label='Forecast', color='red')
        else:
            # Fallback to just plotting it at the end of the existing index
            ax.plot(range(len(series), len(series) + 7), forecast_list, label='Forecast', color='red')

    ax.set_title("Share Price Forecast")
    ax.set_xlabel("Date/Index")
    ax.set_ylabel("Price")
    ax.legend()
    plt.tight_layout()
    
    return forecast_list, ax
