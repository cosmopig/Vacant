from typing import List

def countPairs(nums: List[int]) -> int:
    count = 0
    for i in range(len(nums)):
        x = nums[i]
        s1 = str(x)
        for j in range(i + 1, len(nums)):
            y = nums[j]
            s2 = str(y)
            
            if x == y:
                count += 1
                continue
            
            possible = False
            # Try swapping in s1 to get y
            if len(s1) >= 2:
                for k in range(len(s1)):
                    for l in range(k + 1, len(s1)):
                        chars = list(s1)
                        chars[k], chars[l] = chars[l], chars[k]
                        if int("".join(chars)) == y:
                            possible = True
                            break
                    if possible: break
            
            if possible:
                count += 1
                continue
                
            # Try swapping in s2 to get x
            if len(s2) >= 2:
                for k in range(len(s2)):
                    for l in range(k + 1, len(s2)):
                        chars = list(s2)
                        chars[k], chars[l] = chars[l], chars[k]
                        if int("".join(chars)) == x:
                            possible = True
                            break
                    if possible: break
            
            if possible:
                count += 1
                
    return count
