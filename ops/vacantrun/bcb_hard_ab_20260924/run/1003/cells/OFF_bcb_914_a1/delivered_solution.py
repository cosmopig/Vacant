import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

def task_func(df):
    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date just in case
    df = df.sort_values('date').reset_index(drop=True)
    
    # Convert dates to timestamps (numeric) for regression
    # Using .view(np.int64) // 10**9 gives seconds since epoch
    df['timestamp'] = df['date'].apply(lambda x: x.timestamp())
    
    X = df[['timestamp']].values
    y = df['closing_price'].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Generate future dates
    last_date = df['date'].max()
    future_dates = [last_date + pd.Timedelta(seconds=24*60*60 * i) for i in range(1, 8)]
    
    # Predict prices
    future_timestamps = np.array([d.timestamp() for d in future_dates]).reshape(-1, 1)
    pred_prices = model.predict(future_timestamps).tolist()
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(df['date'], df['closing_price'], label='Original')
    ax.plot(future_dates, pred_prices, label='Predicted', linestyle='--')
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return pred_prices, ax
