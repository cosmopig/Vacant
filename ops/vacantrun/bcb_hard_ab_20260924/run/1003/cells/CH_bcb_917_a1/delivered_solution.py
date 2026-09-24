import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from statsmodels.tsa.arima.model import ARIMA
from typing import List, Tuple

def task_func(df: pd.DataFrame) -> Tuple[List[float], Axes]:
    # Ensure the data is sorted by date if it's not already
    df = df.sort_values('date').reset_index(drop=True)
    
    # Prepare the series for ARIMA
    series = df['closing_price'].astype(float)
    series.index = pd.to_datetime(df['date'])
    series = series.asfreq('D')
    
    # Fit ARIMA model - using (1, 1, 0) as a starting point which is common for trends
    model = ARIMA(series, order=(1, 1, 0), enforce_stationarity=False, enforce_invertibility=False)
    model_fit = model.fit()
    
    # Forecast for next 7 days
    forecast = model_fit.forecast(steps=7)
    forecast_list = forecast.tolist()
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(df['date'], df['closing_price'], label='Historical')
    
    # Generate future dates for plotting the forecast
    last_date = pd.to_datetime(df['date'].iloc[-1])
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=7)
    ax.plot(future_dates, forecast_list, label='Forecast', color='red')
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return forecast_list, ax
