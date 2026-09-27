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
    except Exception:
        html = b""

    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='data-table')
    
    data = []
    if table:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if cells:
                data.append([cell.get_text(strip=True) for cell in cells])

    with open(CSV_FILE_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if data:
            writer.writerows(data)
            
    return CSV_FILE_PATH
