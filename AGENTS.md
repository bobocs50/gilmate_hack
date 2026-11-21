# Working agreement

Gilmate is built in a few hours at DevFest Münster 2026 by one person directing coding agents. Read CONTRACT.md before touching anything: it says who owns which files and the data every part agrees on.

- Stay in the files your task owns. If you need a change in a file you do not own, stop and say so.
- No invented data. A place, price, distance, stair or bench is shown only when a tool returned it. Missing data is "unknown", never safe.
- The model writes sentences; plain Python owns every coordinate, distance, warning and source.
- No tool books, pays, sends or writes outside the session.
- Free checks first: `python3 tests/drill_*.py` (no network, no key, no model) must pass before every commit. A new behaviour comes with a drill.
- A run that calls the model or the search costs money. Never start one yourself; say what you would run and wait.
- Never read, print or commit `.env`.
- Page changes count only after you opened the page in a real browser and looked at screenshots at phone and desktop size.
- Small commits, one sentence each, only your own files. Push after every commit.
- Report: what works, what you checked and how, what is untested.
