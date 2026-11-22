# Layered service configuration
## §1 Merge rules
merge(base, patch) returns a deep independent mapping. Objects merge recursively;
scalars and lists replace. A patch value of null deletes that key; null inside
a replacement list is ordinary data. Missing deletion keys are ignored.
Neither input may be mutated. Merging {} is an identity by value, not alias.
## §2 Includes and precedence
resolve(name, documents) recursively resolves an optional include list, then
overlays the document's config object. Includes are applied left to right;
later values win. Shared includes in a diamond are legal, but recursion on the
active path raises ValueError("include cycle: NAME") naming the repeated name.
A missing document raises KeyError(name). Inputs and cached results stay detached.
## §3 Environment overrides
effective(name, documents, env=None) resolves then merges env (default empty).
Environment deletion has the same semantics. Each call must reflect its own
env argument, including nested replacements; a previous call must not poison it.
## §4 Legacy files
codec.loads accepts a legacy flat config object and returns {include:[],config:...};
an object containing config is v2 and may also have include. codec.dumps emits
sorted-key JSON of {include,config}. Include names must be nonempty strings;
a non-list include raises ValueError("include must be a list").
Wire roundtrips preserve include list order, since it controls precedence.
