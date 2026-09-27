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
    
    selected_tasks = random.choices(task_list, k=n_tasks)
    selected_employees = random.choices(employees, k=n_tasks)
    
    today = datetime.today().strftime("%Y-%m-%d")
    
    df = pd.DataFrame({
        "Task Name": [t.replace(" ", "_") for t in selected_tasks],
        "Assigned To": selected_employees,
        "Due Date": [today] * n_tasks
    })
    
    return df
