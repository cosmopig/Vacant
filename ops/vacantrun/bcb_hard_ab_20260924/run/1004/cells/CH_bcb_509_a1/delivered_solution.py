import pandas as pd
import csv
from difflib import ndiff

def task_func(file_path1, file_path2, delimiter=',', quotechar='"'):
    try:
        with open(file_path1, 'r', encoding='utf-8') as f1, \
             open(file_path2, 'r', encoding='utf-8') as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()

        if not lines1 or not lines2:
            raise ValueError("One or both files are empty.")

        # The goal says "Compare two CSV files line by line". 
        # It also mentions 'Line Number': The line number in the file where the difference occurs.
        # And status indicators: ' ', '-', '+'.
        
        # If we use ndiff, it handles insertions and deletions correctly but doesn't give us a simple "line number" 
        # that corresponds to both files easily if they are shifted.
        # However, the requirement for '-' (present in first but not second) and '+' (present in second but not first)
        # combined with 'Line Number' suggests we might need to be careful.

        # Let's try a simple line-by-line comparison based on index first as it's the most straightforward 
        # interpretation of "compare two CSV files line by line" and provides clear line numbers.
        
        max_lines = max(len(lines1), len(lines2))
        results = []
        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else None
            line2 = lines2[i] if i < len(lines2) else None
            
            if line1 == line2:
                results.append({'Line Number': i + 1, 'Status': ' ', 'Content': line1})
            elif line1 is not None and line2 is None:
                results.append({'Line Number': i + 1, 'Status': '-', 'Content': line1})
            elif line1 is None and line2 is not None:
                results.append({'Line Number': i + 1, 'Status': '+', 'Content': line2})
        
        df = pd.DataFrame(results)
        return df

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {e}")
    except ValueError as e:
        raise ValueError(str(e))
    except Exception as e:
        raise Exception(f"IO related error: {e}")
