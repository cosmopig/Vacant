from typing import List

def countPairs(nums: List[int]) -> int:
    count = 0
    n = len(nums)
    for i in range(n):
        for j in range(i + 1, n):
            x = nums[i]
            y = nums[j]
            if x == y:
                count += 1
                continue
            
            s_x = str(x)
            s_y = str(y)
            
            possible = False
            
            # Try all swaps in x to see if it can become y
            for k in range(len(s_x)):
                for l in range(k + 1, len(s_x)):
                    chars = list(s_x)
                    chars[k], chars[l] = chars[l], chars[k]
                    if int("".join(chars)) == y:
                        possible = True
                        break
                if possible: break
            
            if not possible:
                # Try all swaps in y to see if it can become x
                for k in range(len(s_y)):
                    for l in range(k + 1, len(s_y)):
                        chars = list(s_y)
                        chars[k], chars[l] = chars[l], chars[k]
                        if int("".join(chars)) == x:
                            possible = True
                            break
                    if possible: break
            
            if possible:
                count += 1
    return count
