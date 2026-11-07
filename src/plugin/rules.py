"""The contract's view of the drone's limits and the map."""

from __future__ import annotations

from contract import BBox, Coordinate, MapPoint, PointKind, Polygon, Rules
from plugin.campus import bbox
from plugin.world import (
    BATTERY_M,
    BUFFER_M,
    CHARGE_DWELL_S,
    DROPOFF_DWELL_S,
    NOTAM_OFF_S,
    NOTAM_ON_S,
    SPEED_MPS,
    START_S,
    clock,
)


def rules() -> Rules:
    return Rules(
        battery_m=BATTERY_M,
        speed_mps=SPEED_MPS,
        buffer_m=BUFFER_M,
        start_time=clock(START_S),
        dropoff_dwell_s=DROPOFF_DWELL_S,
        charge_dwell_s=CHARGE_DWELL_S,
        notam_from=clock(NOTAM_ON_S),
        notam_until=clock(NOTAM_OFF_S),
    )


def box() -> BBox:
    return BBox(**bbox())


def points(data: dict) -> list[MapPoint]:
    return [
        MapPoint(
            id=p["id"],
            kind=PointKind(p["kind"]),
            lon=p["lon"],
            lat=p["lat"],
            window_open=clock(p["window"][0]) if p["window"] else "",
            window_close=clock(p["window"][1]) if p["window"] else "",
        )
        for p in data["points"]
    ]


def polygon(name: str, ring: list[list[float]]) -> Polygon:
    return Polygon(name=name, ring=[Coordinate(lon=lon, lat=lat) for lon, lat in ring])
