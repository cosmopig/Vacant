import pandas as pd
import csv
from difflib import ndiff

def task_func(file_path1, file_path2, delimiter=',', quotechar='"'):
    try:
        rows1 = []
        with open(file_path1, 'r', encoding='utf-8') as f1:
            reader1 = csv.reader(f1, delimiter=delimiter, quotechar=quotechar)
            for row in reader1:
                rows1.append(tuple(row))

        rows2 = []
        with open(file_path2, 'r', encoding='utf-8') as f2:
            reader2 = csv.reader(f2, delimiter=delimiter, quotechar=quotechar)
            for row in reader2:
                rows2.append(tuple(row))

        if not rows1 or not rows2:
            raise ValueError("One or both files are empty.")

    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found: {e}")
    except (IOError, OSError) as e:
        raise Exception(f"IO related error: {e}")

    diff = list(ndiff(rows1, rows2))
    results = []
    for i, line in enumerate(diff):
        status = ''
        content = ''
        if line.startswith('  '):
            status = ' '
            content = line[3:].strip()
        elif line.startswith('- '):
            status = '-'
            content = line[2:].strip()
        elif line.startswith('+ '):
            status = '+'
            content = line[2:].strip()
        else:
            continue
        
        # The content in the test expectation is str(tuple)
        # But ndiff gives us the string representation of the tuple if we pass tuples to it.
        # Wait, let's check what ndiff does with tuples.
        # If I pass a list of tuples to ndiff, it should return strings like "  ('name', 'age')"
        # Let's refine content extraction.
        
        # Actually, the test expectation is:
        # expect = ["1, ,('name', 'age')", "2,-,('Alice', '30')", "3,+,('Alice', '31')", "4, ,('Bob', '25')"]
        # This means content should be exactly what ndiff returns after the prefix.
        
        # Let's re-extract content correctly.
        if line.startswith('  '):
            content = line[2:]
        elif line.startswith('- '):
            content = line[2:]
        elif line.startswith('+ '):
            content = line[2:]
        else:
            continue

        results.append({
            'Line Number': i + 1,
            'Status': status,
            'Content': content
        })

    df = pd.DataFrame(results)
    return df
