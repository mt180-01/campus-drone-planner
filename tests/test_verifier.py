"""The verifier on hand-made geometry, where every boundary can be put exactly where it matters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import verifier
from contract import CampusInput
from tests.synth import lonlat, reference, typed, write_route
from verifier.checks import clearance_problems

ALL = ["depot", "D1", "D2", "D3", "D4", "depot"]
EARLY = "14:40:00"  # the whole round trip is over before the temporary zone is active


def judge(workspace: Path, ref, output):
    return verifier.verify_task("plan-drone-delivery", CampusInput(seed=1), output, typed(ref, type(ref)), str(workspace))


def failing(verdict) -> list[str]:
    return [c["name"] for c in verdict["details"].get("checks", []) if not c["ok"]]


def run(workspace: Path, ref, stops=ALL, legs=None):
    return judge(workspace, ref, write_route(workspace, ref, stops, legs))


def test_a_clean_route_passes_every_check(tmp_path: Path) -> None:
    verdict = run(tmp_path, reference(start=EARLY, optimal=2000.0))
    assert verdict["valid"] is True and verdict["score"] == 1.0 and failing(verdict) == []


def test_a_stretch_of_exactly_2000_m_is_allowed_and_2000_02_is_not(tmp_path: Path) -> None:
    exact = run(tmp_path, reference(start=EARLY, optimal=2000.0))
    assert exact["details"]["stretches_m"] == pytest.approx([2000.0], abs=1e-6) and exact["valid"] is True
    longer = reference({"D1": (250, 0), "D2": (500, 0), "D3": (750, 0), "D4": (1000.01, 0)}, start=EARLY, optimal=2000.0)
    verdict = run(tmp_path, longer)
    assert failing(verdict) == ["battery"] and "battery runs out" in verdict["message"]


def test_a_pad_resets_the_battery(tmp_path: Path) -> None:
    ref = reference({"D1": (250, 0), "D2": (500, 0), "D3": (750, 0), "D4": (1000, 0)}, start=EARLY, optimal=2560.0)
    long_way = ["depot", "D1", "D2", "D3", "D4", "pad1", "depot"]  # 1000 + 781, then 781 m home
    verdict = run(tmp_path, ref, long_way)
    assert verdict["valid"] is True and [round(s) for s in verdict["details"]["stretches_m"]] == [1781, 781]


def test_the_temporary_zone_depends_on_when_the_drone_is_there(tmp_path: Path) -> None:
    assert run(tmp_path, reference(start=EARLY, optimal=2000.0))["valid"] is True  # before 15:00
    late = run(tmp_path, reference(start="14:56:00", optimal=2000.0))  # the way home crosses it at about 15:00:35
    assert failing(late) == ["notam"] and "while it is active" in late["message"]
    after = run(tmp_path, reference(start="15:21:00", optimal=2000.0))  # after 15:20
    assert after["valid"] is True


def test_a_detour_around_the_zone_is_legal_while_it_is_active(tmp_path: Path) -> None:
    ref = reference(start="14:56:00", optimal=2200.0)
    ref.rules.battery_m = 2500.0
    legs = [[], [(380, 80), (500, 80)], [], [], [(500, -80), (380, -80)], []]
    verdict = run(tmp_path, ref, ALL, [leg for leg in legs[:5]])
    assert verdict["valid"] is True, verdict["message"]


FAR = {"D1": (1000, 0), "D2": (1200, 0), "D3": (1400, 0), "D4": (1600, 0)}  # out past the zone, which is crossed at x 395-485


def far_route(workspace: Path, window: tuple[str, str]):
    """The drone leaves at 14:59:00 and is within the zone's buffer at 14:59:39.5-14:59:48.5, on the way out."""
    ref = reference(FAR, start="14:59:00", optimal=3200.0)
    ref.rules.battery_m = 3300.0
    ref.rules.notam_from, ref.rules.notam_until = window
    return run(workspace, ref)


def test_only_the_moment_inside_the_buffer_counts_not_the_whole_segment(tmp_path: Path) -> None:
    # The one segment out to D1 is flown from 14:59:00 to 15:00:40, but its stretch near the zone ends at 14:59:48.5.
    assert far_route(tmp_path, ("15:00:00", "15:00:05"))["valid"] is True
    assert far_route(tmp_path, ("14:59:49", "15:00:05"))["valid"] is True


