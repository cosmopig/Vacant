import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# Constants
COLUMNS = ['A', 'B', 'C', 'D', 'E']
def task_func(a, b):
    num_rows = len(a)
    num_cols = len(b)
    
    # Select the columns based on the length of list 'b'
    if num_cols <= len(COLUMNS):
        selected_columns = COLUMNS[:num_cols]
    else:
        selected_columns = (COLUMNS * (num_cols // len(COLUMNS) + 1))[:num_cols]
    
    # Generate random data for the DataFrame
    # The shape should be (num_rows, num_cols)
    data = np.random.rand(num_rows, num_cols)
    
    # Create the DataFrame
    df = pd.DataFrame(data, index=a, columns=selected_columns)
    
    # Plot as a bar chart
    fig, ax = plt.subplots()
    if not df.empty and len(df.columns) > 0:
        df.plot(kind='bar', ax=ax)
    
    return ax
