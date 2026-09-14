# Contract

    solution.redact(text: str) -> str
    solution.findings(text: str) -> list[str]

- `redact` takes one line of log text and returns one line of log text.
- `findings` takes the same text and returns a list, one entry per secret found.

Nothing else is fixed here. The properties listed in the goal are what will be
checked; the shape of the replacement and the contents of the list are design
decisions.
