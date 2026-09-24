from datetime import datetime
from collections import defaultdict
import matplotlib.pyplot as plt
def task_func(activities):
    if not all(isinstance(activity, datetime) for activity in activities):
        raise TypeError("All activities must be datetime objects.")

    # Count activities per day of the week (0=Monday, 6=Sunday)
    counts = defaultdict(int)
    for activity in activities:
        day_of_week = activity.weekday()
        counts[day_of_week] += 1

    # Ensure all days are represented in the order Monday to Sunday
    days_count = [counts[i] for i in range(7)]
    days_labels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    fig, ax = plt.subplots()
    ax.bar(days_labels, days_count)
    ax.set_xlabel('Day of the Week')
    ax.set_ylabel('Number of Activities')
    ax.set_title('Weekly Activity')

    return ax
