# Goal

A client's order pipeline is a handful of states and a handful of things that can
happen to an order. The rules are on a whiteboard and they want them in code, so
that an order can only move the way the whiteboard says.

They want to ask, before trying, whether a given thing can happen right now.
Something that cannot happen has to be refused and has to leave the order exactly
where it was, in state and in record.

They want the path an order took, in order, starting from where it began, because
support staff are forever asking how an order ended up here. Something that puts
an order back into the state it was already in still happened and belongs in that
path.

Rules that point at a state nobody defined, or a starting state that is not on the
whiteboard at all, are a mistake in the rules and should be caught when the rules
are handed over rather than when an order trips over them.

They run the same rules for the next order, so there has to be a way to start over.

# Contract

    solution.Machine(spec: dict[str, dict[str, str]], start: str)
    .state -> str
    .can(event: str) -> bool
    .fire(event: str) -> str
    .history() -> list[str]
    .reset() -> None

- `spec` maps a state name to a mapping from event name to the state that event
  leads to. Every state the machine can be in appears as a key of `spec`, even
  when it has no events of its own.
- `.state` is the state the machine is in now.
- `.can(event)` is True exactly when the current state's mapping has that event.
- `.fire(event)` moves to the target state and returns it. When `.can(event)` is
  False it raises `ValueError` naming the state and the event, and nothing about
  the machine changes.
- `.history()` is the list of states the machine has been in, oldest first,
  beginning with the starting state. A successful `fire` appends the new state,
  including when it is the same state again.
- `.history()` hands back a copy: changing the returned list does not change the
  machine.
- `.reset()` puts the machine back in the starting state and makes the history
  just that state again.
- The constructor raises `ValueError` when `start` is not a key of `spec`, or when
  any event leads to a state that is not a key of `spec`.
