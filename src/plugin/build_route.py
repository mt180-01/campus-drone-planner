from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

from contract import BuildInput, BuildOutput, PlannedStop, PointKind
from plugin.geo import to_lonlat, to_xy
from plugin.world import (
    CHARGE_DWELL_S,
    DROPOFF_DWELL_S,
    PLAN,
    ROUTE,
    SPEED_MPS,
    START_S,
    World,
    clock,
)


def build_route(given: BuildInput, workspace: Path) -> BuildOutput:
    world = World.load(workspace)
    stops = given.stops
    if len(stops) < 2 or stops[0] != "depot" or stops[-1] != "depot":
        raise ValueError("stops must start and end at depot")
    if len(given.avoid_notam) != len(stops) - 1:
        raise ValueError("avoid_notam needs one entry per leg: one fewer than stops")
    coordinates: list[tuple[float, float]] = []
    marks: list[int] = []  # the index of each stop's coordinate in the route
    for index, stop in enumerate(stops):
        point = world.point(stop)
        if index:
            path = world.leg(stops[index - 1], stop, given.avoid_notam[index - 1])[1]
            coordinates += [to_lonlat(x, y) for x, y in path[1:-1]]
        marks.append(len(coordinates))
        coordinates.append((point.lon, point.lat))
    xy = [to_xy(lon, lat) for lon, lat in coordinates]
    cumulative = [0.0]
    for a, b in pairwise(xy):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    planned, clock_s = [], float(START_S)
    charges: list[float] = []
    for index, stop in enumerate(stops):
        point = world.point(stop)
        if index:
            clock_s += (cumulative[marks[index]] - cumulative[marks[index - 1]]) / SPEED_MPS
        arrive = clock_s
        if 0 < index < len(stops) - 1:
            clock_s += DROPOFF_DWELL_S if point.kind == "dropoff" else CHARGE_DWELL_S
        if point.kind != "dropoff":
            charges.append(cumulative[marks[index]])
        planned.append(PlannedStop(id=stop, kind=PointKind(point.kind), lon=point.lon, lat=point.lat, arrive=clock(arrive), depart=clock(clock_s)))
    (workspace / ROUTE).write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"name": "route"}, "geometry": {"type": "LineString", "coordinates": [list(c) for c in coordinates]}}
                ],
            }
        ),
        encoding="utf-8",
    )
    total = cumulative[-1]
    plan = {
        "start_time": clock(START_S),
        "speed_mps": SPEED_MPS,
        "total_length_m": round(total, 3),
        "stops": [
            {"id": s.id, "kind": s.kind.value, "lon": s.lon, "lat": s.lat, "arrive": s.arrive, "depart": s.depart} for s in planned
        ],
    }
    (workspace / PLAN).write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return BuildOutput(
        route_path=ROUTE,
        plan_path=PLAN,
        total_length_m=round(total, 3),
        finish_time=planned[-1].arrive,
        stretches_m=[round(b - a, 3) for a, b in pairwise(charges)],
        stops=planned,
    )
