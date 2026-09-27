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
        # For each day, we can have multiple activities or just one. 
        # The goal says "randomly generates acitivity durations... for each activity".
        # Let's assume it means for each of the 5 activities, generate a duration if it happened?
        # Or maybe just pick some random activities for that day.
        # Looking at the sample: Date Activity Duration -> YYYY-MM-DD Running 45
        # It seems we should generate data for all activities or a subset.
        # Let's generate one duration for each activity per day to be safe, 
        # but maybe some can be 0 if they didn't happen? 
        # Actually, the prompt says "randomly generates acitivity durations from 0 to 120 for each activity".
        for activity in activities:
            duration = random.randint(0, 120)
            data.append({
                "Date": current_date,
                "Activity": activity,
                "Duration": duration
            })
    
    df = pd.DataFrame(data)
    # Ensure Date is datetime type for plotting
    df['Date'] = pd.to_datetime(df['Date'])
    
    plt.figure(figsize=(10, 6))
    ax = sns.lineplot(data=df, x='Date', y='Duration', hue='Activity')
    
    return ax, df
