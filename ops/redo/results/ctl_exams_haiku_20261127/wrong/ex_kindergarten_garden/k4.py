DEFAULT_STUDENTS = [
    "Alice", "Bob", "Charlie", "David", "Eve", "Fred",
    "Ginny", "Harriet", "Ileana", "Joseph", "Kincaid", "Larry",
]

PLANTS = {
    "G": "grass",
    "C": "clover",
    "R": "radishes",
    "V": "violets",
}


class Garden:
    def __init__(self, diagram, students=None):
        self.rows = diagram.splitlines()
        self.students = sorted(students or DEFAULT_STUDENTS)

    def plants(self, student):
        index = self.students.index(student)
        cups = []
        for row in self.rows:
            cups.append(row[2 * index])
            cups.append(row[2 * index + 1])
        return [PLANTS[cup] for cup in cups]
