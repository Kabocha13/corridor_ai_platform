from engine.action import MoveAction, WallAction
from engine.rules import (
    apply_action,
    blocked_by_wall,
    initial_state,
    is_legal_action,
    legal_actions,
    legal_pawn_moves,
    wall_overlap_or_cross,
)


def test_initial_state_is_correct():
    state = initial_state()
    assert state.turn == "P1"
    assert state.pawns == {"P1": "e1", "P2": "e9"}
    assert state.remaining_walls == {"P1": 10, "P2": 10}


def test_move_actions_are_generated():
    state = initial_state()
    assert MoveAction(action="move", to="e2") in legal_pawn_moves(state)


def test_pawn_can_jump_over_adjacent_opponent():
    state = initial_state()
    state.pawns["P1"] = "e4"
    state.pawns["P2"] = "e5"

    moves = legal_pawn_moves(state)

    assert MoveAction(action="move", to="e6") in moves
    assert MoveAction(action="move", to="e5") not in moves
    assert MoveAction(action="move", to="d5") not in moves
    assert MoveAction(action="move", to="f5") not in moves


def test_pawn_moves_diagonally_when_jump_is_blocked_by_wall():
    state = initial_state()
    state.pawns["P1"] = "e4"
    state.pawns["P2"] = "e5"
    state.walls.append(WallAction(action="wall", at="e5", orientation="h"))

    moves = legal_pawn_moves(state)

    assert MoveAction(action="move", to="e6") not in moves
    assert MoveAction(action="move", to="d5") in moves
    assert MoveAction(action="move", to="f5") in moves


def test_diagonal_jump_respects_side_walls():
    state = initial_state()
    state.pawns["P1"] = "e4"
    state.pawns["P2"] = "e5"
    state.walls.append(WallAction(action="wall", at="e5", orientation="h"))
    state.walls.append(WallAction(action="wall", at="d5", orientation="v"))

    moves = legal_pawn_moves(state)

    assert MoveAction(action="move", to="d5") not in moves
    assert MoveAction(action="move", to="f5") in moves


def test_pawn_moves_diagonally_when_jump_is_off_board():
    state = initial_state()
    state.pawns["P1"] = "e8"
    state.pawns["P2"] = "e9"

    moves = legal_pawn_moves(state)

    assert MoveAction(action="move", to="d9") in moves
    assert MoveAction(action="move", to="f9") in moves


def test_pawn_cannot_jump_when_wall_blocks_adjacent_opponent():
    state = initial_state()
    state.pawns["P1"] = "e4"
    state.pawns["P2"] = "e5"
    state.walls.append(WallAction(action="wall", at="e4", orientation="h"))

    moves = legal_pawn_moves(state)

    assert MoveAction(action="move", to="e6") not in moves
    assert MoveAction(action="move", to="d5") not in moves
    assert MoveAction(action="move", to="f5") not in moves


def test_wall_can_be_placed():
    state = initial_state()
    wall = WallAction(action="wall", at="e3", orientation="h")
    assert is_legal_action(state, wall)
    next_state = apply_action(state, wall)
    assert wall in next_state.walls


def test_wall_blocks_movement():
    state = initial_state()
    state.walls.append(WallAction(action="wall", at="e1", orientation="h"))
    assert blocked_by_wall(state, "e1", "e2")


def test_duplicate_wall_cannot_be_placed():
    state = initial_state()
    state.walls.append(WallAction(action="wall", at="e3", orientation="h"))
    assert wall_overlap_or_cross(state, WallAction(action="wall", at="e3", orientation="h"))


def test_crossing_wall_cannot_be_placed():
    state = initial_state()
    state.walls.append(WallAction(action="wall", at="e3", orientation="h"))
    assert wall_overlap_or_cross(state, WallAction(action="wall", at="e3", orientation="v"))


def test_wall_that_blocks_all_paths_is_illegal():
    state = initial_state()
    for x in "abcdefgh":
        if x != "e":
            state.walls.append(WallAction(action="wall", at=f"{x}1", orientation="h"))
    assert not is_legal_action(state, WallAction(action="wall", at="e1", orientation="h"))


def test_p1_goal_wins():
    state = initial_state()
    state.pawns["P1"] = "e8"
    state.pawns["P2"] = "a9"
    next_state = apply_action(state, MoveAction(action="move", to="e9"))
    assert next_state.winner == "P1"
    assert next_state.reason == "goal"


def test_p2_goal_wins():
    state = initial_state()
    state.turn = "P2"
    state.pawns["P1"] = "a1"
    state.pawns["P2"] = "e2"
    next_state = apply_action(state, MoveAction(action="move", to="e1"))
    assert next_state.winner == "P2"
    assert next_state.reason == "goal"


def test_legal_actions_include_walls_and_moves():
    actions = legal_actions(initial_state())
    assert any(action.action == "move" for action in actions)
    assert any(action.action == "wall" for action in actions)
