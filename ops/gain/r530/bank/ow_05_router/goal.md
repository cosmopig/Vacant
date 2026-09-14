# Goal

A client is writing a very small web framework and needs to take an incoming path
and find which registered pattern it belongs to, pulling out the named pieces of
the path along the way. Their problem is that a path often matches more than one
pattern, and they want the same answer every time -- the more specific one.

The routes are registered by half a dozen modules that load in whatever order the
importer happens to choose, so the answer must not depend on that order.

They also want a pattern that swallows the rest of the path for serving files,
and they want a mistake in a pattern to be reported when the route is registered
rather than on the first request that hits it.

A path that belongs to nobody has to be distinguishable from a path that matched
with no named pieces.
