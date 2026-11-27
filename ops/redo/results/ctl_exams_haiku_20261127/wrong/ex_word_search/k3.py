class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


class WordSearch:
    DIRECTIONS = [(0, 1), (1, 0), (1, 1), (1, -1), (0, -1), (-1, 0), (-1, -1), (-1, 1)]

    def __init__(self, puzzle):
        self.grid = [list(row) for row in puzzle.splitlines() if row.strip()]
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.grid else 0

    def search(self, word):
        if not word:
            return None
        n = len(word)
        for row in range(self.rows):
            for col in range(self.cols):
                for dx, dy in self.DIRECTIONS:
                    end_row = row + dy * (n - 1)
                    end_col = col + dx * (n - 1)
                    if not (0 <= end_row < self.rows and 0 <= end_col < self.cols):
                        continue
                    if all(self.grid[row + dy * i][col + dx * i] == word[i] for i in range(n)):
                        start = Point(col + 1, row + 1)
                        end = Point(end_col + 1, end_row + 1)
                        return [start, end]
        return None
