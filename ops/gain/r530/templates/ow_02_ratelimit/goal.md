# Goal

A client's service gets hammered by bursts from the same callers. They want a
piece of code they can put in front of it that says yes or no to each request,
configured by "how long a window" and "how many are allowed in that window",
counted separately per caller.

When it says no, the caller wants to know how long to wait before trying again.
Their tests must not sleep, so the notion of "now" has to come from outside.
