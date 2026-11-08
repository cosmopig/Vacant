# Task

Question 1: Calculate the mean and standard deviation of the percentage of votes received by the Democratic and Republican parties. Then, determine if the distribution of the percentage of votes follows a normal distribution using Anderson-Darling test with the significance level (alpha) of 0.05.

## Constraints

The desired calculation of the mean should be rounded up to 2 decimal places and the standard deviation should be rounded up to 3 decimal places.
Use Anderson-Darling test to assess the normalcy of the distribution and if the p-value obtained is less than 0.05, then the distribution can be considered as 'Not Normal' else 'Normal'.

## Answer format

@mean_dem[mean_dem] 
@mean_gop[mean_gop]
@std_dev_dem[std_dev_dem]
@std_dev_gop[std_dev_gop]
@dist_dem[dist_dem]
@dist_gop[dist_gop]
where "mean_dem" and "mean_gop" are numbers representing the mean values for Democratic and Republican parties respectively, rounded to two decimal places.
where "std_dev_dem" and "std_dev_gop" are numbers representing the standard deviation values for Democratic and Republican parties respectively, rounded to three decimal places.
where "dist_dem" and "dist_gop" are strings that can either be "Normal" or "Not Normal" based on the conditions specified in the constraints.

## Data

The data file for this task is `data/election2016.csv`.
