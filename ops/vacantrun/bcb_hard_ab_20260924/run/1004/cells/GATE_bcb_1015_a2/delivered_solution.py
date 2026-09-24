import requests
from lxml import html
import pandas as pd
import sqlite3

def task_func(webpage_url: str, database_name: str = "my_database.db") -> int:
    try:
        # Fetch the content from the URL or local file
        if webpage_url.startswith('http'):
            response = requests.get(webpage_url)
            response.raise_for_status()
            html_content = response.text
        else:
            with open(webpage_url, 'r', encoding='utf-8') as f:
                html_content = f.read()
    except requests.RequestException:
        raise
    except FileNotFoundError:
        # The goal doesn't specify what to do if local file is missing, 
        # but usually we should let it propagate or handle it.
        # Given the prompt says "URL or local file", I'll just let it raise.
        raise

    try:
        # Parse HTML content and find tables
        all_dfs = pd.read_html(html_content)
        if not all_dfs:
            return 0
        
        target_df = all_dfs[0]
        
        if target_df.empty:
            return 0

        # Connect to SQLite database
        conn = sqlite3.connect(database_name)
        try:
            # "replace the table 'my_table' in the specified SQLite database with new data"
            target_df.to_sql('my_table', conn, if_exists='replace', index=False)
            return len(target_df)
        finally:
            conn.close()

    except sqlite3.DatabaseError as e:
        # The goal says "The function should raise the exception for: ... sqlite3.DatabaseError"
        raise e
    except Exception:
        # If pandas fails to parse any tables, return 0 as per goal
        return 0
