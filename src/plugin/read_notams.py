from __future__ import annotations

from pathlib import Path

from contract import NotamsInput, NotamsOutput


def read_notams(given: NotamsInput, workspace: Path) -> NotamsOutput:
    path = workspace / given.file.value
    if not path.is_file():
        raise FileNotFoundError(f"{given.file.value} does not exist: call open_campus first")
    return NotamsOutput(file=given.file.value, text=path.read_text(encoding="utf-8"))
