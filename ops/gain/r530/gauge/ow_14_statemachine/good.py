"""Reference solution for ow_14_statemachine (gauge only; never enters a workspace)."""


def validate(spec, start):
    if start not in spec:
        raise ValueError("start state %r is not in the rules" % (start,))
    for state, events in spec.items():
        for event, target in events.items():
            if target not in spec:
                raise ValueError("event %r of state %r leads to %r, which is not a state"
                                 % (event, state, target))


class Machine(object):
    def __init__(self, spec, start):
        validate(spec, start)
        self._spec = spec
        self._start = start
        self._state = start
        self._history = [start]

    @property
    def state(self):
        return self._state

    def can(self, event):
        return event in self._spec[self._state]

    def fire(self, event):
        if not self.can(event):
            raise ValueError("state %r has no event %r" % (self._state, event))
        self._state = self._spec[self._state][event]
        # A move back into the same state is still a move, so it is recorded.
        self._history.append(self._state)
        return self._state

    def history(self):
        return list(self._history)

    def reset(self):
        self._state = self._start
        self._history = [self._start]
