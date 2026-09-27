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
    start_date = datetime.fromtimestamp(epoch_milliseconds / 1000.0)
    current_date = datetime.now()
    
    sales_data = []
    
    # Iterate through each day from start_date to current_date
    curr = start_date
    while curr <= current_date:
        for product in products:
            sales = random.randint(10, 50)
            sales_data.append({
                'Product': product,
                'Date': curr,
                'Sales': sales
            })
        # Move to the next day
        curr += pd.Timedelta(days=1)
    
    df = pd.DataFrame(sales_data)
    return df
