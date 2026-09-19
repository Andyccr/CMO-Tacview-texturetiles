"""Concurrent tile downloader with resume, skip, catalog, and 404 handling."""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional

import requests

from .catalog import Catalog
from .constants import (
    CHUNK_SIZE,
    DEFAULT_BASE_URL,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
    DEFAULT_WORKERS,
    MIN_VALID_BYTES,
)
from .session import request_timeout, thread_session
from .tiles import Tile

ResultCallback = Callable[["DownloadResult", int, int], None]
LOG = logging.getLogger("cmo_tacview_tiles")


class RateLimiter:
    """Space out HTTP starts across worker threads."""

    def __init__(self, interval: float = 0.0) -> None:
        self.interval = max(0.0, float(interval))
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


class DownloadError(RuntimeError):
    """A single-tile download failed after retries."""


@dataclass(frozen=True)
class RemoteMeta:
    exists: bool
    size: Optional[int] = None
    etag: Optional[str] = None
    last_modified: Optional[str] = None


@dataclass
class DownloadResult:
    tile: Tile
    status: str  # ok | skip | missing | fail
    path: Optional[Path] = None
    bytes_written: int = 0
    error: Optional[str] = None
    elapsed: float = 0.0
    etag: Optional[str] = None
    cached: bool = False

    @property
    def remote_size(self) -> Optional[int]:
        return self.bytes_written or None


@dataclass
class DownloadSummary:
    results: List[DownloadResult] = field(default_factory=list)
    elapsed: float = 0.0

    @property
    def ok(self) -> int:
        return sum(1 for r in self.results if r.status == "ok")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skip")

    @property
    def missing(self) -> int:
        return sum(1 for r in self.results if r.status == "missing")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def cached_missing(self) -> int:
        return sum(1 for r in self.results if r.status == "missing" and r.cached)

    @property
    def bytes_written(self) -> int:
        return sum(r.bytes_written for r in self.results)

    @property
    def failed_results(self) -> List[DownloadResult]:
        return [r for r in self.results if r.status == "fail"]

    def to_dict(self) -> dict:
        return {
            "downloaded": self.ok,
            "skipped": self.skipped,
            "missing": self.missing,
            "failed": self.failed,
            "cached_missing": self.cached_missing,
            "bytes": self.bytes_written,
            "elapsed": round(self.elapsed, 3),
            "failures": [
                {"tile": r.tile.name, "error": r.error} for r in self.failed_results
            ],
        }


@dataclass
class ProbeResult:
    tile: Tile
    status: str  # ok | missing | fail
    bytes: Optional[int] = None
    etag: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False
    url: str = ""


def download_tiles(
    tiles: Iterable[Tile],
    output_dir: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    skip_existing: bool = True,
    force: bool = False,
    dry_run: bool = False,
    trust_local: bool = False,
    skip_known_missing: bool = True,
    catalog: Optional[Catalog] = None,
    delay: float = 0.0,
    on_result: Optional[ResultCallback] = None,
) -> DownloadSummary:
    """Download ``tiles`` into ``output_dir``.

    Missing tiles (HTTP 404) are expected — CMO does not publish a tile for
    every 1° cell — and are reported as ``missing``, not failures.
    """
    tile_list = list(tiles)
    output_dir = Path(output_dir)
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    summary = DownloadSummary()
    total = len(tile_list)
    if total == 0:
        return summary

    workers = max(1, min(int(workers), total))
    lock = threading.Lock()
    done = 0
    start = time.perf_counter()

    def _handle(result: DownloadResult) -> None:
        nonlocal done
        with lock:
            summary.results.append(result)
            done += 1
            current = done
            if catalog is not None and result.error != "dry-run":
                size = None
                if result.path and result.path.exists():
                    size = result.path.stat().st_size
                elif result.bytes_written:
                    size = result.bytes_written
                recorded = "ok" if result.status == "skip" else result.status
                catalog.record(
                    result.tile,
                    recorded,
                    size=size,
                    etag=result.etag,
                    error=result.error if result.status == "fail" else None,
                )
        if on_result is not None:
            on_result(result, current, total)

    if dry_run:
        for tile in tile_list:
            _handle(
                DownloadResult(
                    tile=tile,
                    status="skip",
                    path=output_dir / tile.filename,
                    error="dry-run",
                )
            )
        summary.elapsed = time.perf_counter() - start
        return summary

    limiter = RateLimiter(delay)

    def _job(tile: Tile) -> DownloadResult:
        return download_one(
            tile,
            output_dir / tile.filename,
            base_url=base_url,
            timeout=timeout,
            retries=retries,
            skip_existing=skip_existing and not force,
            trust_local=trust_local and not force,
            skip_known_missing=skip_known_missing and not force,
            catalog=catalog,
            limiter=limiter,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_job, tile): tile for tile in tile_list}
        try:
            for future in as_completed(futures):
                tile = futures[future]
                try:
                    result = future.result()
                except KeyboardInterrupt:
                    raise
                except Exception as exc:  # noqa: BLE001 — worker must not kill the pool
                    result = DownloadResult(tile=tile, status="fail", error=str(exc))
                _handle(result)
        except KeyboardInterrupt:
            for future in futures:
                future.cancel()
            raise

    summary.elapsed = time.perf_counter() - start
    return summary


