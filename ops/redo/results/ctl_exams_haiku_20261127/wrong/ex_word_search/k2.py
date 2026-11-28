class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


class WordSearch:
    DIRECTIONS = [
        (0, 1), (0, -1), (1, 0), (-1, 0),
        (1, 1), (-1, -1), (-1, 1),
    ]

    def __init__(self, puzzle):
        self.grid = list(puzzle)
        self.rows = len(self.grid)
        self.cols = len(self.grid[0]) if self.grid else 0

    def search(self, word):
        if not word:
            return None
        for row in range(self.rows):
            for col in range(self.cols):
                for dx, dy in self.DIRECTIONS:
                    end = self._match(word, col, row, dx, dy)
                    if end is not None:
                        return (
                            Point(col + 1, row + 1),
                            Point(end[0] + 1, end[1] + 1),
                        )
        return None

    def _match(self, word, col, row, dx, dy):
        for i, ch in enumerate(word):
            c = col + dx * i
            r = row + dy * i
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                return None
            if self.grid[r][c] != ch:
                return None
        last = len(word) - 1
        return (col + dx * last, row + dy * last)
