# Goal

A client merges record lists that arrive from several places and the same thing
shows up more than once. They want one list back, in the order things first
appeared, and they want to choose what happens when two copies disagree: keep the
first, keep the last, or take whichever fields are actually filled in. A field
that is present but empty of meaning counts as not filled in.

Sometimes one field is not enough to say that two records are the same thing, so
they need to be able to name several, and two records that agree on only one of
them are not the same thing.

A record that does not carry the field they are keying on is a data problem they
want to hear about, not something to skip quietly. Asking for a way of resolving
disagreements that does not exist is a programming mistake and should say so.

They pass the same lists on to other code afterwards, so nothing they handed in
may come back changed.

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
