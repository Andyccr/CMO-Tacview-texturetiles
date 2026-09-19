"""Shared defaults for the CMO Tacview texture downloader."""

from __future__ import annotations

DEFAULT_BASE_URL = "https://warfaresims.slitherine.com/Tacview_Textures/"
DEFAULT_OUTPUT_DIR = "tacview_textures"
DEFAULT_WORKERS = 4
DEFAULT_TIMEOUT = 30.0
DEFAULT_RETRIES = 3
DEFAULT_MAX_TILES = 400
DEFAULT_CONFIRM_AFTER = 50
CHUNK_SIZE = 64 * 1024
MIN_VALID_BYTES = 256
USER_AGENT = (
    "CMO-Tacview-texturetiles/2.0 "
    "(+https://github.com/Andyccr/CMO-Tacview-texturetiles; personal CMO use)"
)

# Official install locations (Windows). CMO and standalone Tacview both work.
WINDOWS_TEXTURE_RELATIVE = ("Tacview", "Data", "Terrain", "Textures")
CMO_TEXTURE_RELATIVE = ("Resources", "Tacview", "Data", "Terrain", "Textures")