def test_being_near_the_zone_at_the_instant_it_opens_or_closes_is_a_violation(tmp_path: Path) -> None:
    assert failing(far_route(tmp_path, ("14:59:48", "15:00:05"))) == ["notam"]  # still near at 14:59:48.0
    assert failing(far_route(tmp_path, ("14:59:30", "14:59:40"))) == ["notam"]  # already near at 14:59:39.5
    assert far_route(tmp_path, ("14:59:20", "14:59:39"))["valid"] is True  # closes half a second before the buffer
    assert failing(far_route(tmp_path, ("14:59:48", "14:59:48"))) == ["notam"]  # an instant inside the stretch
    assert far_route(tmp_path, ("14:50:00", "14:50:30"))["valid"] is True  # long over


def test_five_meters_exactly_touches_the_buffer_and_is_a_violation() -> None:
    ring = {"B": [(300.0, 100.0), (400.0, 100.0), (400.0, 200.0), (300.0, 200.0)]}
    assert clearance_problems([(250.0, 95.0), (450.0, 95.0)], ring, 5.0)[0][2] == 5.0
    assert clearance_problems([(250.0, 94.999), (450.0, 94.999)], ring, 5.0) == []
    assert clearance_problems([(250.0, 95.001), (450.0, 95.001)], ring, 5.0)[0][1] == "B"
    assert clearance_problems([(250.0, 150.0), (450.0, 150.0)], ring, 5.0)[0][2] == 0.0  # through the building
    assert clearance_problems([(350.0, 120.0), (360.0, 130.0)], ring, 5.0)[0][2] == 0.0  # wholly inside


def test_passing_just_outside_and_just_inside_the_buffer_of_a_building(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2100.0)
    ref.rules.battery_m = 2500.0
    outside = [[], [(300, 94.999), (400, 94.999)], [], [], []]
    inside = [[], [(300, 95.001), (400, 95.001)], [], [], []]
    assert run(tmp_path, ref, ALL, outside)["valid"] is True
    verdict = run(tmp_path, ref, ALL, inside)
    assert failing(verdict) == ["no_fly"] and "B1" in verdict["message"]


def test_a_route_through_a_building_is_refused(tmp_path: Path) -> None:
    ref = reference({"D1": (250, 150), "D2": (500, 150), "D3": (750, 0), "D4": (1000, 0)}, start=EARLY, optimal=2000.0)
    ref.rules.battery_m = 3000.0
    assert "no_fly" in failing(run(tmp_path, ref))  # D1 to D2 runs straight through the building at y 100-200


def test_the_length_limit_is_1_10_times_the_optimum(tmp_path: Path) -> None:
    exactly = run(tmp_path, reference(start=EARLY, optimal=2000.0 / 1.10))
    assert exactly["valid"] is True
    over = run(tmp_path, reference(start=EARLY, optimal=2000.0 / 1.1001))
    assert failing(over) == ["length"] and "over the 1.1 limit" in over["message"]


def test_a_missing_drop_off_is_refused(tmp_path: Path) -> None:
    verdict = run(tmp_path, reference(start=EARLY, optimal=2000.0), ["depot", "D1", "D2", "D4", "depot"])
    assert failing(verdict) == ["dropoffs"] and "D3" in verdict["message"]


def test_a_time_window_is_enforced_at_both_ends(tmp_path: Path) -> None:
    # D3 is reached at 14:42:15 at the fixed speed.
    for window, valid in (("14:42:00", "14:43:00"), True), (("14:40:00", "14:41:00"), False), (("14:43:00", "14:44:00"), False):
        ref = reference(start=EARLY, optimal=2000.0, windows={"D3": window})
        verdict = run(tmp_path, ref)
        assert verdict["valid"] is valid and (valid or failing(verdict) == ["windows"])
    on_the_dot = reference(start=EARLY, optimal=2000.0, windows={"D3": ("14:42:15", "14:42:15")})
    assert run(tmp_path, on_the_dot)["valid"] is True


