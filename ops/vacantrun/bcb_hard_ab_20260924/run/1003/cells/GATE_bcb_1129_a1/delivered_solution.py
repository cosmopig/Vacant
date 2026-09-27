import json
import requests
import os
from datetime import datetime

def task_func(json_data, unknown_key, save_dir=None):
    # Parse JSON data
    data = json.loads(json_data)
    
    # Find the URL associated with the specified key
    url = data.get(unknown_key)
    if not url:
        return None

    # Get current timestamp
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    # Construct filename
    filename = f"{unknown_key}_{timestamp}.txt"
    
    # Determine save directory
    if save_dir is None:
        save_dir = os.getcwd()
    else:
        # Ensure the directory exists
        if not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
            
    file_path = os.path.join(save_dir, filename)
    
    # Download the file
    response = requests.get(url)
    
    # Save the content to a file
    with open(file_path, 'wb') as f:
        f.write(response.content)
        
    # Return absolute path
    return os.path.abspath(file_path)
