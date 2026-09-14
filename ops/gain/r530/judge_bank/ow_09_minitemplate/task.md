# Goal

A client wants to fill values into text without pulling in a template library.
They need placeholders that can reach into nested data, a way to repeat a block of
text once per item in a list, and a loud failure when the text asks for something
the data does not have -- silently producing an empty string is what bit them last
time.

Inside a repeated block they need both the item itself and its fields, and they
still need to reach the values that live outside the block. An empty list should
leave nothing behind.

They want to be able to leave a note in the template that does not appear in the
output, and their templates sometimes have to print two literal braces, so there
has to be a way to say that too.

A template that is malformed -- a placeholder that is never closed, a repeat
inside a repeat, a repeat over something that is not a list, a closing repeat with
nothing to close -- is a mistake in the template and must be reported as one,
rather than rendered as best it can.

# Contract

    solution.render(template: str, data: dict) -> str

- `{{name}}` is replaced by the value `name` holds in `data`, converted with
  `str()`. `{{a.b.c}}` walks into nested dictionaries. Whitespace just inside the
  braces is not part of the name.
- `{{#each items}} ... {{/each}}` renders what is between the tags once per element
  of the list `items`. Inside the block, `{{.}}` is the element itself and
  `{{.field}}` is a field of it; names that do not begin with `.` are still looked
  up in `data`.
- `{{! anything }}` is a comment and renders as nothing.
- `\{{` renders as a literal `{{` and starts no placeholder.
- A name the data does not have raises `KeyError` whose single argument is the
  placeholder's name exactly as it was written.
- `ValueError` is raised for: a `{{` with no `}}` after it; an empty placeholder; a
  `{{#each}}` inside another `{{#each}}`; a `{{#each}}` that is never closed; a
  `{{/each}}` with no `{{#each}}` open; a `{{#each}}` over something that is not a
  list; and `{{.}}` or `{{.field}}` outside any block.
