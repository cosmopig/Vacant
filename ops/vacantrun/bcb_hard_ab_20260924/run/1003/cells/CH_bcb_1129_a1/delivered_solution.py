import json
import requests
import os
from datetime import datetime

def task_func(json_data, unknown_key, save_dir=None):
    # Parse the JSON string to a dictionary
    data = json.loads(json_data)
    
    # Find the URL associated with the specified key
    url = data.get(unknown_key)
    if not url:
        return None

    # Get current timestamp in the required format
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    # Construct filename: {unknown_key}_{timestamp}.txt
    filename = f"{unknown_key}_{timestamp}.txt"
    
    # Determine save directory
    if save_dir is None:
        save_dir = os.getcwd()
    else:
        # Ensure the directory exists
        os.makedirs(save_dir, exist_ok=True)

    # Download the file content from the URL
    response = requests.get(url)
    
    # Save the file to the specified directory
    file_path = os.path.join(save_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(response.content)
    
    # Return the absolute path of the downloaded file
    return os.path.abspath(file_path)
