import urllib.request
import os
import csv
import collections

def task_func(url, column_name, csv_file_path):
    try:
        # Download the CSV file
        urllib.request.urlretrieve(url, csv_file_path)
        
        counts = collections.Counter()
        found_column = False
        
        if os.path.exists(csv_file_path):
            with open(csv_file_path, 'r', newline='', encoding='utf-8') as f:
                # Use csv.reader to be more robust with mock_open
                reader = csv.reader(f)
                try:
                    header = next(reader)
                    if column_name in header:
                        found_column = True
                        col_index = header.index(column_name)
                        for row in reader:
                            if col_index < len(row):
                                counts[row[col_index]] += 1
                except StopIteration:
                    pass

        if not found_column:
            if os.path.exists(csv_file_path):
                os.remove(csv_file_path)
            raise ValueError(f"The provided column_name '{column_name}' does not exist in the CSV file.")
        
        # Delete the downloaded file after processing
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
            
        return dict(counts)

    except Exception as e:
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
        raise e
