def size_label(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    v = float(n)
    while v >= 1000 and i < 3:
        v /= 1000
        i += 1
    if i == 0:
        return "%d B" % n
    return "%.1f %s" % (v, units[i])
