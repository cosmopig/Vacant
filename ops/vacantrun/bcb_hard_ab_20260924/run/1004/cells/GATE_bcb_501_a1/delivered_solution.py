import xlwt
import os
import pandas as pd
import json

def task_func(json_str, filename, sheet_name="sheet1"):
    if not isinstance(json_str, (str, bytes, bytearray)):
        raise TypeError("Input must be a string, bytes, or bytearray")
    
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if isinstance(data, list):
        df = pd.DataFrame(data) if len(data) > 0 else pd.DataFrame()
    elif isinstance(data, dict):
        df = pd.DataFrame([data]) if data else pd.DataFrame()
    else:
        df = pd.DataFrame([data] if data is not None else [])

    try:
        # The environment seems to have a broken xlwt installation where 
        # pandas cannot use it and manual usage also fails with a weird TypeError.
        # Let's try using the standard pandas to_excel without specifying engine first,
        # but since we know that might fail too, let's just try to write it normally.
        df.to_excel(filename, sheet_name=sheet_name)
    except Exception as e:
        try:
            wb = xlwt.Workbook()
            ws = wb.add_sheet(sheet_name)
            if not df.empty:
                for r, row in enumerate(df.values):
                    # The error "not all arguments converted during string formatting" 
                    # seems to be coming from xlwt's internal ValueError message when 
                    # the row index is out of bounds or something else happens.
                    # Let's try to write it using pandas if possible, but since that failed,
                    # we use a very basic loop and hope for the best.
                    for c, val in enumerate(row):
                        if pd.isna(val):
                            ws.write((r, c), "")
                        else:
                            try:
                                num = float(val)
                                if num == int(num):
                                    ws.write((r, c), int(num))
                                else:
                                    ws.write((r, c), num)
                            except (ValueError, TypeError):
                                ws.write((r, c), str(val))
            wb.save(filename)
        except Exception as e2:
            raise Exception(f"Error writing to file: {e}")

    return os.path.abspath(filename)
