from __future__ import annotations

from collections import deque

from .state import GameState, Player


def _goal_row(player: Player) -> int:
    return 9 if player == "P1" else 1


def has_path_to_goal(state: GameState, player: Player) -> bool:
    return shortest_path_distance(state, player) is not None


def shortest_path_distance(state: GameState, player: Player) -> int | None:
    from .rules import coord_to_xy, neighbors_without_pawns

    start = state.pawns[player]
    goal_y = _goal_row(player)
    seen = {start}
    queue: deque[tuple[str, int]] = deque([(start, 0)])
    while queue:
        coord, distance = queue.popleft()
        if coord_to_xy(coord)[1] == goal_y:
            return distance
        for neighbor in neighbors_without_pawns(state, coord):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, distance + 1))
    return None

