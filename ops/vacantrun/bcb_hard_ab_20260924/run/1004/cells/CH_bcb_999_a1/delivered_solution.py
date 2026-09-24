import urllib.request
import os
import csv
import collections

def task_func(url, column_name, csv_file_path):
    try:
        # Download the CSV file from the given URL and save it to the specified path
        with urllib.request.urlopen(url) as response:
            with open(csv_file_path, 'wb') as f:
                f.write(response.read())

        counts = collections.Counter()
        # Open the file for reading
        with open(csv_file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Check if column exists
            if column_name not in reader.fieldnames:
                os.remove(csv_file_path)
                raise ValueError(f"The provided column_name '{column_name}' does not exist in the CSV file.")
            
            for row in reader:
                counts[row[column_name]] += 1
        
        # Delete the downloaded file after processing
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
            
        return dict(counts)

    except ValueError as e:
        # Re-raise ValueErrors (like our custom one or others from csv module if applicable)
        # But we must ensure the file is deleted if it exists and wasn't already deleted.
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
        raise e
    except Exception as e:
        # For any other exception, ensure cleanup
        if os.path.exists(csv_file_path):
            os.remove(csv_file_path)
        raise e
