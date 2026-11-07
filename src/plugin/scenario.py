"""Draw campuses from a seed until one makes every rule bite, then fix the drop-off's time window."""

from __future__ import annotations

import random
from itertools import pairwise

from plugin.campus import document, layout
from plugin.reference import dwell, hop, solve
from plugin.world import SPEED_MPS, START_S, World

ATTEMPTS = 80


def bites(world: World, route: tuple[str, ...]) -> bool:
    """Whether following ``route`` along the plain shortest paths would break the temporary zone."""
    total, wait = 0.0, 0.0
    for a, b in pairwise(route):
        _, avoids = hop(world, a, b, START_S + total / SPEED_MPS + wait, True)
        if avoids:
            return True
        total += world.leg(a, b, False)[0]
        wait += dwell(world, b)
    return False


def generate(seed: int) -> dict:
    """campus.json's content for ``seed``: the zone costs a detour, charging is needed, and a window binds the order."""
    for attempt in range(ATTEMPTS):
        rng = random.Random(seed * 1000 + attempt)
        try:
            parts = layout(rng)
        except ValueError:
            continue
        world = World(document(seed, parts, None))
        free = solve(world, notam=False, window=False)
        plan = solve(world, window=False)
        if free is None or plan is None or free.length < 2200 or not bites(world, free.stops):
            continue
        opening = rng.choice([s for s in plan.stops if world.point(s).kind == "dropoff"])
        arrival = plan.arrivals[plan.stops.index(opening)]
        windowed = document(seed, parts, (opening, round(arrival) - 60, round(arrival) + 180))
        final = solve(World(windowed))
        if final is not None and abs(final.length - plan.length) < 1e-6:
            return windowed
    raise ValueError(f"no campus found for seed {seed}")
