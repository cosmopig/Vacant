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
    
    # Regex for common phone number formats (international and domestic)
    # This pattern looks for numbers starting with + or digits, followed by 7-15 digits total,
    # allowing for spaces, dots, hyphens, and parentheses.
    phone_regex = r'\+?\d[\d\s.-]{7,}\d'

    try:
        if url.startswith('http'):
            response = requests.get(url)
            response.raise_for_status()
            content = response.text
        else:
            # Handle file:// URLs or local paths
            path = url.replace('file://', '')
            if path.startswith('/'):
                path = path[1:]
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

        # Parse HTML if it looks like HTML
        if '<html' in content.lower() or '<body' in content.lower():
            soup = bs4.BeautifulSoup(content, 'html.parser')
            text_content = soup.get_text()
        else:
            text_content = content

        # Find all matches
        matches = re.findall(phone_regex, text_content)
        for match in matches:
            # Clean up the match to remove extra whitespace/punctuation if needed
            clean_match = re.sub(r'\s+', ' ', match).strip()
            if clean_match:
                phone_numbers.append(clean_match)

    except Exception as e:
        pass

    # Remove duplicates and preserve order
    unique_phones = []
    for p in phone_numbers:
        if p not in unique_phones:
            unique_phones.append(p)
    phone_numbers = unique_phones

    # Save to JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"list": phone_numbers}, f, indent=4)
    except Exception as e:
        pass

    return phone_numbers
