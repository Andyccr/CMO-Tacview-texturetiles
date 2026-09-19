"""Resolve a set of tiles from theaters, bounding boxes, names, and padding."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Sequence

from .theaters import THEATERS, get_theater
from .tiles import (
    Tile,
    TileError,
    expand_tiles,
    merge_tiles,
    parse_bbox,
    parse_tile_list,
    tiles_from_bbox,
    tiles_from_file,
)


@dataclass
class SelectionRequest:
    theaters: Sequence[str] = field(default_factory=list)
    bboxes: Sequence[str] = field(default_factory=list)
    tiles: Sequence[str] = field(default_factory=list)
    from_file: Optional[Path] = None
    pad: int = 0

    @classmethod
    def from_args(cls, args: object) -> "SelectionRequest":
        from_file = getattr(args, "from_file", None)
        return cls(
            theaters=list(getattr(args, "theater", None) or []),
            bboxes=list(getattr(args, "bbox", None) or []),
            tiles=list(getattr(args, "tiles", None) or []),
            from_file=Path(from_file) if from_file else None,
            pad=int(getattr(args, "pad", 0) or 0),
        )

    def is_empty(self) -> bool:
        return not (self.theaters or self.bboxes or self.tiles or self.from_file)


def resolve_selection(request: SelectionRequest) -> List[Tile]:
    """Build the unique, sorted tile list for a request."""
    if request.pad < 0:
        raise TileError("--pad must be >= 0")
    groups: List[Iterable[Tile]] = []
    for key in request.theaters:
        groups.append(get_theater(key).tiles())
    for box in request.bboxes:
        south, west, north, east = parse_bbox(box)
        groups.append(tiles_from_bbox(south, west, north, east))
    if request.tiles:
        groups.append(parse_tile_list(request.tiles))
    if request.from_file:
        groups.append(tiles_from_file(request.from_file))
    if not groups:
        known = ", ".join(sorted(THEATERS))
        raise TileError(
            "select tiles with --theater, --bbox, --tiles, or --from-file. "
            f"Theaters: {known}"
        )
    tiles = merge_tiles(*groups)
    if request.pad:
        tiles = expand_tiles(tiles, request.pad)
    return tiles


def pending_tiles(
    tiles: Sequence[Tile],
    *,
    local: Optional[Mapping[str, object]] = None,
    catalog_missing: Optional[Sequence[str]] = None,
    refresh_missing: bool = False,
) -> List[Tile]:
    """Tiles that still need a network fetch: not on disk, not a known 404."""
    local = local or {}
    missing = set(catalog_missing or [])
    pending: List[Tile] = []
    for tile in tiles:
        if tile.name in local:
            continue
        if not refresh_missing and tile.name in missing:
            continue
        pending.append(tile)
    return pending
