"""The tools and the verifier together on generated campuses."""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

import verifier
from contract import BuildInput, CampusInput, LegInput, NotamsInput, PlanOutput, TextFile
from plugin import build_route, leg_info, open_campus, read_notams, reference_plan
from plugin.geo import to_xy
from plugin.reference import dwell, hop, solve
from plugin.scenario import generate
from plugin.world import SPEED_MPS, START_S, World
from tests.synth import typed

SEEDS = (1, 7, 42, 2026, 9999)
TASK = "plan-drone-delivery"


def opened(workspace: Path, seed: int):
    return open_campus(CampusInput(seed=seed), workspace), reference_plan(CampusInput(seed=seed), workspace)


def judge(workspace: Path, seed: int, reference, built):
    output = PlanOutput(route_path=built.route_path, plan_path=built.plan_path, total_length_m=built.total_length_m, finish_time=built.finish_time)
    return verifier.verify_task(TASK, CampusInput(seed=seed), output, typed(reference, type(reference)), str(workspace))


def failing(verdict) -> list[str]:
    return [c["name"] for c in verdict["details"].get("checks", []) if not c["ok"]]


def build(workspace: Path, stops, flags=None):
    return build_route(BuildInput(stops=list(stops), avoid_notam=list(flags or [False] * (len(stops) - 1))), workspace)


