from __future__ import annotations

from pathlib import Path

from contract import CampusInput, ReferenceOutput
from plugin.reference import solve
from plugin.rules import box, points, polygon, rules
from plugin.scenario import generate
from plugin.world import World


def reference_plan(given: CampusInput, workspace: Path) -> ReferenceOutput:
    if not 1 <= given.seed <= 9999:
        raise ValueError("seed must be between 1 and 9999")
    data = generate(given.seed)
    plan = solve(World(data))
    if plan is None:
        raise ValueError(f"seed {given.seed} has no route that keeps every rule")
    return ReferenceOutput(
        rules=rules(),
        bbox=box(),
        points=points(data),
        buildings=[polygon(b["name"], b["ring"]) for b in data["buildings"]],
        notam=polygon(data["notam"]["name"], data["notam"]["ring"]),
        optimal_length_m=round(plan.length, 3),
        optimal_stops=list(plan.stops),
    )
