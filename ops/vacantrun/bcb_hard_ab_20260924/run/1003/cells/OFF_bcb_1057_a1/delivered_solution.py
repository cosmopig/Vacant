import pandas as pd
import itertools
import numpy as np

def task_func(animals=None, foods=None):
    default_animals = ['lion', 'tiger', 'bear']
    default_foods = ['meat', 'grass', 'fruit']
    
    # Check if animals is "empty or not provided"
    animals_missing = (animals is None) or (isinstance(animals, list) and len(animals) == 0)
    # Check if foods is "empty or not provided"
    foods_missing = (foods is None) or (isinstance(foods, list) and len(foods) == 0)
    
    if animals_missing and foods_missing:
        return pd.DataFrame()
    
    if animals_missing:
        animals = default_animals
    elif foods_missing:
        foods = default_foods
        
    # Convert to lists for shuffling
    animals_list = list(animals)
    foods_list = list(foods)
    
    # Shuffle the input lists to ensure variety in layout
    np.random.shuffle(animals_list)
    np.random.shuffle(foods_list)
    
    # Generate all combinations using itertools.product
    pairs = list(itertools.product(animals_list, foods_list))
    
    # The prompt says "The resulting pairs are shuffled randomly"
    # Even though it might not affect the grid if we use index/columns, 
    # let's shuffle them to be safe and follow instructions literally.
    np.random.shuffle(pairs)
    
    # Create the DataFrame where rows represent animals and columns represent foods
    df = pd.DataFrame(index=animals_list, columns=foods_list)
    for i, animal in enumerate(animals_list):
        for j, food in enumerate(foods_list):
            df.loc[animal, food] = f"{animal}:{food}"
            
    return df
