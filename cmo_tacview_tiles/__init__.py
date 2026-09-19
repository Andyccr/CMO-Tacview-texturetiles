"""Download CMO Sentinel-2 Tacview terrain tiles by theater or bounding box."""

from .catalog import Catalog
from .theaters import THEATERS, Theater, get_theater
from .tiles import Tile, expand_tiles, parse_tile_name, tiles_from_bbox

__all__ = [
    "Catalog",
    "THEATERS",
    "Theater",
    "Tile",
    "expand_tiles",
    "get_theater",
    "parse_tile_name",
    "tiles_from_bbox",
    "__version__",
]

__version__ = "2.1.0"
