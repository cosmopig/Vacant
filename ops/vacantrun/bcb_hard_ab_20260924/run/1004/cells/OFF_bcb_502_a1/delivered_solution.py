from datetime import datetime, timedelta
import pandas as pd
import random
import seaborn as sns
import matplotlib.pyplot as plt

def task_func(days_in_past=7, random_seed=0):
    random.seed(random_seed)
    activities = ["Running", "Swimming", "Cycling", "Yoga", "Weight Training"]
    data = []
    
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(days_in_past):
        current_date = (end_date - timedelta(days=i)).strftime('%Y-%m-%d')
        for activity in activities:
            duration = random.randint(0, 120)
            data.append({
                "Date": current_date,
                "Activity": activity,
                "Duration": duration
            })
    
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    
    plt.figure(figsize=(10, 6))
    ax = sns.lineplot(data=df, x='Date', y='Duration', hue='Activity')
    plt.title(f"Daily Activity Durations (Last {days_in_past} Days)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    return ax, df
