"""Static URScript contract checks, NOT a URScript interpreter or robot test.

Only scalar grid expressions are evaluated as arithmetic. Syntax acceptance,
kinematics, motion safety and URCap availability require the actual controller.
"""

import math
from pathlib import Path
import re

import pytest


SCRIPT = (Path(__file__).resolve().parents[1] /
          "robot/urscript/triqui_controller.script").read_text(encoding="utf-8")
CODE = "\n".join(line.split("#", 1)[0].rstrip() for line in SCRIPT.splitlines())


def function(name):
    return re.search(rf"  def {name}\([^\n]*\):\n(.*?)\n  end", CODE, re.S).group(1)


def constant(name):
    return re.search(rf"  global {name} = (.+)", CODE).group(1).strip()


@pytest.mark.parametrize("cell,xy", [
    (1, (0, 0)), (2, (.0655, 0)), (3, (.1310, 0)),
    (4, (0, .0655)), (5, (.0655, .0655)), (6, (.1310, .0655)),
    (7, (0, .1310)), (8, (.0655, .1310)), (9, (.1310, .1310)),
])
def test_measured_pitch_and_mapping_from_script_expressions(cell, xy):
    values = {key: float(constant(key)) for key in
              ("GRID_DX", "GRID_DY", "CELL1_X", "CELL1_Y")}
    assert values["GRID_DX"] == values["GRID_DY"] == .0655
    assert values["CELL1_X"] == values["CELL1_Y"] == 0
    values["cell"] = cell
    body = function("cell_relative_pose")
    for name in ("row", "column"):
        expression = re.search(rf"local {name} = (.+)", body).group(1)
        values[name] = eval(expression, {"__builtins__": {}, "floor": math.floor}, values)
    expressions = re.search(r"return p\[(.*)\]", body, re.S).group(1).split(",")
    actual = [eval(expr.strip(), {"__builtins__": {}}, values) for expr in expressions[:2]]
    assert actual == pytest.approx(xy)


def test_protocol_and_mode_zero_remain_no_motion():
    assert constant("COMMAND_REGISTER") == "128"
    assert constant("STATUS_REGISTER") == "129"
    assert constant("MOTION_MODE") == "0"
    body = function("execute_cell").split("elif (MOTION_MODE == 1)")[0]
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    assert lines == [
        "if (MOTION_MODE == 0):", 'textmsg("NO MOTION - CELL", cell)',
        "sleep(0.1)", "return True",
    ]


def test_unmeasured_parameters_are_not_fictitious_poses_or_rates():
    for name in ("TABLERO_VALUES", "Z_SAFE", "Z_PLACE", "CELL_ORIENTATION",
                 "HOME", "PICK_APPROACH", "PICK", "PICK_EXIT", "JOINT_MOTION", "LINEAR_MOTION"):
        assert constant(name) == "[]"
    for name in ("GEOMETRY_CONFIGURED", "ORIENTATION_CONFIGURED", "PICK_CONFIGURED",
                 "ROBOTIQ_CONFIGURED", "MOTION_CONFIGURED"):
        assert constant(name) == "False"


def test_mode_one_checks_geometry_orientation_before_any_motion():
    gate = function("safe_grid_configured")
    assert "if ((GEOMETRY_CONFIGURED == False) or (ORIENTATION_CONFIGURED == False)):\n      return False" in gate
    assert "length(Z_SAFE) != 1" in gate
    assert "Z_SAFE[0] <= 0" in gate
    body = function("move_to_cell_safe")
    assert body.index("safe_grid_configured() == False") < body.index("return False") < body.index("movej(")
    assert "pose_trans(TABLERO, cell_relative_pose(cell, Z_SAFE[0]))" in body
    assert not any(token in body for token in ("gripper_", "PICK", "movel("))


def test_mode_two_checks_pick_and_robotiq_before_initialization_or_motion():
    gate = function("pick_place_configured")
    assert "safe_grid_configured() == False" in gate
    assert "if ((PICK_CONFIGURED == False) or (ROBOTIQ_CONFIGURED == False)):\n      return False" in gate
    assert "length(HOME) != 6" in gate
    assert "length(Z_PLACE) != 1" in gate
    assert "Z_PLACE[0] >= Z_SAFE[0]" in gate
    body = function("prepare_pick_and_place")
    assert body.index("pick_place_configured() == False") < body.index("gripper_initialize()") < body.index("movej(")
    assert "if (gripper_initialize() == False):\n      return False" in body


def test_robotiq_functions_are_documented_but_not_assumed_available():
    for name in ("rq_reset", "rq_activate_and_wait", "rq_open_and_wait", "rq_close_and_wait"):
        assert f"# {name}()" in SCRIPT or f": {name}()" in SCRIPT
        assert f"{name}(" not in CODE
    for name in ("gripper_initialize", "gripper_open", "gripper_close"):
        body = function(name)
        assert "ROBOTIQ_CONFIGURED == False" in body
        assert body.rstrip().endswith("return False")
    assert "set_digital_out" not in CODE
    assert "set_tool_digital_out" not in CODE


def test_pick_place_sequence_uses_joint_transfers_and_linear_surface_moves():
    pick = function("take_robot_piece")
    sequence = ["movej(get_inverse_kin(taught_pose(PICK_APPROACH))", "gripper_open()",
                "movel(taught_pose(PICK)", "gripper_close()", "movel(taught_pose(PICK_EXIT)"]
    positions = [pick.index(step) for step in sequence]
    assert positions == sorted(positions)
    body = function("prepare_pick_and_place")
    assert body.count("movej(get_inverse_kin(taught_pose(HOME))") == 2
    assert body.index("take_robot_piece()") < body.index("movej(get_inverse_kin(cell_safe)")
    assert body.index("movel(cell_place") < body.index("gripper_open()") < body.index("movel(cell_safe")


def test_grid_has_no_individual_hardcoded_cell_poses():
    assert not re.search(r"(?:CELL|cell)_?[1-9].*=.*p\[", CODE)
    assert len(re.findall(r"\bp\[", CODE)) == 2  # generic conversion + relative formula
