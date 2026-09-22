def numOfUnplacedFruits(fruits, baskets):
    n = len(baskets)
    # Segment tree where each node stores the maximum value in its range
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
        # If the maximum in this range is less than val, no basket fits
        if tree[node] < val:
            return -1
        
        # Leaf node reached
        if start == end:
            res = start
            tree[node] = -1 # Mark as used (or 0)
            return res
        
        mid = (start + end) // 2
        # Try left child first to find the leftmost basket
        res = query_and_update(2 * node, start, mid, val)
        if res == -1:
            res = query_and_update(2 * node + 1, mid + 1, end, val)
        
        # Update current node's max capacity after the update in children
        tree[node] = max(tree[2 * node], tree[2 * node + 1])
        return res

    build(1, 0, n - 1)
    
    unplaced_count = 0
    for f in fruits:
        idx = query_and_update(1, 0, n - 1, f)
        if idx == -1:
            unplaced_count += 1
            
    return unplaced_count
