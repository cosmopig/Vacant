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
        raise ValueError("n_tasks must be non-negative")
    
    if seed is not None:
        random.seed(seed)
    
    # Current date
    today = datetime.now().date()
    
    # Select n_tasks tasks and n_tasks employees
    # Using choices to allow n_tasks > len(task_list) or len(employees)
    selected_tasks = random.choices(task_list, k=n_tasks)
    selected_employees = random.choices(employees, k=n_tasks)
    
    # Prepare data for DataFrame
    tasks_data = [task.replace(" ", "_") for task in selected_tasks]
    
    df = pd.DataFrame({
        'Task Name': tasks_data,
        'Assigned To': selected_employees,
        'Due Date': [today] * n_tasks
    })
    
    return df
