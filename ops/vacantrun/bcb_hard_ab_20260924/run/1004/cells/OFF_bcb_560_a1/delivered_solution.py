from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

def task_func(data):
    """
    Plots a bar chart of monthly data values for a single year, with 'month' on the x-axis and 'value' on the y-axis.
    The function should output with:
        Axes object: A matplotlib.axes.Axes object representing the plot, with the title formatted as 'Monthly Data for yyyy', x label as 'Month', and y label as 'Value'.
    """
    if not data or data == '':
        raise ValueError("Data is empty")

    # The input format seems to be a comma-separated string of "YYYY-MM-DD,value"
    # based on the test case: data = '2022-01-100,2022-02-200,2022-03-150'
    # Wait, looking at the test case again:
    # data = '2022-01-100,2022-02-200,2022-03-150'
    # This looks like "YYYY-MM" and then a value? 
    # Or is it "YYYY-M-DD" and "value"?
    # Let's re-examine: '2022-01-100,2022-02-200,2022-03-150'
    # If I split by ',', I get ['2022-01-100', '2022-02-200', '2022-03-150']
    # This doesn't look like standard CSV. 
    # Maybe it's "YYYY-MM" and then the value? But there is no comma between them.
    # Let's look at the test again: data = '2022-01-100,2022-02-200,2022-03-150'
    # If it was "YYYY-MM" and value, maybe it's "2022-01" and "100"? 
    # But there is no comma.
    # Wait, '2022-01-100' could be YYYY-MM-DD where DD is the value? No, that doesn't make sense.
    # Let's look at it again: '2022-01-100'. Maybe it's "YYYY-MM" and then a hyphen and then the value?
    # 2022-01 (Year-Month) - 100 (Value).
    # Let's try to parse it that way.

    parts = data.split(',')
    rows = []
    for p in parts:
        if not p: continue
        # Try to split by the last hyphen if there are multiple, or just find where the value starts.
        # Actually, let's look at '2022-01-100'. 
        # If we assume the format is YYYY-MM-Value:
        # We can split by '-' and take first two as date parts, last one as value.
        date_parts = p.split('-')
        if len(date_parts) >= 3:
            year = date_parts[0]
            month = date_parts[1]
            value = int(date_parts[2])
            rows.append({'month': month, 'value': value, 'year': year})
        else:
            pass

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Could not parse data")

    # The goal says "month" on x-axis and "value" on y-axis.
    # It also says title 'Monthly Data for yyyy'.
    year = df['year'].iloc[0]
    
    fig, ax = plt.subplots()
    ax.bar(df['month'], df['value'])
    ax.set_title(f'Monthly Data for {year}')
    ax.set_xlabel('Month')
    ax.set_ylabel('Value')
    
    return ax
