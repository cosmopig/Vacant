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
        df = pd.DataFrame(data) if data else pd.DataFrame()
    else:
        df = pd.DataFrame([data])

    try:
        # Try pandas first
        try:
            df.to_excel(filename, sheet_name=sheet_name, engine='xlwt', index=False)
        except ValueError as e:
            if "No Excel writer 'xlwt'" in str(e):
                # Fallback to manual xlwt if pandas fails to find the engine
                wb = xlwt.Workbook()
                ws = wb.add_sheet(sheet_name)
                if not df.empty:
                    for col_num, col_name in enumerate(df.columns):
                        ws.write(0, col_num, str(col_name))
                    for row_num, row_data in enumerate(df.values, start=1):
                        for col_num, value in enumerate(row_data):
                            # xlwt write takes (x, y, value) as separate arguments
                            ws.write(row_num, col_num, value)
                wb.save(filename)
            else:
                raise e
    except Exception as e:
        raise Exception(f"Error writing to file: {e}")

    return os.path.abspath(filename)
