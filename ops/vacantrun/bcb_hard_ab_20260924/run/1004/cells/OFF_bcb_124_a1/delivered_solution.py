from random import randint,seed as random_seed
import time
import matplotlib.pyplot as plt
def task_func(my_list, size=100, seed=100):
    if not isinstance(my_list, list):
        raise TypeError("my_list must be a list")
    
    for item in my_list:
        if not isinstance(item, (int, float)):
            raise ValueError("All elements in my_list must be numeric")

    start_time = time.time()
    
    # Enhance 'my_list' by appending the number 12
    my_list.append(12)
    
    # Calculate sum of elements in 'my_list'
    total_sum = sum(my_list)
    
    # The size of the random numbers list is determined by the sum, limited by 'size'
    num_elements = min(total_sum, size)
    
    random_seed(seed)
    generated_numbers = [randint(1, 100) for _ in range(max(0, num_elements))]
    
    end_time = time.time()
    time_taken = end_time - start_time

    # Plot histogram
    fig, ax = plt.subplots()
    ax.hist(generated_numbers, bins=range(1, 102), align='left', edgecolor='black')
    ax.set_xlabel('Number')
    ax.set_ylabel('Frequency')
    ax.set_xticks(range(1, 101))

    return (time_taken, ax)
