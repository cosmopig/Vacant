from random import randint,seed as random_seed
import time
import matplotlib.pyplot as plt
def task_func(my_list, size=100, seed=100):
    if not isinstance(my_list, list):
        raise TypeError("my_list must be a list")
    
    for item in my_list:
        if not isinstance(item, (int, float)):
            raise ValueError("All elements in my_list must be numeric")

    # Enhance 'my_list' by appending the number 12
    my_list.append(12)
    
    random_seed(seed)
    start_time = time.time()
    
    # Generate a list of random integers based on the sum of elements in 'my_list', limited by 'size'
    total_sum = sum(my_list)
    num_elements = min(total_sum, size)
    
    random_numbers = [randint(1, 100) for _ in range(num_elements)]
    
    end_time = time.time()
    time_taken = end_time - start_time
    
    # Plot a histogram of the generated random numbers
    fig, ax = plt.subplots()
    ax.hist(random_numbers, bins=range(1, 102), edgecolor='black', align='left')
    ax.set_xlabel('Number')
    ax.set_ylabel('Frequency')
    ax.set_xticks(range(1, 101))
    
    return (time_taken, ax)
