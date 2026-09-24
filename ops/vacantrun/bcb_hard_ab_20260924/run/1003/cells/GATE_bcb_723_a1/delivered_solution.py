import urllib.request
from bs4 import BeautifulSoup
import csv
import os
# Constants
CSV_FILE_PATH = 'scraped_data.csv'
def task_func(url):
    try:
        with urllib.request.urlopen(url) as response:
            html = response.read()
    except Exception:
        html = ""

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='data-table')
    
    rows = []
    if table:
        for tr in table.find_all('tr'):
            cells = [td.get_text().strip() for td in tr.find_all('td')]
            if cells:
                rows.append(cells)

    with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if rows:
            writer.writerows(rows)
            
    return CSV_FILE_PATH
