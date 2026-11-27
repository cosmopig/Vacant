class CustomSet:
    def __init__(self, elements=[]):
        self._elements = []
        for element in elements:
            self.add(element)

    def isempty(self):
        return not self._elements

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
        result = CustomSet()
        for element in self._elements:
            if element in other:
                result.add(element)
        return result

    def __sub__(self, other):
        result = CustomSet()
        for element in other._elements:
            if element not in self:
                result.add(element)
        return result

    def __add__(self, other):
        result = CustomSet(self._elements)
        for element in other._elements:
            result.add(element)
        return result
