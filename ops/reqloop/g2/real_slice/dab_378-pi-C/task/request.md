# Task

2. Preprocess the dataset by handling missing values in the "24-Hour Passes Purchased (midnight to 11:59 pm)" and "7-Day Passes Purchased (midnight to 11:59 pm)" columns. Use the mean imputation method to fill in the missing values. Then, analyze the distribution of the "Trips over the past 24-hours (midnight to 11:59pm)" column before and after the missing value imputation process. Evaluate if the imputation has significantly affected the distribution and what implications it has on the dataset analysis.

## Constraints

Use the mean imputation method to fill in missing values for both the "24-Hour Passes Purchased (midnight to 11:59 pm)" and "7-Day Passes Purchased (midnight to 11:59 pm)" columns. Then, calculate the mean, median, standard deviation, skewness, and kurtosis for the "Trips over the past 24-hours (midnight to 11:59pm)" column before and after imputation.

## Answer format

@pre_mean[mean_before]
@pre_median[median_before]
@pre_sd[sd_before]
@pre_skewness[skew_before]
@pre_kurtosis[kurt_before]
@post_mean[mean_after]
@post_median[median_after]
@post_sd[sd_after]
@post_skewness[skew_after]
@post_kurtosis[kurt_after]
where all variables represent the corresponding statistical values calculated before (prefix: pre) and after (prefix: post) the imputation, each rounded to two decimal places.

## Data

The data file for this task is `data/2014_q4.csv`.
