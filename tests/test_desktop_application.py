from __future__ import annotations

import pytest

from ur_tictactoe.communication import STATUS_ERROR
from ur_tictactoe.desktop.application import AppConfig, GameApplication, SimulatedModbusClient
from ur_tictactoe.game import HARD, HUMAN, INTERMEDIATE, ROBOT
from ur_tictactoe.runtime import RuntimeState


@pytest.mark.parametrize(
    ("human_first", "human", "robot", "turn"),
    [(False, "O", "X", ROBOT), (True, "X", "O", HUMAN)],
)
def test_starting_player_configuration(
    human_first: bool, human: str, robot: str, turn: str
) -> None:
    app = GameApplication(simulation=True)
    assert app.new_game(HARD, human_first)
    snapshot = app.snapshot()
    assert (snapshot.human_symbol, snapshot.robot_symbol, snapshot.turn) == (
        human,
        robot,
        turn,
    )


@pytest.mark.parametrize("difficulty", [HARD, INTERMEDIATE])
def test_supported_difficulty_is_preserved(difficulty: str) -> None:
    app = GameApplication(simulation=True)
    app.new_game(difficulty, True)
    assert app.snapshot().difficulty == difficulty


@pytest.mark.parametrize("moves, expected", [
    ((3, 7, 9, 8), "human_wins"),
    ((1, 2, 4), "robot_wins"),
])
def test_intermediate_desktop_reproducible_outcomes(moves, expected):
    traces = []
    for _ in range(2):
        app = GameApplication(simulation=True)
        try:
            assert app.new_game(INTERMEDIATE, True, seed=42)
            human_moves, trace = iter(moves), []
            for _ in range(60):
                snapshot = app.snapshot()
                trace.append(snapshot)
                if snapshot.runtime_state == RuntimeState.GAME_OVER:
                    break
                if snapshot.runtime_state == RuntimeState.WAITING_HUMAN:
                    assert app.play_human_cell(next(human_moves))
                else:
                    app.update()
            assert app.snapshot().result == expected
            traces.append(trace)
        finally:
            app.close()
    assert traces[0] == traces[1]


def test_valid_simulated_human_click_updates_snapshot_board() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, True)
    assert app.play_human_cell(5)
    assert app.snapshot().board[4] == "X"


def test_click_on_occupied_cell_is_rejected() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, True)
    assert app.play_human_cell(5)
    assert not app.play_human_cell(5)


def test_click_during_robot_turn_is_rejected() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, False)
    assert not app.play_human_cell(1)
    assert app.snapshot().board == (None,) * 9


def test_fake_robot_advances_ready_busy_done_and_verification() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, False)

    app.update()
    expected = app.snapshot().pending_robot_move
    assert app.snapshot().runtime_state == RuntimeState.WAITING_ROBOT
    app.update()
    assert app.snapshot().runtime_state == RuntimeState.ROBOT_BUSY
    app.update()
    assert app.snapshot().runtime_state == RuntimeState.VERIFYING_ROBOT
    assert app.snapshot().board == (None,) * 9
    app.update()
    assert app.snapshot().board[expected - 1] == "X"
    assert app.snapshot().runtime_state == RuntimeState.WAITING_HUMAN


def test_complete_simulation_reaches_game_over() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, True)

    for _ in range(30):
        snapshot = app.snapshot()
        if snapshot.runtime_state == RuntimeState.GAME_OVER:
            break
        if snapshot.runtime_state == RuntimeState.WAITING_HUMAN:
            cell = next(index + 1 for index, value in enumerate(snapshot.board) if value is None)
            app.play_human_cell(cell)
        else:
            app.update()

    assert app.snapshot().runtime_state == RuntimeState.GAME_OVER
    assert app.snapshot().result != "active"


@pytest.mark.parametrize("human_first", [False, True])
@pytest.mark.parametrize("seed", [0, 7, 42])
def test_expert_desktop_acceptance_is_legal_and_never_loses(human_first, seed) -> None:
    import random

    app = GameApplication(simulation=True)
    app.new_game(HARD, human_first, seed=seed)
    rng = random.Random(seed)
    previous = app.snapshot().board
    for _ in range(60):
        snapshot = app.snapshot()
        if snapshot.runtime_state == RuntimeState.GAME_OVER:
            break
        if snapshot.runtime_state == RuntimeState.WAITING_HUMAN:
            legal = [i + 1 for i, value in enumerate(snapshot.board) if value is None]
            assert app.play_human_cell(rng.choice(legal))
        else:
            app.update()
        current = app.snapshot().board
        assert all(old is None or old == new for old, new in zip(previous, current))
        assert sum(old != new for old, new in zip(previous, current)) <= 1
        previous = current
    assert app.snapshot().runtime_state == RuntimeState.GAME_OVER
    assert app.snapshot().result in ("robot_wins", "draw")


def test_new_game_uses_a_clean_board() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, True)
    app.play_human_cell(1)
    app.new_game(INTERMEDIATE, False)
    assert app.snapshot().board == (None,) * 9
    assert app.snapshot().turn == ROBOT


def test_runtime_error_is_exposed_in_application_snapshot() -> None:
    app = GameApplication(simulation=True)
    app.new_game(HARD, False)
    client = app.runtime.modbus_client
    assert isinstance(client, SimulatedModbusClient)
    client._statuses[:] = [STATUS_ERROR]
    app.update()
    snapshot = app.snapshot()
    assert snapshot.runtime_state == RuntimeState.ERROR
    assert snapshot.last_error == "MODBUS_STATUS_ERROR"


def test_real_mode_does_not_accept_simulated_human_click() -> None:
    app = GameApplication(simulation=False, config=AppConfig())
    assert not app.new_game(HARD, True)
    assert not app.play_human_cell(1)
    assert app.snapshot().board == (None,) * 9
    assert app.snapshot().last_error == "HARDWARE_NOT_AVAILABLE"
