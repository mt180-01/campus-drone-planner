# Campus Drone Planner

A `nanoagent.plugin/v0001` plugin that checks whether an agent can plan a delivery drone's route with geometry.

A drone leaves a depot, delivers to four drop-offs (one with a time window), and lands at the depot. Its battery
lasts 2.0 km per charge and charging pads refill it. Buildings are no-fly polygons with a 5 m safety buffer, and a
temporary no-fly zone in `notams.txt` is active only from 15:00 to 15:20. The agent writes `route.geojson` and
`plan.json` (stops in order, timestamps at a fixed speed). The route must be at most 1.10 times the length of a
reference optimum, found with a visibility graph and an exhaustive search over the small routing problem.

The traps: a stretch of exactly 2000 m is allowed but 2000.01 m is not; merely touching the buffer is a violation;
the temporary zone matters only while it is active, so the same path can be legal or illegal depending on when the
drone flies it; the time window fixes the order of the drop-offs; and swapped latitude and longitude put the route
outside the map's bounding box.

## Tools

| Tool | Does | Code |
|---|---|---|
| `open_campus` | Builds the campus from a seed: `campus.json`, `notams.txt`, the points and the drone's limits | `src/plugin/open_campus.py` |
| `read_notams` | Reads `notams.txt`: the notice of the temporary zone and its hours | `src/plugin/read_notams.py` |
| `leg_info` | The shortest path between two points around the buildings, with or without avoiding the temporary zone | `src/plugin/leg_info.py` |
| `build_route` | Writes `route.geojson` and `plan.json` for stops in order, with timestamps at the fixed speed | `src/plugin/build_route.py` |
| `reference_plan` | The reference: the shortest route that keeps every rule (never offered to the agent) | `src/plugin/reference_plan.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `plan-drone-delivery` | Plans the drone's route across a campus around no-fly zones, within its battery, in time | `agent`, with `open_campus`, `read_notams`, `leg_info`, `build_route`; reference `reference_plan` |

The verifier (`verifier/`) is plain Python and calls no model. `shapely` is not allowed in the verifier's sandbox,
so it does its own geometry in pure Python (`verifier/geometry.py`: segment-to-polygon distance, and the exact
stretch of each segment that lies within the buffer of the temporary zone), and the tests check it against
`shapely`. The tools use `shapely` to build the visibility graph and the reference.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # environment variable NAMEs this plugin needs, never values
├── src/plugin/      # the MCP server: __main__.py, its IMPLEMENTATIONS, the campus, graph and reference
├── tests/
├── ui/              # how the page draws the outputs: renderers.js and renderers.css
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier package
```

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

Publishing checks every plugin rule: push the plugin to a public GitHub
repository and submit it on RUSH Lab.
