import re
import pandas as pd
from datetime import datetime

def task_func(log_file):
    # Regex to match 'TYPE: [YYYY-MM-DD HH:MM:SS] - MESSAGE'
    # Example: INFO: [2023-10-27 10:00:00] - System started
    pattern = re.compile(r'^(\w+):\s\[(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\]\s-\s(.*)$')
    
    data = []
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if match:
                msg_type, timestamp_str, message = match.groups()
                try:
                    # Validate timestamp format
                    dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    data.append({
                        'Type': msg_type,
                        'Timestamp': dt,
                        'Message': message
                    })
                except ValueError:
                    raise ValueError("Invalid timestamp in log entry.")

    if not data:
        raise ValueError("No valid log entries found.")

    df = pd.DataFrame(data)
    # Ensure Timestamp is sorted if needed, though usually logs are sequential
    # df = df.sort_values(by='Timestamp')

    output_file = "structured_logs.csv"
    df.to_csv(output_file, index=False)
    return output_file
