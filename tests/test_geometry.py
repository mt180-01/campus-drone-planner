"""The verifier's pure-Python geometry against shapely, on random polygons (convex and not) and segments."""

from __future__ import annotations

import math
import random

import pytest
from shapely.geometry import LineString, Point, Polygon

import plugin.geo as plugin_geo
from verifier import geometry

L_SHAPE = [(0.0, 0.0), (60.0, 0.0), (60.0, 25.0), (30.0, 25.0), (30.0, 70.0), (0.0, 70.0)]
SQUARE = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
OCTAGON = [(40 * math.cos(k * math.pi / 4), 40 * math.sin(k * math.pi / 4)) for k in range(8)]


def segments(rng: random.Random, count: int):
    for _ in range(count):
        yield (rng.uniform(-80, 140), rng.uniform(-80, 140)), (rng.uniform(-80, 140), rng.uniform(-80, 140))


@pytest.mark.parametrize("ring", [L_SHAPE, SQUARE, OCTAGON])
def test_segment_polygon_distance_matches_shapely(ring) -> None:
    polygon = Polygon(ring)
    for a, b in segments(random.Random(7), 600):
        assert geometry.segment_polygon_distance(a, b, ring) == pytest.approx(LineString([a, b]).distance(polygon), abs=1e-9)


@pytest.mark.parametrize("ring", [L_SHAPE, SQUARE, OCTAGON])
def test_near_intervals_match_the_buffered_polygon(ring) -> None:
    buffered = Polygon(ring).buffer(5.0, quad_segs=64)
    for a, b in segments(random.Random(11), 300):
        line = LineString([a, b])
        spans = geometry.near_intervals(a, b, ring, 5.0)
        hit = line.intersection(buffered)
        pieces = [] if hit.is_empty else ([hit] if not hasattr(hit, "geoms") else list(hit.geoms))
        expected = sorted((min(line.project(Point(c)) for c in p.coords) / line.length, max(line.project(Point(c)) for c in p.coords) / line.length) for p in pieces if not p.is_empty)
        merged = spans
        assert len(merged) == len(expected) or any(hi - lo < 1e-3 for lo, hi in expected + merged), (a, b)
        for (lo, hi), (elo, ehi) in zip(merged, expected):
            assert lo * line.length == pytest.approx(elo * line.length, abs=0.03)
            assert hi * line.length == pytest.approx(ehi * line.length, abs=0.03)


def test_a_segment_through_the_middle_of_a_polygon_is_wholly_near() -> None:
    # Deeper than the buffer from every edge, yet inside: the middle must not be a gap.
    assert geometry.near_intervals((-100.0, 25.0), (150.0, 25.0), SQUARE, 5.0) == [(0.4 - 5 / 250, 0.6 + 5 / 250)]


def test_the_flat_maps_agree() -> None:
    rng = random.Random(3)
    for _ in range(100):
        lon, lat = -122.17 + rng.uniform(0, 0.02), 37.43 + rng.uniform(0, 0.01)
        assert geometry.to_xy(lon, lat) == plugin_geo.to_xy(lon, lat)


def test_clock_seconds_accepts_only_clock_times() -> None:
    assert geometry.clock_seconds("14:56:00") == 53760
    assert geometry.clock_seconds("00:00:00") == 0 and geometry.clock_seconds("23:59:59") == 86399
    for bad in ("24:00:00", "14:60:00", "14:56", "1:2:3", "14:56:0x", "", None, 53760):
        assert geometry.clock_seconds(bad) is None
