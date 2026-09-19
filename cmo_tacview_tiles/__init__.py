"""Download CMO Sentinel-2 Tacview terrain tiles by theater or bounding box."""

from .theaters import THEATERS, Theater, get_theater
from .tiles import Tile, tiles_from_bbox, parse_tile_name

__all__ = [
    "THEATERS",
    "Theater",
    "Tile",
    "get_theater",
    "parse_tile_name",
    "tiles_from_bbox",
    "__version__",
]

__version__ = "2.0.0"
