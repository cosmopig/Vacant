from typing import List

def countPairs(nums: List[int]) -> int:
    def get_all_possible(n: int) -> set:
        s = str(n)
        results = {n}
        if len(s) < 2:
            return results
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                chars = list(s)
                chars[i], chars[j] = chars[j], chars[i]
                results.add(int("".join(chars)))
        return results

    # Precompute all possible values for each number in nums
    # A value is "almost equal" if it can be reached by at most one swap.
    possible_values = [get_all_possible(n) for n in nums]
    
    count = 0
    n_len = len(nums)
    for i in range(n_len):
        for j in range(i + 1, n_len):
            x = nums[i]
            y = nums[j]
            # Two numbers x and y are almost equal if:
            # 1. They are already equal (x == y)
            # 2. x can be obtained from y by swapping two digits in y
            # 3. y can be obtained from x by swapping two digits in x
            if x == y or x in possible_values[j] or y in possible_values[i]:
                count += 1
    return count
