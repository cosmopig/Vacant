"""Allow `python -m vacant.cli ...` invocation alongside the installed
`vacant` console script. Used by integration tests that spawn the CLI
as a subprocess against the in-repo source tree.
"""

from __future__ import annotations

from vacant.cli.commands import main

if __name__ == "__main__":
    main()
