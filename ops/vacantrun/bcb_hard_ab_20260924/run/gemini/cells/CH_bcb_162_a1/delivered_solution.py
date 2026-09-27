import re
import matplotlib.pyplot as plt
import numpy as np

def task_func(text, rwidth=0.8):
    words = re.findall(r'\w+', text)
    lengths = [len(word) for word in words]
    fig, ax = plt.subplots()
    if lengths:
        ax.hist(lengths, rwidth=rwidth)
    return ax
