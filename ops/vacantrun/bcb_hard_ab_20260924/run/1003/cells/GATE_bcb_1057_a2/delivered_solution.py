import pandas as pd
import itertools
import numpy as np

def task_func(animals=None, foods=None):
    predefined_animals = ['lion', 'tiger', 'bear']
    predefined_foods = ['meat', 'fruit', 'vegetables']
    
    if (not animals or animals is None) and (not foods or foods is None):
        return pd.DataFrame()
    
    if not animals or animals is None:
        animals = predefined_animals
    if not foods or foods is None:
        foods = predefined_foods
        
    u_animals = list(dict.fromkeys(animals))
    u_foods = list(dict.fromkeys(foods))
    
    pairs = list(itertools.product(u_animals, u_foods))
    np.random.shuffle(pairs)
    
    df = pd.DataFrame(index=u_animals, columns=u_foods)
    
    for i, (a, f) in enumerate(pairs):
        row_idx = i // len(u_foods)
        col_idx = i % len(u_foods)
        df.iloc[row_idx, col_idx] = f"{a}:{f}"
        
    return df
