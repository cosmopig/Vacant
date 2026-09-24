from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

def task_func(data):
    """
    Plots a bar chart of monthly data values for a single year, with 'month' on the x-axis and 'value' on the y-axis.
    The function should output with:
        Axes object: A matplotlib.axes.Axes object representing the plot, with the title formatted as 'Monthly Data for yyyy', x label as 'Month', and y label as 'Value'.
    """
    if not data or data.strip() == "":
        raise ValueError("Data is empty")

    # The test shows data = '2022-01-100,2022-02-200,2022-03-150'
    # This looks like a comma-separated string of "YYYY-MM-Value"
    parts = data.split(',')
    rows = []
    for part in parts:
        if '-' in part and '-' in part[part.find('-')+1:]:
            date_str, value_str = part.rsplit('-', 1)
            # date_str is "2022-01" or similar
            # We need to extract year and month
            year = int(date_str.split('-')[0])
            month = date_str.split('-')[1]
            value = float(value_str)
            rows.append({'month': month, 'value': value, 'year': year})
        else:
            # Fallback if format is different but still has a dash
            date_part, value_part = part.split('-', 1)
            year = int(date_part.split('-')[0])
            month = date_part.split('-')[1]
            value = float(value_part)
            rows.append({'month': month, 'value': value, 'year': year})

    df = pd.DataFrame(rows)
    
    # The test expects "Monthly Data for 2022"
    # If multiple years are present, we might need to handle it, but the goal says "single year".
    year = df['year'].iloc[0] if 'year' in df.columns else datetime.now().year

    fig, ax = plt.subplots()
    ax.bar(df['month'], df['value'])
    
    ax.set_title(f'Monthly Data for {year}')
    ax.set_xlabel('Month')
    ax.set_ylabel('Value')
    
    return ax
