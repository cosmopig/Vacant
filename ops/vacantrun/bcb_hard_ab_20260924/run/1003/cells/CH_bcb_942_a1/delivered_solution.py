import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
# Constants
START_DATE = '2016-01-01'
PERIODS = 13
FREQ = 'WOM-2FRI'
CATEGORIES = ['Electronics', 'Fashion', 'Home & Kitchen', 'Automotive', 'Sports']

def task_func(start_date=START_DATE, periods=PERIODS, freq=FREQ, categories=CATEGORIES):
    # Generate dates
    dates = pd.date_range(start=start_date, periods=periods, freq=freq)
    
    data = []
    for date in dates:
        for category in categories:
            # Generate some random sales data with a bit of trend/noise
            base_sales = np.random.randint(100, 500)
            trend = (dates.get_loc(date) / periods) * 200
            sales = base_sales + trend + np.random.randint(-50, 50)
            data.append({'Date': date, 'Category': category, 'Sales': sales})
            
    df = pd.DataFrame(data)
    
    # Visualization
    fig, ax = plt.subplots(figsize=(10, 6))
    for category in categories:
        category_data = df[df['Category'] == category]
        ax.plot(category_data['Date'], category_data['Sales'], label=category)
    
    ax.set_title('Category-wise Sales Trends')
    ax.set_xlabel('Date')
    ax.set_ylabel('Sales')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return df, ax
