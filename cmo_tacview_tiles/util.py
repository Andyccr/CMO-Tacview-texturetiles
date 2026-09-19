"""Small shared helpers."""

from __future__ import annotations

from typing import List, Optional, Sequence


def format_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(value) < 1024 or unit == "GiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{n} B"


def glue_negative_option_values(argv: Sequence[str]) -> List[str]:
    """Allow ``--bbox -2,-70,8,-60`` which argparse would otherwise treat as flags."""
    glued: List[str] = []
    i = 0
    while i < len(argv):
        current = argv[i]
        if (
            current == "--bbox"
            and i + 1 < len(argv)
            and argv[i + 1].startswith("-")
            and not argv[i + 1].startswith("--")
        ):
            glued.append(f"--bbox={argv[i + 1]}")
            i += 2
            continue
        glued.append(current)
        i += 1
    return glued


def is_webp_magic(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
