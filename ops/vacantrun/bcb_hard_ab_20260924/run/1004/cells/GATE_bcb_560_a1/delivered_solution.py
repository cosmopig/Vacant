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

    # The test case shows data = '2022-01-100,2022-02-200,2022-03-150'
    # We need to parse this string. It seems like comma-separated values where each value is a date and a number?
    # Wait, '2022-01-100' looks like 'YYYY-MM-Value'. 
    # Let's look at the test again: data = '2022-01-100,2022-02-200,2022-03-150'
    # If it was YYYY-MM-DD, 100 would be DD. But the goal says "monthly data values".
    # Let's try to split by comma and then parse each part.
    
    parts = data.split(',')
    parsed_data = []
    for p in parts:
        p = p.strip()
        if not p: continue
        # Assuming format YYYY-MM-Value or similar. 
        # Let's try to split by '-' and take the first two as year/month, last part as value.
        sub_parts = p.split('-')
        if len(sub_parts) >= 3:
            year = sub_parts[0]
            month = sub_parts[1]
            # The value might be joined with the last '-' if there are more than 2 dashes?
            # Or it's just the last part.
            value = int("".join(sub_parts[2:]))
            parsed_data.append({'year': year, 'month': month, 'value': value})
        else:
            # Fallback if format is different
            parsed_data.append({'year': 'unknown', 'month': p, 'value': 0})

    df = pd.DataFrame(parsed_data)
    
    fig, ax = plt.subplots()
    ax.bar(df['month'], df['value'])
    
    # The title should be 'Monthly Data for yyyy'
    # From the test: data = '2022-01-100...', title is 'Monthly Data for 2022'
    year_val = df['year'].iloc[0] if not df.empty else "0000"
    ax.set_title(f'Monthly Data for {year_val}')
    ax.set_xlabel('Month')
    ax.set_ylabel('Value')
    
    return ax
