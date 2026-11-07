from pathlib import Path

from .checks import CAMPUS, NOTAMS, result
from .geometry import clock_seconds
from .mapdata import from_campus

IDS = ["depot", "pad1", "pad2", "pad3", "D1", "D2", "D3", "D4"]


def verify_input(value):
    if not 1 <= value.seed <= 9999:
        return result(False, "seed must be between 1 and 9999")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    if output_value.campus_path != CAMPUS or output_value.notams_path != NOTAMS:
        return result(False, f"the files must be {CAMPUS} and {NOTAMS}")
    try:
        campus = from_campus(workspace)
    except ValueError as error:
        return result(False, str(error))
    if not (Path(workspace) / NOTAMS).is_file():
        return result(False, f"{NOTAMS} does not exist")
    shown = {p.id: (p.kind.value, p.lon, p.lat) for p in output_value.points}
    actual = {i: (p["kind"], p["lon"], p["lat"]) for i, p in campus["points"].items()}
    if sorted(actual) != sorted(IDS) or shown != actual:
        return result(False, "the points differ from campus.json or are not depot, pad1 to pad3 and D1 to D4")
    windows = [p for p in output_value.points if p.window_open]
    if len(windows) != 1 or windows[0].kind.value != "dropoff" or clock_seconds(windows[0].window_open) is None:
        return result(False, "exactly one drop-off must have a time window")
    if output_value.building_count != len(campus["buildings"]) or len(campus["buildings"]) < 6:
        return result(False, "building_count differs from campus.json or the campus has too few buildings")
    return result(True, "the campus is open", buildings=output_value.building_count)
