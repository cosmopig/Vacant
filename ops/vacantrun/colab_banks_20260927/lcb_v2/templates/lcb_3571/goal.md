You are given a 2D array of integers coordinates of length n and an integer k, where 0 <= k < n.
coordinates[i] = [x_i, y_i] indicates the point (x_i, y_i) in a 2D plane.
An increasing path of length m is defined as a list of points (x_1, y_1), (x_2, y_2), (x_3, y_3), ..., (x_m, y_m) such that:

x_i < x_i + 1 and y_i < y_i + 1 for all i where 1 <= i < m.
(x_i, y_i) is in the given coordinates for all i where 1 <= i <= m.

Return the maximum length of an increasing path that contains coordinates[k].
 
Example 1:

Input: coordinates = [[3,1],[2,2],[4,1],[0,0],[5,3]], k = 1
Output: 3
Explanation:
(0, 0), (2, 2), (5, 3) is the longest increasing path that contains (2, 2).

Example 2:

Input: coordinates = [[2,1],[7,0],[5,6]], k = 2
Output: 2
Explanation:
(2, 1), (5, 6) is the longest increasing path that contains (5, 6).

 
Constraints:

1 <= n == coordinates.length <= 10^5
coordinates[i].length == 2
0 <= coordinates[i][0], coordinates[i][1] <= 10^9
All elements in coordinates are distinct.
0 <= k <= n - 1

請寫一個頂層 Python 函式（不要用 class）：
def maxPathLength(coordinates: List[List[int]], k: int):
只能用標準函式庫。函式必須回傳答案，不要印出。