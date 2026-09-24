import requests
import os
import zipfile
def task_func(url, destination_directory, headers=None):
    if not os.path.exists(destination_directory):
        os.makedirs(destination_directory)
    
    # Determine the zip filename from the URL
    zip_filename = os.path.basename(url.split('?')[0])
    if not zip_filename.endswith('.zip'):
        zip_filename += '.zip'
    
    zip_path = os.path.join(destination_directory, zip_filename)
    
    # Download the zip file
    response = requests.get(url, headers=headers, stream=True)
    response.raise_for_status()
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    # Extract the zip file
    extracted_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(destination_directory)
        extracted_files = zip_ref.namelist()
    
    return extracted_files
