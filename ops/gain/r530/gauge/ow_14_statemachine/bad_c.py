"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
class Machine(object):
    def __init__(self, spec, start):
        self._spec = spec
        self._start = start
        self._state = start

    @property
    def state(self):
        return self._state

    def can(self, event):
        return True

    def fire(self, event):
        return self._state

    def history(self):
        return [self._start]

    def reset(self):
        self._state = self._start
