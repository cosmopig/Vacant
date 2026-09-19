def strip_comments(text):
    lines = text.split('\n')
    result = []
    for line in lines:
        if '#' in line:
            content = line[:line.find('#')]
            result.append(content.rstrip())
        else:
            result.append(line)
    return '\n'.join(result)
