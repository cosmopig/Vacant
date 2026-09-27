# Task

Perform comprehensive data preprocessing for the dataset by handling missing values in the life expectancy column. Choose an appropriate strategy and implement it using Python code.

## Constraints

Assume there are missing values in the life expectancy column.
Impute missing values with the mean life expectancy of the same country.
If there are countries with all life expectancy values missing, replace missing values with the mean life expectancy of the entire dataset.

## Answer format

@number_of_missing_values_in_lifeexp_before[n_before]
@number_of_missing_values_in_lifeexp_after[n_after]
where "n_before" and "n_after" are integers representing the number of missing values in the life expectancy column before and after the imputation process.

## Data

The data file for this task is `data/gapminder_cleaned.csv`.
