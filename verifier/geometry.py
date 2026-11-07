"""Plane geometry in pure Python: the campus's flat map, and distances between segments and polygons."""

import math
from itertools import pairwise

EARTH_RADIUS = 6_371_008.8
LAT0, LON0 = 37.43, -122.17
COS0 = math.cos(math.radians(LAT0))


def to_xy(lon, lat):
    return EARTH_RADIUS * COS0 * math.radians(lon - LON0), EARTH_RADIUS * math.radians(lat - LAT0)


def clock_seconds(text):
    """HH:MM:SS as seconds, or None when it is not a time."""
    parts = text.split(":") if isinstance(text, str) else []
    if len(parts) != 3 or not all(part.isdigit() and len(part) == 2 for part in parts):
        return None
    hours, minutes, seconds = (int(part) for part in parts)
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds


def point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = dx * dx + dy * dy
    if span == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def orientation(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return (value > 0) - (value < 0)


def on_segment(a, b, p):
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])


def segments_intersect(a, b, c, d):
    o1, o2, o3, o4 = orientation(a, b, c), orientation(a, b, d), orientation(c, d, a), orientation(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return (
        (o1 == 0 and on_segment(a, b, c))
        or (o2 == 0 and on_segment(a, b, d))
        or (o3 == 0 and on_segment(c, d, a))
        or (o4 == 0 and on_segment(c, d, b))
    )


def segment_segment_distance(a, b, c, d):
    if segments_intersect(a, b, c, d):
        return 0.0
    return min(
        point_segment_distance(a, c, d),
        point_segment_distance(b, c, d),
        point_segment_distance(c, a, b),
        point_segment_distance(d, a, b),
    )


def inside(p, ring):
    """Whether ``p`` is strictly inside the polygon ``ring`` (ray casting)."""
    crossings = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            crossings = not crossings
    return crossings


def segment_polygon_distance(a, b, ring):
    """The distance from the segment ab to the polygon, 0 when they touch or the segment is inside."""
    if inside(a, ring) or inside(b, ring):
        return 0.0
    return min(segment_segment_distance(a, b, c, d) for c, d in zip(ring, ring[1:] + ring[:1]))


def box_of(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def near(a, b, ring_box, margin):
    """A cheap test that the segment ab can be within ``margin`` of a polygon with bounding box ``ring_box``."""
    return not (
        max(a[0], b[0]) < ring_box[0] - margin
        or min(a[0], b[0]) > ring_box[2] + margin
        or max(a[1], b[1]) < ring_box[1] - margin
        or min(a[1], b[1]) > ring_box[3] + margin
    )


def lerp(a, b, t):
    return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])


def edge_interval(a, b, c, d, radius):
    """The parameters t of a + t(b - a) within ``radius`` of the edge cd, as one closed interval, or None."""
    def f(t):
        return point_segment_distance(lerp(a, b, t), c, d)

    low, high = 0.0, 1.0
    for _ in range(100):
        m1, m2 = low + (high - low) / 3, high - (high - low) / 3
        if f(m1) < f(m2):
            high = m2
        else:
            low = m1
    best = (low + high) / 2
    if f(best) > radius:
        return None
    ends = []
    for outer in (0.0, 1.0):
        if f(outer) <= radius:
            ends.append(outer)
            continue
        inner, far = best, outer
        for _ in range(100):
            mid = (inner + far) / 2
            if f(mid) <= radius:
                inner = mid
            else:
                far = mid
        ends.append(inner)
    return ends[0], ends[1]


def crossings(a, b, ring):
    """The parameters t in [0, 1] where a + t(b - a) meets an edge of the polygon."""
    found = []
    for c, d in zip(ring, ring[1:] + ring[:1]):
        r, s = (b[0] - a[0], b[1] - a[1]), (d[0] - c[0], d[1] - c[1])
        denominator = r[0] * s[1] - r[1] * s[0]
        if denominator == 0:
            continue
        t = ((c[0] - a[0]) * s[1] - (c[1] - a[1]) * s[0]) / denominator
        u = ((c[0] - a[0]) * r[1] - (c[1] - a[1]) * r[0]) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            found.append(t)
    return found


def near_intervals(a, b, ring, radius):
    """The parameters t where a + t(b - a) is inside the polygon or within ``radius`` of it, as merged closed intervals."""
    if a == b:
        return [(0.0, 1.0)] if segment_polygon_distance(a, b, ring) <= radius else []
    spans = []
    for c, d in zip(ring, ring[1:] + ring[:1]):
        span = edge_interval(a, b, c, d, radius)
        if span:
            spans.append(span)
    cuts = sorted({0.0, 1.0, *crossings(a, b, ring)})
    spans += [(lo, hi) for lo, hi in pairwise(cuts) if inside(lerp(a, b, (lo + hi) / 2), ring)]
    merged = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged
