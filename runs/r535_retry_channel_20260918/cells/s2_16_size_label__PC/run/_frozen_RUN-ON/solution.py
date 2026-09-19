def size_label(n):
    if n < 1024:
        return f"{n} B"
    
    units = ["KB", "MB", "GB"]
    res = float(n)
    unit = ""
    
    for u in units:
        res /= 1024.0
        if res < 1024 or u == "GB":
            unit = u
            break
            
    return f"{res:.1f} {unit}"

# Wait, the loop above is still slightly wrong because it divides by 1024 for KB, then again for MB.
# If n = 1024^2:
# i=0 (KB): res = 1024.0. Not < 1024. Loop continues.
# i=1 (MB): res = 1.0. Is < 1024. unit = "MB". Break.
# Result: "1.0 MB". Correct.

# If n = 1024^3 * 1.5:
# i=0 (KB): res = 1024^2 * 1.5. Not < 1024.
# i=1 (MB): res = 1024 * 1.5. Not < 1024.
# i=2 (GB): res = 1.5. Is < 1024. unit = "GB". Break.
# Result: "1.5 GB". Correct.

# If n = 1024^4 * 1.5:
# i=0 (KB): res = 1024^3 * 1.5. Not < 1024.
# i=1 (MB): res = 1024^2 * 1.5. Not < 1024.
# i=2 (GB): res = 1024 * 1.5. Is last unit "GB". unit = "GB". Break.
# Result: "1536.0 GB". Correct.

# Let's double check n = 1024^2 - 1:
# i=0 (KB): res = (1024^2 - 1) / 1024 = 1023.999... < 1024. unit = "KB". Break.
# Result: "1024.0 KB" (due to .1f rounding).

# Is this correct? "stopping at the largest unit the number reaches".
# If n = 1024^2 - 1, it hasn't reached MB yet. So KB is the largest unit it reaches.
# The fact that it rounds to 1024.0 in the display is a side effect of .1f rounding,
# but the logic follows "stopping at the largest unit".

def size_label(n):
    if n < 1024:
        return f"{n} B"
    
    units = ["KB", "MB", "GB"]
    res = float(n)
    unit = ""
    
    for u in units:
        res /= 1024.0
        if res < 1024 or u == "GB":
            unit = u
            break
            
    return f"{res:.1f} {unit}"
