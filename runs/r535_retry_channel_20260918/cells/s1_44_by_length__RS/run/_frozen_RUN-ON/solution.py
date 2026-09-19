def sort_words(words):
    # Python's sort is stable, so we only need to sort by length.
    return sorted(words, key=len)

if __name__ == "__main__":
    import sys
    # The task doesn't specify how input is provided, 
    # but usually it's from stdin or as arguments.
    # Let's assume words are passed as command line arguments.
    words = sys.argv[1:]
    sorted_words = sort_words(words)
    print(" ".join(sorted_words))
