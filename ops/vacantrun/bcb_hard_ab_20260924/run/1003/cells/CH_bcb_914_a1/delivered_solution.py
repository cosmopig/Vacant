import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

def task_func(df):
    # Ensure date is in datetime format and sort it
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # Convert dates to timestamps (seconds)
    # Using .view(np.int64) gives nanoseconds, so we divide by 10**9 to get seconds.
    # However, for simplicity and compatibility with different pandas versions, 
    # using .astype(np.int64) or .apply(lambda x: x.timestamp()) is safer.
    df['timestamp'] = df['date'].apply(lambda x: x.timestamp())
    
    X = df[['timestamp']].values
    y = df['closing_price'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Generate future timestamps for the next 7 days
    last_date = df['date'].max()
    last_timestamp = last_date.timestamp()
    time_step = 24 * 60 * 60  # seconds in a day
    
    future_timestamps = []
    for i in range(1, 8):
        future_timestamps.append(last_timestamp + i * time_step)
    
    X_future = np.array(future_timestamps).reshape(-1, 1)
    predicted_prices = model.predict(X_future)
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(df['date'], df['closing_price'], label='Original')
    
    # Create future dates for plotting
    future_dates = [last_date + pd.Timedelta(days=i) for i in range(1, 8)]
    ax.plot(future_dates, predicted_prices, label='Predicted', linestyle='--')
    
    ax.legend()
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    ax.set_title('Stock Price Prediction')
    
    return list(predicted_prices), ax
