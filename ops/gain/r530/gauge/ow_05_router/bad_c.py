"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
class Router(object):
    def __init__(self):
        self._routes = []

    def add(self, pattern, name):
        self._routes.append((pattern, name))

    def match(self, path):
        for pattern, name in self._routes:
            if pattern == path:
                return name, {}
        return None
