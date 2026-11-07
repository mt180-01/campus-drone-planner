"""The campus's flat map and the shortest paths on it: a visibility graph around inflated no-fly polygons."""

from __future__ import annotations

import heapq
import math
from itertools import pairwise

from shapely.geometry import LineString, Point, Polygon
from shapely.prepared import prep

EARTH_RADIUS = 6_371_008.8
LAT0, LON0 = 37.43, -122.17
COS0 = math.cos(math.radians(LAT0))
# Routes keep 5.5 m from a polygon, half a meter more than the 5 m the verifier demands.
CLEARANCE = 5.5


def to_xy(lon: float, lat: float) -> tuple[float, float]:
    return EARTH_RADIUS * COS0 * math.radians(lon - LON0), EARTH_RADIUS * math.radians(lat - LAT0)


def to_lonlat(x: float, y: float) -> tuple[float, float]:
    return round(LON0 + math.degrees(x / (EARTH_RADIUS * COS0)), 8), round(LAT0 + math.degrees(y / EARTH_RADIUS), 8)


def length(path: list[tuple[float, float]]) -> float:
    return sum(math.dist(a, b) for a, b in pairwise(path))


class Router:
    """Shortest paths around ``rings`` (no-fly polygons), each inflated by CLEARANCE with sharp corners."""

    def __init__(self, rings: list[list[tuple[float, float]]]) -> None:
        inflated = [Polygon(ring).buffer(CLEARANCE, join_style="mitre", mitre_limit=5.0) for ring in rings]
        self.solid = [prep(polygon.buffer(-0.05, join_style="mitre")) for polygon in inflated]
        corners = [corner for polygon in inflated for corner in list(polygon.exterior.coords)[:-1]]
        self.vertices = [c for c in corners if not any(s.contains(Point(c)) for s in self.solid)]
        self.edges: dict[int, list[tuple[int, float]]] = {i: [] for i in range(len(self.vertices))}
        for i, p in enumerate(self.vertices):
            for j in range(i + 1, len(self.vertices)):
                if self.visible(p, self.vertices[j]):
                    d = math.dist(p, self.vertices[j])
                    self.edges[i].append((j, d))
                    self.edges[j].append((i, d))
        self.attached: dict[tuple[float, float], list[tuple[int, float]]] = {}

    def visible(self, p: tuple[float, float], q: tuple[float, float]) -> bool:
        line = LineString([p, q])
        return not any(solid.intersects(line) for solid in self.solid)

    def attach(self, p: tuple[float, float]) -> list[tuple[int, float]]:
        if p not in self.attached:
            if any(solid.contains(Point(p)) for solid in self.solid):
                raise ValueError(f"point {p} is inside a no-fly buffer")
            self.attached[p] = [(i, math.dist(p, v)) for i, v in enumerate(self.vertices) if self.visible(p, v)]
        return self.attached[p]

    def path(self, a: tuple[float, float], b: tuple[float, float]) -> list[tuple[float, float]]:
        if self.visible(a, b):
            return [a, b]
        start, goal = self.attach(a), dict(self.attach(b))
        best = {i: d for i, d in start}
        came: dict[int, int | None] = {i: None for i, _ in start}
        queue = [(d, i) for i, d in start]
        heapq.heapify(queue)
        done: set[int] = set()
        while queue:
            d, i = heapq.heappop(queue)
            if i in done:
                continue
            done.add(i)
            for j, step in self.edges[i]:
                if d + step < best.get(j, math.inf):
                    best[j], came[j] = d + step, i
                    heapq.heappush(queue, (d + step, j))
        reachable = [(best[i] + d, i) for i, d in goal.items() if i in best]
        if not reachable:
            raise ValueError(f"no path from {a} to {b}")
        _, last = min(reachable)
        chain = [last]
        while came[chain[-1]] is not None:
            chain.append(came[chain[-1]])
        return [a, *(self.vertices[i] for i in reversed(chain)), b]
