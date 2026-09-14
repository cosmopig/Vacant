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
