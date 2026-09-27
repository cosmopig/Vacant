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
    
    # Regex for common phone number formats (e.g., +1-234-567-8901, (123) 456-7890, 123-456-7890, etc.)
    phone_regex = r'\+?\d[\d\-\(\)\s]{7,}\d'

    try:
        if url.startswith('http'):
            response = requests.get(url)
            response.raise_for_status()
            content = response.text
        else:
            with open(url, 'r', encoding='utf-8') as f:
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
            cleaned_match = match.strip()
            if any(char.isdigit() for char in cleaned_match):
                refined_match = "".join([c for c in cleaned_match if c.isdigit() or c in '+-(). ']).strip()
                # Ensure it's not just symbols and has some digits
                if refined_match and any(char.isdigit() for char in refined_match):
                    if refined_match not in phone_numbers:
                        phone_numbers.append(refined_match)

    except Exception as e:
        pass

    # Save to JSON file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"list": phone_numbers}, f)
    except Exception:
        pass

    return phone_numbers
