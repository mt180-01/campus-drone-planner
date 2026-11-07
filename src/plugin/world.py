"""The campus as the tools see it: loaded from campus.json, in meters on the flat map."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as ShapelyPoint

from plugin.geo import Router, length, to_xy

CAMPUS = "campus.json"
NOTAMS = "notams.txt"
ROUTE = "route.geojson"
PLAN = "plan.json"
BATTERY_M = 2000.0
SPEED_MPS = 10.0
BUFFER_M = 5.0
START_S = 14 * 3600 + 56 * 60
DROPOFF_DWELL_S = 30
CHARGE_DWELL_S = 120
NOTAM_ON_S = 15 * 3600
NOTAM_OFF_S = 15 * 3600 + 20 * 60
# The reference treats the temporary zone as this far wider than the verifier does, to be safe.
NOTAM_MARGIN_M = 5.25


def clock(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}"


def seconds_of(text: str) -> int:
    hours, minutes, seconds = (int(part) for part in text.split(":"))
    return hours * 3600 + minutes * 60 + seconds


@dataclass(frozen=True)
class Point:
    id: str
    kind: str
    lon: float
    lat: float
    xy: tuple[float, float]
    window: tuple[int, int] | None


class World:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.buildings = {b["name"]: [to_xy(*c) for c in b["ring"]] for b in data["buildings"]}
        self.notam = [to_xy(*c) for c in data["notam"]["ring"]]
        self.points = {
            p["id"]: Point(p["id"], p["kind"], p["lon"], p["lat"], to_xy(p["lon"], p["lat"]), tuple(p["window"]) if p["window"] else None)
            for p in data["points"]
        }
        self._routers: dict[bool, Router] = {}
        self._legs: dict[tuple[str, str, bool], tuple[float, list[tuple[float, float]]]] = {}
        self.notam_polygon = Polygon(self.notam)

    @classmethod
    def load(cls, workspace: Path) -> World:
        path = workspace / CAMPUS
        if not path.is_file():
            raise FileNotFoundError(f"{CAMPUS} does not exist: call open_campus first")
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def point(self, point_id: str) -> Point:
        if point_id not in self.points:
            raise ValueError(f"unknown point {point_id!r}: use depot, pad1 to pad3 or D1 to D4")
        return self.points[point_id]

    def router(self, avoid_notam: bool) -> Router:
        if avoid_notam not in self._routers:
            rings = list(self.buildings.values()) + ([self.notam] if avoid_notam else [])
            self._routers[avoid_notam] = Router(rings)
        return self._routers[avoid_notam]

    def leg(self, a: str, b: str, avoid_notam: bool) -> tuple[float, list[tuple[float, float]]]:
        if (a, b, avoid_notam) not in self._legs:
            path = self.router(avoid_notam).path(self.point(a).xy, self.point(b).xy)
            self._legs[(a, b, avoid_notam)] = (length(path), path)
        return self._legs[(a, b, avoid_notam)]

    def zone_times(self, a: str, b: str, leave: float) -> list[tuple[float, float]]:
        """When, leaving at ``leave`` seconds, the plain shortest path a to b is near the temporary zone."""
        line = LineString(self.leg(a, b, False)[1])
        hit = line.intersection(self.notam_polygon.buffer(NOTAM_MARGIN_M))
        pieces = [hit] if hit.is_empty or not hasattr(hit, "geoms") else list(hit.geoms)
        spans = []
        for piece in pieces:
            if not piece.is_empty:
                along = [line.project(ShapelyPoint(c)) for c in piece.coords]
                spans.append((leave + min(along) / SPEED_MPS, leave + max(along) / SPEED_MPS))
        return spans
