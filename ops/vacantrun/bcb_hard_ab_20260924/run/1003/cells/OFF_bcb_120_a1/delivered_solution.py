import pandas as pd
from datetime import datetime, timedelta
from random import randint, seed as random_seed

def task_func(start_date=datetime(2020, 1, 1), end_date=datetime(2020, 12, 31), seed=42):
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        raise ValueError("Both start_date and end_date must be datetime.datetime instances.")
    
    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date.")
    
    random_seed(seed)
    
    num_days = (end_date - start_date).days + 1
    dates = []
    for _ in range(num_days):
        offset = randint(0, num_days - 1)
        dates.append(start_date + timedelta(days=offset))
    
    return pd.Series(dates)
