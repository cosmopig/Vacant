# Task

Examine the correlation between the average number of agents talking and the average waiting time for callers.

## Constraints

Transform the average waiting time from 'HH:MM:SS' string format to seconds (integer type). Then use the Pearson's method to calculate the correlation coefficient between the average number of agents talking and the transformed average waiting time. The result should be rounded to three decimal places.

## Answer format

@correlation_coefficient[float], where float is a number between -1 and 1 that measures the correlation between the average number of agents talking and the average waiting time for callers. The number should be rounded to three decimal places.

## Data

The data file for this task is `data/20170413_000000_group_statistics.csv`.
