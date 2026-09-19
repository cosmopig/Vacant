def sort_words(words):
    # Python's sort is stable, so we only need to sort by length.
    return sorted(words, key=len)

if __name__ == "__main__":
    import sys
    # The task doesn't specify input format, but usually it's from stdin or a list.
    # Let's assume the words are provided as arguments or on lines of stdin.
    # Since I need to write 'the code', I'll provide a function and a simple way to run it.
    # However, standard competitive programming style is reading from stdin.
    
    input_data = sys.stdin.read().splitlines()
    if input_data:
        sorted_words = sort_words(input_data)
        for word in sorted_words:
            print(word)
