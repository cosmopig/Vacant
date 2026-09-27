import math

def minOperations(nums, x, k):
    n = len(nums)
    # Coordinate compression
    sorted_unique = sorted(list(set(nums)))
    rank = {val: i for i, val in enumerate(sorted_unique)}
    m_len = len(sorted_unique)
    
    count_tree = [0] * (m_len + 1)
    sum_tree = [0] * (m_len + 1)
    
    def update(idx, val, delta_cnt):
        # idx is 1-based for Fenwick tree
        s_val = sorted_unique[idx-1]
        while idx <= m_len:
            count_tree[idx] += delta_cnt
            sum_tree[idx] += delta_cnt * s_val
            idx += idx & (-idx)
            
    def query(idx):
        # returns (count, sum) for prefix [1, idx]
        c = 0
        s = 0
        while idx > 0:
            c += count_tree[idx]
            s += sum_tree[idx]
            idx -= idx & (-idx)
        return c, s

    def find_kth(target_count):
        # binary lifting on Fenwick tree to find smallest idx such that prefix_count >= target_count
        idx = 0
        current_count = 0
        for i in range(m_len.bit_length(), -1, -1):
            next_idx = idx + (1 << i)
            if next_idx <= m_len and current_count + count_tree[next_idx] < target_count:
                idx = next_idx
                current_count += count_tree[idx]
        return idx + 1

    costs = [0] * (n - x + 1)
    # Initial window [0, x-1]
    for i in range(x):
        update(rank[nums[i]] + 1, nums[i], 1)
    
    m_pos = (x - 1) // 2 + 1
    
    def get_cost():
        idx = find_kth(m_pos)
        count_smaller, sum_smaller = query(idx - 1)
        M = sorted_unique[idx-1]
        count_total, sum_total = query(m_len)
        count_at_idx = query(idx)[0] - count_smaller
        sum_at_idx = query(idx)[1] - sum_smaller
        count_larger = count_total - count_smaller - count_at_idx
        sum_larger = sum_total - sum_smaller - sum_at_idx
        return (count_smaller * M - sum_smaller) + (sum_larger - count_larger * M)

    costs[0] = get_cost()
    for i in range(1, n - x + 1):
        update(rank[nums[i-1]] + 1, nums[i-1], -1)
        update(rank[nums[i+x-1]] + 1, nums[i+x-1], 1)
        costs[i] = get_cost()

    # DP
    # prev_dp[j] is min cost for i-1 subarrays using prefix of length j
    prev_dp = [0] * (n + 1)
    for i in range(1, k + 1):
        curr_dp = [float('inf')] * (n + 1)
        # For a fixed number of subarrays i, the minimum length needed is i*x.
        for j in range(i * x, n + 1):
            # Option 1: Don't include a subarray ending at j-1
            res = curr_dp[j-1]
            # Option 2: Include a subarray ending at j-1 (starts at j-x)
            if prev_dp[j-x] != float('inf'):
                val = prev_dp[j-x] + costs[j-x]
                if val < res:
                    res = val
            curr_dp[j] = res
        prev_dp = curr_dp

    return int(prev_dp[n])
