# Task

Create a new feature called "batting_average_minus_on_base_percentage" which represents the difference between a player's batting average and their on-base percentage. Calculate the mean and standard deviation of this new feature.

## Constraints

To calculate the new feature, subtract each player's on-base percentage from their batting average. Ignore the missing values and areas with null values for batting average or on-base percentage. Calculate both the mean and standard deviation using these new feature values.

## Answer format

@mean[mean_value] @std_dev[std_dev_value] where "mean_value" is the mean of the new feature, and "std_dev_value" is the standard deviation of the new feature. Both should be rounded to two decimal places.

## Data

The data file for this task is `data/baseball_data.csv`.