def download_one(
    tile: Tile,
    dest: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    skip_existing: bool = True,
    trust_local: bool = False,
    skip_known_missing: bool = True,
    catalog: Optional[Catalog] = None,
    limiter: Optional[RateLimiter] = None,
) -> DownloadResult:
    started = time.perf_counter()
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = tile.url(base_url)
    part = dest.with_name(dest.name + ".part")

    if skip_known_missing and catalog is not None and catalog.is_known_missing(tile):
        return DownloadResult(
            tile=tile,
            status="missing",
            elapsed=time.perf_counter() - started,
            cached=True,
            error="catalog",
        )

    if trust_local and dest.exists() and dest.stat().st_size >= MIN_VALID_BYTES:
        return DownloadResult(
            tile=tile,
            status="skip",
            path=dest,
            bytes_written=0,
            elapsed=time.perf_counter() - started,
        )

    session = thread_session(retries=retries, timeout=timeout)
    tmo = request_timeout(session, timeout)
    if limiter is not None:
        limiter.wait()
    LOG.debug("HEAD %s", url)

    try:
        remote = head_remote(session, url, tmo)
        if not remote.exists:
            _cleanup(part)
            return DownloadResult(
                tile=tile,
                status="missing",
                elapsed=time.perf_counter() - started,
                etag=remote.etag,
            )

        remote_size = remote.size if remote.size is not None else -1
        if skip_existing and dest.exists() and remote_size > 0 and dest.stat().st_size == remote_size:
            _cleanup(part)
            return DownloadResult(
                tile=tile,
                status="skip",
                path=dest,
                bytes_written=0,
                elapsed=time.perf_counter() - started,
                etag=remote.etag,
            )

        written = _get_to_file(session, url, dest, part, remote_size, tmo)
        return DownloadResult(
            tile=tile,
            status="ok",
            path=dest,
            bytes_written=written,
            elapsed=time.perf_counter() - started,
            etag=remote.etag,
        )
    except DownloadError as exc:
        return DownloadResult(
            tile=tile,
            status="fail",
            error=str(exc),
            elapsed=time.perf_counter() - started,
        )
    except requests.RequestException as exc:
        return DownloadResult(
            tile=tile,
            status="fail",
            error=str(exc),
            elapsed=time.perf_counter() - started,
        )


