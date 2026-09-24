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
        raise e

    if not content:
        return {}

    if from_encoding is None:
        detection = chardet.detect(content)
        from_enc = detection.get('encoding')
        # If encoding is missing or confidence is 0 (if it exists), raise error
        confidence = detection.get('confidence', 1)
        if from_enc is None or confidence == 0:
            raise ValueError("Unable to detect encoding for non-empty content")
    else:
        from_enc = from_encoding

    try:
        decoded_data = content.decode(from_enc)
    except (LookupError, UnicodeDecodeError):
        raise ValueError("Unable to detect encoding for non-empty content")

    # Re-encode to the target encoding and then decode back to string for json.loads
    re_encoded_bytes = decoded_data.encode(to_encoding)
    final_string = re_encoded_bytes.decode(to_encoding)
    
    return json.loads(final_string)
