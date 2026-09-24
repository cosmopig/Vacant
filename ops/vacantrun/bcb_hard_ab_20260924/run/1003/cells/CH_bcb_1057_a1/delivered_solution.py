import pandas as pd
import itertools
import numpy as np
import random

def task_func(animals=None, foods=None):
    default_animals = ['dog', 'cat', 'rabbit']
    default_foods = ['meat', 'vegetables', 'seeds']
    
    is_animals_empty = animals is None or (isinstance(animals, list) and len(animals) == 0)
    is_foods_empty = foods is None or (isinstance(foods, list) and len(foods) == 0)
    
    if is_animals_empty and is_foods_empty:
        return pd.DataFrame()
    
    if is_animals_empty:
        animals = default_animals
    if is_foods_empty:
        foods = default_foods
        
    # Ensure they are lists
    animals_list = list(animals)
    foods_list = list(foods)
    
    # Shuffle the order of animals and foods to ensure variety in layout.
    # This satisfies "The resulting pairs are shuffled randomly" because 
    # it changes the order of pairs produced by itertools.product, 
    # while maintaining the row/column mapping required by the contract.
    shuffled_animals = random.sample(animals_list, len(animals_list))
    shuffled_foods = random.sample(foods_list, len(foods_list))
    
    # Generate all possible combinations using itertools.product
    pairs = list(itertools.product(shuffled_animals, shuffled_foods))
    
    # Create a DataFrame where each row represents a unique animal 
    # and each column represents a food item.
    df = pd.DataFrame(index=shuffled_animals, columns=shuffled_foods)
    
    # Fill the DataFrame with the generated pairs in row-major order.
    # Because we used shuffled_animals for index and shuffled_foods for columns,
    # and itertools.product(shuffled_animals, shuffled_foods) produces 
    # pairs in row-major order relative to these lists, this will correctly 
    # place each pair (A_i, F_j) at cell (i, j).
    for i, (animal, food) in enumerate(pairs):
        df.iloc[i // len(shuffled_foods), i % len(shuffled_foods)] = f"{animal}:{food}"
        
    return df
