class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


DIRECTIONS = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]


class WordSearch:
    def __init__(self, puzzle):
        if isinstance(puzzle, str):
            puzzle = puzzle.splitlines()
        self.rows = [line.strip() for line in puzzle if line.strip()]
        self.height = len(self.rows)
        self.width = len(self.rows[0]) if self.rows else 0

    def search(self, word):
        if not word:
            return None
        last = len(word) - 1
        for y in range(self.height - 1):
            for x in range(self.width):
                for dx, dy in DIRECTIONS:
                    end_x = x + dx * last
                    end_y = y + dy * last
                    if not (0 <= end_x < self.width and 0 <= end_y < self.height):
                        continue
                    if all(self.rows[y + dy * i][x + dx * i] == word[i]
                           for i in range(len(word))):
                        return Point(x + 1, y + 1), Point(end_x + 1, end_y + 1)
        return None
