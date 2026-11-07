from __future__ import annotations

import json
from pathlib import Path

from contract import CampusInput, CampusOutput
from plugin.campus import notam_text
from plugin.rules import box, points, rules
from plugin.scenario import generate
from plugin.world import CAMPUS, NOTAMS, PLAN, ROUTE


def open_campus(given: CampusInput, workspace: Path) -> CampusOutput:
    if not 1 <= given.seed <= 9999:
        raise ValueError("seed must be between 1 and 9999")
    data = generate(given.seed)
    for stale in (PLAN, ROUTE):
        (workspace / stale).unlink(missing_ok=True)
    (workspace / CAMPUS).write_text(json.dumps(data), encoding="utf-8")
    (workspace / NOTAMS).write_text(notam_text(data["notam"]["ring"]), encoding="utf-8")
    return CampusOutput(
        campus_path=CAMPUS,
        notams_path=NOTAMS,
        rules=rules(),
        bbox=box(),
        points=points(data),
        building_count=len(data["buildings"]),
    )
