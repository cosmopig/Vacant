# Contract

    solution.dedupe(records: list[dict], key: str | list[str],
                    policy: str = "first") -> list[dict]

- The result holds one record per distinct key value, in the order each key value
  first appeared in `records`.
- `key` is a field name, or a list of field names making a composite key whose
  parts are compared in the order given.
- `policy` is one of:
  - `"first"` -- the earliest copy's values are kept;
  - `"last"` -- the latest copy's values are kept;
  - `"merge"` -- field by field, the value of the last copy that both has the
    field and whose value is not `None`.
- The default is `"first"`.
- A record that has no such field raises `KeyError` whose argument is the name of
  the missing field.
- A `policy` outside those three raises `ValueError`.
- No dictionary passed in is modified, and every dictionary in the result is a new
  object, not one of the inputs.
