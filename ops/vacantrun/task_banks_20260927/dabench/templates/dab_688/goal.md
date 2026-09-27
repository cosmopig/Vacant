# Task

3. Using feature engineering, create a new feature called "time_of_day" based on the "dt" column. The "time_of_day" feature should categorize the timestamp into morning (6:00 to 11:59), afternoon (12:00 to 17:59), evening (18:00 to 23:59), and night (0:00 to 5:59) (included). Provide the count of each category in the "time_of_day" column.

## Constraints

For each time of the day, include the first minute of each category and exclude the first minute of the next category. If there's multiple entry which belongs to the same minute, account them all into the corresponding category.

## Answer format

@morning[integer], @afternoon[integer], @evening[integer], @night[integer]

## Data

The data file for this task is `data/ravenna_250715.csv`.
