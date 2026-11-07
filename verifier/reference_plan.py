from .checks import result


def verify_input(value):
    if not 1 <= value.seed <= 9999:
        return result(False, "seed must be between 1 and 9999")
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    stops = output_value.optimal_stops
    drops = sorted(p.id for p in output_value.points if p.kind.value == "dropoff")
    if stops[:1] != ["depot"] or stops[-1:] != ["depot"] or not set(drops) <= set(stops) or len(drops) != 4:
        return result(False, "the optimal route must start and end at the depot and visit all four drop-offs")
    if output_value.optimal_length_m <= 0 or len(output_value.buildings) < 6 or len(output_value.notam.ring) < 3:
        return result(False, "the reference needs a positive length, buildings and a temporary zone")
    return result(True, "the reference is well formed", optimal_length_m=output_value.optimal_length_m)
