import pandas as pd
from statistics import mean
import random
# Constants for generating the report data
FIELDS = ['Physics', 'Math', 'Chemistry', 'Biology', 'English', 'History']
STUDENTS = ['Student_' + str(i) for i in range(1, 101)]
def task_func(additional_fields = []):
    subjects = FIELDS + additional_fields
    # Ensure subjects are unique and maintain order
    unique_subjects = []
    for s in subjects:
        if s not in unique_subjects:
            unique_subjects.append(s)
    
    data = {}
    for student in STUDENTS:
        data[student] = [random.randint(0, 100) for _ in unique_subjects]
    
    df = pd.DataFrame(data, index=STUDENTS)
    df.columns = unique_subjects
    
    # Calculate Average Grade for each student
    df['Average Grade'] = df[unique_subjects].mean(axis=1)
    
    # Calculate average grade per subject
    avg_grades = df[unique_subjects].mean()
    
    # Add 'Average' row
    new_row = {}
    for subject in unique_subjects:
        new_row[subject] = avg_grades[subject]
    new_row['Average Grade'] = df['Average Grade'].mean()
    
    df.loc['Average'] = new_row

    return df
