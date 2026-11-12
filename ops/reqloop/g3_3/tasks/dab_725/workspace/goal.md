# Task

1. Investigate the relationship between 'displacement' and 'mpg' by analyzing the distribution of 'mpg' for each unique value of 'displacement'. Calculate the mean and median 'mpg' for each of the three most common unique values of 'displacement'.

## Constraints

{
- Only consider the three unique 'displacement' values that occur most frequently in the dataset.
- The 'mpg' means and medians must be calculated for each of these three values separately, with 'mpg' values only from rows with the corresponding 'displacement' value.
- Results must be rounded to two decimal places.
}

## Answer format

{
@mean1[mean1], @median1[median1]
@mean2[mean2], @median2[median2]
@mean3[mean3], @median3[median3]
where "mean1", "median1", "mean2", "median2", "mean3", "median3" are corresponding mean and median 'mpg' values for each of the top three 'displacement' values, respectively. Each value should be a float, rounded to two decimal places.

## Data

The data file for this task is `data/auto-mpg.csv`.
