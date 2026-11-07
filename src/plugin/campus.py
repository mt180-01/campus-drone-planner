"""A campus laid out from a seed: buildings on a grid of alleys, a depot, pads, drop-offs and a temporary zone."""

from __future__ import annotations

import math
import random

from shapely.geometry import Point, Polygon

from plugin.geo import to_lonlat

WIDTH, HEIGHT = 1200.0, 900.0
NEAR = 15.0  # a point keeps this far from every no-fly polygon


def building(rng: random.Random, column: int, row: int, notched: bool) -> list[tuple[float, float]]:
    w, h = rng.uniform(110, 190), rng.uniform(90, 160)
    x, y = column * 300 + 45 + rng.uniform(0, 210 - w), row * 300 + 45 + rng.uniform(0, 210 - h)
    if not notched:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return [(x, y), (x + w, y), (x + w, y + 0.45 * h), (x + 0.5 * w, y + 0.45 * h), (x + 0.5 * w, y + h), (x, y + h)]


def layout(rng: random.Random) -> dict:
    cells = [(c, r) for c in range(4) for r in range(3)]
    notched = rng.choice(cells)
    rings = [building(rng, c, r, (c, r) == notched) for c, r in cells if (c, r) == notched or rng.random() >= 0.2]
    centre = (300.0 * rng.randint(1, 3), 300.0 * rng.randint(1, 2))
    zone = [(centre[0] + 55 * math.cos(k * math.pi / 4), centre[1] + 55 * math.sin(k * math.pi / 4)) for k in range(8)]
    obstacles = [Polygon(ring) for ring in rings] + [Polygon(zone)]

    def free(low: tuple[float, float], high: tuple[float, float], others: list, apart: float) -> tuple[float, float]:
        for _ in range(5000):
            p = (rng.uniform(low[0], high[0]), rng.uniform(low[1], high[1]))
            if all(o.distance(Point(p)) >= NEAR for o in obstacles) and all(math.dist(p, q) >= apart for q in others):
                return p
        raise ValueError("no free spot")

    depot = free((20, 20), (250, 250), [], 0)
    pads = []
    for _ in range(3):
        pads.append(free((20, 20), (WIDTH - 20, HEIGHT - 20), [depot, *pads], 300))
    drops = []
    for _ in range(4):
        drops.append(free((20, 20), (WIDTH - 20, HEIGHT - 20), [depot, *pads, *drops], 150))
    points = [("depot", "depot", depot)]
    points += [(f"pad{i}", "pad", p) for i, p in enumerate(pads, 1)]
    points += [(f"D{i}", "dropoff", p) for i, p in enumerate(drops, 1)]
    return {"rings": rings, "zone": zone, "points": points}


def lonlat_ring(ring: list[tuple[float, float]]) -> list[list[float]]:
    return [list(to_lonlat(x, y)) for x, y in ring]


def document(seed: int, parts: dict, window: tuple[str, int, int] | None) -> dict:
    """campus.json: everything in longitude and latitude, rounded to 8 decimals (about a millimeter)."""
    points = []
    for point_id, kind, (x, y) in parts["points"]:
        lon, lat = to_lonlat(x, y)
        points.append({"id": point_id, "kind": kind, "lon": lon, "lat": lat, "window": list(window[1:]) if window and window[0] == point_id else None})
    return {
        "seed": seed,
        "buildings": [{"name": f"B{i}", "ring": lonlat_ring(ring)} for i, ring in enumerate(parts["rings"], 1)],
        "notam": {"name": "NOTAM A0412/26", "ring": lonlat_ring(parts["zone"])},
        "points": points,
    }


def bbox() -> dict:
    west, south = to_lonlat(0, 0)
    east, north = to_lonlat(WIDTH, HEIGHT)
    return {"min_lon": west, "min_lat": south, "max_lon": east, "max_lat": north}


def notam_text(zone: list[list[float]]) -> str:
    corners = "\n".join(f"  {lon:.8f} {lat:.8f}" for lon, lat in zone)
    return (
        "NOTAM A0412/26 NOTAMN\n"
        "VALID FROM: 2026-03-14 15:00:00 UTC\n"
        "VALID UNTIL: 2026-03-14 15:20:00 UTC\n"
        "TEMPORARY NO-FLY ZONE (crane operation). Unmanned aircraft are prohibited inside the polygon below\n"
        "(longitude latitude, corners in order, the ring closes on the first corner), and outside the\n"
        "hours above the zone does not apply:\n"
        f"{corners}\n"
    )
