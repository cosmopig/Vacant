# Task

Identify and remove any outliers in the "row retention time" column using the Z-score method with a Z-score threshold of 3. Provide the number of removed outliers.

## Constraints

Use the Z-score method to identify outliers in the "row retention time" column. Any data point with a Z-score greater than 3 or less than -3 is considered an outlier and should be removed.

## Answer format

@removed_outliers_count[count] where "count" is a non-negative integer indicating the count of removed outliers.

## Data

The data file for this task is `data/imp.score.ldlr.metabolome.csv`.
