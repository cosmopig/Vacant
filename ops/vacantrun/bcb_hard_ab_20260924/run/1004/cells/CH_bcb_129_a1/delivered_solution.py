import requests
from bs4 import BeautifulSoup
import pandas as pd

def task_func(url='http://example.com'):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ConnectionError("If there is an issue connecting to the URL.")
    except requests.exceptions.HTTPError as e:
        raise e

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    
    if not table:
        raise ValueError("No table data was found on the page or if the page content cannot be parsed.")

    rows = table.find_all('tr')
    if not rows:
        raise ValueError("No table data was found on the page or if the page content cannot be parsed.")

    data = []
    headers = None

    # Find headers first
    th_elements = table.find_all('th')
    if th_elements:
        for row in rows:
            ths = row.find_all('th')
            if ths:
                headers = [th.get_text(strip=True) for th in ths]
                break

    # Extract all data from all <tr>
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue
        row_data = [cell.get_text(strip=True) for cell in cells]
        data.append(row_data)

    if not data:
        raise ValueError("No table data was found on the page or if the page content cannot be parsed.")

    if headers:
        # If we have headers, but some rows might have different number of columns (e.g. due to colspans)
        # Pandas will handle it if we provide column names.
        df = pd.DataFrame(data, columns=headers)
    else:
        df = pd.DataFrame(data)

    return df
