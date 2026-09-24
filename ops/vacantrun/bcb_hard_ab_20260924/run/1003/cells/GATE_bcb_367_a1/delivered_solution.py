from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
def task_func(activities):
    for activity in activities:
        if not isinstance(activity, datetime):
            raise TypeError("Activities must be datetime objects.")

    counts = defaultdict(int)
    for activity in activities:
        day_idx = activity.weekday()
        counts[day_idx] += 1

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    activity_counts = [counts[i] for i in range(7)]

    fig, ax = plt.subplots()
    ax.bar(days, activity_counts)
    ax.set_xlabel('Day of the Week')
    ax.set_ylabel('Number of Activities')
    ax.set_title('Weekly Activity')

    return ax
