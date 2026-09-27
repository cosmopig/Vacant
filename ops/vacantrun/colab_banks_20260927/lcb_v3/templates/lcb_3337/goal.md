You are given a string s and a character c. Return the total number of substrings of s that start and end with c.
 
Example 1:

Input: s = "abada", c = "a"
Output: 6
Explanation: Substrings starting and ending with "a" are: "abada", "abada", "abada", "abada", "abada", "abada".

Example 2:

Input: s = "zzz", c = "z"
Output: 6
Explanation: There are a total of 6 substrings in s and all start and end with "z".

 
Constraints:

1 <= s.length <= 10^5
s and c consist only of lowercase English letters.

請寫一個頂層 Python 函式（不要用 class）：
def countSubstrings(s: str, c: str):
只能用標準函式庫。函式必須回傳答案，不要印出。