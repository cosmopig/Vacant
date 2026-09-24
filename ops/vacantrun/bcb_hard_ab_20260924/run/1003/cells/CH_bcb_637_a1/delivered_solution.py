from random import sample
from typing import Tuple
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

def task_func(num_students):
    courses = ['Math', 'Science', 'History', 'Art']
    data = []
    
    # Generate random grades for students in multiple courses
    for i in range(num_students):
        student_id = f"Student_{i+1}"
        grades = [np.random.randint(0, 101) for _ in courses]
        data.append([student_id] + grades)
            
    df = pd.DataFrame(data, columns=['Student'] + courses)
    
    # Calculate the average grade in each course
    avg_grades = df[courses].mean().reset_index()
    avg_grades.columns = ['Course', 'Average Grade']
    
    # Calculate the number of students with a passing grade (>= 60)
    passing_counts = (df[courses] >= 60).sum().reset_index()
    passing_counts.columns = ['Course', 'Passing Count']
    
    # Merge results into a summary DataFrame for visualization
    summary_df = pd.merge(avg_grades, passing_counts, on='Course', how='left').fillna(0)
    summary_df['Passing Count'] = summary_df['Passing Count'].astype(int)
    
    # Visualization
    fig, ax = plt.subplots()
    
    x = np.arange(len(summary_df))
    width = 0.35
    
    ax.bar(x - width/2, summary_df['Average Grade'], width, label='Average Grade')
    ax.bar(x + width/2, summary_df['Passing Count'], width, label='Passing Count')
    
    ax.set_xticks(x)
    ax.set_xticklabels(summary_df['Course'])
    ax.set_title('Course-wise Average and Passing Grade Counts')
    ax.legend()
    
    return df, ax
