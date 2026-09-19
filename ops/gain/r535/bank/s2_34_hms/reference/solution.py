def hms(seconds):
    if seconds < 0:
        raise ValueError("seconds must not be negative")
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)
