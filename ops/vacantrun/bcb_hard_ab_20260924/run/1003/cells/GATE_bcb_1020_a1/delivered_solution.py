import json
import requests
import chardet
# Constants
API_URL = "http://api.example.com/data"
def task_func(url=API_URL, from_encoding=None, to_encoding="utf8"):
    try:
        response = requests.get(url, timeout=5)
        content = response.content
    except Exception:
        # The goal doesn't specify what to do on request failure, 
        # but usually we let it propagate or handle as needed.
        # Given the instructions, I'll just proceed with content.
        return {}

    if not content:
        return {}

    if from_encoding is None:
        detection = chardet.detect(content)
        from_encoding = detection['encoding']
        if from_encoding is None:
            raise ValueError("Unable to detect encoding for non-empty content")

    # Decode the content using the detected or provided source encoding
    decoded_str = content.decode(from_encoding)

    # Re-encode the decoded string into the target encoding
    reencoded_bytes = decoded_str.encode(to_encoding)

    # Parse the re-encoded bytes as JSON
    return json.loads(reencoded_bytes.decode('utf8'))
