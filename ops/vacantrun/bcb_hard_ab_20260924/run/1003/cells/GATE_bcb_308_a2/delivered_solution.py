import pandas as pd
from statistics import mean
import random
# Constants for generating the report data
FIELDS = ['Physics', 'Math', 'Chemistry', 'Biology', 'English', 'History']
STUDENTS = ['Student_' + str(i) for i in range(1, 101)]
def task_func(additional_fields = []):
    all_fields = FIELDS + additional_fields
    data = {}
    for student in STUDENTS:
        data[student] = {field: random.randint(0, 100) for field in all_fields}
    
    df = pd.DataFrame.from_dict(data, orient='index')
    
    # Calculate average grade for each student (row-wise mean of the subjects)
    df['Average Grade'] = df[all_fields].mean(axis=1)
    
    # Calculate average grade for each subject (column-wise mean of all students)
    avg_grades = df[all_fields].mean()
    
    # Create a series for the 'Average' row
    avg_row = pd.Series(avg_grades, name='Average')
    
    # To add it correctly, we can use .loc
    df.loc['Average'] = avg_row
    
    return df
