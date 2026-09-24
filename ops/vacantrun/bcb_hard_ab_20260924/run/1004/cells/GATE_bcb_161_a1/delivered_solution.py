import re
import pandas as pd
from datetime import datetime

def task_func(log_file):
    log_pattern = re.compile(r'(\w+): \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] - (.*)')
    data = []
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                match = log_pattern.match(line.strip())
                if match:
                    msg_type, timestamp_str, message = match.groups()
                    try:
                        # Validate timestamp format
                        datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        data.append({
                            'Type': msg_type,
                            'Timestamp': timestamp_str,
                            'Message': message
                        })
                    except ValueError:
                        raise ValueError(f"Invalid timestamp format in log entry: {timestamp_str}")
                else:
                    # If a line doesn't match the pattern, we skip it or could raise an error. 
                    # The goal says "Extracts logging information... from a log file".
                    # Usually this implies lines that don't match are ignored unless specified otherwise.
                    pass

        if not data:
            raise ValueError("No valid log entries found.")

        df = pd.DataFrame(data)
        output_file = 'structured_logs.csv'
        df.to_csv(output_file, index=False)
        return output_file

    except FileNotFoundError:
        # The goal doesn't specify what to do if file is missing, 
        # but usually we let it bubble up or handle as needed.
        raise
