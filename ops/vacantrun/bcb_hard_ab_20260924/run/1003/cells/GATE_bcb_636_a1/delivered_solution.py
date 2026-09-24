import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# Constants
COLUMNS = ['Column1', 'Column2', 'Column3', 'Column4', 'Column5']
def task_func(rows):
    # Create a DataFrame with random integer values between 0 and 9
    data = np.random.randint(0, 10, size=(rows, len(COLUMNS)))
    df = pd.DataFrame(data, columns=COLUMNS)

    # Count the non-zero values in each column
    non_zero_counts = (df != 0).sum()

    # Visualize this information using a bar plot
    fig, ax = plt.subplots()
    if rows > 0:
        non_zero_counts.plot(kind='bar', ax=ax)
        ax.set_title('Non-Zero Values Count')
        ax.set_xlabel('Columns')
        ax.set_ylabel('Count')

    return df, ax
