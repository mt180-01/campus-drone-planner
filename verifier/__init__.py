"""The deterministic verifier: each tool's checks live in its own module, on contract instances."""

from contract import Task, Tool

from . import build_route, leg_info, open_campus, plan_task, read_notams, reference_plan

TOOLS = {
    Tool.OPEN_CAMPUS: open_campus,
    Tool.READ_NOTAMS: read_notams,
    Tool.LEG_INFO: leg_info,
    Tool.BUILD_ROUTE: build_route,
    Tool.REFERENCE_PLAN: reference_plan,
}

# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.PLAN_DELIVERY: plan_task.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)].verify_input(value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)].verify_output(input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
