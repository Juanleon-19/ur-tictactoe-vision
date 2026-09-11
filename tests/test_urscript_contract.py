"""Static URScript contract checks, NOT a URScript interpreter or robot test.

Scalar expressions and a simple function subset run with synthetic poses and
fake motion/gripper calls. URScript syntax acceptance, kinematics, motion safety
and URCap availability require the actual controller.
"""

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


# Synthetic non-planar corners; never production robot coordinates.
CORNERS = {"P1": [0, 0, 1, .1, .2, .3], "P3": [4, 0, 3, 4, 5, 6],
           "P7": [0, 6, 5, 7, 8, 9], "P9": [8, 10, 9, 10, 11, 12]}


def arithmetic_pose(cell):
    values = {name: list(pose) for name, pose in CORNERS.items()}
    for name, expression in re.findall(r"global (P[1-9]) = p\[(.*?)\]\n", CODE, re.S):
        values[name] = [eval(component.strip(), {"__builtins__": {}}, values)
                        for component in expression.split(",")]
    return values[f"P{cell}"]



@pytest.mark.parametrize("cell,xyz", [
    (1, [0,0,1]), (2, [2,0,2]), (3, [4,0,3]),
    (4, [0,3,3]), (5, [3,4,4.5]), (6, [6,5,6]),
    (7, [0,6,5]), (8, [4,8,7]), (9, [8,10,9]),
])
def test_interpolated_xyz_and_fixed_orientation(cell, xyz):
    assert arithmetic_pose(cell) == pytest.approx(xyz + CORNERS["P1"][3:])


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


def test_only_assignment_poses_and_validated_motion_parameters():
    for forbidden in ("TABLERO", "GRID_DX", "GRID_DY", "CELL1_X", "CELL1_Y",
                      "CELL_ORIENTATION", "GEOMETRY_CONFIGURED", "ORIENTATION_CONFIGURED",
                      "Z_SAFE", "Z_PLACE", "_const", "get_inverse_kin_has_solution", "=[]",
                      "interpolated_cell_pose", "floor(", "selected_cell_pose", "move_to_cell_safe"):
        assert forbidden not in CODE.replace(" = []", "=[]")
    for name, value in {"APPROACH_DZ": -.060, "JOINT_A": .20, "JOINT_V": .10,
                        "LINEAR_A": .05, "LINEAR_V": .02}.items():
        assert float(constant(name)) == value
    assert not re.search(r"global P(?:1|_PICK|_HOME) =", CODE)
    # Initialization is guarded so C7 does not evaluate poses.
    assert 'if ((MOTION_MODE == 1) or (MOTION_MODE == 2)):' in CODE
    for cell in (2, 3, 4, 5, 6, 7, 8, 9):
        assert f"global P{cell} = p[" in CODE


def translated_function(name, env):
    """Execute this simple function subset with fakes, NOT a URScript parser."""
    import textwrap
    lines = []
    for line in textwrap.dedent(function(name)).splitlines():
        if line.strip() == "end":
            continue
        line = line.replace("local ", "")
        if "global " in line:
            variable = line.strip().split()[1]
            lines.insert(0, "    global " + variable)
            line = line.replace("global ", "")
        if line.strip() == "halt":
            line = line.replace("halt", "raise ValueError('Invalid cell')")
        lines.append("    " + line)
    parameter = "cell"
    exec(f"def {name}({parameter}):\n" + "\n".join(lines), env)
    return env[name]


def motion_environment():
    class PoseLiteral:
        def __getitem__(self, components):
            return tuple(components)
    events = []
    env = {"p": PoseLiteral(), "gripper_initialized": False, "MOTION_MODE": 1,
           "sleep": lambda seconds: events.append(("sleep", (seconds,), {})),
           "textmsg": lambda *args: None, "get_inverse_kin": lambda pose: pose,
           "pose_trans": lambda pose, offset: ("up", pose, offset),
           "P_PICK": "pickup", "P_HOME": "home"}
    env.update({key: float(constant(key)) for key in
                ("APPROACH_DZ", "JOINT_A", "JOINT_V", "LINEAR_A", "LINEAR_V")})
    env.update({f"P{cell}": tuple(arithmetic_pose(cell)) for cell in range(1, 10)})
    for name in ("movej", "movel", "rq_activate_and_wait", "rq_open_and_wait", "rq_close_and_wait"):
        env[name] = lambda *args, name=name, **kwargs: events.append((name, args, kwargs))
    for name in ("prepare_pick_and_place", "execute_cell"):
        translated_function(name, env)
    return env, events


