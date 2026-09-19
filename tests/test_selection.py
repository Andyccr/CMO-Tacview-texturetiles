from __future__ import annotations

from pathlib import Path

from cmo_tacview_tiles.selection import SelectionRequest, resolve_selection
from cmo_tacview_tiles.tiles import TileError
import pytest


def test_resolve_theater_and_pad() -> None:
    tiles = resolve_selection(SelectionRequest(theaters=["hormuz"]))
    padded = resolve_selection(SelectionRequest(theaters=["hormuz"], pad=1))
    assert len(padded) > len(tiles)


def test_resolve_from_file(tmp_path: Path) -> None:
    path = tmp_path / "list.txt"
    path.write_text("N25E121\n")
    tiles = resolve_selection(SelectionRequest(from_file=path))
    assert [t.name for t in tiles] == ["N25E121"]


def test_empty_selection_errors() -> None:
    with pytest.raises(TileError, match="select tiles"):
        resolve_selection(SelectionRequest())


def test_pending_skips_local_and_missing() -> None:
    from cmo_tacview_tiles.selection import pending_tiles
    from cmo_tacview_tiles.tiles import parse_tile_name

    tiles = [
        parse_tile_name("N25E121"),
        parse_tile_name("N25E122"),
        parse_tile_name("N10E010"),
    ]
    pending = pending_tiles(
        tiles,
        local={"N25E121": True},
        catalog_missing=["N10E010"],
    )
    assert [t.name for t in pending] == ["N25E122"]
