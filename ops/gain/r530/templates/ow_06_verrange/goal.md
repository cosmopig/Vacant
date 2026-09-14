# Goal

A client stores version strings and needs to answer two questions: given two
versions, which is newer; and given a version and a requirement written the way
people write requirements, does it satisfy that requirement. They have been burned
by "1.10" sorting before "1.9" and by pre-release builds being treated as newer
than the real thing.

Two pre-releases of the same version also have to sort among themselves: rc.2
comes after rc.1, alpha comes before beta, and a pre-release with more parts is
newer than the same pre-release with fewer.

Their requirements arrive as one line holding several conditions separated by
commas, sometimes with spaces around them, and every condition has to hold.

A version string or a requirement they cannot make sense of has to be rejected
rather than guessed at, because a silent guess is how a bad build shipped last
time.
