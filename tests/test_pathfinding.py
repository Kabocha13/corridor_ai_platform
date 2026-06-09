from engine.action import WallAction
from engine.pathfinding import has_path_to_goal, shortest_path_distance
from engine.rules import initial_state


def test_shortest_path_exists_initially():
    state = initial_state()
    assert has_path_to_goal(state, "P1")
    assert shortest_path_distance(state, "P1") == 8


def test_path_distance_accounts_for_walls():
    state = initial_state()
    state.walls.append(WallAction(action="wall", at="e1", orientation="h"))
    assert shortest_path_distance(state, "P1") > 8

