from random import sample
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def task_func(num_students):
    courses = ['Math', 'Science', 'History', 'Art']
    data = []
    
    for i in range(num_students):
        course = sample(courses, 1)[0]
        grade = np.random.randint(40, 101)
        data.append({'Student': f'Student_{i+1}', 'Course': course, 'Grade': grade})
    
    df_raw = pd.DataFrame(data)
    
    # Calculate summary statistics
    summary = df_raw.groupby('Course')['Grade'].agg(['mean', lambda x: (x >= 60).sum()]).reset_index()
    summary.columns = ['Course', 'Average Grade', 'Passing Count']
    
    # Visualization
    fig, ax = plt.subplots()
    
    # Plotting Average Grade and Passing Count side by side for each course
    x = np.arange(len(summary['Course']))
    width = 0.35
    
    ax.bar(x - width/2, summary['Average Grade'], width, label='Average Grade')
    ax.bar(x + width/2, summary['Passing Count'], width, label='Passing Count')
    
    ax.set_xticks(x)
    ax.set_xticklabels(summary['Course'])
    ax.set_title('Course-wise Average and Passing Grade Counts')
    ax.set_ylabel('Score / Count')
    ax.legend()
    
    return summary, ax
