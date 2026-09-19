def longest_run(s):
    best_ch, best_n = s[0], 0
    cur_ch, cur_n = None, 0
    for c in s:
        if c == cur_ch:
            cur_n += 1
        else:
            cur_ch, cur_n = c, 1
        if cur_n > best_n:
            best_ch, best_n = cur_ch, cur_n
    return {"ch": best_ch, "n": best_n}
