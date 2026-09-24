import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# Constants
COLUMNS = ['A', 'B', 'C', 'D', 'E']
def task_func(a, b):
    num_rows = len(a)
    num_cols = len(b)
    selected_columns = COLUMNS[:num_cols]
    
    # Generate random data
    data = np.random.rand(num_rows, num_cols)
    
    # Create DataFrame
    df = pd.DataFrame(data, index=a, columns=selected_columns)
    
    if df.empty:
        fig, ax = plt.subplots()
        return ax
    
    # Plot as a bar chart and return the Axes object
    ax = df.plot(kind='bar')
    return ax
