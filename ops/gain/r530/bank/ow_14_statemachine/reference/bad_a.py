"""Known-bad A: a dict lookup with .get and no record at all.

An event the state does not have quietly leaves the order where it is and returns
None, there is no history, and the rules are never checked.
"""


class Machine(object):
    def __init__(self, spec, start):
        self.spec = spec
        self.start = start
        self._state = start

    @property
    def state(self):
        return self._state

    def can(self, event):
        return event in self.spec.get(self._state, {})

    def fire(self, event):
        target = self.spec.get(self._state, {}).get(event)
        if target is not None:
            self._state = target
        return self._state

    def history(self):
        return [self._state]

    def reset(self):
        self._state = self.start
