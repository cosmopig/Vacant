# Goal

A client is about to start posting their application logs into a shared channel and
needs the secrets taken out of each line first. They know roughly what their secrets
look like and gave three real examples from yesterday's log:

    AKIAIOSFODNN7EXAMPLE
    Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.abcdef
    postgres://svc:hunter2@db.internal:5432/app

What they care about:

- after the pass, none of the secret text is anywhere in the result;
- everything in the line that is not a secret comes back exactly as it was, because
  a person is going to read the line and needs the rest of it;
- running the pass on a line that has already been through it changes nothing
  further;
- a secret that appears twice in one line is gone both times;
- they can ask what was found in a line so a dashboard can count it, and a line with
  nothing in it answers with nothing.

What the replacement looks like, and how much of the surrounding structure is kept,
is up to whoever writes it.
