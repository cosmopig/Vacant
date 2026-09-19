def strip_comments(text):
    lines = text.split('\n')
    result = []
    for line in lines:
        if '#' in line:
            content = line.split('#', 1)[0]
            result.append(content.rstrip())
        else:
            result.append(line)
    return '\n'.join(result)
