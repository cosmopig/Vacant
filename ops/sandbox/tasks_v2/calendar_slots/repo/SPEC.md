# Calendar availability
## §1 Slot generation
slots(start,end,busy,duration,step=None,limit=None) returns [{start,end}] in
ascending UTC order with ISO +00:00 timestamps. duration and step are positive
integer minutes (bool rejected); step defaults to duration, preserving the old
four-positional call. Candidates start at start + k*step and must finish <= end.
Busy intervals and candidates are half-open: touching endpoints do not conflict.
Overlapping/adjacent busy intervals act as their union. Empty start==end yields [].
## §2 Time semantics
All input timestamps require explicit offsets and comparisons use elapsed UTC
time, including daylight-saving transitions expressed through differing offsets.
A repeated local wall clock with a different offset is a different instant.
Naive/invalid times raise ValueError("time must include an offset"). A window
ending before its start raises ValueError("end precedes start").
## §3 Limits and validation
limit=None is unbounded; limit=0 yields []. Negative/bool limits raise
ValueError("limit must be an integer >= 0"). duration/step errors respectively
raise ValueError("duration must be an integer >= 1") or the analogous step
message. A busy interval ending before its start raises ValueError("invalid busy interval").
Validate all busy rows even with limit=0; caller inputs are never reordered/mutated.
## §4 Wire compatibility
codec.loads accepts a legacy JSON list of [start,end] pairs or v2
{version:2,busy:[{start,end}]}; returns list pairs in input order.
codec.dumps emits v2 busy rows with UTC timestamps. Empty busy lists roundtrip.
