import json
import requests
import os
from datetime import datetime

def task_func(json_data, unknown_key, save_dir=None):
    # Parse the JSON string
    data = json.loads(json_data)
    
    # Find the URL associated with the specified key
    url = data.get(unknown_key)
    if not url:
        return None

    # Get current timestamp in the required format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    # Construct the filename
    filename = f"{unknown_key}_{timestamp}.txt"
    
    # Determine save directory
    if save_dir is None:
        save_dir = os.getcwd()
    else:
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

    # Full path for saving the file
    file_path = os.path.join(save_dir, filename)
    
    # Download and save the file
    response = requests.get(url)
    
    # Check for success if status_code is available, otherwise assume success (for mocks)
    if not hasattr(response, 'status_code') or response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
        return os.path.abspath(file_path)
    else:
        return None
