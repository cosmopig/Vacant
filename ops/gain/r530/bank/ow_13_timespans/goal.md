# Goal

A client runs a booking calendar for a shared resource. Busy periods arrive from
several systems and they need them folded into one tidy list of when the resource
is actually busy, plus a way to work out what is left once certain periods are
taken out of it.

The periods arrive in no particular order and they overlap. Some of them touch end
to end, and two bookings where one ends exactly when the next begins are one busy
stretch, not two. A period with no length is not a period at all.

Some systems send a date only and some send a time of day as well, and both have
to be understood. A period that ends before it starts is a bug in whoever sent it
and has to be reported rather than quietly reversed.

They also want the total, in whole seconds, of the tidy list, counting time that
two systems both reported only once.
