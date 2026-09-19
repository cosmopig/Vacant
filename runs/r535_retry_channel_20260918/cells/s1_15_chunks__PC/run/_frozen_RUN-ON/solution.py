def chunks(xs, n):
    """
    Cut a list into consecutive pieces of a given maximum size, in order.

    The last piece is whatever is left over and may be shorter than the others.
    All the pieces come back gathered in one list, and each piece is itself a list.

    Args:
        xs (list): The input list to chunk.
        n (int): The maximum size of each chunk.

    Returns:
        list[list]: A list of lists containing the chunks.
    """
    if n <= 0:
        raise ValueError("Chunk size must be greater than zero.")
    
    return [xs[i : i + n] for i in range(0, len(xs), n)]
