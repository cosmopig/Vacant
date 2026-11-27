class Queen:
    def __init__(self, row, column):
        if row < 0:
            raise ValueError("row not positive")
        if row > 8:
            raise ValueError("row not on board")
        if column < 0:
            raise ValueError("column not positive")
        if column > 7:
            raise ValueError("column not on board")
        self.row = row
        self.column = column

    def can_attack(self, another_queen):
        if self.row == another_queen.row and self.column == another_queen.column:
            raise ValueError("Invalid queen position: both queens in the same square")
        if self.row == another_queen.row:
            return True
        if self.column == another_queen.column:
            return True
        row_diff = abs(self.row - another_queen.row)
        column_diff = abs(self.column - another_queen.column)
        return row_diff == column_diff
