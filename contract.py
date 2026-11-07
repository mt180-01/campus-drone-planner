"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    OPEN_CAMPUS = "open_campus"
    READ_NOTAMS = "read_notams"
    LEG_INFO = "leg_info"
    BUILD_ROUTE = "build_route"
    REFERENCE_PLAN = "reference_plan"


class Task(Enum):
    PLAN_DELIVERY = "plan-drone-delivery"


class PointKind(Enum):
    DEPOT = "depot"
    PAD = "pad"
    DROPOFF = "dropoff"


class TextFile(Enum):
    NOTAMS = "notams.txt"


LON = "Longitude in degrees, east positive"
LAT = "Latitude in degrees, north positive"
STOP = "A point's id: depot, pad1, pad2, pad3 or D1 to D4"
CLOCK = "A time of day, HH:MM:SS"
LENGTH = "Length in meters, measured on the local flat map the campus is drawn on"


@dataclass
class Coordinate(Output):
    lon: Annotated[float, LON]
    lat: Annotated[float, LAT]


@dataclass
class BBox(Output):
    min_lon: Annotated[float, "The map's western edge"]
    min_lat: Annotated[float, "The map's southern edge"]
    max_lon: Annotated[float, "The map's eastern edge"]
    max_lat: Annotated[float, "The map's northern edge"]


@dataclass
class MapPoint(Output):
    id: Annotated[str, STOP]
    kind: Annotated[PointKind, "The depot is where the drone starts and ends; a pad recharges it; a drop-off is a delivery"]
    lon: Annotated[float, LON]
    lat: Annotated[float, LAT]
    window_open: Annotated[str, "For a drop-off with a time window, the earliest arrival (HH:MM:SS); empty when it has none"]
    window_close: Annotated[str, "For a drop-off with a time window, the latest arrival (HH:MM:SS); empty when it has none"]


@dataclass
class Polygon(Output):
    name: Annotated[str, "The polygon's name"]
    ring: Annotated[list[Coordinate], "The corners in order; the ring is closed without repeating the first corner"]


@dataclass
class Rules(Output):
    battery_m: Annotated[float, "Meters the drone can fly on a full charge; a stretch of exactly this length is allowed"]
    speed_mps: Annotated[float, "The drone's fixed speed in meters per second"]
    buffer_m: Annotated[float, "Safety buffer around every no-fly polygon in meters; a route that only touches the buffer is in violation"]
    start_time: Annotated[str, "When the drone leaves the depot, HH:MM:SS"]
    dropoff_dwell_s: Annotated[int, "Seconds spent at each drop-off"]
    charge_dwell_s: Annotated[int, "Seconds spent recharging at a pad (or at the depot when it is passed through mid-route)"]
    notam_from: Annotated[str, "When the temporary no-fly zone becomes active, HH:MM:SS"]
    notam_until: Annotated[str, "When the temporary no-fly zone stops being active, HH:MM:SS"]


@dataclass
class PlannedStop(Output):
    id: Annotated[str, STOP]
    kind: Annotated[PointKind, "What the stop is"]
    lon: Annotated[float, LON]
    lat: Annotated[float, LAT]
    arrive: Annotated[str, CLOCK]
    depart: Annotated[str, CLOCK]


@dataclass
class CampusInput(Output):
    seed: Annotated[int, "Which campus to plan on, 1 to 9999: the same seed always gives the same campus"]


@dataclass
class CampusOutput(Output):
    campus_path: Annotated[str, "The campus map file written to the workspace"]
    notams_path: Annotated[str, "The NOTAM file written to the workspace"]
    rules: Annotated[Rules, "The drone's limits"]
    bbox: Annotated[BBox, "The map's bounding box: every route coordinate must be inside it"]
    points: Annotated[list[MapPoint], "The depot, three charging pads and four drop-offs"]
    building_count: Annotated[int, "How many buildings (permanent no-fly polygons) the campus has"]


@dataclass
class NotamsInput(Output):
    file: Annotated[TextFile, "Which text file to read"]


@dataclass
class NotamsOutput(Output):
    file: Annotated[str, "The file read"]
    text: Annotated[str, "The file's text exactly"]


@dataclass
class LegInput(Output):
    from_id: Annotated[str, STOP]
    to_id: Annotated[str, STOP]
    avoid_notam: Annotated[bool, "Whether the path must also keep clear of the temporary no-fly zone"]


@dataclass
class LegOutput(Output):
    from_id: Annotated[str, STOP]
    to_id: Annotated[str, STOP]
    avoid_notam: Annotated[bool, "Whether the path keeps clear of the temporary no-fly zone"]
    length_m: Annotated[float, LENGTH]
    path: Annotated[list[Coordinate], "The shortest path around the buildings, from the first point to the second"]


@dataclass
class BuildInput(Output):
    stops: Annotated[list[str], "The ids to visit in order; it starts and ends at depot"]
    avoid_notam: Annotated[list[bool], "One entry per leg between consecutive stops: whether that leg avoids the temporary no-fly zone"]


@dataclass
class BuildOutput(Output):
    route_path: Annotated[str, "The route file written to the workspace: route.geojson"]
    plan_path: Annotated[str, "The plan file written to the workspace: plan.json"]
    total_length_m: Annotated[float, LENGTH]
    finish_time: Annotated[str, "When the drone lands at the end of the route, HH:MM:SS"]
    stretches_m: Annotated[list[float], "The length flown between consecutive charges, depot start and end included"]
    stops: Annotated[list[PlannedStop], "Each stop with its arrival and departure times at the fixed speed"]


@dataclass
class ReferenceOutput(Output):
    rules: Annotated[Rules, "The drone's limits"]
    bbox: Annotated[BBox, "The map's bounding box"]
    points: Annotated[list[MapPoint], "The depot, pads and drop-offs"]
    buildings: Annotated[list[Polygon], "Every building: permanent no-fly polygons"]
    notam: Annotated[Polygon, "The temporary no-fly zone"]
    optimal_length_m: Annotated[float, LENGTH]
    optimal_stops: Annotated[list[str], "The stops of the shortest route that keeps every rule"]


@dataclass
class PlanOutput(Output):
    route_path: Annotated[str, "The route file in the workspace: route.geojson"]
    plan_path: Annotated[str, "The plan file in the workspace: plan.json"]
    total_length_m: Annotated[float, LENGTH]
    finish_time: Annotated[str, "When the drone lands, HH:MM:SS"]


TOOLS = {
    Tool.OPEN_CAMPUS: (CampusInput, CampusOutput),
    Tool.READ_NOTAMS: (NotamsInput, NotamsOutput),
    Tool.LEG_INFO: (LegInput, LegOutput),
    Tool.BUILD_ROUTE: (BuildInput, BuildOutput),
    Tool.REFERENCE_PLAN: (CampusInput, ReferenceOutput),
}
TASKS = {Task.PLAN_DELIVERY: (CampusInput, PlanOutput)}