@pytest.mark.parametrize("cell", range(1, 10))
def test_explicit_selection_and_mode1_only_moves_to_up(cell):
    env, events = motion_environment()
    assert env["execute_cell"](cell) is True
    assert events == [("movej", (("up", env[f"P{cell}"], (0,0,-.06,0,0,0)),), {"a": .20, "v": .10})]
    body = function("execute_cell").split("elif (MOTION_MODE == 1):")[1].split("elif (MOTION_MODE == 2):")[0]
    assert not any(token in body for token in ("movel", "rq_", "gripper", "P_PICK"))
    assert "movej(get_inverse_kin(Pn_UP), a=0.20, v=0.10)" in body


@pytest.mark.parametrize("cell", (0, 10, 1.5))
def test_invalid_cell_never_moves_or_grips(cell):
    env, events = motion_environment()
    assert env["execute_cell"](cell) is False
    assert env["prepare_pick_and_place"](cell) is False
    assert not events


def test_mode2_exact_sequence_and_activation_only_once():
    env, events = motion_environment()
    offset = (0,0,-.06,0,0,0)
    joints, linear = {"a": .20, "v": .10}, {"a": .05, "v": .02}
    for cell in (5, 1):
        events.clear()
        assert env["prepare_pick_and_place"](cell) is True
        pose = env[f"P{cell}"]
        expected = [("rq_activate_and_wait", (), {})] if cell == 5 else []
        expected += [
            ("rq_open_and_wait", (), {}),
            ("movej", (("up", "pickup", offset),), joints),
            ("movel", ("pickup",), linear), ("rq_close_and_wait", (), {}),
            ("movel", (("up", "pickup", offset),), linear),
            ("movej", (("up", pose, offset),), joints),
            ("movel", (pose,), linear), ("rq_open_and_wait", (), {}),
            ("movel", (("up", pose, offset),), linear),
            ("movej", ("home",), joints),
        ]
        assert events == expected
    assert 'return prepare_pick_and_place(cell)' in function("execute_cell")
    assert not any(token in CODE for token in ("rq_reset", "set_digital_out", "set_tool_digital_out"))


def test_modbus_state_machine_is_unchanged():
    # Frozen at f6887c1 before the taught-feature refactor (normalized newlines).
    import hashlib
    protocol = SCRIPT[SCRIPT.index("  global controller_status ="):]
    diagnostic = ('        if (MOTION_MODE == 1):\n'
                  '          textmsg("RECEIVED COMMAND", command)\n'
                  '        end\n')
    assert protocol.count(diagnostic) == 1
    assert protocol.index(diagnostic) < protocol.index("controller_status = STATUS_BUSY")
    protocol = protocol.replace(diagnostic, "")
    assert hashlib.sha256(protocol.encode()).hexdigest() == "845ba95b3d65286a18bd35457b588e3b219efb406126e31f46c20c0f672ed478"


def test_startup_clears_command_before_ready_and_operational_loop():
    clear = "write_port_register(COMMAND_REGISTER, COMMAND_IDLE)"
    assert constant("COMMAND_IDLE") == "0"
    assert CODE.count(clear) == 1
    assert CODE.index(clear) < CODE.index("global controller_status = STATUS_READY")
    assert CODE.index(clear) < CODE.index("write_port_register(STATUS_REGISTER, controller_status)")
    assert CODE.index(clear) < CODE.index("while (True):") < CODE.index("read_port_register(COMMAND_REGISTER)")


