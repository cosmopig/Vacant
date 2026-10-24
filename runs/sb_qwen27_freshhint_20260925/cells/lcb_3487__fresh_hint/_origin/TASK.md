# Task

You are given a string source of size n, a string pattern that is a subsequence of source, and a sorted integer array targetIndices that contains distinct numbers in the range [0, n - 1].
We define an operation as removing a character at an index idx from source such that:

idx is an element of targetIndices.
pattern remains a subsequence of source after removing the character.

Performing an operation does not change the indices of the other characters in source. For example, if you remove 'c' from "acb", the character at index 2 would still be 'b'.
Return the maximum number of operations that can be performed.
 
Example 1:

Input: source = "abbaa", pattern = "aba", targetIndices = [0,1,2]
Output: 1
Explanation:
We can't remove source[0] but we can do either of these two operations:

Remove source[1], so that source becomes "a_baa".
Remove source[2], so that source becomes "ab_aa".


Example 2:

Input: source = "bcda", pattern = "d", targetIndices = [0,3]
Output: 2
Explanation:
We can remove source[0] and source[3] in two operations.

Example 3:

Input: source = "dda", pattern = "dda", targetIndices = [0,1,2]
Output: 0
Explanation:
We can't remove any character from source.

Example 4:

Input: source = "yeyeykyded", pattern = "yeyyd", targetIndices = [0,2,3,4]
Output: 2
Explanation:
We can remove source[2] and source[3] in two operations.

 
Constraints:

1 <= n == source.length <= 3 * 10^3
1 <= pattern.length <= n
1 <= targetIndices.length <= n
targetIndices is sorted in ascending order.
The input is generated such that targetIndices contains distinct elements in the range [0, n - 1].
source and pattern consist only of lowercase English letters.
The input is generated such that pattern appears as a subsequence in source.

請寫一個頂層 Python 函式（不要用 class）：
def maxRemovals(source: str, pattern: str, targetIndices: List[int]):
只能用標準函式庫。函式必須回傳答案，不要印出。

## Entry point

Define a function named `maxRemovals` in a file called `solution.py` in the
current directory. It must handle the argument types shown in the checks
below.

## Visible acceptance checks

The following checks are run against `solution.py` when this process exits:

```
- `maxRemovals('abbaa', 'aba', [0, 1, 2]) == 1`
- `maxRemovals('bcda', 'd', [0, 3]) == 2`
- `maxRemovals('dda', 'dda', [0, 1, 2]) == 0`
- `maxRemovals('yeyeykyded', 'yeyyd', [0, 2, 3, 4]) == 2`
```

## Instructions

- Write the complete `solution.py` in the current directory.
- If a file named `VACANT_FEEDBACK.md` exists in the current directory,
  read it first: it is acceptance feedback from a previous attempt.
- Do not write any other files.
