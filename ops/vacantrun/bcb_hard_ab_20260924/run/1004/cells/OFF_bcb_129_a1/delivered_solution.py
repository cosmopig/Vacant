import requests
from bs4 import BeautifulSoup
import pandas as pd

def task_func(url='http://example.com'):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Issue connecting to {url}") from e
    except requests.exceptions.HTTPError as e:
        raise e

    # Use response.text and ensure it's a string for BeautifulSoup
    content = str(response.text) if response.text is not None else ""
    soup = BeautifulSoup(content, 'html.parser')
    table = soup.find('table')
    
    if not table:
        raise ValueError("No table found on the page.")

    rows = table.find_all('tr')
    if not rows:
        raise ValueError("No table data found on the page.")

    data = []
    headers = None

    # Check if first row has <th> elements for headers
    first_row = rows[0]
    th_elements = first_row.find_all('th')
    
    if th_elements:
        headers = [th.get_text(strip=True) for th in th_elements]
        # If the first row is headers, we start data from second row
        data_rows = rows[1:]
    else:
        # No <th> elements in first row, check if it's just a header-like row with <td>
        # But goal says "named after the table's header row (<th> elements), if present"
        data_rows = rows

    for row in data_rows:
        cells = row.find_all(['td', 'th'])
        if cells:
            data.append([cell.get_text(strip=True) for cell in cells])

    if not data:
        raise ValueError("No table data found on the page.")

    df = pd.DataFrame(data, columns=headers)
    return df
