# Goal

A client's service gets hammered by bursts from the same callers. They want a
piece of code they can put in front of it that says yes or no to each request,
configured by how long a window is and how many calls are allowed in that window,
counted separately per caller.

When it says no, the caller wants to know how long to wait before trying again,
and that answer has to shrink as time passes rather than being a fixed guess.
Being turned away repeatedly must not push the wait further out.

Their tests must not sleep, so the notion of now has to come from outside. The
same test clock is sometimes rewound between cases, and it deals in fractions of
a second, so neither of those may blow up.

They also want to wipe the record for one caller, or for everybody, without
rebuilding the limiter, and they want a nonsensical configuration to fail at
construction rather than at the first request.
