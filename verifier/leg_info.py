import math

from .checks import STOP_ID, clearance_problems, lengths, project, result
from .geometry import to_xy
from .mapdata import from_campus

BUFFER = 5.0


def verify_input(value):
    if not STOP_ID.fullmatch(value.from_id) or not STOP_ID.fullmatch(value.to_id) or value.from_id == value.to_id:
        return result(False, "from_id and to_id must be two different ids: depot, pad1 to pad3 or D1 to D4")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    try:
        campus = from_campus(workspace)
    except ValueError as error:
        return result(False, str(error))
    start, end = campus["points"][input_value.from_id], campus["points"][input_value.to_id]
    path = [(c.lon, c.lat) for c in output_value.path]
    if len(path) < 2 or path[0] != (start["lon"], start["lat"]) or path[-1] != (end["lon"], end["lat"]):
        return result(False, "the path must run from the first point to the second")
    xy = project(path)
    flown = lengths(xy)[-1]
    if abs(flown - output_value.length_m) > 0.05:
        return result(False, f"length_m is {output_value.length_m} but the path is {flown:.3f} m long")
    if flown < math.dist(to_xy(start["lon"], start["lat"]), to_xy(end["lon"], end["lat"])) - 0.05:
        return result(False, "the path is shorter than the straight line")
    rings = dict(campus["buildings"])
    if input_value.avoid_notam:
        rings["notam"] = campus["notam"]
    problems = clearance_problems(xy, rings, BUFFER)
    if problems:
        return result(False, f"segment {problems[0][0]} is {problems[0][2]:.3f} m from {problems[0][1]}: inside the {BUFFER} m buffer")
    return result(True, "the path keeps clear of every no-fly polygon", length_m=output_value.length_m)
