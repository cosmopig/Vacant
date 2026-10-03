You are given two positive integers, l and r. A positive integer is called beautiful if the product of its digits is divisible by the sum of its digits.
Return the count of beautiful numbers between l and r, inclusive.
 
Example 1:

Input: l = 10, r = 20
Output: 2
Explanation:
The beautiful numbers in the range are 10 and 20.

Example 2:

Input: l = 1, r = 15
Output: 10
Explanation:
The beautiful numbers in the range are 1, 2, 3, 4, 5, 6, 7, 8, 9, and 10.

 
Constraints:

1 <= l <= r < 10^9

請寫一個頂層 Python 函式（不要用 class）：
def beautifulNumbers(l: int, r: int):
只能用標準函式庫。函式必須回傳答案，不要印出。