"""SRTM-style 1° terrain tile names used by Tacview and CMO."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence
from urllib.parse import urljoin

TILE_NAME_RE = re.compile(
    r"^(?P<ns>[NS])(?P<lat>\d{2})(?P<ew>[EW])(?P<lon>\d{3})(?:[TBC])?$",
    re.IGNORECASE,
)

# Inclusive SW-corner ranges for a 1° Tacview tile.
LAT_MIN, LAT_MAX = -90, 89
LON_MIN, LON_MAX = -180, 179


class TileError(ValueError):
    """Raised when a tile name or bounding box is invalid."""


@dataclass(frozen=True, order=True)
class Tile:
    """One 1°×1° texture tile, identified by its south-west corner."""

    lat: int
    lon: int

    def __post_init__(self) -> None:
        if not LAT_MIN <= self.lat <= LAT_MAX:
            raise TileError(f"latitude {self.lat} is outside {LAT_MIN}..{LAT_MAX}")
        if not LON_MIN <= self.lon <= LON_MAX:
            raise TileError(f"longitude {self.lon} is outside {LON_MIN}..{LON_MAX}")

    @property
    def name(self) -> str:
        ns = "N" if self.lat >= 0 else "S"
        ew = "E" if self.lon >= 0 else "W"
        return f"{ns}{abs(self.lat):02d}{ew}{abs(self.lon):03d}"

    @property
    def filename(self) -> str:
        return f"{self.name}.webp"

    def url(self, base_url: str) -> str:
        base = base_url if base_url.endswith("/") else base_url + "/"
        return urljoin(base, self.filename)

    @property
    def south(self) -> int:
        return self.lat

    @property
    def north(self) -> int:
        return self.lat + 1

    @property
    def west(self) -> int:
        return self.lon

    @property
    def east(self) -> int:
        return self.lon + 1


def normalize_longitude(lon: int) -> int:
    """Wrap a longitude into the inclusive range [-180, 179]."""
    wrapped = ((int(lon) + 180) % 360) - 180
    return -180 if wrapped == 180 else wrapped


def parse_tile_name(value: str) -> Tile:
    """Parse ``N25E121`` / ``N25E121.webp`` into a :class:`Tile`."""
    raw = value.strip()
    if raw.lower().endswith(".webp"):
        raw = raw[:-5]
    elif raw.lower().endswith(".png") or raw.lower().endswith(".jpg"):
        raw = raw[:-4]
    elif raw.lower().endswith(".jpeg"):
        raw = raw[:-5]
    match = TILE_NAME_RE.match(raw)
    if not match:
        raise TileError(
            f"invalid tile name {value!r}; expected SRTM form like N25E121 or S09W070"
        )
    lat = int(match.group("lat"))
    lon = int(match.group("lon"))
    if match.group("ns").upper() == "S":
        lat = -lat
    if match.group("ew").upper() == "W":
        lon = -lon
    return Tile(lat=lat, lon=normalize_longitude(lon))


def parse_tile_list(values: Iterable[str]) -> List[Tile]:
    tiles: List[Tile] = []
    for raw in values:
        for piece in str(raw).replace(";", ",").split(","):
            piece = piece.strip()
            if piece:
                tiles.append(parse_tile_name(piece))
    return unique_tiles(tiles)


def parse_bbox(text: str) -> Tuple[float, float, float, float]:
    """Parse ``south,west,north,east`` (degrees)."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise TileError("bbox must be south,west,north,east (four comma-separated numbers)")
    try:
        south, west, north, east = (float(p) for p in parts)
    except ValueError as exc:
        raise TileError(f"bbox values must be numbers: {text!r}") from exc
    return south, west, north, east


def tiles_from_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
) -> List[Tile]:
    """Return every 1° tile whose cell intersects the closed bounding box.

    Longitude may wrap the antimeridian (``west > east`` in the usual sense,
    e.g. 170°E to 170°W). Latitude does not wrap.
    """
    if not math.isfinite(south) or not math.isfinite(north):
        raise TileError("bbox latitude must be finite")
    if not math.isfinite(west) or not math.isfinite(east):
        raise TileError("bbox longitude must be finite")
    if south > north:
        raise TileError(f"bbox south ({south}) must be <= north ({north})")
    if south < LAT_MIN or north > LAT_MAX + 1:
        raise TileError(
            f"bbox latitude {south}..{north} is outside {LAT_MIN}..{LAT_MAX + 1}"
        )

    lat_start = max(LAT_MIN, math.floor(south))
    lat_end = min(LAT_MAX, math.floor(north))  # inclusive SW corners
    if lat_start > lat_end:
        return []

    lons = _longitude_sw_corners(west, east)
    tiles: List[Tile] = []
    for lat in range(lat_start, lat_end + 1):
        for lon in lons:
            tiles.append(Tile(lat=lat, lon=lon))
    return unique_tiles(tiles)


def _longitude_sw_corners(west: float, east: float) -> List[int]:
    """Inclusive SW-corner longitudes walking east from ``west`` to ``east``.

    If ``east < west`` the range wraps the antimeridian (170°E → 170°W).
    A span of 360° or more is rejected so this tool cannot be used to grab
    the entire planet in one call.
    """
    span = (east - west) if east >= west else (east + 360.0) - west
    if span >= 360.0 - 1e-9:
        raise TileError("bbox spans the entire planet; choose a smaller region")

    end = east if east >= west else east + 360.0
    start_i = math.floor(west)
    end_i = math.floor(end)
    seen = set()
    lons: List[int] = []
    for lon in range(start_i, end_i + 1):
        normalized = normalize_longitude(lon)
        if normalized not in seen:
            seen.add(normalized)
            lons.append(normalized)
    return lons


def unique_tiles(tiles: Sequence[Tile]) -> List[Tile]:
    seen = set()
    out: List[Tile] = []
    for tile in sorted(tiles):
        if tile not in seen:
            seen.add(tile)
            out.append(tile)
    return out


def merge_tiles(*groups: Iterable[Tile]) -> List[Tile]:
    combined: List[Tile] = []
    for group in groups:
        combined.extend(group)
    return unique_tiles(combined)
