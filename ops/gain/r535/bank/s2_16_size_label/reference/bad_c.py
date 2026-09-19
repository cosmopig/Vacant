def human_size(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1024 and i < 3:
        v /= 1024
        i += 1
    if i == 0:
        return "%d B" % n
    return "%.1f %s" % (v, units[i])
