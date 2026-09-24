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
    for category in categories:
        # Generate some random sales data for each category
        sales = np.random.randint(100, 1000, size=len(dates))
        for date, sale in zip(dates, sales):
            data.append({'Date': date, 'Category': category, 'Sales': sale})
    
    df = pd.DataFrame(data)
    
    # Plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    for category in categories:
        cat_data = df[df['Category'] == category]
        ax.plot(cat_data['Date'], cat_data['Sales'], label=category)
    
    ax.set_title('Category-wise Sales Trends')
    ax.set_xlabel('Date')
    ax.set_ylabel('Sales')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return df, ax
