import pandas as pd
from statistics import mean
import random
# Constants for generating the report data
FIELDS = ['Physics', 'Math', 'Chemistry', 'Biology', 'English', 'History']
STUDENTS = ['Student_' + str(i) for i in range(1, 101)]
def task_func(additional_fields = []):
    subjects = FIELDS + additional_fields
    data = {}
    for student in STUDENTS:
        data[student] = [random.randint(0, 100) for _ in subjects]
    
    df = pd.DataFrame(data, index=STUDENTS)
    df.columns = subjects
    
    # Calculate Average Grade for each student
    df['Average Grade'] = df[subjects].mean(axis=1)
    
    # Calculate average grade for each subject (across all students)
    avg_values = df[subjects].mean()
    
    # Create a dictionary for the new row
    new_row_dict = {col: avg_values[col] for col in subjects}
    new_row_dict['Average Grade'] = 0
    
    df.loc['Average'] = new_row_dict
    
    print(f"Columns: {list(df.columns)}")
    print(f"Index: {list(df.index)}")
    return df
