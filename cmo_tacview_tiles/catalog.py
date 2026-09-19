"""Persistent catalog of remote tile status next to downloaded files.

The official host 404s unpublished 1° cells. Remembering those misses avoids
re-probing the same ocean squares on every run.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .constants import CATALOG_FILENAME, MIN_VALID_BYTES
from .tiles import Tile, parse_tile_name
from .util import is_webp_magic

SCHEMA_VERSION = 1


@dataclass
class CatalogEntry:
    name: str
    status: str  # ok | skip | missing | fail
    bytes: Optional[int] = None
    etag: Optional[str] = None
    error: Optional[str] = None
    updated: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        return {k: v for k, v in data.items() if v is not None}


class Catalog:
    def __init__(self, path: Path, entries: Optional[Dict[str, CatalogEntry]] = None):
        self.path = Path(path)
        self.entries: Dict[str, CatalogEntry] = dict(entries or {})

    @classmethod
    def load(cls, output_dir: Path) -> "Catalog":
        path = Path(output_dir) / CATALOG_FILENAME
        if not path.is_file():
            return cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(path)
        entries: Dict[str, CatalogEntry] = {}
        for name, item in (raw.get("tiles") or {}).items():
            if not isinstance(item, dict):
                continue
            entries[name] = CatalogEntry(
                name=name,
                status=str(item.get("status") or "fail"),
                bytes=item.get("bytes"),
                etag=item.get("etag"),
                error=item.get("error"),
                updated=item.get("updated"),
            )
        return cls(path, entries)

    def record(
        self,
        tile: Tile,
        status: str,
        *,
        size: Optional[int] = None,
        etag: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.entries[tile.name] = CatalogEntry(
            name=tile.name,
            status=status,
            bytes=size,
            etag=etag,
            error=error,
            updated=_now(),
        )

    def get(self, tile: Tile) -> Optional[CatalogEntry]:
        return self.entries.get(tile.name)

    def is_known_missing(self, tile: Tile) -> bool:
        entry = self.get(tile)
        return entry is not None and entry.status == "missing"

    def failed_tiles(self) -> List[Tile]:
        tiles: List[Tile] = []
        for entry in self.entries.values():
            if entry.status == "fail":
                try:
                    tiles.append(parse_tile_name(entry.name))
                except ValueError:
                    continue
        return tiles

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "updated": _now(),
            "tiles": {name: entry.to_dict() for name, entry in sorted(self.entries.items())},
        }
        data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=".catalog.", suffix=".tmp", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(data)
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def scan_local(output_dir: Path) -> Dict[str, Path]:
    """Map tile names to existing ``.webp`` files in ``output_dir``."""
    found: Dict[str, Path] = {}
    directory = Path(output_dir)
    if not directory.is_dir():
        return found
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() != ".webp":
            continue
        if path.name.endswith(".part"):
            continue
        try:
            tile = parse_tile_name(path.stem)
        except ValueError:
            continue
        if path.stat().st_size < MIN_VALID_BYTES:
            continue
        found[tile.name] = path
    return found


@dataclass
class VerifyIssue:
    name: str
    problem: str
    path: Optional[str] = None


def verify_files(output_dir: Path, catalog: Optional[Catalog] = None) -> List[VerifyIssue]:
    """Check local WebP files for magic bytes and catalog size mismatches."""
    issues: List[VerifyIssue] = []
    directory = Path(output_dir)
    if not directory.is_dir():
        return [VerifyIssue(name="", problem=f"folder not found: {directory}")]
    for path in sorted(directory.glob("*.webp")):
        if path.name.endswith(".part"):
            continue
        try:
            tile = parse_tile_name(path.stem)
        except ValueError:
            issues.append(VerifyIssue(name=path.name, problem="not an SRTM tile name", path=str(path)))
            continue
        size = path.stat().st_size
        header = path.read_bytes()[:12] if size >= 12 else path.read_bytes()
        if size < MIN_VALID_BYTES:
            issues.append(VerifyIssue(name=tile.name, problem=f"too small ({size} bytes)", path=str(path)))
            continue
        if not is_webp_magic(header):
            issues.append(VerifyIssue(name=tile.name, problem="not a WebP (missing RIFF/WEBP header)", path=str(path)))
        if catalog is not None:
            entry = catalog.get(tile)
            if entry and entry.bytes and entry.bytes != size:
                issues.append(
                    VerifyIssue(
                        name=tile.name,
                        problem=f"size {size} != catalog {entry.bytes}",
                        path=str(path),
                    )
                )
    return issues


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
