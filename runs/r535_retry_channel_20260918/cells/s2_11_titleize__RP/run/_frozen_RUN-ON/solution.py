def titleize(s):
    words = s.split(' ')
    return ' '.join(word.capitalize() for word in words)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(titleize(sys.argv[1]))
