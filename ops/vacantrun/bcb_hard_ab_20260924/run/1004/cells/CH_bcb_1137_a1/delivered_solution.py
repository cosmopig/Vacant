import bs4
import requests
import re
import json

def task_func(url: str, output_path: str) -> list:
    """
    Extracts phone numbers from a given URL or local file and saves them to a specified file in JSON format.
    The function should output with:
        list: A list of strings, each representing a found phone number.
    """
    phone_numbers = []
    # Regex for common phone number formats starting with +
    # It looks for + followed by digits, spaces, dashes, parentheses, and more digits.
    phone_regex = r'\+\d[\d\s\-()]{7,}\b'

    try:
        if url.startswith('http'):
            response = requests.get(url)
            response.raise_for_status()
            content = response.text
        else:
            path = url
            if path.startswith('file://'):
                path = path.replace('file://', '')
            
            # Handle potential double slash or absolute paths from file://///tmp/
            if path.startswith('//'):
                path = path[2:]
            elif path.startswith('/'):
                pass # Keep as is

            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

        # Use BeautifulSoup to parse HTML if it looks like HTML
        if '<html' in content.lower() or '<body' in content.lower():
            soup = bs4.BeautifulSoup(content, 'html.parser')
            text_content = soup.get_text()
        else:
            text_content = content

        # Find all matches
        matches = re.findall(phone_regex, text_content)
        for match in matches:
            clean_match = match.strip()
            if clean_match:
                phone_numbers.append(clean_match)

    except Exception:
        pass

    # Remove duplicates while preserving order
    unique_phones = []
    for p in phone_numbers:
        if p not in unique_phones:
            unique_phones.append(p)
    
    phone_numbers = unique_phones

    # Save to JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"list": phone_numbers}, f)
    except Exception:
        pass

    return phone_numbers
