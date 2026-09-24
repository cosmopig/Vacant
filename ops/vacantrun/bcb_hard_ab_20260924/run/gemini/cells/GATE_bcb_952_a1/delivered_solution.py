import pandas as pd
import random
from datetime import datetime

def task_func(
    task_list,
    n_tasks,
    employees=["John Doe", "Jane Smith", "James Brown", "Mary Johnson", "Robert Davis"],
    seed=None,
):
    if n_tasks < 0:
        raise ValueError("n_tasks cannot be negative")
    
    if seed is not None:
        random.seed(seed)
        
    if n_tasks == 0:
        return pd.DataFrame(columns=['Task Name', 'Assigned To', 'Due Date'])

    sanitized_tasks = [task.replace(' ', '_') for task in task_list]
    
    selected_tasks = random.choices(sanitized_tasks, k=n_tasks)
    selected_employees = random.choices(employees, k=n_tasks)
    
    today_str = datetime.today().strftime("%Y-%m-%d")
    
    df = pd.DataFrame({
        'Task Name': selected_tasks,
        'Assigned To': selected_employees,
        'Due Date': [today_str] * n_tasks
    })
    
    return df
