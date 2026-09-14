# Goal

A client publishes articles and needs a piece of URL for each one. They hand over a
whole batch of titles at once, as they come out of their editor.

What they care about:

- one slug per title, in the same order as the titles they handed in;
- a slug holds only lowercase letters, digits and hyphens, never starts or ends with
  a hyphen, and never has two hyphens in a row;
- no two slugs in a batch are the same, because a URL has to point at one article,
  and the same title really does show up twice in a batch;
- handing in the same batch twice gives the same slugs, because the slugs go into a
  sitemap they diff;
- a title that is already a clean slug, and that nothing else in the batch collides
  with, comes back exactly as it was;
- a title written in a script with no Latin letters in it at all still gets a usable
  slug rather than an empty one.

How a title is turned into a slug, and what a collision is resolved with, is up to
whoever writes it.
