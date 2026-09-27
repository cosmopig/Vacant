def countArrays(original, bounds):
    n = len(original)
    L = -float('inf')
    R = float('inf')
    
    for i in range(n):
        u_i, v_i = bounds[i]
        # copy[i] = x + original[i] - original[0]
        # u_i <= x + original[i] - original[0] <= v_i
        # u_i - (original[i] - original[0]) <= x <= v_i - (original[i] - original[0])
        l_i = u_i - (original[i] - original[0])
        r_i = v_i - (original[i] - original[0])
        
        if l_i > L:
            L = l_i
        if r_i < R:
            R = r_i
            
    if L > R:
        return 0
    else:
        return int(R - L + 1)
