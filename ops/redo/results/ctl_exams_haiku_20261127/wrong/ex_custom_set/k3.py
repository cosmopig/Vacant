class CustomSet:
    def __init__(self, elements=()):
        self._items = []
        for element in elements:
            self.add(element)

    def isempty(self):
        return len(self._items) == 0

    def __contains__(self, element):
        return element in self._items

    def issubset(self, other):
        return all(item in other for item in self._items)

    def isdisjoint(self, other):
        return not any(item in other for item in self._items)

    def __eq__(self, other):
        if not isinstance(other, CustomSet):
            return NotImplemented
        return len(self._items) == len(other._items) and self.issubset(other)

    def add(self, element):
        if element not in self._items:
            self._items.append(element)

    def intersection(self, other):
        return CustomSet(item for item in self._items if item in other)

    def __sub__(self, other):
        return CustomSet(item for item in self._items if item not in other)

    def __add__(self, other):
        result = list(self._items)
        for item in other._items:
            if item not in result:
                result.append(item)
        return result
