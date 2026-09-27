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
    
    data = []
    
    # Iterate through each day from start_date to current_date
    # We use a while loop because we want to include the current date if it's different
    temp_date = start_date
    while temp_date <= current_date:
        for product in products:
            sales = random.randint(10, 50)
            data.append({
                "Product": product,
                "Date": temp_date,
                "Sales": sales
            })
        # Increment by one day
        temp_date += pd.Timedelta(days=1)
    
    df = pd.DataFrame(data)
    return df
