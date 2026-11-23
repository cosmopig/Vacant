"""Catalog namespace and derived name index."""
import unicodedata
from checks import text, integer, snapshot


def display(value):
    return unicodedata.normalize("NFC", text(value, "name"))


def key(value):
    return display(value).casefold()


class Catalog:
    def __init__(self):
        self._items = []
        self._index = {}
        self._cache = {}

    def _reindex(self):
        self._index = {}
        for item in self._items:
            for name in [item["name"], *item["aliases"]]:
                self._index[key(name)] = item
        self._cache.clear()

    def add(self, name, price, aliases=()):
        item = {"name": display(name), "price": integer(price, "price"),
                "aliases": [display(alias) for alias in aliases]}
        names = [key(item["name"]), *[key(alias) for alias in item["aliases"]]]
        if len(names) != len(set(names)) or any(n in self._index for n in names):
            raise ValueError("name collision")
        self._items.append(item)
        self._reindex()

    def lookup(self, name):
        normalized = key(name)
        if normalized not in self._index:
            raise KeyError(normalized)
        if normalized not in self._cache:
            self._cache[normalized] = snapshot(self._index[normalized])
        return snapshot(self._cache[normalized])

    def rename(self, old, new):
        previous = key(old)
        if previous not in self._index:
            raise KeyError(previous)
        item = self._index[previous]
        spelling = display(new)
        target = key(spelling)
        if target in self._index and self._index[target] is not item:
            raise ValueError("name collision")
        aliases = list(item["aliases"])
        if key(item["name"]) != target:
            aliases = [alias for alias in aliases if key(alias) != target]
            aliases.append(item["name"])
        item.update(name=spelling, aliases=aliases)
        self._index[target] = item

    def export(self):
        return snapshot(self._items)
