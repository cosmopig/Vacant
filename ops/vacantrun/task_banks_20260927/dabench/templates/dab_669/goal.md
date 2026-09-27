# Task

Identify and remove any outliers in the MedInc column of the provided dataset using the IQR method. Then calculate the mean and standard deviation of the cleaned MedInc column.

## Constraints

Identify an outlier as any value that falls below Q1 - 1.5 * IQR or above Q3 + 1.5 * IQR, where Q1 and Q3 are the first and third quartiles, respectively, and IQR is the interquartile range (Q3 - Q1). Calculate the mean and standard deviation to two decimal places.

## Answer format

@mean[mean_value] where "mean_value" is a float rounded to two decimal places. @standard_deviation[standard_deviation_value] where "standard_deviation_value" is a float rounded to two decimal places.

## Data

The data file for this task is `data/my_test_01.csv`.
