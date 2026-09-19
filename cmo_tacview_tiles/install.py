"""Copy downloaded textures into Tacview / CMO data folders."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence

from .constants import CATALOG_FILENAME, CMO_TEXTURE_RELATIVE, WINDOWS_TEXTURE_RELATIVE


@dataclass(frozen=True)
class InstallTarget:
    path: Path
    label: str
    exists: bool


@dataclass
class InstallSummary:
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    targets: List[Path] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def discover_targets() -> List[InstallTarget]:
    """Guess Tacview texture folders on this machine."""
    found: List[InstallTarget] = []
    seen = set()

    def add(path: Path, label: str) -> None:
        resolved = path.expanduser()
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        found.append(InstallTarget(path=resolved, label=label, exists=resolved.is_dir()))

    programdata = os.environ.get("ProgramData")
    appdata = os.environ.get("APPDATA")
    if programdata:
        add(Path(programdata).joinpath(*WINDOWS_TEXTURE_RELATIVE), "Tacview ProgramData")
    if appdata:
        add(Path(appdata).joinpath(*WINDOWS_TEXTURE_RELATIVE), "Tacview APPDATA")

    for candidate, label in _cmo_install_candidates():
        add(candidate.joinpath(*CMO_TEXTURE_RELATIVE), label)

    env_target = os.environ.get("CMO_TACVIEW_TEXTURES")
    if env_target:
        add(Path(env_target), "CMO_TACVIEW_TEXTURES")

    return found


def _cmo_install_candidates() -> List[tuple]:
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    roots = [
        (Path(program_files) / "Steam" / "steamapps" / "common" / "Command Modern Operations", "Steam CMO"),
        (Path(program_files_x86) / "Steam" / "steamapps" / "common" / "Command Modern Operations", "Steam CMO (x86)"),
        (Path(program_files_x86) / "Matrix Games" / "Command Modern Operations", "Matrix CMO"),
        (Path(program_files) / "Matrix Games" / "Command Modern Operations", "Matrix CMO"),
    ]
    steam = os.environ.get("STEAM_DIR") or os.environ.get("SteamPath")
    if steam:
        roots.append(
            (
                Path(steam) / "steamapps" / "common" / "Command Modern Operations",
                "Steam CMO (STEAM_DIR)",
            )
        )
    return roots


def list_texture_files(source: Path) -> List[Path]:
    source = Path(source)
    if not source.is_dir():
        raise FileNotFoundError(f"source folder not found: {source}")
    files = sorted(
        p
        for p in source.iterdir()
        if p.is_file() and p.suffix.lower() == ".webp" and not p.name.endswith(".part")
        and p.name != CATALOG_FILENAME
    )
    return files


def install_textures(
    source: Path,
    targets: Sequence[Path],
    *,
    dry_run: bool = False,
    overwrite: bool = True,
) -> InstallSummary:
    files = list_texture_files(source)
    summary = InstallSummary()
    if not files:
        summary.errors.append(f"no .webp tiles in {source}")
        return summary

    for target in targets:
        target = Path(target)
        summary.targets.append(target)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
        for src in files:
            dest = target / src.name
            try:
                if dest.exists() and not overwrite:
                    if dest.stat().st_size == src.stat().st_size:
                        summary.skipped += 1
                        continue
                if dry_run:
                    summary.copied += 1
                    continue
                shutil.copy2(src, dest)
                summary.copied += 1
            except OSError as exc:
                summary.failed += 1
                summary.errors.append(f"{src.name} -> {dest}: {exc}")
    return summary


def format_target_help(targets: Iterable[InstallTarget]) -> str:
    lines = ["Detected install locations:"]
    any_found = False
    for item in targets:
        mark = "yes" if item.exists else "no "
        lines.append(f"  [{mark}] {item.label}: {item.path}")
        any_found = True
    if not any_found:
        lines.append("  (none on this OS — pass --target explicitly)")
        lines.append(
            "  Windows defaults: %ProgramData%\\Tacview\\Data\\Terrain\\Textures"
        )
        lines.append(
            "                    [CMO]\\Resources\\Tacview\\Data\\Terrain\\Textures"
        )
    return "\n".join(lines)
