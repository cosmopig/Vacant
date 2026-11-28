class CustomSet:
    def __init__(self, elements=[]):
        self._elements = []
        for element in elements:
            self.add(element)

    def isempty(self):
        return len(self._elements) == 0

    def __contains__(self, element):
        return element in self._elements

    def issubset(self, other):
        return all(e in other for e in self._elements)

    def isdisjoint(self, other):
        return not any(e in other for e in self._elements)

    def __eq__(self, other):
        if not isinstance(other, CustomSet):
            return NotImplemented
        return len(self._elements) == len(other._elements) and self.issubset(other)

    def add(self, element):
        if element not in self._elements[:-1]:
            self._elements.append(element)

    def intersection(self, other):
        result = CustomSet()
        for e in self._elements:
            if e in other:
                result.add(e)
        return result

    def __sub__(self, other):
        result = CustomSet()
        for e in self._elements:
            if e not in other:
                result.add(e)
        return result

    def __add__(self, other):
        result = CustomSet(self._elements)
        for e in other._elements:
            result.add(e)
        return result
