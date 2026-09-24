import pandas as pd
from datetime import datetime
import random

def task_func(
    epoch_milliseconds,
    random_seed=0,
    products=["Product1", "Product2", "Product3", "Product4", "Product5"],
):
    random.seed(random_seed)
    
    # Convert epoch milliseconds to datetime
    start_dt = datetime.fromtimestamp(epoch_milliseconds / 1000.0)
    end_dt = datetime.now()
    
    sales_data = []
    
    current_date = start_dt.date()
    target_date = end_dt.date()
    
    # Iterate through each day from start_dt to current date
    while current_date <= target_date:
        for product in products:
            sales = random.randint(10, 50)
            sales_data.append({
                'Product': product,
                'Date': datetime.combine(current_date, start_dt.time()),
                'Sales': sales
            })
        current_date += pd.Timedelta(days=1)
    
    df = pd.DataFrame(sales_data)
    # Ensure the Date column is of datetime type (it should be already from combine, but just in case)
    df['Date'] = pd.to_datetime(df['Date'])
    return df
