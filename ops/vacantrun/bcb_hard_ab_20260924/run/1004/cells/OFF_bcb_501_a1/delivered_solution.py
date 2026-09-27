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

    # Ensure filename ends with .xls for xlwt
    if not filename.lower().endswith('.xls'):
        filename += '.xls'

    try:
        # Try using pandas first as it is the standard way to handle this
        df.to_excel(filename, sheet_name=sheet_name, index=False, engine='xlwt')
    except Exception:
        try:
            # Fallback to manual xlwt writing if pandas' engine selection fails or behaves unexpectedly
            wb = xlwt.Workbook()
            ws = wb.add_sheet(sheet_name)
            if not df.empty:
                for col_num, col_name in enumerate(df.columns):
                    # Use write(row, col, value)
                    ws.write(0, col_num, str(col_name))
                for row_num, row_data in enumerate(df.values, start=1):
                    for col_num, value in enumerate(row_data):
                        # Use write(row, col, value)
                        ws.write(row_num, col_num, value)
            wb.save(filename)
        except Exception as e2:
            raise Exception(f"Error writing to file: {e2}")

    return os.path.abspath(filename)
