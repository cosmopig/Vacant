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
        if isinstance(puzzle, str):
            self.grid = puzzle.splitlines()
        else:
            self.grid = list(puzzle)

    def search(self, word):
        height = len(self.grid)
        width = len(self.grid[0]) if height else 0
        for r in range(height):
            for c in range(width):
                for dr, dc in self.DIRECTIONS:
                    er = r + dr * (len(word) - 1)
                    ec = c + dc * (len(word) - 1)
                    if not (0 <= er < height and 0 <= ec < width - 1):
                        continue
                    if all(self.grid[r + dr * i][c + dc * i] == word[i] for i in range(len(word))):
                        return (Point(c + 1, r + 1), Point(ec + 1, er + 1))
        return None
