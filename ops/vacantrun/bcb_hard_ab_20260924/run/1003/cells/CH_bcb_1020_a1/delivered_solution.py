import json
import requests
import chardet

# Constants
API_URL = "http://api.example.com/data"

def task_func(url=API_URL, from_encoding=None, to_encoding="utf8"):
    try:
        response = requests.get(url, timeout=5)
        content = response.content
    except Exception as e:
        # The goal doesn't specify what to do if the request fails, 
        # but usually we let it propagate or handle it. 
        # Given the instructions, I'll just let it be.
        raise e

    if not content:
        return {}

    if from_encoding is None:
        detection = chardet.detect(content)
        from_encoding = detection['encoding']
        if from_encoding is None:
            raise ValueError("Unable to detect encoding for non-empty content")

    # Decode the content using the detected or provided encoding
    decoded_data = content.decode(from_encoding)

    # Re-encode the data to the target encoding
    re_encoded_data = decoded_data.encode(to_encoding)

    # Parse and return as JSON
    return json.loads(re_encoded_data)
