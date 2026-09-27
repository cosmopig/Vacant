import matplotlib.pyplot as plt
import pandas as pd
import random
from datetime import datetime, timedelta

def task_func(seed=42):
    try:
        random.seed(seed)
        
        # Generate data for the past 30 days
        end_date = datetime.now()
        dates = [end_date - timedelta(days=i) for i in range(30)]
        dates.reverse()
        
        values = [random.uniform(10, 100) for _ in range(30)]
        
        df = pd.DataFrame({
            'Date': dates,
            'Value': values
        })
        
        # Plotting
        fig, ax = plt.subplots()
        ax.plot(df['Date'], df['Value'])
        
        # Styling
        ax.set_xlabel('Date')
        ax.set_ylabel('Value')
        ax.set_title('Random Time Series Data')
        
        # Set font to Arial
        plt.rcParams['font.family'] = 'Arial'
        
        return ax
    except Exception as e:
        raise ValueError(f"An error occurred while generating the data or plot: {e}")
