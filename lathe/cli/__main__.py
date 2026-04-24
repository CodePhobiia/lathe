"""``python -m lathe.cli`` entry point.

Dispatches to the subcommand handlers in the sibling ``*_cmd``
modules.
"""

from __future__ import annotations

from . import main

if __name__ == "__main__":
    main()
