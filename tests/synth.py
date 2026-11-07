"""Hand-made geometry for the verifier's boundary cases: a flat test map, routes written with exact timestamps."""

from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path

from slimconfig import build_output, plain_output

from contract import BBox, Coordinate, MapPoint, PlanOutput, PointKind, Polygon, ReferenceOutput, Rules
from plugin.geo import COS0, EARTH_RADIUS, LAT0, LON0

SPEED = 10.0


def lonlat(x: float, y: float) -> tuple[float, float]:
    """The unrounded inverse of the map projection, so lengths in the tests are exact."""
    return LON0 + math.degrees(x / (EARTH_RADIUS * COS0)), LAT0 + math.degrees(y / EARTH_RADIUS)


def ring(name: str, corners: list[tuple[float, float]]) -> Polygon:
    return Polygon(name=name, ring=[Coordinate(lon=lon, lat=lat) for lon, lat in (lonlat(*c) for c in corners)])


def square(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def point(point_id: str, kind: PointKind, x: float, y: float, window: tuple[str, str] = ("", "")) -> MapPoint:
    lon, lat = lonlat(x, y)
    return MapPoint(id=point_id, kind=kind, lon=lon, lat=lat, window_open=window[0], window_close=window[1])


def reference(
    drops: dict[str, tuple[float, float]] | None = None,
    *,
    start: str = "14:56:00",
    optimal: float = 1.0,
    windows: dict[str, tuple[str, str]] | None = None,
    extra_pads: bool = True,
) -> ReferenceOutput:
    """A flat test map: a building south-east of the axis, a temporary zone on the x-axis at x 400-500."""
    drops = drops or {"D1": (250, 0), "D2": (500, 0), "D3": (750, 0), "D4": (1000, 0)}
    windows = windows or {}
    points = [point("depot", PointKind.DEPOT, 0, 0)]
    if extra_pads:
        points += [point("pad1", PointKind.PAD, 500, 600), point("pad2", PointKind.PAD, 1000, 600), point("pad3", PointKind.PAD, 0, 600)]
    points += [point(i, PointKind.DROPOFF, *xy, windows.get(i, ("", ""))) for i, xy in drops.items()]
    west, south = lonlat(-500, -1000)
    east, north = lonlat(3000, 1500)
    return ReferenceOutput(
        rules=Rules(
            battery_m=2000.0, speed_mps=SPEED, buffer_m=5.0, start_time=start, dropoff_dwell_s=30, charge_dwell_s=120,
            notam_from="15:00:00", notam_until="15:20:00",
        ),
        bbox=BBox(min_lon=west, min_lat=south, max_lon=east, max_lat=north),
        points=points,
        buildings=[ring("B1", square(300, 100, 400, 200))],
        notam=ring("NOTAM", square(400, -50, 480, 50)),
        optimal_length_m=optimal,
        optimal_stops=["depot", *drops, "depot"],
    )


def clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def write_route(
    workspace: Path,
    ref: ReferenceOutput,
    stops: list[str],
    legs: list[list[tuple[float, float]]] | None = None,
) -> PlanOutput:
    """Write route.geojson and plan.json for ``stops``, going straight (or along ``legs``' extra vertices)."""
    at = {p.id: (p.lon, p.lat) for p in ref.points}
    from verifier.geometry import to_xy

    coordinates = [at[stops[0]]]
    marks = [0]
    for index, stop in enumerate(stops[1:]):
        for x, y in (legs[index] if legs else []):
            coordinates.append(lonlat(x, y))
        coordinates.append(at[stop])
        marks.append(len(coordinates) - 1)
    xy = [to_xy(*c) for c in coordinates]
    cumulative = [0.0]
    for a, b in pairwise(xy):
        cumulative.append(cumulative[-1] + math.dist(a, b))
    kinds = {p.id: p.kind for p in ref.points}
    now, planned = float(int(ref.rules.start_time[:2]) * 3600 + int(ref.rules.start_time[3:5]) * 60), []
    for index, stop in enumerate(stops):
        if index:
            now += (cumulative[marks[index]] - cumulative[marks[index - 1]]) / SPEED
        arrive = now
        if 0 < index < len(stops) - 1:
            now += 30 if kinds[stop] is PointKind.DROPOFF else 120
        planned.append({"id": stop, "kind": kinds[stop].value, "lon": at[stop][0], "lat": at[stop][1], "arrive": clock(arrive), "depart": clock(now)})
    (workspace / "route.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": [list(c) for c in coordinates]}}]})
    )
    (workspace / "plan.json").write_text(
        json.dumps({"start_time": ref.rules.start_time, "speed_mps": SPEED, "total_length_m": cumulative[-1], "stops": planned})
    )
    return PlanOutput(route_path="route.geojson", plan_path="plan.json", total_length_m=cumulative[-1], finish_time=planned[-1]["arrive"])


def typed(value, cls):
    return build_output(plain_output(value), cls)
