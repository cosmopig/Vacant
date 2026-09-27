import urllib.request
from bs4 import BeautifulSoup
import csv
import os
# Constants
CSV_FILE_PATH = 'scraped_data.csv'
def task_func(url):
    try:
        response = urllib.request.urlopen(url)
        html = response.read()
        response.close()
    except Exception:
        html = b""

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='data-table')
    
    rows_to_write = []
    if table:
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data:
                rows_to_write.append(row_data)

    with open(CSV_FILE_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if rows_to_write:
            writer.writerows(rows_to_write)
        else:
            pass

    return CSV_FILE_PATH
