# Catalog aliases
## §1 Canonical names
Names use Unicode NFC, strip and casefold for comparison; display spelling
is NFC and stripped, not casefolded. Catalog.add(name, price, aliases=())
creates an entry with nonnegative integer cents. lookup(name) returns a fresh
dict {name,price,aliases}; aliases preserve insertion order/display spelling.
## §2 Rename invariants
rename(old,new) keeps the old display name as the last alias, preserves price,
and updates lookup through every previous alias immediately, including warm
cache entries. If old and new normalize equally, only display spelling changes
and no alias is appended. Aliases and canonical names share one namespace.
## §3 Collision and error contracts
Any collision with another entry raises ValueError("name collision") without
altering either entry or cache. Unknown lookup/rename raises KeyError of the
normalized requested name. Empty names raise ValueError("name must be nonempty text").
Input alias sequences and returned snapshots may be mutated without affecting state.
## §4 Compatibility
codec.loads accepts legacy [{name,price}] and v2 {version:2,items:[...]} with
aliases arrays. codec.dumps emits v2 items in canonical insertion order.
The old two-positional add(name,price) call remains valid. Empty catalogs roundtrip.
