import requests
from lxml import html
import pandas as pd
import sqlite3

def task_func(webpage_url: str, database_name: str = "my_database.db") -> int:
    # Fetch content
    try:
        if webpage_url.startswith('http'):
            response = requests.get(webpage_url)
            response.raise_for_status()
            html_content = response.text
        else:
            with open(webpage_url, 'r', encoding='utf-8') as f:
                html_content = f.read()
    except requests.RequestException:
        raise

    # Parse tables
    try:
        dfs = pd.read_html(html_content)
        if not dfs:
            return 0
        df = dfs[0]
        if df.empty:
            return 0
    except ValueError:
        # This is raised by pandas if no tables are found
        return 0
    except Exception:
        # Other parsing errors return 0 as per "If the HTML content does not contain a table... return 0"
        return 0

    # Database operations
    try:
        conn = sqlite3.connect(database_name)
        try:
            df.to_sql('my_table', conn, if_exists='replace', index=False)
            return len(df)
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        raise e
