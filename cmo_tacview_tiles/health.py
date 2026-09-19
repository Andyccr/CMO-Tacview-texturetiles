"""Health checks and leftover-file cleanup."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .constants import DEFAULT_BASE_URL, DEFAULT_TIMEOUT
from .downloader import DownloadError, head_remote
from .session import build_session, request_timeout
from .tiles import parse_tile_name


CANARY_TILE = "N25E121"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class DoctorReport:
    checks: List[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def run_doctor(
    *,
    output: Path,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    canary: str = CANARY_TILE,
) -> DoctorReport:
    from . import __version__
    import requests
    import sys

    report = DoctorReport()
    report.checks.append(
        Check("python", True, f"{sys.version.split()[0]}  tool {__version__}")
    )
    report.checks.append(Check("requests", True, requests.__version__))

    out = Path(output)
    try:
        out.mkdir(parents=True, exist_ok=True)
        probe = out / ".cmo_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        report.checks.append(Check("output", True, str(out.resolve())))
    except OSError as exc:
        report.checks.append(Check("output", False, str(exc)))

    session = build_session(retries=1, timeout=timeout)
    tmo = request_timeout(session, timeout)
    tile = parse_tile_name(canary)
    url = tile.url(base_url)
    try:
        remote = head_remote(session, url, tmo)
        if remote.exists:
            size = f"{remote.size} bytes" if remote.size else "unknown size"
            report.checks.append(Check("host", True, f"{url}  {size}"))
        else:
            report.checks.append(Check("host", False, f"{url} returned 404"))
    except (DownloadError, OSError) as exc:
        report.checks.append(Check("host", False, str(exc)))
    return report


def clean_partials(output: Path, *, dry_run: bool = False) -> List[Path]:
    directory = Path(output)
    if not directory.is_dir():
        return []
    removed: List[Path] = []
    for path in sorted(directory.glob("*.part")):
        removed.append(path)
        if not dry_run:
            path.unlink(missing_ok=True)
    return removed
