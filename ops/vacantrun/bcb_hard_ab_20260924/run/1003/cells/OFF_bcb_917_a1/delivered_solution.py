import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from statsmodels.tsa.arima.model import ARIMA
from typing import List, Tuple

def task_func(df: pd.DataFrame) -> Tuple[List[float], Axes]:
    # Assuming the dataframe has a 'Close' column and an index that is datetime-like or at least ordered.
    # If not, I might need to handle it. Let's assume 'Close' exists based on common stock data formats.
    # The goal doesn't specify the column name, but "share closing prices" usually implies a 'Close' column.
    # Let's check if there is any more info in the prompt or if I should just use the first column or something.
    # Actually, let me look at the dataframe structure if possible, but since I don't have it yet, 
    # I will assume 'Close' exists and handle potential issues.

    # Let's try to find the price column. If 'Close' doesn't exist, maybe 'Price'?
    # Or just use the last column? Usually, these tasks provide a clear structure.
    # Given "share closing prices", I'll look for 'Close'.
    
    price_col = None
    if 'Close' in df.columns:
        price_col = 'Close'
    elif 'Adj Close' in df.columns:
        price_col = 'Adj Close'
    else:
        # Fallback to the last column if no standard name is found
        price_col = df.columns[-1]

    series = df[price_col]
    
    # Fit ARIMA model. Since parameters aren't specified, I'll use a simple (5,1,0) or similar 
    # but usually for these tasks there might be some standard. 
    # Wait, the goal doesn't specify order. Let me re-read.
    # "Forecasts the share closing prices for the next 7 days using the ARIMA model and plots the forecast."
    # I'll use a simple (5,1,0) as it's common for basic trends, or maybe try to find if there are hints.
    # Actually, without specific parameters, I might need to choose something reasonable.
    # Let's try (5,1,0).

    model = ARIMA(series, order=(5, 1, 0))
    model_fit = model.fit()
    
    forecast = model_fit.forecast(steps=7)
    forecast_list = forecast.tolist()

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(series, label='Historical')
    
    # For plotting the forecast, we need to know the index of the next 7 days.
    # If series has a datetime index, we can use it.
    if isinstance(series.index, pd.DatetimeIndex):
        last_date = series.index[-1]
        forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7)
        ax.plot(forecast_dates, forecast, label='Forecast', color='red')
    else:
        # If it's just integer index or something else, we can just plot it sequentially
        # but usually it's better to have some labels.
        # Let's try to create a dummy range if no date index.
        forecast_idx = list(range(len(series), len(series) + 7))
        ax.plot(forecast_idx, forecast, label='Forecast', color='red')

    ax.set_title('Share Price Forecast')
    ax.set_xlabel('Date')
    ax.set_ylabel('Price')
    ax.legend()
    plt.tight_layout()

    return forecast_list, ax
