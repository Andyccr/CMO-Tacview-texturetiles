from __future__ import annotations


def make_webp(size: int = 512, tag: bytes = b"TEST") -> bytes:
    """Return a RIFF/WEBP-shaped blob of the requested size."""
    if size < 16:
        raise ValueError("size too small")
    payload = bytearray(size)
    payload[0:4] = b"RIFF"
    payload[8:12] = b"WEBP"
    payload[12 : 12 + len(tag)] = tag
    return bytes(payload)
