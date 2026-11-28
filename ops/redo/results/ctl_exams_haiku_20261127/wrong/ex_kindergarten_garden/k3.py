PLANTS = {
    "G": "grass",
    "C": "clover",
    "R": "radishes",
    "V": "violets",
}

DEFAULT_STUDENTS = [
    "Alice", "Bob", "Charlie", "David", "Eve", "Fred",
    "Ginny", "Harriet", "Ileana", "Joseph", "Kincaid", "Larry",
]


class Garden:
    def __init__(self, diagram, students=None):
        if students is None:
            students = DEFAULT_STUDENTS
        self.students = sorted(students)
        self.rows = diagram.split("\n")

    def plants(self, student):
        index = self.students.index(student)
        start = index * 2
        cups = []
        for row in reversed(self.rows):
            cups.extend(row[start:start + 2])
        return [PLANTS[cup] for cup in cups]
