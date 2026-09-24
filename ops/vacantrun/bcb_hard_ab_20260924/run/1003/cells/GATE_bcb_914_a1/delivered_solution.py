import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

def task_func(df):
    # Ensure 'date' is datetime
    df['date'] = pd.to_datetime(df['date'])
    
    # Sort by date just in case
    df = df.sort_values('date')
    
    # Prepare data for linear regression
    # We can use the timestamp (seconds since epoch) as the independent variable X
    X = df['date'].map(pd.Timestamp.timestamp).values.reshape(-1, 1)
    y = df['closing_price'].values
    
    # Fit the model
    model = LinearRegression()
    model.fit(X, y)
    
    # Generate future dates for the next 7 days
    last_date = df['date'].max()
    future_dates = [last_date + pd.Timedelta(seconds=24*60*60 * i) for i in range(1, 8)]
    
    # Prepare X values for prediction
    X_future = np.array([d.timestamp() for d in future_dates]).reshape(-1, 1)
    
    # Predict prices
    pred_prices = model.predict(X_future).tolist()
    
    # Plotting
    fig, ax = plt.subplots()
    ax.plot(df['date'], df['closing_price'], label='Historical')
    ax.plot(future_dates, pred_prices, label='Predicted', linestyle='--')
    ax.set_xlabel('Date')
    ax.set_ylabel('Closing Price')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return pred_prices, ax
