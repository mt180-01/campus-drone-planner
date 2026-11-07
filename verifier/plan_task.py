"""verify_task for plan-drone-delivery: route.geojson and plan.json judged against the rules, check by check."""

import math
from itertools import pairwise

from .checks import PLAN, ROUTE, clearance_problems, coordinates_of, is_number, lengths, project, read_json, result
from .geometry import box_of, clock_seconds, near, near_intervals
from .mapdata import from_reference

LIMIT = 1.10  # the route may be 10% longer than the reference optimum
TOLERANCE = 1e-6  # float slack on a length that is exactly at its limit
ON_ROUTE = 0.5  # a stop is on the route when a vertex is this close
CLOCK_SLACK = 1.0  # seconds


def check(name, ok, message):
    return {"name": name, "ok": ok, "message": message}


def verdict(checks, **details):
    failed = [item for item in checks if not item["ok"]]
    if not failed:
        return result(True, "the route keeps every rule and is within 10% of the optimum", checks=checks, **details)
    return result(
        False,
        "; ".join(f"{item['name']}: {item['message']}" for item in failed),
        score=(len(checks) - len(failed)) / len(checks),
        checks=checks,
        **details,
    )


def refuse(message, **details):
    return result(False, message, score=0.0, **details)


def swapped(pairs, bbox):
    return all(bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3] for lon, lat in pairs)


def locate(xy, stops, points):
    """The route vertex of each plan stop, searching forward in order; None for a stop that is not on the route."""
    found, start = [], 0
    for stop in stops:
        target = points[stop["id"]]["xy"]
        index = next((i for i in range(start, len(xy)) if math.dist(xy[i], target) <= ON_ROUTE), None)
        found.append(index)
        if index is None:
            return found
        start = index
    return found


def timeline(world, stops, marks, cumulative):
    """(arrive, depart) seconds at every stop for a drone leaving at the start time at the fixed speed."""
    times, clock_s = [], float(world["start"])
    for index, stop in enumerate(stops):
        if index:
            clock_s += (cumulative[marks[index]] - cumulative[marks[index - 1]]) / world["speed"]
        arrive = clock_s
        if 0 < index < len(stops) - 1:
            clock_s += world["drop_dwell"] if world["points"][stop["id"]]["kind"] == "dropoff" else world["charge_dwell"]
        times.append((arrive, clock_s))
    return times


def zone_problems(world, xy, marks, cumulative, times):
    """(segment, seconds) for each segment flown within the buffer of the temporary zone while the zone is active.

    Only the part of a segment that is near the zone counts, and only the moment the drone is there."""
    zone, margin = world["notam"], world["buffer"]
    zone_box = box_of(zone)
    found = []
    for stop in range(len(marks) - 1):
        leave = times[stop][1]
        for index in range(marks[stop], marks[stop + 1]):
            if not near(xy[index], xy[index + 1], zone_box, margin):
                continue
            start = leave + (cumulative[index] - cumulative[marks[stop]]) / world["speed"]
            end = leave + (cumulative[index + 1] - cumulative[marks[stop]]) / world["speed"]
            for low, high in near_intervals(xy[index], xy[index + 1], zone, margin):
                enter, exit_ = start + low * (end - start), start + high * (end - start)
                if enter <= world["notam_off"] + 1e-9 and exit_ >= world["notam_on"] - 1e-9:
                    found.append((index, round(max(enter, world["notam_on"]), 1)))
                    break
    return found


