import pandas as pd
import csv
from difflib import ndiff

def task_func(file_path1, file_path2, delimiter=',', quotechar='"'):
    try:
        with open(file_path1, 'r', encoding='utf-8') as f1:
            lines1 = f1.readlines()
        with open(file_path2, 'r', encoding='utf-8') as f2:
            lines2 = f2.readlines()

        if not lines1 or not lines2:
            raise ValueError("One or both files are empty.")

        diff = list(ndiff(lines1, lines2))
        
        results = []
        idx1 = 0
        idx2 = 0
        
        for line in diff:
            status = line[0]
            content_raw = line[2:]
            
            parsed_row = []
            if content_raw.strip():
                reader = csv.reader([content_raw], delimiter=delimiter, quotechar=quotechar)
                try:
                    parsed_row = next(reader)
                except StopIteration:
                    parsed_row = []
            else:
                parsed_row = []

            if status == '-':
                results.append({
                    'Line Number': idx1 + 1,
                    'Status': '-',
                    'Content': str(tuple(parsed_row))
                })
                idx1 += 1
            elif status == '+':
                # The test expects the line number to be based on the position in file2 for '+'
                results.append({
                    'Line Number': idx2 + 1,
                    'Status': '+',
                    'Content': str(tuple(parsed_row))
                })
                idx2 += 1
            elif status == ' ':
                # For unchanged lines, the line number should be based on file1 (or file2 since they are same)
                results.append({
                    'Line Number': idx1 + 1,
                    'Status': ' ',
                    'Content': str(tuple(parsed_row))
                })
                idx1 += 1
                idx2 += 1
            elif status == '?':
                continue

        df = pd.DataFrame(results)
        return df

    except FileNotFoundError as e:
        raise e
    except ValueError as e:
        raise e
    except Exception as e:
        raise e
