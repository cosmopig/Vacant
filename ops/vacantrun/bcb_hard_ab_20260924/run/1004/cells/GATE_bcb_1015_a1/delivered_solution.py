import requests
from lxml import html
import pandas as pd
import sqlite3

def task_func(webpage_url: str, database_name: str = "my_database.db") -> int:
    try:
        # Fetch the content from the URL or local file
        response = requests.get(webpage_url)
        response.raise_for_status()
        content = response.text
        
        if not isinstance(content, (str, bytes)):
            return 0
    except requests.RequestException:
        raise

    # Parse HTML content
    try:
        tree = html.fromstring(content)
    except Exception:
        return 0
    
    # Find all tables
    tables = tree.xpath('//table')
    if not tables:
        return 0
    
    # The goal says "replace the table 'my_table'". This is slightly ambiguous.
    target_table = None
    for table in tables:
        if 'my_table' in table.get('id', '') or 'my_table' in table.get('class', ''):
            target_table = table
            break
    
    # If no specific "my_table" found, use the first one as a fallback? 
    if target_table is None and tables:
        target_table = tables[0]

    if target_table is None:
        return 0

    try:
        # Use pandas to read the table into a DataFrame
        table_str = str(target_table)
        dfs = pd.read_html(table_str)
        if not dfs or not isinstance(dfs, list):
            return 0
        df = dfs[0]
        
        if df.empty:
            return 0

        # Connect to SQLite database
        conn = sqlite3.connect(database_name)
        
        try:
            conn.execute("DROP TABLE IF EXISTS my_table")
        except sqlite3.DatabaseError:
            pass

        # Write the dataframe to "my_table"
        df.to_sql('my_table', conn, if_exists='replace', index=False)
        
        conn.close()
        return len(df)
    except sqlite3.DatabaseError as e:
        raise e
    except Exception:
        # The goal says "If the HTML content does not contain a table or if the table is empty, 
        # the function will return 0". It doesn't specify what to do for other errors like ValueError from pd.read_html.
        return 0
