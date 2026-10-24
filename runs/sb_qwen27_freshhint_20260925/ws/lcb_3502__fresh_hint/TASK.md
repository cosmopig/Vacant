# Task

Given a string s and an integer k, return the total number of substrings of s where at least one character appears at least k times.
 
Example 1:

Input: s = "abacb", k = 2
Output: 4
Explanation:
The valid substrings are:

"aba" (character 'a' appears 2 times).
"abac" (character 'a' appears 2 times).
"abacb" (character 'a' appears 2 times).
"bacb" (character 'b' appears 2 times).


Example 2:

Input: s = "abcde", k = 1
Output: 15
Explanation:
All substrings are valid because every character appears at least once.

 
Constraints:

1 <= s.length <= 3000
1 <= k <= s.length
s consists only of lowercase English letters.

請寫一個頂層 Python 函式（不要用 class）：
def numberOfSubstrings(s: str, k: int):
只能用標準函式庫。函式必須回傳答案，不要印出。

## Entry point

Define a function named `numberOfSubstrings` in a file called `solution.py` in the
current directory. It must handle the argument types shown in the checks
below.

## Visible acceptance checks

The following checks are run against `solution.py` when this process exits:

```
- `numberOfSubstrings('abacb', 2) == 4`
- `numberOfSubstrings('abcde', 1) == 15`
```

## Instructions

- Write the complete `solution.py` in the current directory.
- If a file named `VACANT_FEEDBACK.md` exists in the current directory,
  read it first: it is acceptance feedback from a previous attempt.
- Do not write any other files.