def probe_tiles(
    tiles: Iterable[Tile],
    *,
    base_url: str = DEFAULT_BASE_URL,
    workers: int = DEFAULT_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    catalog: Optional[Catalog] = None,
    skip_known_missing: bool = True,
) -> List[ProbeResult]:
    tile_list = list(tiles)
    if not tile_list:
        return []
    workers = max(1, min(int(workers), len(tile_list)))
    results: List[ProbeResult] = []
    lock = threading.Lock()

    def _job(tile: Tile) -> ProbeResult:
        url = tile.url(base_url)
        if skip_known_missing and catalog is not None and catalog.is_known_missing(tile):
            return ProbeResult(tile=tile, status="missing", cached=True, url=url)
        session = thread_session(retries=retries, timeout=timeout)
        tmo = request_timeout(session, timeout)
        try:
            remote = head_remote(session, url, tmo)
            if not remote.exists:
                return ProbeResult(tile=tile, status="missing", etag=remote.etag, url=url)
            return ProbeResult(
                tile=tile,
                status="ok",
                bytes=remote.size,
                etag=remote.etag,
                url=url,
            )
        except (DownloadError, requests.RequestException) as exc:
            return ProbeResult(tile=tile, status="fail", error=str(exc), url=url)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_job, tile) for tile in tile_list]
        for future in as_completed(futures):
            result = future.result()
            with lock:
                results.append(result)
                if catalog is not None and result.status in {"ok", "missing"}:
                    catalog.record(
                        result.tile,
                        result.status,
                        size=result.bytes,
                        etag=result.etag,
                    )
    order = {tile.name: i for i, tile in enumerate(tile_list)}
    results.sort(key=lambda r: order.get(r.tile.name, 0))
    return results


def head_remote(session: requests.Session, url: str, timeout: float) -> RemoteMeta:
    """HEAD a tile URL. 404 → ``exists=False``. 405/501 falls back to GET."""
    response = session.head(url, timeout=timeout, allow_redirects=True)
    if response.status_code == 404:
        return RemoteMeta(exists=False)
    if response.status_code in (405, 501):
        response.close()
        return _probe_get_meta(session, url, timeout)
    if response.status_code >= 400:
        raise DownloadError(f"HEAD {url} -> HTTP {response.status_code}")
    length = response.headers.get("Content-Length")
    etag = response.headers.get("ETag")
    last_modified = response.headers.get("Last-Modified")
    if length is None:
        meta = _probe_get_meta(session, url, timeout)
        return RemoteMeta(
            exists=meta.exists,
            size=meta.size,
            etag=etag or meta.etag,
            last_modified=last_modified or meta.last_modified,
        )
    return RemoteMeta(
        exists=True,
        size=int(length),
        etag=etag,
        last_modified=last_modified,
    )


def _probe_get_meta(session: requests.Session, url: str, timeout: float) -> RemoteMeta:
    response = session.get(url, timeout=timeout, stream=True, allow_redirects=True)
    try:
        if response.status_code == 404:
            return RemoteMeta(exists=False)
        if response.status_code >= 400:
            raise DownloadError(f"GET {url} -> HTTP {response.status_code}")
        length = response.headers.get("Content-Length")
        return RemoteMeta(
            exists=True,
            size=int(length) if length is not None else None,
            etag=response.headers.get("ETag"),
            last_modified=response.headers.get("Last-Modified"),
        )
    finally:
        response.close()


def _get_to_file(
    session: requests.Session,
    url: str,
    dest: Path,
    part: Path,
    remote_size: int,
    timeout: float,
) -> int:
    resume_from = part.stat().st_size if part.exists() else 0
    headers = {}
    if resume_from > 0 and remote_size > resume_from:
        headers["Range"] = f"bytes={resume_from}-"

    response = session.get(
        url, timeout=timeout, stream=True, allow_redirects=True, headers=headers
    )
    try:
        if response.status_code == 404:
            _cleanup(part)
            raise DownloadError(f"tile disappeared during GET: {url}")
        if response.status_code >= 400:
            raise DownloadError(f"GET {url} -> HTTP {response.status_code}")

        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            raise DownloadError(f"server returned HTML instead of a texture: {url}")

        mode = "ab" if response.status_code == 206 and resume_from > 0 else "wb"
        if mode == "wb":
            resume_from = 0

        with open(part, mode) as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    handle.write(chunk)
                    resume_from += len(chunk)
    finally:
        response.close()

    size = part.stat().st_size if part.exists() else 0
    if remote_size > 0 and size != remote_size:
        raise DownloadError(
            f"size mismatch for {url}: got {size} bytes, expected {remote_size}"
        )
    if size < MIN_VALID_BYTES:
        _cleanup(part)
        raise DownloadError(f"file too small to be a texture ({size} bytes): {url}")

    os.replace(part, dest)
    return size


def _cleanup(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
