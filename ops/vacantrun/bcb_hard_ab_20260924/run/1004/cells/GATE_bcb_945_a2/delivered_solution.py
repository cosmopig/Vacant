import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

def task_func(start_date='2016-01-01', periods=13, freq='WOM-2FRI', sales_data=None):
    if sales_data is None:
        dates = pd.date_range(start=start_date, periods=periods, freq=freq)
        sales_values = np.linspace(100, 500, periods) + np.random.normal(0, 20, periods)
    else:
        num_periods = len(sales_data)
        dates = pd.date_range(start=start_date, periods=num_periods, freq=freq)
        sales_values = np.array(sales_data)

    # Use day of the month as a feature for linear regression
    X = np.array([d.day for d in dates]).reshape(-1, 1)
    y = sales_values

    model = LinearRegression()
    model.fit(X, y)

    # Generate future dates
    last_date = dates[-1]
    
    if len(dates) > 1:
        diff = (dates[1] - dates[0])
        future_dates = pd.date_range(start=last_date + diff, periods=periods, freq=freq)
    else:
        # Fallback if only one date is provided
        future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=periods, freq=freq)
        
    X_future = np.array([d.day for d in future_dates]).reshape(-1, 1)
    forecasted_sales = model.predict(X_future)

    return forecasted_sales
