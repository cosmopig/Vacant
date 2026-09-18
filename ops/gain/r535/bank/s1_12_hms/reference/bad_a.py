def hms(total_seconds):
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return "%02d:%02d:%02d" % (h, m, s)
