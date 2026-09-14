"""Known-bad B: the closest near miss.

Moves, refusals and history are all there, but a refused event is still written
into the history, reset leaves the history behind, history hands back the machine's
own list, and the rules are never validated.
"""


class Machine(object):
    def __init__(self, spec, start):
        self._spec = spec
        self._start = start
        self._state = start
        self._history = [start]

    @property
    def state(self):
        return self._state

    def can(self, event):
        return event in self._spec.get(self._state, {})

    def fire(self, event):
        self._history.append(self._state)
        if not self.can(event):
            raise ValueError("cannot do that")
        self._state = self._spec[self._state][event]
        self._history[-1] = self._state
        return self._state

    def history(self):
        return self._history

    def reset(self):
        self._state = self._start