def test_swapped_latitude_and_longitude_are_detected(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    route = json.loads((tmp_path / "route.geojson").read_text())
    line = route["features"][0]["geometry"]["coordinates"]
    route["features"][0]["geometry"]["coordinates"] = [[lat, lon] for lon, lat in line]
    (tmp_path / "route.geojson").write_text(json.dumps(route))
    verdict = judge(tmp_path, ref, output)
    assert verdict["valid"] is False and verdict["score"] == 0.0 and "swapped" in verdict["message"]


def test_coordinates_off_the_map_are_detected(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    route = json.loads((tmp_path / "route.geojson").read_text())
    route["features"][0]["geometry"]["coordinates"][2][0] += 1.0
    (tmp_path / "route.geojson").write_text(json.dumps(route))
    verdict = judge(tmp_path, ref, output)
    assert verdict["valid"] is False and "outside the map" in verdict["message"] and "swapped" not in verdict["message"]


def test_the_route_must_start_and_end_at_the_depot(tmp_path: Path) -> None:
    assert "endpoints" in failing(run(tmp_path, reference(start=EARLY, optimal=2000.0), ["depot", "D1", "D2", "D3", "D4"]))
    assert "endpoints" in failing(run(tmp_path, reference(start=EARLY, optimal=2000.0), ["D1", "D2", "D3", "D4", "depot"]))


def test_timestamps_must_follow_from_the_route_at_the_fixed_speed(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    plan = json.loads((tmp_path / "plan.json").read_text())
    plan["stops"][2]["arrive"] = "14:41:30"
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    verdict = judge(tmp_path, ref, output)
    assert failing(verdict) == ["timestamps"] and "D2" in verdict["message"]
    plan["speed_mps"] = 12.0
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    assert "plan_rules" in failing(judge(tmp_path, ref, output))


def test_a_plan_stop_that_is_not_on_the_route_is_refused(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    plan = json.loads((tmp_path / "plan.json").read_text())
    plan["stops"][3]["id"] = "pad1"  # D3's place on the route is not pad1
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    verdict = judge(tmp_path, ref, output)
    assert verdict["valid"] is False and "dropoffs" in failing(verdict) and "timestamps" in failing(verdict)


def test_dishonest_claims_are_refused(tmp_path: Path) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    output.total_length_m -= 5
    assert failing(judge(tmp_path, ref, output)) == ["claims"]
    output.total_length_m += 5
    output.finish_time = "15:59:59"
    assert failing(judge(tmp_path, ref, output)) == ["claims"]


@pytest.mark.parametrize(
    "damage",
    ["missing_route", "missing_plan", "not_json", "polygon", "one_point", "text_coordinate", "two_features", "bad_plan", "wrong_path"],
)
def test_malformed_files_are_refused_not_crashed_on(tmp_path: Path, damage: str) -> None:
    ref = reference(start=EARLY, optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    route = json.loads((tmp_path / "route.geojson").read_text())
    geometry = route["features"][0]["geometry"]
    if damage == "missing_route":
        (tmp_path / "route.geojson").unlink()
    elif damage == "missing_plan":
        (tmp_path / "plan.json").unlink()
    elif damage == "not_json":
        (tmp_path / "route.geojson").write_text("{not json")
    elif damage == "polygon":
        geometry["type"] = "Polygon"
    elif damage == "one_point":
        geometry["coordinates"] = geometry["coordinates"][:1]
    elif damage == "text_coordinate":
        geometry["coordinates"][1] = ["east", "north"]
    elif damage == "two_features":
        route["features"].append(route["features"][0])
    elif damage == "bad_plan":
        (tmp_path / "plan.json").write_text(json.dumps({"stops": "none"}))
    elif damage == "wrong_path":
        output.route_path = "../route.geojson"
    if damage in ("polygon", "one_point", "text_coordinate", "two_features"):
        (tmp_path / "route.geojson").write_text(json.dumps(route))
    verdict = judge(tmp_path, ref, output)
    assert verdict["valid"] is False and verdict["score"] == 0.0


def test_the_verdict_is_deterministic(tmp_path: Path) -> None:
    ref = reference(start="14:56:00", optimal=2000.0)
    output = write_route(tmp_path, ref, ALL)
    assert json.dumps(judge(tmp_path, ref, output), sort_keys=True) == json.dumps(judge(tmp_path, ref, output), sort_keys=True)


def test_the_flat_map_round_trips() -> None:
    from verifier.geometry import to_xy

    for x, y in ((0.0, 0.0), (1200.0, 900.0), (-300.5, 77.25)):
        assert to_xy(*lonlat(x, y)) == pytest.approx((x, y), abs=1e-6)
