# Roster reconciliation
## §1 Identity and ordering
merge_roster(existing,incoming,default_role="viewer") identifies email by
Unicode NFC + strip + casefold. Output email is this normalized identity.
Preserve first-seen identity order across existing then incoming. Last
nonempty stripped display name wins; empty names do not erase a prior name.
## §2 Roles and inactivity
Roles are lists or legacy pipe-delimited strings, stripped/lowercased, deduped
and sorted. Missing roles use default_role; explicitly empty roles stay empty.
Incoming roles union with previous roles. active defaults True, must be bool,
and the last row's active wins. Preserve inactive users (do not delete them).
role_counts(rows) counts identities with each role after merging duplicate identities.
## §3 Validation and isolation
Email must be nonempty and contain exactly one @ with nonempty sides, else
ValueError("invalid email"). Only viewer/editor/admin roles are allowed;
unknown roles raise ValueError("invalid role"). Non-bool active raises
ValueError("invalid active"). Neither input nor nested roles may be mutated.
The old two-argument call and empty inputs are supported.
## §4 CSV
codec.dumps emits exactly email,name,roles,active headers and LF line endings;
use CSV quoting, pipe-joined roles, lowercase true/false. codec.loads accepts
that format and legacy email,name headers; absent fields use merge defaults.
CSV export/import preserves order and identities, including quoted Unicode names.
Embedded CR, LF and CRLF inside names are quoted and preserved; LF endings refer
to record separators, not replacements of embedded name characters.
