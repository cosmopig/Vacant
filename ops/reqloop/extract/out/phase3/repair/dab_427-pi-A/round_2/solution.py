import pandas as pd

def count_null_min_p():
    # Read the data file
    df = pd.read_csv('data/cost_data_with_errors.csv')
    
    # Count null values in "min_p" column
    count = df['min_p'].isna().sum()
    return count

if __name__ == "__main__":
    result = count_null_min_p()
    print(f"@null_entries_count[{result}]")
