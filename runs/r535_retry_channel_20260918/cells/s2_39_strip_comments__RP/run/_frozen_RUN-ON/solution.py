def strip_comments(text):
    lines = []
    for line in text.splitlines():
        if '#' in line:
            parts = line.split('#', 1)
            content = parts[0].rstrip()
            lines.append(content)
        else:
            lines.append(line)
    return '\n'.join(lines)

if __name__ == "__main__":
    import sys
    input_text = sys.stdin.read()
    if input_text:
        print(strip_comments(input_text), end="")
