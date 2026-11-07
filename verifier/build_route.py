from .checks import PLAN, ROUTE, STOP_ID, clearance_problems, coordinates_of, lengths, project, read_json, result
from .mapdata import from_campus

BUFFER = 5.0


def verify_input(value):
    if len(value.stops) < 2 or value.stops[0] != "depot" or value.stops[-1] != "depot":
        return result(False, "stops must start and end at depot")
    if not all(STOP_ID.fullmatch(stop) for stop in value.stops) or any(a == b for a, b in zip(value.stops, value.stops[1:])):
        return result(False, "stops must be known ids, none repeated back to back")
    if len(value.avoid_notam) != len(value.stops) - 1:
        return result(False, "avoid_notam needs one entry per leg")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    if output_value.route_path != ROUTE or output_value.plan_path != PLAN:
        return result(False, f"the files must be {ROUTE} and {PLAN}")
    try:
        pairs = coordinates_of(read_json(workspace, ROUTE))
        plan = read_json(workspace, PLAN)
        campus = from_campus(workspace)
    except ValueError as error:
        return result(False, str(error))
    xy = project(pairs)
    total = lengths(xy)[-1]
    if abs(total - output_value.total_length_m) > 0.01:
        return result(False, f"total_length_m is {output_value.total_length_m} but the route is {total:.3f} m")
    if [s["id"] for s in plan["stops"]] != input_value.stops or [s.id for s in output_value.stops] != input_value.stops:
        return result(False, "the plan's stops are not the stops asked for")
    if plan["stops"][-1]["arrive"] != output_value.finish_time:
        return result(False, "finish_time is not the last stop's arrival")
    problems = clearance_problems(xy, campus["buildings"], BUFFER)
    if problems:
        return result(False, f"segment {problems[0][0]} is {problems[0][2]:.3f} m from {problems[0][1]}")
    return result(True, "the route and plan are written and clear of every building", total_length_m=output_value.total_length_m)
