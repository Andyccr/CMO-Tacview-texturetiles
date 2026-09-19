"""ASCII coverage maps and GeoJSON for a tile set."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Optional, Sequence

from .tiles import Tile, normalize_longitude

# present / unpublished / planned / failed / unknown
GLYPHS = {
    "present": "#",
    "unpublished": ".",
    "planned": "-",
    "failed": "!",
    "unknown": "?",
}


def classify_tile(
    tile: Tile,
    *,
    local: Optional[Mapping[str, object]] = None,
    catalog_status: Optional[str] = None,
) -> str:
    local = local or {}
    if tile.name in local:
        return "present"
    if catalog_status == "missing":
        return "unpublished"
    if catalog_status == "fail":
        return "failed"
    return "planned"


def render_map(
    tiles: Sequence[Tile],
    states: Mapping[str, str],
) -> str:
    """Render a north-up ASCII grid. ``states`` is keyed by tile name."""
    if not tiles:
        return "(no tiles)"
    lats = sorted({t.lat for t in tiles}, reverse=True)
    lons = _display_lons([t.lon for t in tiles])
    by_pos = {(t.lat, t.lon): t for t in tiles}

    header_nums = [_lon_label(lon) for lon in lons]
    col_w = max(3, max(len(n) for n in header_nums))
    lat_w = 3
    lines = [" " * (lat_w + 1) + " ".join(n.rjust(col_w) for n in header_nums)]
    for lat in lats:
        cells = []
        for lon in lons:
            tile = by_pos.get((lat, normalize_longitude(lon)))
            if tile is None:
                cells.append(" ".rjust(col_w))
            else:
                glyph = GLYPHS.get(states.get(tile.name, "unknown"), "?")
                cells.append(glyph.rjust(col_w))
        lines.append(f"{_lat_label(lat).rjust(lat_w)} " + " ".join(cells))
    legend = "  ".join(f"{glyph} {name}" for name, glyph in GLYPHS.items())
    lines.append(legend)
    return "\n".join(lines)


def tiles_geojson(
    tiles: Sequence[Tile],
    states: Optional[Mapping[str, str]] = None,
) -> dict:
    """GeoJSON FeatureCollection of 1° polygons (south-west origin)."""
    states = states or {}
    features = []
    for tile in tiles:
        west, south = float(tile.west), float(tile.south)
        east, north = float(tile.east), float(tile.north)
        # Keep antimeridian tiles as 179..180 rather than wrapping to -180.
        if east < west:
            east = west + 1
        ring = [
            [west, south],
            [east, south],
            [east, north],
            [west, north],
            [west, south],
        ]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": tile.name,
                    "status": states.get(tile.name, "unknown"),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _lat_label(lat: int) -> str:
    return f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"


def _lon_label(lon: int) -> str:
    wrapped = normalize_longitude(lon)
    if wrapped >= 0:
        return f"E{wrapped:03d}"
    return f"W{abs(wrapped):03d}"


def _display_lons(lons: Iterable[int]) -> List[int]:
    """West→east column order, unwrapping the antimeridian when needed."""
    unique = sorted(set(lons))
    if len(unique) <= 1:
        return unique
    n = len(unique)
    gap_sizes = []
    for i in range(n):
        if i == n - 1:
            gap_sizes.append((unique[0] + 360) - unique[i])
        else:
            gap_sizes.append(unique[i + 1] - unique[i])
    max_gap = max(gap_sizes)
    wraps = unique[0] <= -170 and unique[-1] >= 170 and max_gap > 20
    if not wraps:
        return unique
    start = (gap_sizes.index(max_gap) + 1) % n
    return unique[start:] + unique[:start]
