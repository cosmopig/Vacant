import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import csv
def task_func(
    url: str,
    base_url: str = "https://www.example.com",
    csv_file: str = "scraped_data.csv",
) -> int:
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception:
        return 0

    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('a', href=True)
    
    unique_links = set()
    for link in links:
        href = link['href']
        absolute_url = urljoin(base_url, href)
        # Normalize the URL to remove fragments and trailing slashes for uniqueness if they are considered same
        # However, usually "absolute URLs" means exactly what's joined. 
        # Let's stick to basic join first as per common scraping tasks.
        unique_links.add(absolute_url)

    with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for link in sorted(list(unique_links)):
            writer.writerow([link])

    return len(unique_links)
