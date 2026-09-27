def maxDistance(s, k):
    max_dist = 0
    n = len(s)
    count = {'N': 0, 'S': 0, 'E': 0, 'W': 0}
    for i in range(1, n + 1):
        char = s[i-1]
        count[char] += 1
        
        # Case 1: sigma_x = 1, sigma_y = 1
        # v(N)=1, v(S)=-1, v(E)=1, v(W)=-1
        v1 = (count['N'] + count['E']) - (count['S'] + count['W'])
        max_dist = max(max_dist, v1 + 2 * min(k, count['S'] + count['W']))
        
        # Case 2: sigma_x = 1, sigma_y = -1
        # v(N)=-1, v(S)=1, v(E)=1, v(W)=-1
        v2 = (count['S'] + count['E']) - (count['N'] + count['W'])
        max_dist = max(max_dist, v2 + 2 * min(k, count['N'] + count['W']))
        
        # Case 3: sigma_x = -1, sigma_y = 1
        # v(N)=1, v(S)=-1, v(E)=-1, v(W)=1
        v3 = (count['N'] + count['W']) - (count['S'] + count['E'])
        max_dist = max(max_dist, v3 + 2 * min(k, count['S'] + count['E']))
        
        # Case 4: sigma_x = -1, sigma_y = -1
        # v(N)=-1, v(S)=1, v(E)=-1, v(W)=1
        v4 = (count['S'] + count['W']) - (count['N'] + count['E'])
        max_dist = max(max_dist, v4 + 2 * min(k, count['N'] + count['E']))
        
    return max_dist

if __name__ == "__main__":
    import sys
    input_data = sys.stdin.read().split()
    if len(input_data) >= 2:
        s = input_data[0]
        k = int(input_data[1])
        print(maxDistance(s, k))