def test_a_campus_is_reproducible_and_complete(tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    first = open_campus(CampusInput(seed=42), tmp_path)
    open_campus(CampusInput(seed=42), other)
    assert (tmp_path / "campus.json").read_bytes() == (other / "campus.json").read_bytes()
    assert [p.id for p in first.points] == ["depot", "pad1", "pad2", "pad3", "D1", "D2", "D3", "D4"]
    assert sum(1 for p in first.points if p.window_open) == 1 and first.rules.battery_m == 2000.0
    assert generate(1) != generate(2)
    for p in first.points:
        assert first.bbox.min_lon <= p.lon <= first.bbox.max_lon and first.bbox.min_lat <= p.lat <= first.bbox.max_lat


def test_the_notam_file_names_the_hours_and_the_zone(tmp_path: Path) -> None:
    open_campus(CampusInput(seed=42), tmp_path)
    notam = read_notams(NotamsInput(file=TextFile.NOTAMS), tmp_path)
    assert "15:00:00" in notam.text and "15:20:00" in notam.text and notam.text == (tmp_path / "notams.txt").read_text()
    with pytest.raises(FileNotFoundError):
        read_notams(NotamsInput(file=TextFile.NOTAMS), tmp_path / "nowhere")


@pytest.mark.parametrize("seed", SEEDS)
def test_every_leg_keeps_5_5_m_from_every_building_by_shapely(tmp_path: Path, seed: int) -> None:
    campus, _ = opened(tmp_path, seed)
    world = World.load(tmp_path)
    buildings = [Polygon(ring) for ring in world.buildings.values()]
    ids = [p.id for p in campus.points]
    for a in ids[:4] + ids[4:6]:
        for b in ids:
            if a == b:
                continue
            for avoid in (False, True):
                leg = leg_info(LegInput(from_id=a, to_id=b, avoid_notam=avoid), tmp_path)
                line = LineString([to_xy(c.lon, c.lat) for c in leg.path])
                assert all(line.distance(polygon) >= 5.5 - 1e-3 for polygon in buildings), (a, b, avoid)
                if avoid:
                    assert line.distance(world.notam_polygon) >= 5.5 - 1e-3
                assert leg.length_m >= math.dist(world.point(a).xy, world.point(b).xy) - 1e-3
                assert verifier.verify_output("leg_info", LegInput(from_id=a, to_id=b, avoid_notam=avoid), leg, str(tmp_path))["valid"]


def test_the_legs_are_symmetric_and_the_detour_is_never_shorter(tmp_path: Path) -> None:
    opened(tmp_path, 42)
    for a, b in (("depot", "D3"), ("pad1", "D2"), ("D1", "D4")):
        plain = leg_info(LegInput(from_id=a, to_id=b, avoid_notam=False), tmp_path).length_m
        back = leg_info(LegInput(from_id=b, to_id=a, avoid_notam=False), tmp_path).length_m
        around = leg_info(LegInput(from_id=a, to_id=b, avoid_notam=True), tmp_path).length_m
        assert plain == pytest.approx(back, abs=0.01) and around >= plain - 1e-6


def test_the_tools_refuse_bad_requests(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="open_campus"):
        leg_info(LegInput(from_id="depot", to_id="D1", avoid_notam=False), tmp_path)
    with pytest.raises(ValueError, match="seed"):
        open_campus(CampusInput(seed=0), tmp_path)
    opened(tmp_path, 42)
    with pytest.raises(ValueError, match="different"):
        leg_info(LegInput(from_id="D1", to_id="D1", avoid_notam=False), tmp_path)
    with pytest.raises(ValueError, match="unknown point"):
        leg_info(LegInput(from_id="D9", to_id="D1", avoid_notam=False), tmp_path)
    for stops, flags in ((["D1", "depot"], [False]), (["depot", "D1"], [False]), (["depot", "D1", "depot"], [False])):
        with pytest.raises(ValueError):
            build_route(BuildInput(stops=stops, avoid_notam=flags), tmp_path)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_reference_route_passes_every_check(tmp_path: Path, seed: int) -> None:
    _, reference = opened(tmp_path, seed)
    plan = solve(World.load(tmp_path))
    built = build(tmp_path, plan.stops, plan.flags)
    verdict = judge(tmp_path, seed, reference, built)
    assert verdict["valid"] is True and verdict["score"] == 1.0, verdict["message"]
    assert built.total_length_m == pytest.approx(reference.optimal_length_m, abs=0.05)
    assert max(built.stretches_m) <= 2000.0 and reference.optimal_length_m > 2200
    assert verifier.verify_output("build_route", BuildInput(stops=list(plan.stops), avoid_notam=list(plan.flags)), built, str(tmp_path))["valid"]
    assert verifier.verify_output("reference_plan", CampusInput(seed=seed), reference, str(tmp_path))["valid"]


@pytest.mark.parametrize("seed", SEEDS)
def test_ignoring_the_temporary_zone_is_caught_on_every_campus(tmp_path: Path, seed: int) -> None:
    _, reference = opened(tmp_path, seed)
    shortest = solve(World.load(tmp_path), notam=False, window=False)
    built = build(tmp_path, shortest.stops)
    verdict = judge(tmp_path, seed, reference, built)
    assert verdict["valid"] is False and "notam" in failing(verdict), verdict["message"]


@pytest.mark.parametrize("seed", SEEDS)
def test_visiting_only_in_a_bad_order_breaks_the_time_window_or_the_length(tmp_path: Path, seed: int) -> None:
    _, reference = opened(tmp_path, seed)
    drops = [s for s in reference.optimal_stops if s.startswith("D")]
    pads = [p.id for p in reference.points if p.kind.value == "pad"]
    world = World.load(tmp_path)
    worst = None
    for order in ([*drops[::-1]], [*drops[1:], drops[0]]):
        for pad in pads:
            stops = ["depot", *order[:2], pad, *order[2:], "depot"]
            built = build(tmp_path, stops, [True] * (len(stops) - 1))
            verdict = judge(tmp_path, seed, reference, built)
            if not verdict["valid"]:
                worst = failing(verdict)
    assert worst, "no reordered route was refused"
    assert world


def test_no_ordering_with_at_most_one_pad_beats_the_reference(tmp_path: Path) -> None:
    """Every order of the drop-offs with at most one charging stop, judged by the verifier: the reference is the shortest."""
    _, reference = opened(tmp_path, 42)
    world = World.load(tmp_path)
    for p in reference.points:  # without the time window many orders are legal, and the reference must beat them all
        p.window_open = p.window_close = ""
    world.points = {i: replace(p, window=None) for i, p in world.points.items()}
    optimum = solve(world).length
    reference.optimal_length_m = optimum
    drops = [s for s in reference.optimal_stops if s.startswith("D")]
    pads = [p.id for p in reference.points if p.kind.value != "dropoff"]
    valid, refused = [], 0
    for order in itertools.permutations(drops):
        for gap in [None, *range(5)]:
            for pad in ([None] if gap is None else pads):
                stops = ["depot", *order, "depot"]
                if gap is not None:
                    stops.insert(1 + gap, pad)
                stops = [x for i, x in enumerate(stops) if i == 0 or x != stops[i - 1]]
                total, wait, flags = 0.0, 0.0, []
                for a, b in pairwise(stops):
                    flown, avoids = hop(world, a, b, START_S + total / SPEED_MPS + wait, True)
                    flags.append(avoids)
                    total += flown
                    wait += dwell(world, b)
                built = build(tmp_path, stops, flags)
                if judge(tmp_path, 42, reference, built)["valid"]:
                    valid.append((built.total_length_m, stops))
                else:
                    refused += 1
    best = min(valid)
    assert best[0] >= optimum - 0.5 and best[0] == pytest.approx(optimum, abs=0.5), (best, optimum)
    assert refused > 0 and len(valid) >= 2


def test_the_swapped_coordinates_of_a_real_route_are_caught(tmp_path: Path) -> None:
    _, reference = opened(tmp_path, 42)
    plan = solve(World.load(tmp_path))
    built = build(tmp_path, plan.stops, plan.flags)
    route = json.loads((tmp_path / "route.geojson").read_text())
    line = route["features"][0]["geometry"]["coordinates"]
    route["features"][0]["geometry"]["coordinates"] = [[lat, lon] for lon, lat in line]
    (tmp_path / "route.geojson").write_text(json.dumps(route))
    verdict = judge(tmp_path, 42, reference, built)
    assert verdict["valid"] is False and "swapped" in verdict["message"]
