import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# Constants
COLUMNS = ['A', 'B', 'C', 'D', 'E']
def task_func(a, b):
    """
    Generate a pandas DataFrame with random values based on lists 'a' and 'b', 
    and plot it as a bar chart. List 'a' sets the DataFrame's row indices, 
    while the length of list 'b' determines the number of columns using 
    predefined names from the 'COLUMNS = ['A', 'B', 'C', 'D', 'E']' list.

    Args:
        a (list): List of values to be used as row indices for the DataFrame.
        b (list): List whose length determines the number of columns in the DataFrame.

    Returns:
        matplotlib.axes.Axes: The Axes object of the plotted bar chart.
    """
    # Determine the number of columns based on the length of list 'b'
    num_cols = len(b)
    # Select the first num_cols from COLUMNS, or all if b is empty (though usually it won't be)
    selected_columns = COLUMNS[:num_cols] if num_cols > 0 else []
    
    # Create a DataFrame with random values. 
    # The number of rows is the length of list 'a'.
    # The number of columns is determined by the length of list 'b' (up to the size of COLUMNS).
    num_rows = len(a)
    num_cols = min(len(b), len(COLUMNS))
    data = np.random.rand(num_rows, num_cols)
    df = pd.DataFrame(data, index=a, columns=COLUMNS[:num_cols])

    # Plot as a bar chart
    fig, ax = plt.subplots()
    if not df.empty and len(df.columns) > 0:
        df.plot(kind='bar', ax=ax)
    plt.tight_layout()
    
    return ax
