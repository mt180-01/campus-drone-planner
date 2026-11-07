"""The exact reference: the shortest route that keeps every rule, found by searching every order of the drop-offs."""

from __future__ import annotations

import math
from dataclasses import dataclass

from plugin.world import (
    BATTERY_M,
    CHARGE_DWELL_S,
    DROPOFF_DWELL_S,
    NOTAM_OFF_S,
    NOTAM_ON_S,
    SPEED_MPS,
    START_S,
    World,
)

MOST_CHARGES = 3  # charging stops (pads, or the depot passed through) before the final landing


@dataclass(frozen=True)
class Plan:
    stops: tuple[str, ...]
    flags: tuple[bool, ...]
    length: float
    arrivals: tuple[float, ...]


def dwell(world: World, stop: str) -> int:
    return DROPOFF_DWELL_S if world.point(stop).kind == "dropoff" else CHARGE_DWELL_S


def hop(world: World, a: str, b: str, leave: float, notam: bool) -> tuple[float, bool]:
    """The length of the leg a to b leaving at ``leave`` seconds, and whether it must avoid the temporary zone.

    A leg takes the shortest path unless it is near the zone while the zone is active."""
    flown = world.leg(a, b, False)[0]
    if not notam or not any(t0 <= NOTAM_OFF_S and t1 >= NOTAM_ON_S for t0, t1 in world.zone_times(a, b, leave)):
        return flown, False
    return world.leg(a, b, True)[0], True


def solve(world: World, *, notam: bool = True, window: bool = True) -> Plan | None:
    ids = list(world.points)
    drops = {i for i in ids if world.point(i).kind == "dropoff"}
    best: list[Plan | None] = [None]
    best_length = [math.inf]

    def search(cur: str, seen: frozenset, used: float, total: float, wait: float, stops: list, flags: list, arrivals: list, charges: int) -> None:
        if total >= best_length[0]:
            return
        if seen == drops and cur == "depot" and len(stops) > 1:
            best_length[0] = total
            best[0] = Plan(tuple(stops), tuple(flags), total, tuple(arrivals))
            return
        for nxt in sorted(ids, key=lambda i: world.leg(cur, i, False)[0] if i != cur else math.inf):
            if nxt == cur or (nxt in drops and nxt in seen):
                continue
            charging = nxt not in drops
            final = nxt == "depot" and seen == drops
            if charging and not final and (charges >= MOST_CHARGES or world.point(cur).kind != "dropoff"):
                continue
            leave = START_S + total / SPEED_MPS + wait
            flown, avoids = hop(world, cur, nxt, leave, notam)
            if used + flown > BATTERY_M:
                continue
            arrive = leave + flown / SPEED_MPS
            if window and nxt in drops and world.point(nxt).window and not world.point(nxt).window[0] <= arrive <= world.point(nxt).window[1]:
                continue
            stops.append(nxt)
            flags.append(avoids)
            arrivals.append(arrive)
            search(
                nxt,
                seen | {nxt} if nxt in drops else seen,
                0.0 if charging else used + flown,
                total + flown,
                wait + dwell(world, nxt),
                stops,
                flags,
                arrivals,
                charges + (1 if charging and not final else 0),
            )
            stops.pop()
            flags.pop()
            arrivals.pop()

    search("depot", frozenset(), 0.0, 0.0, 0.0, ["depot"], [], [float(START_S)], 0)
    return best[0]
