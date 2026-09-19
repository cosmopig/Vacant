def strip_comments(text):
    lines = text.splitlines()
    result = []
    for line in lines:
        if '#' in line:
            parts = line.split('#', 1)
            # The part before the hash is what we keep, but we must strip trailing whitespace
            content = parts[0].rstrip()
            result.append(content)
        else:
            # No hash in the line, just strip trailing whitespace
            result.append(line.rstrip())
    return "\n".join(result)

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    print(strip_comments(input_text))
