import matplotlib.pyplot as plt
import pandas as pd
import random
from datetime import datetime, timedelta

def task_func(seed=42):
    try:
        random.seed(seed)
        
        # Generate 30 days of data
        end_date = datetime.now()
        dates = [end_date - timedelta(days=i) for i in range(30)]
        dates.sort()
        
        values = []
        current_val = random.uniform(10, 100)
        for _ in range(30):
            current_val += random.uniform(-5, 5)
            values.append(current_val)
            
        df = pd.DataFrame({
            'Date': dates,
            'Value': values
        })
        
        # Set font to Arial if possible
        plt.rcParams['font.family'] = 'Arial'
        
        fig, ax = plt.subplots()
        ax.plot(df['Date'], df['Value'])
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.set_title('Random Time Series Data')
        
        return ax
    except Exception as e:
        raise ValueError(f"An error occurred while generating the data or plot: {e}")
