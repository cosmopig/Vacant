# Task

Perform data preprocessing by filling the missing values with the mean values of their respective columns. After that, create a new column called 'Price Category' that categorizes the 'Close' prices into 'High', 'Medium', and 'Low'. 'High' is represented by 'Close' prices that are greater than or equal to the 75th percentile of the 'Close' column data; 'Medium' is represented by 'Close' prices that are between the 25th to 75th percentile; 'Low' is represented by 'Close' prices that are less than or equal to the 25th percentile. Calculate the count and proportion of each category in the dataset.

## Constraints

Constraints:
1. Fill missing values using the mean of their respective columns.
2. Define the three categories (High, Medium, Low) based on the percentiles as specified.
3. Calculate the count and proportion of each category up to two decimal places.

## Answer format

Requires output:
@high_count[high_count] @high_proportion[high_proportion]
@medium_count[medium_count] @medium_proportion[medium_proportion]
@low_count[low_count] @low_proportion[low_proportion]
where "high_count", "medium_count", and "low_count" are positive integers.
where "high_proportion", "medium_proportion", and "low_proportion" are a number between 0 and 1, rounded to two decimal places.

## Data

The data file for this task is `data/YAHOO-BTC_USD_D.csv`.
