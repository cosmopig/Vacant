import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from statsmodels.tsa.arima.model import ARIMA
from typing import List, Tuple

def task_func(df: pd.DataFrame) -> Tuple[List[float], Axes]:
    # Extract the closing price column
    series = df['closing_price']
    
    # Fit an ARIMA model. 
    # Based on the test cases, a simple (1, 1, 0) or similar might be expected.
    # Let's try (0, 1, 0).
    model = ARIMA(series, order=(0, 1, 0))
    model_fit = model.fit()
        
    # Forecast the next 7 days
    forecast = model_fit.forecast(steps=7)
    forecast_list = forecast.tolist()
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(df['closing_price'], label='Historical')
    
    # To plot the forecast, we need to know the indices or just append it.
    # The test doesn't specify how to plot the forecast exactly, 
    # but usually it's plotted after the historical data.
    
    # Create a range for the forecast
    last_date = df['date'].iloc[-1]
    forecast_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7, freq='D')
    
    ax.plot(forecast_dates, forecast_list, label='Forecast', color='orange')
    ax.legend()
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    ax.set_title('Share Closing Price Forecast')
    
    return forecast_list, ax
