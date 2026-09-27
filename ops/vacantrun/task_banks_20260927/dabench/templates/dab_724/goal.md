# Task

3. Perform outlier detection on the 'acceleration' column using the Z-score method. Identify any outliers and remove them from the dataset. Recalculate the mean and standard deviation of the 'acceleration' column after removing the outliers.

## Constraints

Consider observations as outliers if their Z-scores are outside of the -3 to 3 range. For the "average acceleration" after outlier removal, calculate it using the arithmetic mean formula. Calculate the standard deviation using the population standard deviation formula, not the sample standard deviation formula. Round both measures to two decimal places.

## Answer format

@mean_acceleration[avg_acceleration]
@std_acceleration[acceleration_std]
where "avg_acceleration" and "acceleration_std" are numbers rounded to two decimal places.

## Data

The data file for this task is `data/auto-mpg.csv`.
