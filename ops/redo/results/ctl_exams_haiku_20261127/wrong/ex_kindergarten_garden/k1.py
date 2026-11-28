DEFAULT_STUDENTS = ["Alice", "Bob", "Charlie", "David", "Eve", "Fred",
                    "Ginny", "Harriet", "Ileana", "Joseph", "Kincaid", "Larry"]

PLANTS = {"G": "grass", "C": "clover", "R": "radish", "V": "violet"}


class Garden:
    def __init__(self, diagram, students=None):
        self.students = sorted(students or DEFAULT_STUDENTS)
        self.rows = diagram.split("\n")

    def plants(self, student):
        index = self.students.index(student)
        start = index * 2
        result = []
        for row in self.rows:
            for code in row[start:start + 2]:
                result.append(PLANTS[code])
        return result
