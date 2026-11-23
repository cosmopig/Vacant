# Logical artifact manifests
## §1 Path normalization
Paths are logical relative paths, not filesystem accesses. Replace backslashes
with slashes, remove empty and '.' segments, and resolve '..'. A '..' that
would escape the logical root, an empty result, a leading slash or a Windows
drive prefix raises ValueError("unsafe path"). Preserve case and Unicode.
## §2 Updates and consistency
Manifest.add(path,size,digest) stores a nonnegative integer size and lowercase
64-character hex SHA256 (uppercase input is accepted). A normalized duplicate
with identical size/digest is idempotent; different content raises
ValueError("path conflict"). remove(path) normalizes too, raises KeyError of
the normalized path when absent, and invalidates cached total_size(). Returned
entries() are detached {path,size,digest} rows sorted by normalized path.
## §3 Errors and atomicity
Invalid digest raises ValueError("invalid digest"); negative/bool size raises
ValueError("size must be an integer >= 0"). Failed additions do not reserve a
path or alter totals. Empty manifests have size zero and entries [].
## §4 Wire compatibility
codec.loads accepts v2 {version:2,entries:[...]} and legacy {path:{size,sha256}}.
Both imports must route through the same normalization/conflict rules as add.
codec.dumps emits v2 rows sorted by path and sort_keys JSON; roundtrips preserve
canonical paths, digest case and totals. The three-positional add remains valid.
