def countArrays(original, bounds):
    n = len(original)
    if n == 0:
        return 0
    
    # The condition (copy[i] - copy[i-1]) == (original[i] - original[i-1])
    # implies that copy[i] = copy[0] + (original[i] - original[0]).
    # Let S_i = original[i] - original[0]. Then copy[i] = copy[0] + S_i.
    # The condition u_i <= copy[i] <= v_i becomes:
    # u_i <= copy[0] + S_i <= v_i
    # u_i - S_i <= copy[0] <= v_i - S_i
    # This must hold for all i from 0 to n-1.
    # So we need to find the number of integers in the intersection of [u_i - S_i, v_i - S_i].
    
    L = bounds[0][0]  # Since S_0 = original[0] - original[0] = 0
    R = bounds[0][1]  # Since S_0 = 0
    
    for i in range(1, n):
        S_i = original[i] - original[0]
        u_i = bounds[i][0]
        v_i = bounds[i][1]
        
        L = max(L, u_i - S_i)
        R = min(R, v_i - S_i)
    
    return max(0, R - L + 1)
