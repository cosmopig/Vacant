from random import randint
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
# Constants
TEAMS = ['Team A', 'Team B', 'Team C', 'Team D', 'Team E']
PENALTY_COST = 1000  # in dollars
def task_func(goals, penalties):
    data = []
    for i in range(len(TEAMS)):
        team = TEAMS[i]
        g = randint(0, goals)
        p = randint(0, penalties)
        fine = p * PENALTY_COST
        data.append({
            'Team': team,
            'Goals': g,
            'Penalty Cost': fine
        })
    
    df = pd.DataFrame(data)
    
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    sns.barplot(x='Team', y='Goals', data=df, ax=axes[0])
    axes[0].set_title('Goals per Team')
    
    sns.barplot(x='Team', y='Penalty Cost', data=df, ax=axes[1])
    axes[1].set_title('Penalty Costs per Team')
    
    plt.tight_layout()
    
    return df, [axes[0], axes[1]]
