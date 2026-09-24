import requests
from lxml import html
import pandas as pd
import sqlite3

def task_func(webpage_url: str, database_name: str = "my_database.db") -> int:
    try:
        # Fetch the content from URL or local file
        if webpage_url.startswith("http"):
            response = requests.get(webpage_url)
            response.raise_for_status()
            content = response.text
        else:
            with open(webpage_url, 'r', encoding='utf-8') as f:
                content = f.read()

        # Parse the HTML content
        tree = html.fromstring(content)
        
        # Find all tables in the HTML
        tables = tree.xpath('//table')
        if not tables:
            return 0
        
        # The goal says "replace the table 'my_table'". 
        # Usually, this implies finding a specific table or just processing the first one if it's intended to be 'my_table'.
        # If multiple tables exist, we need to decide which one. 
        # Given the prompt says "replace the table 'my_table'", it might mean a table with an ID or class of 'my_table'.
        
        target_table = None
        for table in tables:
            if table.get('id') == 'my_table' or table.get('class') == 'my_table':
                target_table = table
                break
        
        # If no specific 'my_table' found, use the first table as a fallback? 
        # Or maybe it means the only table if there is only one.
        if not target_table and len(tables) > 0:
            target_table = tables[0]

        if not target_table:
            return 0

        # Use pandas to read the table into a DataFrame
        df = pd.read_html(str(target_table))[0]
        
        if df.empty:
            return 0

        # Connect to SQLite database
        conn = sqlite3.connect(database_name)
        try:
            # Replace the table 'my_table' in the specified SQLite database with new data each time it is called.
            # This means we should drop the existing table if it exists and create a new one, or just replace its content.
            # "Replace" usually implies dropping and recreating or truncating and inserting. 
            # Given "replace the table", DROP TABLE IF EXISTS followed by CREATE TABLE is safest to ensure schema matches DF.
            
            cursor = conn.cursor()
            # We need a name for the table in the DB. The prompt says "the table 'my_table'".
            # So we assume the table name in the database is also 'my_table'.
            cursor.execute("DROP TABLE IF EXISTS my_table")
            df.to_sql('my_table', conn, if_exists='replace', index=False)
            
            return len(df)
        finally:
            conn.close()

    except requests.RequestException:
        raise
    except sqlite3.DatabaseError:
        # The test expects DatabaseError to be raised. 
        # If it's caught here, we must re-raise it.
        raise
    except Exception:
        return 0