def verify_task(arguments, output, reference, workspace):
    if output.route_path != ROUTE or output.plan_path != PLAN:
        return refuse(f"the files must be {ROUTE} and {PLAN}")
    world = from_reference(reference)
    try:
        pairs = coordinates_of(read_json(workspace, ROUTE))
        plan = read_json(workspace, PLAN)
    except ValueError as error:
        return refuse(str(error))
    bbox = world["bbox"]
    if not all(bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3] for lon, lat in pairs):
        hint = "latitude and longitude look swapped: the pairs must be [longitude, latitude]" if swapped(pairs, bbox) else (
            "some coordinates are outside the map's bounding box"
        )
        return refuse(hint, checks=[check("bbox", False, hint)])
    stops = plan.get("stops") if isinstance(plan, dict) else None
    well_formed = (
        isinstance(stops, list)
        and len(stops) >= 2
        and all(
            isinstance(s, dict) and s.get("id") in world["points"] and isinstance(s.get("arrive"), str) and isinstance(s.get("depart"), str)
            for s in stops
        )
        and is_number(plan.get("speed_mps"))
        and is_number(plan.get("total_length_m"))
    )
    if not well_formed:
        return refuse("plan.json must hold start_time, speed_mps, total_length_m and stops of known ids with arrive and depart times")

    xy = project(pairs)
    cumulative = lengths(xy)
    total = cumulative[-1]
    checks = [check("bbox", True, "every coordinate is inside the map")]
    rules_ok = plan.get("start_time") == reference.rules.start_time and plan["speed_mps"] == world["speed"]
    checks.append(
        check("plan_rules", rules_ok, "the plan leaves at the start time at the fixed speed" if rules_ok else (
            f"the plan must leave at {reference.rules.start_time} at {world['speed']} m/s"
        ))
    )
    depot = world["points"]["depot"]["xy"]
    ends = stops[0]["id"] == "depot" == stops[-1]["id"] and math.dist(xy[0], depot) <= ON_ROUTE and math.dist(xy[-1], depot) <= ON_ROUTE
    checks.append(check("endpoints", ends, "the drone starts and lands at the depot" if ends else "the route must start and end at the depot"))

    problems = clearance_problems(xy, world["buildings"], world["buffer"])
    first = problems[0] if problems else None
    checks.append(
        check(
            "no_fly",
            not problems,
            "no segment comes within the buffer of a building" if not problems else (
                f"{len(problems)} segments are within {world['buffer']} m of a building, e.g. segment {first[0]} is {first[2]:.3f} m from {first[1]}"
            ),
        )
    )
    ratio = total / reference.optimal_length_m
    within = total <= LIMIT * reference.optimal_length_m + TOLERANCE
    checks.append(
        check(
            "length",
            within,
            f"{total:.1f} m is {ratio:.3f} times the optimum {reference.optimal_length_m:.1f} m" + ("" if within else f", over the {LIMIT} limit"),
        )
    )
    claims = (
        abs(plan["total_length_m"] - total) <= 0.5
        and abs(output.total_length_m - total) <= 0.5
        and output.finish_time == stops[-1]["arrive"]
    )
    checks.append(check("claims", claims, "the reported length and finish time match the route" if claims else "total_length_m or finish_time differs from the route and plan"))

    marks = locate(xy, stops, world["points"])
    on_route = None not in marks
    visited = {s["id"] for s in stops if world["points"][s["id"]]["kind"] == "dropoff"}
    wanted = {i for i, p in world["points"].items() if p["kind"] == "dropoff"}
    missing = sorted(wanted - visited)
    checks.append(check("dropoffs", not missing and on_route, "every drop-off is visited" if not missing and on_route else (
        f"drop-offs not visited: {missing}" if missing else "a plan stop is not on the route, in order"
    )))
    if not on_route:
        reason = "the stops are not all on the route in order"
        checks += [check(name, False, reason) for name in ("timestamps", "battery", "notam", "windows")]
        return verdict(checks, route_length_m=round(total, 3))

    times = timeline(world, stops, marks, cumulative)
    off = [
        s["id"]
        for s, (arrive, depart) in zip(stops, times)
        if clock_seconds(s["arrive"]) is None
        or clock_seconds(s["depart"]) is None
        or abs(clock_seconds(s["arrive"]) - arrive) > CLOCK_SLACK
        or abs(clock_seconds(s["depart"]) - depart) > CLOCK_SLACK
    ]
    checks.append(check("timestamps", not off, "the timestamps follow from the route at the fixed speed" if not off else f"timestamps differ at {off}"))

    # The drone starts full, a pad or the depot recharges it, and the last stretch ends wherever the route does.
    charges = sorted({0, marks[-1], *(mark for stop, mark in zip(stops, marks) if world["points"][stop["id"]]["kind"] != "dropoff")})
    stretches = [cumulative[b] - cumulative[a] for a, b in pairwise(charges)]
    longest = max(stretches)
    battery_ok = longest <= world["battery"] + TOLERANCE
    checks.append(
        check(
            "battery",
            battery_ok,
            f"the longest stretch between charges is {longest:.3f} m of {world['battery']:.0f} m" + ("" if battery_ok else ": the battery runs out"),
        )
    )
    zone = zone_problems(world, xy, marks, cumulative, times)
    checks.append(
        check(
            "notam",
            not zone,
            "the temporary zone is avoided while it is active" if not zone else (
                f"segment {zone[0][0]} is within {world['buffer']} m of the temporary zone at {zone[0][1]} s after midnight, while it is active"
            ),
        )
    )
    late = [
        stop["id"]
        for stop, (arrive, _) in zip(stops, times)
        if world["points"][stop["id"]]["window"] and not world["points"][stop["id"]]["window"][0] <= arrive <= world["points"][stop["id"]]["window"][1]
    ]
    checks.append(check("windows", not late, "every time window is met" if not late else f"arrival outside the time window at {late}"))
    return verdict(checks, route_length_m=round(total, 3), optimal_length_m=reference.optimal_length_m, stretches_m=[round(s, 3) for s in stretches])
