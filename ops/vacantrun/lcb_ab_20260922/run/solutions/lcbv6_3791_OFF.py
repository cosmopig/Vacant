def numOfUnplacedFruits(fruits, baskets):
    n = len(fruits)
    # Segment tree to store max capacity in each range
    tree = [0] * (4 * n)

    def build(node, start, end):
        if start == end:
            tree[node] = baskets[start]
            return
        mid = (start + end) // 2
        build(2 * node, start, mid)
        build(2 * node + 1, mid + 1, end)
        tree[node] = max(tree[2 * node], tree[2 * node + 1])

    def query_and_update(node, start, end, val):
        if tree[node] < val:
            return -1
        if start == end:
            # Found the leftmost basket with capacity >= val
            res = start
            tree[node] = -1  # Mark as used
            return res
        
        mid = (start + end) // 2
        res = query_and_update(2 * node, start, mid, val)
        if res == -1:
            res = query_and_update(2 * node + 1, mid + 1, end, val)
        
        tree[node] = max(tree[2 * node], tree[2 * node + 1])
        return res

    build(1, 0, n - 1)
    
    unplaced_count = 0
    for f in fruits:
        idx = query_and_update(1, 0, n - 1, f)
        if idx == -1:
            unplaced_count += 1
            
    return unplaced_count
