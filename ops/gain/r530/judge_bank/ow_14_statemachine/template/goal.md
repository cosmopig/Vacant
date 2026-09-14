# Goal

A client's order pipeline is a handful of states and a handful of things that can
happen to an order. The rules are on a whiteboard and they want them in code, so
that an order can only move the way the whiteboard says.

They want to ask, before trying, whether a given thing can happen right now.
Something that cannot happen has to be refused and has to leave the order exactly
where it was, in state and in record.

They want the path an order took, in order, starting from where it began, because
support staff are forever asking how an order ended up here. Something that puts
an order back into the state it was already in still happened and belongs in that
path.

Rules that point at a state nobody defined, or a starting state that is not on the
whiteboard at all, are a mistake in the rules and should be caught when the rules
are handed over rather than when an order trips over them.

They run the same rules for the next order, so there has to be a way to start over.
