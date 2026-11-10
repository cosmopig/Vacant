<!-- SYNTHETIC EXAMPLE PROFILE derived from personas/examples.json (example_cautious) on PR #92.
     Written by hand to demo the metric. NOT a real user's process. -->
How this user wants work done:
- If a request leaves a business rule or output format open, ask ONE short question and stop before editing.   [scope: feature, bugfix]
- Search and read the relevant code and its tests before the first edit.   [scope: code]
- Run the existing tests before the first edit and again after the last edit.   [scope: code]
- Smallest diff that fixes the issue; never remove or rename a public function.   [scope: refactor]
- For written deliverables, read the inputs first and show the arithmetic.   [scope: deliverable]
