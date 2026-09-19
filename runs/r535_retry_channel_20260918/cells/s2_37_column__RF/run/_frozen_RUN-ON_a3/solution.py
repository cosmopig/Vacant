def column(rows, field):
    """
    Pulls one field out of every row of a list of lookups, in order, 
    and gives back a list.

    The result is written out as one column of a table whose other columns 
    come from the same rows, so the rows and the entries have to stay lined up.

    Args:
        rows (list): A list of dictionaries representing rows in a table.
        field (str): The key of the field to extract.

    Returns:
        list: A list of values for the specified field from each row.
    """
    return [row[field] for row in rows]
