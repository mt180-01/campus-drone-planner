from __future__ import annotations

from pathlib import Path

from contract import Coordinate, LegInput, LegOutput
from plugin.geo import to_lonlat
from plugin.world import World


def leg_info(given: LegInput, workspace: Path) -> LegOutput:
    world = World.load(workspace)
    if given.from_id == given.to_id:
        raise ValueError("a leg needs two different points")
    flown, path = world.leg(given.from_id, given.to_id, given.avoid_notam)
    start, end = world.point(given.from_id), world.point(given.to_id)
    corners = [(start.lon, start.lat), *(to_lonlat(x, y) for x, y in path[1:-1]), (end.lon, end.lat)]
    return LegOutput(
        from_id=given.from_id,
        to_id=given.to_id,
        avoid_notam=given.avoid_notam,
        length_m=round(flown, 3),
        path=[Coordinate(lon=lon, lat=lat) for lon, lat in corners],
    )
