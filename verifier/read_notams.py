from pathlib import Path

from .checks import result


def verify_input(value):
    return result(True, "input is valid")


def verify_output(input_value, output_value, workspace):
    path = Path(workspace) / input_value.file.value
    if output_value.file != input_value.file.value or not path.is_file():
        return result(False, "the file read is not the one asked for")
    if output_value.text != path.read_text(encoding="utf-8"):
        return result(False, "the text differs from the file")
    return result(True, "the NOTAM text is exact", characters=len(output_value.text))
