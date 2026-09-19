#!/usr/bin/env python3
"""Compatibility wrapper around the v2 CLI.

The original script scraped the official texture directory and downloaded
every ``.webp`` file it found. Warfare Sims has since disabled directory
listing, and they ask players not to batch-grab the entire planet.

Use a theater, bounding box, or explicit tile names instead:

    python multithreading.py theaters
    python multithreading.py download --theater taiwan -o ./tiles
    python multithreading.py download --bbox 24,54,28,59
    python multithreading.py download --tiles N25E121,N25E122
"""

from __future__ import annotations

import sys

from cmo_tacview_tiles.cli import main

_RETIRED = """\
The old mass-download spider is retired.

Directory listing is disabled on the official host, so scraping
https://warfaresims.slitherine.com/Tacview_Textures/ no longer works.
Warfare Sims also asks players to download only the theater they need.

Examples:
  python -m cmo_tacview_tiles theaters
  python -m cmo_tacview_tiles download --theater taiwan -o ./tiles
  python -m cmo_tacview_tiles download --bbox 24,54,28,59
  python -m cmo_tacview_tiles download --tiles N25E121,N25E122
"""


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        sys.stderr.write(_RETIRED + "\n")
        raise SystemExit(main(["--help"]))
    raise SystemExit(main(argv))
