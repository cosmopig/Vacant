import requests
from lxml import html
import pandas as pd
import sqlite3

def task_func(webpage_url: str, database_name: str = "my_database.db") -> int:
    try:
        # Fetch the content from the URL
        response = requests.get(webpage_url)
        response.raise_for_status()
        html_content = response.text
    except requests.RequestException:
        raise

    # Parse HTML content
    tree = html.fromstring(html_content)
    
    # Find all tables
    tables = tree.xpath('//table')
    if not tables:
        return 0
    
    dfs = []
    for table in tables:
        try:
            df_list = pd.read_html(str(table))
            if df_list:
                dfs.append(df_list[0])
        except Exception:
            continue
    
    if not dfs:
        return 0
    
    # Use the first non-empty dataframe found
    df = None
    for d in dfs:
        if not d.empty:
            df = d
            break
    
    if df is None or df.empty:
        return 0

    try:
        conn = sqlite3.connect(database_name)
        # Replace the table 'my_table'. This means dropping it if it exists and creating a new one.
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS my_table")
        df.to_sql("my_table", conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()
    except sqlite3.DatabaseError:
        raise

    return len(df)
