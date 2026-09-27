# Task

Explore the distribution of the "importance.score" column and determine if it follows a normal distribution by conducting a Shapiro-Wilk test. If the p-value is less than 0.05, apply a log transformation to make the distribution closer to normal. Calculate the mean and standard deviation of the transformed "importance.score" column.

## Constraints

1. Use the Shapiro-Wilk test to determine the normality of the data in the "importance.score" column. The null hypothesis for this test is that the data was drawn from a normal distribution.
2. Use a significance level of 0.05 for the Shapiro-Wilk test.
3. If the p-value from the Shapiro-Wilk test is less than 0.05, apply a natural log transformation to the "importance.score" column.

## Answer format

@is_normal[p_value]
@transformed_importance_score_mean[mean]
@transformed_importance_score_std[std]

where "p_value" is a number between 0 and 1, rounded to four decimal places.
where "mean" is the mean of the transformed "importance.score" column, rounded to two decimal places.
where "std" is the standard deviation of the transformed "importance.score" column, rounded to two decimal places.

## Data

The data file for this task is `data/imp.score.ldlr.metabolome.csv`.
