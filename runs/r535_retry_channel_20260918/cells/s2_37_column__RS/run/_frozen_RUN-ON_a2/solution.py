def column(rows, field):
    """
    Pulls one field out of every row of a list of lookups, in order, 
    and gives back a list. The result is written out as one column of 
    a table whose other columns come from the same rows, so the rows 
    and the entries have to stay lined up.

    Args:
        rows (list): A list of dictionaries representing rows in a table.
        field (str): The key to extract from each dictionary.

    Returns:
        list: A list of values corresponding to the specified field for each row.
    """
    return [row[field] for row in rows if field in row]
