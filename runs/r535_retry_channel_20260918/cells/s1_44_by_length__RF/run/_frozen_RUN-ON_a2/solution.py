def sort_words(words):
    return sorted(words, key=len)

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().split()
    sorted_list = sort_words(input_data)
    for word in sorted_list:
        print(word)
