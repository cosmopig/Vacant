def column(rows, field):
    """
    Pulls one field out of every row of a list of lookups, in order, 
    and gives back a list.

    The result is written out as one column of a table whose other columns 
    come from the same rows, so the rows and the entries have to stay lined up.
    """
    return [row[field] for row in rows]
