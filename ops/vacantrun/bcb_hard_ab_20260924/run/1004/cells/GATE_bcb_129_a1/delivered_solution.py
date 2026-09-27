import requests
from bs4 import BeautifulSoup
import pandas as pd

def task_func(url='http://example.com'):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError("If there is an issue connecting to the URL.") from e
    except requests.exceptions.HTTPError as e:
        raise requests.HTTPError(f"If the HTTP request to the URL fails: {e}") from e

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    
    if not table:
        raise ValueError("If no table data is found on the page or if the page content cannot be parsed.")

    rows = table.find_all('tr')
    if not rows:
        raise ValueError("If no table data is found on the page or if the page content cannot be parsed.")

    data = []
    headers = []
    
    # Check for header row (usually first row)
    first_row = rows[0]
    ths = first_row.find_all('th')
    if ths:
        headers = [th.get_text(strip=True) for th in ths]
        data_rows = rows[1:]
    else:
        data_rows = rows

    for row in data_rows:
        cells = row.find_all(['td', 'th'])
        if cells:
            row_data = [cell.get_text(strip=True) for cell in cells]
            data.append(row_data)

    if not data:
        raise ValueError("If no table data is found on the page or if the page content cannot be parsed.")

    df = pd.DataFrame(data, columns=headers if headers else None)
    return df
