"""The campus as the verifier sees it: plain Python values in meters, from the reference or from campus.json."""

from .checks import CAMPUS, read_json
from .geometry import clock_seconds, to_xy


def ring_xy(ring):
    return [to_xy(c.lon, c.lat) for c in ring]


def from_reference(reference):
    rules = reference.rules
    return {
        "bbox": (reference.bbox.min_lon, reference.bbox.min_lat, reference.bbox.max_lon, reference.bbox.max_lat),
        "buildings": {b.name: ring_xy(b.ring) for b in reference.buildings},
        "notam": ring_xy(reference.notam.ring),
        "points": {
            p.id: {
                "kind": p.kind.value,
                "lon": p.lon,
                "lat": p.lat,
                "xy": to_xy(p.lon, p.lat),
                "window": (clock_seconds(p.window_open), clock_seconds(p.window_close)) if p.window_open else None,
            }
            for p in reference.points
        },
        "battery": rules.battery_m,
        "speed": rules.speed_mps,
        "buffer": rules.buffer_m,
        "start": clock_seconds(rules.start_time),
        "drop_dwell": rules.dropoff_dwell_s,
        "charge_dwell": rules.charge_dwell_s,
        "notam_on": clock_seconds(rules.notam_from),
        "notam_off": clock_seconds(rules.notam_until),
    }


def from_campus(workspace):
    """The map in the workspace's campus.json; raises ValueError if it is missing or malformed."""
    data = read_json(workspace, CAMPUS)
    try:
        return {
            "buildings": {b["name"]: [to_xy(lon, lat) for lon, lat in b["ring"]] for b in data["buildings"]},
            "notam": [to_xy(lon, lat) for lon, lat in data["notam"]["ring"]],
            "points": {
                p["id"]: {"kind": p["kind"], "lon": p["lon"], "lat": p["lat"], "xy": to_xy(p["lon"], p["lat"]), "window": p["window"]}
                for p in data["points"]
            },
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"campus.json is malformed: {error}") from error
