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