def run_operational_subset(stale, *, clear_at_start=True, fresh_cell=None):
    """Run the actual scalar init/loop subset with in-memory registers, no UR API."""
    import textwrap
    clear = "write_port_register(COMMAND_REGISTER, COMMAND_IDLE)"
    source = CODE[CODE.index("  " + clear):CODE.rindex("\nend")]
    if not clear_at_start:
        source = source.replace("  " + clear, "")  # Reproduce the prior hazard.
    lines = []
    for line in textwrap.dedent(source).splitlines():
        if not line.strip() or line.strip() == "end":
            continue
        line = line.replace("global ", "").replace("local ", "")
        line = line.replace("while (True):", "for tick in range(3):")
        lines.append(line)
        if line.endswith(":"):
            lines.append(" " * (len(line) - len(line.lstrip()) + 2) + "pass")
    registers, writes, cells = {128: stale}, [], []
    def write(address, value):
        registers[address] = value
        writes.append((address, value))
    def idle(_seconds):
        if fresh_cell is not None and not cells:
            registers[128] = fresh_cell
    env = {"__builtins__": {}, "range": range, "MOTION_MODE": 2,
           "write_port_register": write, "read_port_register": registers.__getitem__,
           "textmsg": lambda *args: None, "sleep": idle,
           "execute_cell": lambda cell: cells.append(cell) or True}
    env.update({name: int(constant(name)) for name in (
        "COMMAND_REGISTER", "STATUS_REGISTER", "COMMAND_IDLE",
        "STATUS_READY", "STATUS_BUSY", "STATUS_DONE", "STATUS_ERROR")})
    exec("\n".join(lines), env)
    return registers, writes, cells


@pytest.mark.parametrize("stale", range(1, 10))
def test_stale_command_cannot_execute_after_restart(stale):
    registers, writes, cells = run_operational_subset(stale)
    assert writes == [(128, 0), (129, 0)]
    assert registers == {128: 0, 129: 0} and cells == []
    # The very same source with the startup clear removed reproduces the bug.
    assert run_operational_subset(stale, clear_at_start=False)[2] == [stale]


def test_startup_clear_does_not_discard_later_valid_turn():
    _, writes, cells = run_operational_subset(9, fresh_cell=5)
    assert cells == [5]
    assert writes == [(128, 0), (129, 0), (129, 1), (129, 2)]


def test_c1_through_c7_procedures_and_handshake_are_unchanged():
    # Frozen at f6887c1; includes helper functions used by C1-C7.
    import hashlib
    source = (Path(__file__).resolve().parents[1] /
              "src/ur_tictactoe/commissioning/tests.py").read_text(encoding="utf-8")
    contract = source.split("def safe_grid(r, cells):")[0]
    assert hashlib.sha256(contract.encode()).hexdigest() == "8457a0a1150752e3d248b03688d4c06d8e248d39219e106caf6058c7a2bf6ce2"


def test_mode1_diagnostics_surround_explicit_motion():
    env, events = motion_environment()
    env["textmsg"] = lambda *args: events.append(("textmsg", args, {}))
    assert env["execute_cell"](5) is True
    pose = env["P5"]
    up = ("up", pose, (0,0,-.06,0,0,0))
    assert events == [
        ("textmsg", ("EXECUTE MODE1", 5), {}),
        ("textmsg", ("MODE1 COMMAND", 5), {}),
        ("textmsg", ("MODE1 TARGET", pose), {}),
        ("textmsg", ("MODE1 TARGET UP", up), {}),
        ("textmsg", ("MODE1 BEFORE MOVEJ", 5), {}),
        ("movej", (up,), {"a": .20, "v": .10}),
        ("textmsg", ("MODE1 MOVE COMPLETE", 5), {}),
    ]


def test_mode1_motion_failure_never_logs_completion_or_returns_success():
    env, events = motion_environment()
    env["textmsg"] = lambda *args: events.append(args)
    def fail(*args, **kwargs):
        raise RuntimeError("simulated move failure")
    env["movej"] = fail
    with pytest.raises(RuntimeError):
        env["execute_cell"](5)
    assert events[-1] == ("MODE1 BEFORE MOVEJ", 5)
    assert not any(event[0] == "MODE1 MOVE COMPLETE" for event in events)


def test_mode0_still_only_logs_and_sleeps():
    env, events = motion_environment()
    env["MOTION_MODE"] = 0
    env["textmsg"] = lambda *args: events.append(("textmsg", args, {}))
    assert env["execute_cell"](5) is True
    assert events == [("textmsg", ("NO MOTION - CELL", 5), {}), ("sleep", (.1,), {})]
