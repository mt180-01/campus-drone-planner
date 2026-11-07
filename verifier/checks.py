"""Checks shared by the tool verifiers. Pure functions of their arguments and the files on disk."""

import json
import math
import re
from itertools import pairwise
from pathlib import Path

from .geometry import box_of, near, segment_polygon_distance, to_xy

ROUTE = "route.geojson"
PLAN = "plan.json"
CAMPUS = "campus.json"
NOTAMS = "notams.txt"
STOP_ID = re.compile(r"^(depot|pad[1-3]|D[1-4])$")


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def read_json(workspace, name):
    """The JSON in the workspace file ``name``; raises ValueError if it is missing or not JSON."""
    path = Path(workspace) / name
    if not path.is_file():
        raise ValueError(f"{name} does not exist")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"{name} is not valid JSON: {error}") from error


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def coordinates_of(route):
    """The [lon, lat] pairs of a route.geojson that holds one LineString; raises ValueError otherwise."""
    if not isinstance(route, dict):
        raise ValueError("route.geojson must be a JSON object")  # noqa: TRY004 (callers catch ValueError for every malformed input)
    if route.get("type") == "FeatureCollection":
        features = route.get("features")
        if not isinstance(features, list) or len(features) != 1 or not isinstance(features[0], dict):
            raise ValueError("route.geojson must hold exactly one feature")
        route = features[0]
    geometry = route.get("geometry") if route.get("type") == "Feature" else route
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise ValueError("the route must be one LineString")
    pairs = geometry.get("coordinates")
    if not isinstance(pairs, list) or len(pairs) < 2:
        raise ValueError("the route needs at least two coordinates")
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) < 2 or not is_number(pair[0]) or not is_number(pair[1]):
            raise ValueError("every coordinate must be a pair of finite numbers [longitude, latitude]")
    return [(pair[0], pair[1]) for pair in pairs]


def project(pairs):
    return [to_xy(lon, lat) for lon, lat in pairs]


def lengths(xy):
    """The cumulative length along the polyline at every vertex."""
    total = [0.0]
    for a, b in pairwise(xy):
        total.append(total[-1] + math.dist(a, b))
    return total


def clearance_problems(xy, rings, margin):
    """(segment index, polygon name, distance) for every segment within ``margin`` of a polygon (touching counts)."""
    boxes = {name: box_of(ring) for name, ring in rings.items()}
    found = []
    for index, (a, b) in enumerate(pairwise(xy)):
        for name, ring in rings.items():
            if near(a, b, boxes[name], margin):
                distance = segment_polygon_distance(a, b, ring)
                if distance <= margin:
                    found.append((index, name, distance))
    return found
