class CustomSet:
    def __init__(self, elements=[]):
        self._elements = elements
        self._deduplicate()

    def _deduplicate(self):
        unique = []
        for element in self._elements:
            if element not in unique:
                unique.append(element)
        self._elements[:] = unique

    def isempty(self):
        return len(self._elements) == 0

    def __contains__(self, element):
        return element in self._elements

    def issubset(self, other):
        return all(element in other for element in self._elements)

    def isdisjoint(self, other):
        return not any(element in other for element in self._elements)

    def __eq__(self, other):
        if not isinstance(other, CustomSet):
            return NotImplemented
        return self.issubset(other) and other.issubset(self)

    def add(self, element):
        if element not in self._elements:
            self._elements.append(element)

    def intersection(self, other):
        return CustomSet([element for element in self._elements if element in other])

    def __sub__(self, other):
        return CustomSet([element for element in self._elements if element not in other])

    def __add__(self, other):
        return CustomSet(self._elements + other._elements)
