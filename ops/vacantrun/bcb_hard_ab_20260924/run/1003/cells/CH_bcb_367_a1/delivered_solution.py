from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt

def task_func(activities):
    for activity in activities:
        if not isinstance(activity, datetime):
            raise TypeError("Activities must be datetime objects.")
    
    counts = [0] * 7
    for activity in activities:
        # weekday() returns 0 for Monday and 6 for Sunday
        counts[activity.weekday()] += 1
    
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    fig, ax = plt.subplots()
    ax.bar(days, counts)
    ax.set_xlabel('Day of the Week')
    ax.set_ylabel('Number of Activities')
    ax.set_title('Weekly Activity')
    return ax
