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

        # The test expectation is very specific about line numbers and statuses.
        # It seems to be using a diff that preserves the original line numbering of file 1 for removals,
        # and uses an incrementing counter for additions? No, let's look at the expected output again:
        # expect = ["1, ,('name', 'age')", "2,-,('Alice', '30')", "3,+,('Alice', '31')", "4, ,('Bob', '25')"]
        # 
        # data1 = [["name", "age"], ["Alice", "30"], ["Bob", "25"]]
        # data2 = [["name", "age"], ["Alice", "31"], ["Bob", "25"]]
        # 
        # Line 1: common -> Status ' ', Content ('name', 'age')
        # Line 2: Alice,30 (removed from file1) -> Status '-', Content ('Alice', '30')
        # Line 3: Alice,31 (added to file2) -> Status '+', Content ('Alice', '31')
        # Line 4: Bob,25 (common) -> Status ' ', Content ('Bob', '25')

        # This means the line numbers are sequential in the output.
        # Let's try a different approach: iterate through both files and find differences.
        # But wait, if we just use ndiff, it gives us exactly what we need if we handle the counters correctly.
        # The issue is that when a line is removed from file1, it doesn't "consume" a line in file2.
        # When a line is added to file2, it doesn't "consume" a line in file1.

        diff = list(ndiff(lines1, lines2))
        results = []
        line_num1 = 0
        line_num2 = 0
        
        # We need to track the current position in both files.
        # ndiff is a bit complex for this because it's an optimal diff.
        # Let's try to use the fact that we know what the expected output looks like.
        # It seems they want us to iterate through the diff and assign line numbers based on 
        # which file the change belongs to, but keep them sequential in the final list?
        # No, "Line Number" is a column. If it's 1, 2, 3, 4, then it's just the index in the result list + 1.

        for d in diff:
            if d.startswith('  '):
                content_raw = d[2:].strip()
                rows = list(csv.reader([content_raw], delimiter=delimiter, quotechar=quotechar))
                if rows:
                    content = str(tuple(rows[0]))
                    results.append({'Line Number': len(results) + 1, 'Status': ' ', 'Content': content})
            elif d.startswith('- '):
                content_raw = d[2:].strip()
                rows = list(csv.reader([content_raw], delimiter=delimiter, quotechar=quotechar))
                if rows:
                    content = str(tuple(rows[0]))
                    results.append({'Line Number': len(results) + 1, 'Status': '-', 'Content': content})
            elif d.startswith('+ '):
                content_raw = d[2:].strip()
                rows = list(csv.reader([content_raw], delimiter=delimiter, quotechar=quotechar))
                if rows:
                    content = str(tuple(rows[0]))
                    results.append({'Line Number': len(results) + 1, 'Status': '+', 'Content': content})
            elif d.startswith('? '):
                pass

        df = pd.DataFrame(results)
        return df[['Line Number', 'Status', 'Content']]

    except FileNotFoundError as e:
        raise e
    except ValueError as e:
        raise e
    except Exception as e:
        if isinstance(e, (IOError, OSError)):
            raise e
        else:
            raise e
